#!/usr/bin/env python3
"""
Integration tests for AWS Script Runner API using FastAPI's TestClient.

This script tests the API endpoints without starting a separate server process.
It validates:
1. Authentication with AWS credentials for both COM and GOV environments
2. Listing accounts in both environments
3. Getting account details
4. Listing instances in specific regions
"""

import os
import json
import time
import logging
import pytest
from typing import Dict, Any, List, Generator
from pathlib import Path
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.main import app
from backend.core.config import settings, AWSEnvironment
from backend.providers.aws.script_runner.schemas.account import AWSCredentials
from backend.providers.aws.common.services.credential_manager import CredentialManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("api_test")

# Test client
client = TestClient(app)

# Environment variables
ENV_FILE_PATH = Path(__file__).parent.parent.parent / ".env"


def load_env_credentials() -> Dict[str, Dict[str, str]]:
    """Load AWS credentials from .env file"""
    logger.info(f"Loading credentials from {ENV_FILE_PATH}")
    
    if not ENV_FILE_PATH.exists():
        logger.error(f".env file not found at {ENV_FILE_PATH}")
        return {}
    
    # Load environment variables
    load_dotenv(ENV_FILE_PATH)
    
    # Extract credentials for each environment
    credentials = {}
    
    # Current time as expiration (1 hour from now)
    expiration_time = time.time() + 3600
    
    # COM environment
    if os.getenv("AWS_ACCESS_KEY_ID_COM") and os.getenv("AWS_SECRET_ACCESS_KEY_COM"):
        session_token = os.getenv("AWS_SESSION_TOKEN_COM")
        if not session_token:
            logger.warning("AWS_SESSION_TOKEN_COM is required but not provided in environment")
            # For test compatibility, use a dummy token
            session_token = "dummy_session_token_for_testing"
            
        credentials["com"] = {
            "access_key": os.getenv("AWS_ACCESS_KEY_ID_COM", ""),
            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY_COM", ""),
            "session_token": session_token,
            "expiration": expiration_time,  # Required by AWSCredentials schema
            "environment": "com"
        }
    
    # GOV environment
    if os.getenv("AWS_ACCESS_KEY_ID_GOV") and os.getenv("AWS_SECRET_ACCESS_KEY_GOV"):
        session_token = os.getenv("AWS_SESSION_TOKEN_GOV")
        if not session_token:
            logger.warning("AWS_SESSION_TOKEN_GOV is required but not provided in environment")
            # For test compatibility, use a dummy token
            session_token = "dummy_session_token_for_testing"
            
        credentials["gov"] = {
            "access_key": os.getenv("AWS_ACCESS_KEY_ID_GOV", ""),
            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY_GOV", ""),
            "session_token": session_token,
            "expiration": expiration_time,  # Required by AWSCredentials schema
            "environment": "gov"
        }
    
    if not credentials:
        logger.error("No valid credentials found in .env file")
    else:
        logger.info(f"Found credentials for environments: {', '.join(credentials.keys())}")
    
    return credentials


@pytest.fixture(scope="module")
def aws_credentials() -> Dict[str, Dict[str, str]]:
    """Fixture to provide AWS credentials"""
    return load_env_credentials()


@pytest.fixture(scope="module")
def credential_manager() -> CredentialManager:
    """Fixture to provide a credential manager instance"""
    return CredentialManager()


