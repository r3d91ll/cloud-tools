from typing import List, Dict, Any, Optional, TypeVar, Type, cast
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Response, BackgroundTasks
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.core.schemas.script import Script, ScriptCreate, ScriptList, Tool, ToolCreate
from backend.db.models.script import Script as ScriptModel, Tool as ToolModel
from backend.core.docs.scripts import (
    SCRIPT_CREATE_EXAMPLE, SCRIPT_UPDATE_EXAMPLE, SCRIPT_RESPONSE_EXAMPLE,
    SCRIPT_LIST_EXAMPLE, TOOL_CREATE_EXAMPLE, TOOL_RESPONSE_EXAMPLE, TOOL_LIST_EXAMPLE,
    LIST_SCRIPTS_DESCRIPTION, GET_SCRIPT_DESCRIPTION, CREATE_SCRIPT_DESCRIPTION,
    UPDATE_SCRIPT_DESCRIPTION, DELETE_SCRIPT_DESCRIPTION, LIST_TOOLS_DESCRIPTION,
    GET_TOOL_DESCRIPTION, CREATE_TOOL_DESCRIPTION
)

# Create router
router = APIRouter(
    prefix="/scripts",
    tags=["scripts"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)

@router.post(
    "/", 
    response_model=Script,
    summary="Create Script",
    description=CREATE_SCRIPT_DESCRIPTION,
    response_description="Newly created script",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "content": {
                "application/json": {
                    "example": SCRIPT_RESPONSE_EXAMPLE
                }
            },
        },
        400: {"description": "Invalid input"},
        409: {"description": "Script with that name already exists"}
    }
)
def create_script(
    script: ScriptCreate,
    db: Session = Depends(get_db)
) -> Script:
    """
    Create a new script.
    """
    # Check if a script with this name already exists
    existing_script = db.query(ScriptModel).filter(ScriptModel.name == script.name).first()
    if existing_script:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Script with name '{script.name}' already exists"
            )
    
    # Create new script
    db_script = ScriptModel(
        name=script.name,
        content=script.content,
        description=script.description,
        script_type=script.script_type,
        tool_id=script.tool_id
    )
    
    # Save to database
    db.add(db_script)
    db.commit()
    db.refresh(db_script)
    
    # Convert SQLAlchemy model to Pydantic schema
    return Script.from_orm(db_script)


@router.get(
    "/", 
    response_model=ScriptList,
    summary="List Scripts",
    description=LIST_SCRIPTS_DESCRIPTION,
    response_description="List of scripts with pagination info",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": SCRIPT_LIST_EXAMPLE
                }
            },
        }
    }
)
def list_scripts(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    script_type: Optional[str] = None,
    db: Session = Depends(get_db)
) -> ScriptList:
    """
    List scripts with pagination.
    """
    # Start with a base query
    query = db.query(ScriptModel)
    
    # Apply filters if provided
    if search:
        query = query.filter(ScriptModel.name.contains(search) | ScriptModel.description.contains(search))
    
    if script_type:
        query = query.filter(ScriptModel.script_type == script_type)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    scripts = query.offset(skip).limit(limit).all()
    
    return ScriptList(
        scripts=[Script.from_orm(script) for script in scripts],
        total=total,
        limit=limit,
        skip=skip
    )


@router.get(
    "/{script_id}", 
    response_model=Script,
    summary="Get Script",
    description=GET_SCRIPT_DESCRIPTION,
    response_description="Script details",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": SCRIPT_RESPONSE_EXAMPLE
                }
            },
        },
        404: {"description": "Script not found"}
    }
)
def get_script(
    script_id: int,
    db: Session = Depends(get_db)
) -> Script:
    """
    Get a specific script by ID.
    """
    script = db.query(ScriptModel).filter(ScriptModel.id == script_id).first()
    
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Script with ID {script_id} not found"
        )
    
    # Convert SQLAlchemy model to Pydantic schema
    return Script.from_orm(script)


