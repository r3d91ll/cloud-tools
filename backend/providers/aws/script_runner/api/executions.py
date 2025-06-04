from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Body
from typing import List, Dict, Any, Optional, cast
from sqlalchemy.orm import Session
from datetime import datetime

from backend.db.session import get_db
from backend.core.utils.type_helpers import safe_str, safe_list, safe_int, safe_sqlalchemy_in
from backend.providers.aws.script_runner.schemas.execution import (
    Execution, ExecutionCreate, ExecutionList, 
    ExecutionBatch, ExecutionBatchCreate, ExecutionStatus, 
    ExecutionProgress
)
from backend.db.models.execution import Execution as ExecutionModel, ExecutionBatch as ExecutionBatchModel
from backend.db.models.script import Script as ScriptModel
from backend.db.models.account import Instance as InstanceModel, Region as RegionModel, Account as AccountModel
from backend.providers.aws.common.services.credential_manager import CredentialManager
from backend.providers.aws.script_runner.services.ssm_executor import SSMExecutor
from backend.providers.aws.script_runner.docs.executions import (
    EXECUTION_CREATE_EXAMPLE, EXECUTION_BATCH_CREATE_EXAMPLE, EXECUTION_RESPONSE_EXAMPLE,
    EXECUTION_LIST_EXAMPLE, EXECUTION_STATUS_EXAMPLE, BATCH_PROGRESS_EXAMPLE,
    LIST_EXECUTIONS_DESCRIPTION, GET_EXECUTION_DESCRIPTION, GET_EXECUTION_STATUS_DESCRIPTION,
    CREATE_EXECUTION_DESCRIPTION, CREATE_EXECUTION_BATCH_DESCRIPTION,
    GET_BATCH_PROGRESS_DESCRIPTION, CANCEL_EXECUTION_DESCRIPTION
)