def test_health_endpoint():
    """Test the health check endpoint"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.parametrize("environment", ["com", "gov"])
def test_auth_credentials(aws_credentials, environment):
    """Test credential validation endpoint"""
    # Skip test if credentials for this environment are not available
    if environment not in aws_credentials:
        pytest.skip(f"No credentials available for {environment} environment")
    
    credentials = aws_credentials[environment]
    response = client.post("/api/auth/aws-credentials", json=credentials)
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["environment"] == environment


@pytest.mark.parametrize("environment", ["com", "gov"])
def test_get_credential_status(aws_credentials, environment):
    """Test credential status endpoint"""
    # Skip test if credentials for this environment are not available
    if environment not in aws_credentials:
        pytest.skip(f"No credentials available for {environment} environment")
    
    # First authenticate
    credentials = aws_credentials[environment]
    client.post("/api/auth/aws-credentials", json=credentials)
    
    # Then check status
    response = client.get(f"/api/auth/aws-credentials/{environment}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["environment"] == environment
    assert data["valid"] is True


def test_list_credential_environments(aws_credentials):
    """Test listing credential environments endpoint"""
    # First authenticate with all available environments
    for env, creds in aws_credentials.items():
        client.post("/api/auth/aws-credentials", json=creds)
    
    # Then list environments
    response = client.get("/api/auth/aws-credentials")
    
    assert response.status_code == 200
    data = response.json()
    assert "environments" in data
    
    # Check that our authenticated environments are listed as valid
    for env in aws_credentials.keys():
        assert env in data["environments"]
        assert data["environments"][env] is True


@pytest.mark.parametrize("environment", ["com", "gov"])
def test_list_accounts(aws_credentials, environment):
    """Test listing accounts endpoint"""
    # Skip test if credentials for this environment are not available
    if environment not in aws_credentials:
        pytest.skip(f"No credentials available for {environment} environment")
    
    # First authenticate
    credentials = aws_credentials[environment]
    client.post("/api/auth/aws-credentials", json=credentials)
    
    # Then list accounts
    response = client.get(f"/api/accounts/?environment={environment}")
    
    assert response.status_code == 200
    data = response.json()
    assert "environment" in data
    assert data["environment"] == environment
    assert "accounts" in data
    assert isinstance(data["accounts"], list)
    
    # If we got accounts, store first account ID for later tests
    if data["accounts"]:
        # Store account ID as a module-level variable for other tests
        globals()[f"first_account_id_{environment}"] = data["accounts"][0]["Id"]
        logger.info(f"Found account ID for {environment}: {data['accounts'][0]['Id']}")


@pytest.mark.parametrize("environment", ["com", "gov"])
def test_get_account_details(aws_credentials, environment):
    """Test getting account details endpoint"""
    # Skip test if credentials for this environment are not available
    if environment not in aws_credentials:
        pytest.skip(f"No credentials available for {environment} environment")
    
    # Skip if we don't have an account ID from the previous test
    account_id_var = f"first_account_id_{environment}"
    if account_id_var not in globals():
        pytest.skip(f"No account ID available for {environment} environment")
    
    account_id = globals()[account_id_var]
    
    # First authenticate
    credentials = aws_credentials[environment]
    client.post("/api/auth/aws-credentials", json=credentials)
    
    # Then get account details
    response = client.get(f"/api/accounts/{account_id}?environment={environment}")
    
    assert response.status_code == 200
    data = response.json()
    assert "account_id" in data
    assert data["account_id"] == account_id
    assert "environment" in data
    assert data["environment"] == environment
    assert "regions" in data
    assert isinstance(data["regions"], list)
    
    # If we got regions, store first region for later tests
    if data["regions"]:
        # Store region as a module-level variable for other tests
        globals()[f"first_region_{environment}"] = data["regions"][0]
        logger.info(f"Found region for {environment}: {data['regions'][0]}")


@pytest.mark.parametrize("environment", ["com", "gov"])
def test_list_instances(aws_credentials, environment):
    """Test listing instances endpoint"""
    # Skip test if credentials for this environment are not available
    if environment not in aws_credentials:
        pytest.skip(f"No credentials available for {environment} environment")
    
    # Skip if we don't have an account ID or region from previous tests
    account_id_var = f"first_account_id_{environment}"
    region_var = f"first_region_{environment}"
    
    if account_id_var not in globals() or region_var not in globals():
        pytest.skip(f"No account ID or region available for {environment} environment")
    
    account_id = globals()[account_id_var]
    region = globals()[region_var]
    
    # First authenticate
    credentials = aws_credentials[environment]
    client.post("/api/auth/aws-credentials", json=credentials)
    
    # Then list instances
    response = client.get(f"/api/accounts/{account_id}/regions/{region}/instances?environment={environment}")
    
    assert response.status_code == 200
    data = response.json()
    assert "account_id" in data
    assert data["account_id"] == account_id
    assert "region" in data
    assert data["region"] == region
    assert "environment" in data
    assert data["environment"] == environment
    assert "instances" in data
    assert isinstance(data["instances"], list)
    assert "count" in data
    assert isinstance(data["count"], int)
    
    # Log the instance count
    logger.info(f"Found {data['count']} instances in {account_id}/{region} ({environment})")


@pytest.mark.parametrize("environment", ["com", "gov"])
def test_invalid_credentials(environment, monkeypatch):
    """Test validation with invalid credentials"""
    # Create a mock function that simulates failed AWS validation
    def mock_validate_credentials(*args, **kwargs):
        return False, "Invalid credentials: Access denied"
    
    # Patch the CredentialManager.validate_credentials method
    from backend.providers.aws.common.services.credential_manager import CredentialManager
    monkeypatch.setattr(CredentialManager, "validate_credentials", mock_validate_credentials)
    
    invalid_credentials = {
        "access_key": "AKIA000000000000FAKE",
        "secret_key": "abcdefghijklmnopqrstuvwxyz1234567890FAKE",
        "session_token": None,
        "expiration": time.time() + 3600,  # Required by schema validation
        "environment": environment
    }

    response = client.post("/api/auth/aws-credentials", json=invalid_credentials)
    
    # Should return 401 Unauthorized with our mocked validation
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]
    data = response.json()
    assert "detail" in data  # Error message


def test_clear_credentials(aws_credentials):
    """Test clearing credentials endpoint"""
    # First authenticate with all available environments
    for env, creds in aws_credentials.items():
        client.post("/api/auth/aws-credentials", json=creds)
    
    # Then clear credentials for each environment
    for env in aws_credentials.keys():
        response = client.delete(f"/api/auth/aws-credentials/{env}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify credentials were cleared
        status_response = client.get(f"/api/auth/aws-credentials/{env}")
        status_data = status_response.json()
        assert status_data["valid"] is False


if __name__ == "__main__":
    # Run the tests directly
    import pytest
    pytest.main(["-xvs", __file__])
