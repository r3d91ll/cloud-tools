"""Integration tests for the accounts API endpoints"""
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, List, Any

from fastapi.testclient import TestClient

from backend.providers.aws.common.services.account_manager import AccountManager
from backend.db.models.account import Account as AccountModel


@patch.object(AccountManager, "list_accounts")
def test_list_accounts(mock_list_accounts, client: TestClient):
    """Test listing AWS accounts endpoint"""
    # Mock data
    mock_accounts = [
        {"account_id": "123456789012", "name": "Test Account 1", "regions": ["us-gov-west-1"]},
        {"account_id": "210987654321", "name": "Test Account 2", "regions": ["us-gov-west-1", "us-gov-east-1"]}
    ]
    mock_list_accounts.return_value = mock_accounts
    
    # Test endpoint
    response = client.get("/api/accounts/?environment=gov")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "accounts" in data
    assert len(data["accounts"]) == 2
    assert data["accounts"][0]["account_id"] == "123456789012"
    assert data["accounts"][1]["account_id"] == "210987654321"
    
    # Verify service call
    mock_list_accounts.assert_called_once_with("gov")
    
    # Test with no valid credentials
    mock_list_accounts.side_effect = ValueError("No valid credentials found for gov")
    
    response = client.get("/api/accounts/?environment=gov")
    assert response.status_code == 401
    assert "detail" in response.json()
    assert "valid credentials" in response.json()["detail"].lower()


@patch.object(AccountManager, "get_account_details")
def test_get_account(mock_get_account_details, client: TestClient):
    """Test getting account details endpoint"""
    # Mock data
    mock_account = {
        "account_id": "123456789012",
        "name": "Test Account",
        "regions": [
            {
                "name": "us-gov-west-1",
                "instances": [
                    {"instance_id": "i-12345", "platform": "linux"},
                    {"instance_id": "i-67890", "platform": "windows"}
                ]
            }
        ]
    }
    mock_get_account_details.return_value = mock_account
    
    # Test endpoint
    response = client.get("/api/accounts/123456789012?environment=gov")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == "123456789012"
    assert data["name"] == "Test Account"
    assert len(data["regions"]) == 1
    assert data["regions"][0]["name"] == "us-gov-west-1"
    assert len(data["regions"][0]["instances"]) == 2
    
    # Verify service call
    mock_get_account_details.assert_called_once_with("123456789012", "gov")
    
    # Test with account not found
    mock_get_account_details.side_effect = ValueError("Account not found")
    
    response = client.get("/api/accounts/999999999999?environment=gov")
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "not found" in response.json()["detail"].lower()


@patch.object(AccountManager, "get_instances")
def test_list_instances(mock_get_instances, client: TestClient):
    """Test listing instances endpoint"""
    # Mock data
    mock_instances = [
        {"instance_id": "i-12345", "platform": "linux", "name": "Web Server", "state": "running"},
        {"instance_id": "i-67890", "platform": "windows", "name": "DB Server", "state": "running"}
    ]
    mock_get_instances.return_value = mock_instances
    
    # Test endpoint
    response = client.get("/api/accounts/123456789012/regions/us-gov-west-1/instances?environment=gov")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "instances" in data
    assert len(data["instances"]) == 2
    assert data["instances"][0]["instance_id"] == "i-12345"
    assert data["instances"][1]["instance_id"] == "i-67890"
    
    # Verify service call
    mock_get_instances.assert_called_once_with("123456789012", "us-gov-west-1", "gov")
    
    # Test with no instances found
    mock_get_instances.return_value = []
    
    response = client.get("/api/accounts/123456789012/regions/us-gov-east-1/instances?environment=gov")
    assert response.status_code == 200
    assert len(response.json()["instances"]) == 0


@patch.object(AccountManager, "sync_accounts")
def test_sync_accounts(mock_sync_accounts, client: TestClient):
    """Test syncing accounts endpoint"""
    # Mock data
    mock_sync_result = {
        "accounts_added": 2,
        "regions_added": 3,
        "instances_discovered": 5
    }
    mock_sync_accounts.return_value = mock_sync_result
    
    # Test endpoint
    response = client.post("/api/accounts/sync?environment=gov")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["accounts_added"] == 2
    assert data["regions_added"] == 3
    assert data["instances_discovered"] == 5
    
    # Verify service call
    mock_sync_accounts.assert_called_once_with("gov")
    
    # Test with error
    mock_sync_accounts.side_effect = ValueError("Failed to sync accounts")
    
    response = client.post("/api/accounts/sync?environment=gov")
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "failed to sync" in response.json()["detail"].lower()