# Create router
router = APIRouter(
    prefix="/executions",
    tags=["executions"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)

# Initialize services
credential_manager = CredentialManager()
ssm_executor = SSMExecutor(credential_manager)


async def execute_script_task(
    execution_id: int,
    db_session: Session
) -> None:
    """
    Background task to execute a script on an EC2 instance.
    
    Args:
        execution_id: ID of the execution record
        db_session: Database session
    """
    # Get execution from database
    execution = db_session.query(ExecutionModel).filter(ExecutionModel.id == execution_id).first()
    if not execution:
        return
    
    # Update status to running
    execution.status = ExecutionStatus.RUNNING.value
    db_session.commit()
    
    try:
        # Get instance details
        instance = db_session.query(InstanceModel).filter(InstanceModel.id == execution.instance_id).first()
        if not instance:
            execution.status = ExecutionStatus.FAILED.value
            execution.output = "Instance not found in database"
            db_session.commit()
            return
        
        # Get region and account details
        region = db_session.query(RegionModel).filter(RegionModel.id == instance.region_id).first()
        if not region:
            execution.status = ExecutionStatus.FAILED.value
            execution.output = "Region not found in database"
            db_session.commit()
            return
        
        account = db_session.query(AccountModel).filter(AccountModel.id == region.account_id).first()
        if not account:
            execution.status = ExecutionStatus.FAILED.value
            execution.output = "Account not found in database"
            db_session.commit()
            return
        
        # Get script details
        script = db_session.query(ScriptModel).filter(ScriptModel.id == execution.script_id).first()
        if not script:
            execution.status = ExecutionStatus.FAILED.value
            execution.output = "Script not found in database"
            db_session.commit()
            return
        
        # Check if all required objects are available and get the values we need
        if instance is None or script is None or account is None or region is None:
            execution.status = ExecutionStatus.FAILED.value
            execution.output = "Missing required instance, script, account, or region information"
            db_session.commit()
            return
        
        # Extract the values we need for SSM execution with safe string conversion
        instance_id_str = safe_str(instance.instance_id)
        command_str = safe_str(script.content)
        account_id_str = safe_str(account.account_id)
        region_str = safe_str(region.name)
        environment_str = safe_str(account.environment)
        
        # Execute the script via SSM
        command_id = ssm_executor.send_command(
            instance_id=instance_id_str,
            command=command_str,
            account_id=account_id_str,
            region=region_str,
            environment=environment_str,
            comment=f"Execution ID: {execution_id}"
        )
        
        if not command_id:
            execution.status = ExecutionStatus.FAILED.value
            execution.output = "Failed to send command to instance"
            db_session.commit()
            return
        
        # Update execution record with command ID
        execution.command_id = command_id
        db_session.commit()
        
        # Wait for command completion
        result = ssm_executor.wait_for_command_completion(
            command_id=command_id,
            instance_id=instance_id_str,
            account_id=account_id_str,
            region=region_str,
            environment=environment_str
        )
        
        # Update execution record with results
        execution.output = result.get("Output", "") + "\n" + result.get("Error", "")
        execution.exit_code = result.get("ExitCode")
        execution.status = ExecutionStatus.COMPLETED.value if result.get("Status") == "Success" else ExecutionStatus.FAILED.value
        execution.end_time = datetime.utcnow()
        db_session.commit()
        
    except Exception as e:
        # Handle any exceptions
        execution.status = ExecutionStatus.FAILED.value
        execution.output = f"Error executing script: {str(e)}"
        execution.end_time = datetime.utcnow()
        db_session.commit()


@router.post(
    "/", 
    response_model=Execution, 
    status_code=status.HTTP_201_CREATED,
    summary="Create Execution",
    description=CREATE_EXECUTION_DESCRIPTION,
    response_description="Created execution details",
    responses={
        201: {
            "content": {
                "application/json": {
                    "example": EXECUTION_RESPONSE_EXAMPLE
                }
            },
        },
        404: {"description": "Script or instance not found"}
    }
)
async def create_execution(
    execution: ExecutionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Execution:
    """
    Create a new script execution.
    
    This endpoint creates a new execution record and starts the script execution
    on the specified EC2 instance as a background task.
    """
    # Check if script exists
    script = db.query(ScriptModel).filter(ScriptModel.id == execution.script_id).first()
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Script with ID {execution.script_id} not found"
        )
    
    # Check if instance exists
    instance = db.query(InstanceModel).filter(InstanceModel.id == execution.instance_id).first()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance with ID {execution.instance_id} not found"
        )
    
    # Create execution record
    db_execution = ExecutionModel(
        script_id=execution.script_id,
        instance_id=execution.instance_id,
        status=ExecutionStatus.PENDING.value,
        start_time=datetime.utcnow()
    )
    
    # Save to database
    db.add(db_execution)
    db.commit()
    db.refresh(db_execution)
    
    # Start background task to execute the script
    # Get the execution ID as an integer to pass to the background task
    execution_id = safe_int(db_execution.id)
    # Start the background task with the execution ID and a new database session
    background_tasks.add_task(execute_script_task, execution_id, db)
    
    # Convert SQLAlchemy model to Pydantic schema
    return Execution.from_orm(db_execution)


@router.get(
    "/", 
    response_model=ExecutionList,
    summary="List Executions",
    description=LIST_EXECUTIONS_DESCRIPTION,
    response_description="List of executions with pagination info",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": EXECUTION_LIST_EXAMPLE
                }
            },
        }
    }
)
def list_executions(
    status: Optional[str] = None,
    script_id: Optional[int] = None,
    instance_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> ExecutionList:
    """
    List all executions with optional filtering.
    
    This endpoint retrieves executions with pagination and filtering options.
    """
    # Build query
    query = db.query(ExecutionModel)
    
    # Apply filters
    if status:
        query = query.filter(ExecutionModel.status == status)
    
    if script_id:
        query = query.filter(ExecutionModel.script_id == script_id)
    
    if instance_id:
        query = query.filter(ExecutionModel.instance_id == instance_id)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and order by start_time descending (newest first)
    # First get a query with just pagination to avoid None.desc() error
    paginated_query = query.offset(skip).limit(limit)
    
    # Then add ordering only if start_time is a valid column (to satisfy mypy)
    if hasattr(ExecutionModel, 'start_time') and ExecutionModel.start_time is not None:
        executions = paginated_query.order_by(ExecutionModel.start_time.desc()).all()
    else:
        executions = paginated_query.all()
    
    # Convert SQLAlchemy models to Pydantic schemas
    pydantic_executions = [Execution.from_orm(execution) for execution in executions]
    
    return ExecutionList(
        executions=pydantic_executions,
        total=total
    )


@router.get(
    "/{execution_id}", 
    response_model=Execution,
    summary="Get Execution",
    description=GET_EXECUTION_DESCRIPTION,
    response_description="Detailed execution information",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": EXECUTION_RESPONSE_EXAMPLE
                }
            },
        },
        404: {"description": "Execution not found"}
    }
)
def get_execution(
    execution_id: int,
    db: Session = Depends(get_db)
) -> Execution:
    """
    Get a specific execution by ID.
    """
    execution = db.query(ExecutionModel).filter(ExecutionModel.id == execution_id).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution with ID {execution_id} not found"
        )
    
    # Convert the SQLAlchemy model to a Pydantic schema
    return Execution.from_orm(execution)


