"""Integration test for credential refreshing functionality"""
import os
import json
import pytest
import requests
from typing import Dict, Any

# API base URL - would be configured via environment in real deployment
BASE_URL = "http://localhost:8000"  # Adjust based on your local development setup
API_URL = f"{BASE_URL}/api/v1"


def load_test_credentials() -> Dict[str, Any]:
    """Load test AWS credentials from file"""
    creds_path = os.path.join(os.path.dirname(__file__), "../../../test/.creds")
    
    if not os.path.exists(creds_path):
        pytest.skip(f"Test credentials file not found: {creds_path}")
    
    try:
        with open(creds_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        pytest.skip(f"Invalid JSON in credentials file: {creds_path}")


@pytest.fixture
def auth_setup():
    """Set up test credentials and clean up after test"""
    # Load test credentials
    creds = load_test_credentials()
    
    # Set default environment if not specified
    if 'environment' not in creds:
        creds['environment'] = 'com'  # Use commercial AWS by default
    
    # First validate and set up credentials
    response = requests.post(
        f"{API_URL}/auth/aws-credentials",
        json=creds
    )
    
    if response.status_code != 200:
        pytest.skip(f"Could not set up test credentials: {response.text}")
    
    # Return environment for test to use
    yield creds['environment']
    
    # Clean up after test
    requests.delete(f"{API_URL}/auth/aws-credentials/{creds['environment']}")


def test_credential_refresh(auth_setup):
    """Test refreshing credentials via API endpoint"""
    environment = auth_setup
    
    # First check that credentials are valid
    response = requests.get(f"{API_URL}/auth/aws-credentials/{environment}")
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    
    # Now refresh credentials without role assumption
    response = requests.post(f"{API_URL}/auth/aws-credentials/{environment}/refresh")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "expires_in" in data
    assert data["expires_in"] > 0
    assert "assumed_role" not in data
    
    print(f"Successfully refreshed credentials for {environment}")
    print(f"Credentials will expire in {data['expires_in']} seconds")


def test_credential_refresh_with_role(auth_setup):
    """Test refreshing credentials with role assumption"""
    environment = auth_setup
    
    # Get role ARN from environment variable or skip test
    role_arn = os.environ.get("TEST_ROLE_ARN")
    if not role_arn:
        pytest.skip("TEST_ROLE_ARN environment variable not set")
    
    # Refresh credentials with role assumption
    response = requests.post(
        f"{API_URL}/auth/aws-credentials/{environment}/refresh",
        params={"role_arn": role_arn}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "expires_in" in data
    assert data["expires_in"] > 0
    assert data["assumed_role"] == role_arn
    
    print(f"Successfully assumed role {role_arn}")
    print(f"Role credentials will expire in {data['expires_in']} seconds")


if __name__ == "__main__":
    # This allows running the tests directly for quick testing
    # Load test credentials
    creds = load_test_credentials()
    if creds:
        print("Test credentials loaded successfully")
        
        # Set up test environment
        if 'environment' not in creds:
            creds['environment'] = 'com'
        
        print(f"Setting up credentials for {creds['environment']} environment...")
        response = requests.post(
            f"{API_URL}/auth/aws-credentials",
            json=creds
        )
        
        if response.status_code == 200:
            print("Credentials validated successfully")
            
            # Test credential refresh
            print("\nTesting credential refresh...")
            response = requests.post(f"{API_URL}/auth/aws-credentials/{creds['environment']}/refresh")
            if response.status_code == 200:
                data = response.json()
                print(f"Credentials refreshed successfully")
                print(f"Expires in: {data['expires_in']} seconds")
            else:
                print(f"Failed to refresh credentials: {response.text}")
                
            # Clean up
            print("\nCleaning up...")
            requests.delete(f"{API_URL}/auth/aws-credentials/{creds['environment']}")
            print("Done.")
        else:
            print(f"Failed to validate credentials: {response.text}")
    else:
        print("Failed to load test credentials")
