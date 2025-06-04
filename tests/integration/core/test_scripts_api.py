"""Integration tests for the scripts API endpoints"""
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, List, Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.db.models.script import Script as ScriptModel, Tool as ToolModel
from backend.api.scripts import create_script, get_script, list_scripts, update_script, delete_script


def test_list_scripts(client: TestClient, db: Session):
    """Test listing scripts endpoint"""
    # Add test scripts to the database
    script1 = ScriptModel(
        name="Test Script 1",
        content="echo 'Hello World'",
        description="Test script 1 description",
        script_type="bash"
    )
    script2 = ScriptModel(
        name="Test Script 2",
        content="Write-Host 'Hello World'",
        description="Test script 2 description",
        script_type="powershell"
    )
    db.add(script1)
    db.add(script2)
    db.commit()
    
    # Test endpoint
    response = client.get("/api/scripts/")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Test Script 1"
    assert data[1]["name"] == "Test Script 2"
    
    # Test with filter
    response = client.get("/api/scripts/?script_type=bash")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Script 1"


def test_create_script(client: TestClient, db: Session):
    """Test creating a script endpoint"""
    # Create a tool first
    tool = ToolModel(
        name="Test Tool",
        description="Test tool description",
        tool_type="utility"
    )
    db.add(tool)
    db.commit()
    
    # Test creating script with tool
    script_data = {
        "name": "New Test Script",
        "content": "echo 'New Script'",
        "description": "New script description",
        "script_type": "bash",
        "tool_id": tool.id
    }
    
    response = client.post("/api/scripts/", json=script_data)
    
    # Verify response
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Test Script"
    assert data["content"] == "echo 'New Script'"
    assert data["tool_id"] == tool.id
    
    # Verify script was created in DB
    script = db.query(ScriptModel).filter(ScriptModel.name == "New Test Script").first()
    assert script is not None
    assert script.content == "echo 'New Script'"
    
    # Test creating script without required fields
    invalid_data = {
        "name": "Invalid Script",
        "description": "Missing required fields"
    }
    
    response = client.post("/api/scripts/", json=invalid_data)
    assert response.status_code == 422


def test_get_script(client: TestClient, db: Session):
    """Test getting a script endpoint"""
    # Add test script to the database
    script = ScriptModel(
        name="Get Test Script",
        content="echo 'Get Script'",
        description="Get script description",
        script_type="bash"
    )
    db.add(script)
    db.commit()
    
    # Test endpoint
    response = client.get(f"/api/scripts/{script.id}")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Get Test Script"
    assert data["content"] == "echo 'Get Script'"
    
    # Test with non-existent script
    response = client.get("/api/scripts/9999")
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "not found" in response.json()["detail"].lower()


def test_update_script(client: TestClient, db: Session):
    """Test updating a script endpoint"""
    # Add test script to the database
    script = ScriptModel(
        name="Update Test Script",
        content="echo 'Original Content'",
        description="Update script description",
        script_type="bash"
    )
    db.add(script)
    db.commit()
    
    # Test endpoint
    update_data = {
        "name": "Updated Script Name",
        "content": "echo 'Updated Content'",
        "description": "Updated description"
    }
    
    response = client.patch(f"/api/scripts/{script.id}", json=update_data)
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Script Name"
    assert data["content"] == "echo 'Updated Content'"
    assert data["description"] == "Updated description"
    
    # Verify script was updated in DB
    updated_script = db.query(ScriptModel).filter(ScriptModel.id == script.id).first()
    assert updated_script.name == "Updated Script Name"
    assert updated_script.content == "echo 'Updated Content'"
    
    # Test with non-existent script
    response = client.patch("/api/scripts/9999", json=update_data)
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "not found" in response.json()["detail"].lower()


def test_delete_script(client: TestClient, db: Session):
    """Test deleting a script endpoint"""
    # Add test script to the database
    script = ScriptModel(
        name="Delete Test Script",
        content="echo 'Delete Script'",
        description="Delete script description",
        script_type="bash"
    )
    db.add(script)
    db.commit()
    
    # Test endpoint
    response = client.delete(f"/api/scripts/{script.id}")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "deleted" in data["message"].lower()
    
    # Verify script was deleted from DB
    deleted_script = db.query(ScriptModel).filter(ScriptModel.id == script.id).first()
    assert deleted_script is None
    
    # Test with non-existent script
    response = client.delete("/api/scripts/9999")
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "not found" in response.json()["detail"].lower()