@router.put(
    "/{script_id}", 
    response_model=Script,
    summary="Update Script",
    description=UPDATE_SCRIPT_DESCRIPTION,
    response_description="Updated script",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": SCRIPT_UPDATE_EXAMPLE
                }
            },
        },
        404: {"description": "Script not found"},
        400: {"description": "Invalid input"}
    }
)
def update_script(
    script_id: int,
    script_update: ScriptCreate,
    db: Session = Depends(get_db)
) -> Script:
    """
    Update an existing script.
    """
    # Get the script to update
    db_script = db.query(ScriptModel).filter(ScriptModel.id == script_id).first()
    
    if not db_script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Script with ID {script_id} not found"
        )
    
    # Check if name already exists (if changing name)
    if script_update.name != db_script.name:
        existing_script = db.query(ScriptModel).filter(ScriptModel.name == script_update.name).first()
        if existing_script:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Script with name '{script_update.name}' already exists"
            )
    
    # Update script attributes
    db_script.name = script_update.name
    db_script.content = script_update.content
    db_script.description = script_update.description
    db_script.script_type = script_update.script_type
    db_script.tool_id = script_update.tool_id
    
    # Save changes
    db.commit()
    db.refresh(db_script)
    
    # Convert SQLAlchemy model to Pydantic schema
    return Script.from_orm(db_script)


@router.delete(
    "/{script_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Script",
    description=DELETE_SCRIPT_DESCRIPTION,
    responses={
        204: {"description": "Script deleted successfully"},
        404: {"description": "Script not found"}
    }
)
def delete_script(
    script_id: int,
    db: Session = Depends(get_db)
) -> Response:
    """
    Delete a script.
    """
    script = db.query(ScriptModel).filter(ScriptModel.id == script_id).first()
    
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Script with ID {script_id} not found"
        )
    
    # Delete script
    db.delete(script)
    db.commit()
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/tools/", 
    response_model=Tool,
    summary="Create Tool",
    description=CREATE_TOOL_DESCRIPTION,
    response_description="Newly created tool",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "content": {
                "application/json": {
                    "example": TOOL_RESPONSE_EXAMPLE
                }
            },
        },
        400: {"description": "Invalid input"},
        409: {"description": "Tool with that name already exists"}
    }
)
def create_tool(
    tool: ToolCreate,
    db: Session = Depends(get_db)
) -> Tool:
    """
    Create a new tool.
    """
    # Check if a tool with this name already exists
    existing_tool = db.query(ToolModel).filter(ToolModel.name == tool.name).first()
    if existing_tool:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool with name '{tool.name}' already exists"
            )
    
    # Create new tool
    db_tool = ToolModel(
        name=tool.name,
        description=tool.description,
        platform=tool.platform
    )
    
    # Save to database
    db.add(db_tool)
    db.commit()
    db.refresh(db_tool)
    
    # Convert SQLAlchemy model to Pydantic schema
    return Tool.from_orm(db_tool)


@router.get(
    "/tools/", 
    response_model=List[Tool],
    summary="List Tools",
    description=LIST_TOOLS_DESCRIPTION,
    response_description="List of tools",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": TOOL_LIST_EXAMPLE
                }
            },
        }
    }
)
def list_tools(
    skip: int = 0,
    limit: int = 100,
    platform: Optional[str] = None,
    db: Session = Depends(get_db)
) -> List[Tool]:
    """
    List tools with optional platform filter.
    """
    # Start with a base query
    query = db.query(ToolModel)
    
    # Apply filters if provided
    if platform:
        query = query.filter(ToolModel.platform == platform)
    
    # Apply pagination
    tools = query.offset(skip).limit(limit).all()
    
    # Convert SQLAlchemy models to Pydantic schemas
    return [Tool.from_orm(tool) for tool in tools]


@router.get(
    "/tools/{tool_id}", 
    response_model=Tool,
    summary="Get Tool",
    description=GET_TOOL_DESCRIPTION,
    response_description="Tool details",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": TOOL_RESPONSE_EXAMPLE
                }
            },
        },
        404: {"description": "Tool not found"}
    }
)
def get_tool(
    tool_id: int,
    db: Session = Depends(get_db)
) -> Tool:
    """
    Get a specific tool by ID.
    """
    tool = db.query(ToolModel).filter(ToolModel.id == tool_id).first()
    
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found"
        )
    
    # Convert SQLAlchemy model to Pydantic schema
    return Tool.from_orm(tool)
