"""Integration tests for the authentication API endpoints"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.providers.aws.common.services.credential_manager import CredentialManager


@patch.object(CredentialManager, "validate_credentials")
def test_validate_aws_credentials(mock_validate_credentials, client: TestClient):
    """Test the AWS credentials validation endpoint"""
    # Mock successful validation
    mock_validate_credentials.return_value = (True, "Gov credentials validated successfully.")
    
    # Test successful validation
    response = client.post(
        "/api/auth/aws-credentials",
        json={
            "access_key": "test_access_key",
            "secret_key": "test_secret_key",
            "session_token": "test_session_token",
            "expiration": 9999999999,
            "environment": "gov"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "credentials validated" in data["message"].lower()
    assert data["environment"] == "gov"
    
    # Verify validate_credentials was called with correct arguments
    mock_validate_credentials.assert_called_once_with(
        access_key="test_access_key",
        secret_key="test_secret_key",
        session_token="test_session_token",
        environment="gov"
    )
    
    # Mock failed validation
    mock_validate_credentials.return_value = (False, "Credential validation failed: Invalid credentials")
    
    # Test failed validation
    response = client.post(
        "/api/auth/aws-credentials",
        json={
            "access_key": "invalid_access_key",
            "secret_key": "invalid_secret_key",
            "session_token": "invalid_session_token",
            "expiration": 9999999999,
            "environment": "gov"
        }
    )
    
    # Verify response
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "validation failed" in data["detail"].lower()


@patch.object(CredentialManager, "are_credentials_valid")
def test_get_aws_credential_status(mock_are_credentials_valid, client: TestClient):
    """Test the AWS credentials status endpoint"""
    # Mock valid credentials
    mock_are_credentials_valid.return_value = True
    
    # Test with valid credentials
    response = client.get("/api/auth/aws-credentials/gov")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["environment"] == "gov"
    assert data["valid"] is True
    assert "valid" in data["message"].lower()
    
    # Verify are_credentials_valid was called with correct arguments
    mock_are_credentials_valid.assert_called_with("gov")
    
    # Mock invalid credentials
    mock_are_credentials_valid.return_value = False
    
    # Test with invalid credentials
    response = client.get("/api/auth/aws-credentials/gov")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["environment"] == "gov"
    assert data["valid"] is False
    assert "invalid" in data["message"].lower()


@patch.object(CredentialManager, "clear_credentials")
def test_clear_aws_credentials(mock_clear_credentials, client: TestClient):
    """Test the AWS credentials clearing endpoint"""
    # Test clearing credentials
    response = client.delete("/api/auth/aws-credentials/gov")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "cleared" in data["message"].lower()
    
    # Verify clear_credentials was called with correct arguments
    mock_clear_credentials.assert_called_once_with("gov")


@patch.object(CredentialManager, "list_active_environments")
def test_list_aws_credential_environments(mock_list_active_environments, client: TestClient):
    """Test the AWS credentials environments listing endpoint"""
    # Mock environments
    mock_list_active_environments.return_value = {
        "gov": True,
        "com": False
    }
    
    # Test listing environments
    response = client.get("/api/auth/aws-credentials")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "environments" in data
    assert data["environments"]["gov"] is True
    assert data["environments"]["com"] is False
    
    # Verify list_active_environments was called
    mock_list_active_environments.assert_called_once()