@router.get(
    "/{execution_id}/status", 
    response_model=Dict[str, Any],
    summary="Get Execution Status",
    description=GET_EXECUTION_STATUS_DESCRIPTION,
    response_description="Current execution status",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": EXECUTION_STATUS_EXAMPLE
                }
            },
        },
        404: {"description": "Execution not found"}
    }
)
def get_execution_status(
    execution_id: int,
    refresh: bool = Query(False, description="Refresh status from AWS if applicable"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get the current status of an execution.
    
    This endpoint retrieves the current status of an execution and optionally
    refreshes it from AWS if the execution is still running.
    """
    execution = db.query(ExecutionModel).filter(ExecutionModel.id == execution_id).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution with ID {execution_id} not found"
        )
    
    # If refresh is requested and the execution is still running with a command ID
    if refresh and execution.status == ExecutionStatus.RUNNING.value and execution.command_id:
        try:
            # Get instance details
            instance = db.query(InstanceModel).filter(InstanceModel.id == execution.instance_id).first()
            if not instance:
                return {"status": execution.status, "message": "Instance not found"}
            
            # Get region and account details
            region = db.query(RegionModel).filter(RegionModel.id == instance.region_id).first()
            if not region:
                return {"status": execution.status, "message": "Region not found"}
            
            account = db.query(AccountModel).filter(AccountModel.id == region.account_id).first()
            if not account:
                return {"status": execution.status, "message": "Account not found"}
            
            # Get latest status from AWS
            result = ssm_executor.get_command_status(
                command_id=execution.command_id,
                instance_id=instance.instance_id,
                account_id=account.account_id,
                region=region.name,
                environment=account.environment
            )
            
            # Update execution if status has changed
            aws_status = result.get("Status")
            if aws_status in ["Success", "Failed", "Cancelled", "TimedOut"]:
                if aws_status == "Success":
                    execution.status = ExecutionStatus.COMPLETED.value
                else:
                    execution.status = ExecutionStatus.FAILED.value
                
                execution.output = result.get("Output", "") + "\n" + result.get("Error", "")
                execution.exit_code = result.get("ExitCode")
                execution.end_time = datetime.utcnow()
                db.commit()
            
            return {
                "execution_id": execution_id,
                "status": execution.status,
                "aws_status": aws_status,
                "exit_code": result.get("ExitCode"),
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "execution_id": execution_id,
                "status": execution.status,
                "error": str(e),
                "last_updated": datetime.utcnow().isoformat()
            }
    
    # Return current status from database
    return {
        "execution_id": execution_id,
        "status": execution.status,
        "start_time": execution.start_time.isoformat() if execution.start_time else None,
        "end_time": execution.end_time.isoformat() if execution.end_time else None,
        "exit_code": execution.exit_code
    }


@router.post("/batch", response_model=ExecutionBatch, status_code=status.HTTP_201_CREATED)
async def create_execution_batch(
    batch: ExecutionBatchCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ExecutionBatch:
    """
    Create multiple script executions on different instances.
    
    This endpoint allows executing the same script on multiple instances in a single API call.
    """
    # Check if script exists
    script = db.query(ScriptModel).filter(ScriptModel.id == batch.script_id).first()
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Script with ID {batch.script_id} not found"
        )
    
    # Check if all instances exist
    # Check if instance_ids is provided and is a valid list/tuple
    if not batch.instance_ids or not isinstance(batch.instance_ids, (list, tuple)) or len(batch.instance_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid instance IDs provided for batch execution"
        )
    
    # Create a typed list for mypy
    # Ensure we have a non-None list of instance IDs
    instance_ids_list: List[int] = []
    
    # Use our safe_sqlalchemy_in helper to ensure we have a safe list for SQLAlchemy's in_() operation
    instance_ids_list = safe_sqlalchemy_in(batch.instance_ids)
    
    # Skip the query if the list is empty
    if not instance_ids_list:
        # Create an empty model and convert to Pydantic schema
        empty_batch = ExecutionBatchModel()
        return ExecutionBatch.from_orm(empty_batch)
        
    # Query for instances with the provided IDs
    instances = db.query(InstanceModel).filter(InstanceModel.id.in_(instance_ids_list)).all()
    if len(instances) != len(instance_ids_list):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more instances not found"
        )
    
    # Create execution batch record
    db_batch = ExecutionBatchModel(
        name=batch.name,
        description=batch.description,
        status=ExecutionStatus.PENDING.value,
        start_time=datetime.utcnow(),
        parameters=batch.parameters
    )
    
    # Save batch to database
    db.add(db_batch)
    db.commit()
    db.refresh(db_batch)
    
    # Create individual execution records
    for instance_id in batch.instance_ids:
        db_execution = ExecutionModel(
            script_id=batch.script_id,
            instance_id=instance_id,
            status=ExecutionStatus.PENDING.value,
            start_time=datetime.utcnow()
        )
        
        # Save execution to database
        db.add(db_execution)
        db.commit()
        
        # Start background task to execute the script
        # Get the execution ID as an integer to pass to the background task
        execution_id = safe_int(db_execution.id)
        # Start the background task with the execution ID and database session
        background_tasks.add_task(execute_script_task, execution_id, db)
    
    # Convert SQLAlchemy model to Pydantic schema
    return ExecutionBatch.from_orm(db_batch)


@router.get(
    "/batch/{batch_id}/progress", 
    response_model=ExecutionProgress,
    summary="Get Batch Progress",
    description=GET_BATCH_PROGRESS_DESCRIPTION,
    response_description="Batch execution progress summary",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": BATCH_PROGRESS_EXAMPLE
                }
            },
        },
        404: {"description": "Batch not found"}
    }
)
def get_batch_progress(
    batch_id: int,
    db: Session = Depends(get_db)
) -> ExecutionProgress:
    """
    Get the progress of a batch execution.
    
    This endpoint provides a summary of the status of all executions in a batch.
    """
    # Check if batch exists
    batch = db.query(ExecutionBatchModel).filter(ExecutionBatchModel.id == batch_id).first()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution batch with ID {batch_id} not found"
        )
    
    # Count executions by status
    total_query = db.query(ExecutionModel).filter(ExecutionModel.batch_id == batch_id)
    total_instances = total_query.count()
    
    completed_instances = total_query.filter(ExecutionModel.status == ExecutionStatus.COMPLETED.value).count()
    failed_instances = total_query.filter(ExecutionModel.status == ExecutionStatus.FAILED.value).count()
    pending_instances = total_instances - completed_instances - failed_instances
    
    # Determine overall status
    overall_status = ExecutionStatus.PENDING
    if total_instances == 0:
        overall_status = ExecutionStatus.PENDING
    elif pending_instances == 0:
        if failed_instances == 0:
            overall_status = ExecutionStatus.COMPLETED
        else:
            overall_status = ExecutionStatus.FAILED
    else:
        overall_status = ExecutionStatus.RUNNING
    
    return ExecutionProgress(
        total_instances=total_instances,
        completed_instances=completed_instances,
        failed_instances=failed_instances,
        pending_instances=pending_instances,
        overall_status=overall_status
    )
