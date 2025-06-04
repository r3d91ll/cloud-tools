"""Integration tests for the executions API endpoints"""
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, List, Any
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.db.models.script import Script as ScriptModel
from backend.db.models.account import Instance as InstanceModel, Region as RegionModel, Account as AccountModel
from backend.db.models.execution import Execution as ExecutionModel, ExecutionBatch as ExecutionBatchModel
from app.services.aws.ssm_manager import SSMManager


def create_test_dependencies(db: Session):
    """Create necessary test dependencies for execution tests"""
    # Create test account
    account = AccountModel(
        account_id="123456789012",
        name="Test Account",
        environment="gov",
        active=True
    )
    db.add(account)
    db.flush()
    
    # Create test region
    region = RegionModel(
        name="us-gov-west-1",
        account_id=account.id
    )
    db.add(region)
    db.flush()
    
    # Create test instance
    instance = InstanceModel(
        instance_id="i-12345678",
        region_id=region.id,
        platform="linux"
    )
    db.add(instance)
    db.flush()
    
    # Create test script
    script = ScriptModel(
        name="Test Script",
        content="echo 'Test Execution'",
        description="Script for testing executions",
        script_type="bash"
    )
    db.add(script)
    db.commit()
    
    return {
        "account": account,
        "region": region,
        "instance": instance,
        "script": script
    }


@patch.object(SSMManager, "execute_command")
def test_create_execution(mock_execute_command, client: TestClient, db: Session):
    """Test creating an execution endpoint"""
    # Create dependencies
    dependencies = create_test_dependencies(db)
    
    # Mock SSM execution
    mock_execute_command.return_value = {"CommandId": "test-command-id"}
    
    # Test endpoint
    execution_data = {
        "script_id": dependencies["script"].id,
        "instance_id": dependencies["instance"].id,
        "parameters": {"param1": "value1"},
        "environment": "gov"
    }
    
    response = client.post("/api/executions/", json=execution_data)
    
    # Verify response
    assert response.status_code == 201
    data = response.json()
    assert data["script_id"] == dependencies["script"].id
    assert data["instance_id"] == dependencies["instance"].id
    assert data["status"] == "pending"
    assert data["command_id"] == "test-command-id"
    
    # Verify execution was created in DB
    execution = db.query(ExecutionModel).filter(
        ExecutionModel.script_id == dependencies["script"].id,
        ExecutionModel.instance_id == dependencies["instance"].id
    ).first()
    assert execution is not None
    assert execution.command_id == "test-command-id"
    
    # Test with SSM error
    mock_execute_command.side_effect = Exception("SSM execution failed")
    
    response = client.post("/api/executions/", json=execution_data)
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "failed" in response.json()["detail"].lower()


def test_list_executions(client: TestClient, db: Session):
    """Test listing executions endpoint"""
    # Create dependencies
    dependencies = create_test_dependencies(db)
    
    # Create test executions
    execution1 = ExecutionModel(
        script_id=dependencies["script"].id,
        instance_id=dependencies["instance"].id,
        status="completed",
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow() - timedelta(minutes=50),
        output="Execution output 1",
        exit_code=0,
        command_id="cmd-1"
    )
    execution2 = ExecutionModel(
        script_id=dependencies["script"].id,
        instance_id=dependencies["instance"].id,
        status="failed",
        start_time=datetime.utcnow() - timedelta(minutes=30),
        end_time=datetime.utcnow() - timedelta(minutes=25),
        output="Execution failed",
        exit_code=1,
        command_id="cmd-2"
    )
    db.add(execution1)
    db.add(execution2)
    db.commit()
    
    # Test endpoint
    response = client.get("/api/executions/")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["status"] == "completed"
    assert data[1]["status"] == "failed"
    
    # Test with filter by status
    response = client.get("/api/executions/?status=failed")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "failed"
    
    # Test with filter by script_id
    response = client.get(f"/api/executions/?script_id={dependencies['script'].id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@patch.object(SSMManager, "get_command_status")
def test_get_execution(mock_get_command_status, client: TestClient, db: Session):
    """Test getting an execution endpoint"""
    # Create dependencies
    dependencies = create_test_dependencies(db)
    
    # Create test execution
    execution = ExecutionModel(
        script_id=dependencies["script"].id,
        instance_id=dependencies["instance"].id,
        status="running",
        start_time=datetime.utcnow() - timedelta(minutes=5),
        command_id="test-command-id"
    )
    db.add(execution)
    db.commit()
    
    # Mock SSM command status
    mock_get_command_status.return_value = {
        "status": "Success",
        "output": "Command output",
        "exit_code": 0
    }
    
    # Test endpoint
    response = client.get(f"/api/executions/{execution.id}")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == execution.id
    assert data["script_id"] == dependencies["script"].id
    assert data["instance_id"] == dependencies["instance"].id
    assert data["status"] == "completed"  # Updated by SSM status
    assert data["output"] == "Command output"
    assert data["exit_code"] == 0
    
    # Verify execution was updated in DB
    updated_execution = db.query(ExecutionModel).filter(ExecutionModel.id == execution.id).first()
    assert updated_execution.status == "completed"
    assert updated_execution.output == "Command output"
    assert updated_execution.exit_code == 0
    
    # Test with non-existent execution
    response = client.get("/api/executions/9999")
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "not found" in response.json()["detail"].lower()


@patch.object(SSMManager, "execute_command")
def test_create_batch_execution(mock_execute_command, client: TestClient, db: Session):
    """Test creating a batch execution endpoint"""
    # Create dependencies
    dependencies = create_test_dependencies(db)
    
    # Create a second instance for batch execution
    instance2 = InstanceModel(
        instance_id="i-87654321",
        region_id=dependencies["region"].id,
        platform="linux"
    )
    db.add(instance2)
    db.commit()
    
    # Mock SSM execution
    mock_execute_command.return_value = {"CommandId": "batch-command-id"}
    
    # Test endpoint
    batch_data = {
        "name": "Test Batch",
        "description": "Test batch execution",
        "script_id": dependencies["script"].id,
        "instance_ids": [dependencies["instance"].id, instance2.id],
        "parameters": {"param1": "batch_value"},
        "environment": "gov"
    }
    
    response = client.post("/api/executions/batch", json=batch_data)
    
    # Verify response
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Batch"
    assert data["status"] == "pending"
    assert len(data["executions"]) == 2
    
    # Verify batch was created in DB
    batch = db.query(ExecutionBatchModel).filter(ExecutionBatchModel.name == "Test Batch").first()
    assert batch is not None
    assert len(batch.executions) == 2
    
    # Verify both executions reference the batch
    for execution in batch.executions:
        assert execution.batch_id == batch.id
        assert execution.command_id == "batch-command-id"
    
    # Test with invalid instance ID
    invalid_batch_data = {
        "name": "Invalid Batch",
        "description": "Batch with invalid instance",
        "script_id": dependencies["script"].id,
        "instance_ids": [9999],
        "parameters": {"param1": "value1"},
        "environment": "gov"
    }
    
    response = client.post("/api/executions/batch", json=invalid_batch_data)
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "not found" in response.json()["detail"].lower()
