"""Unit tests for the credential manager service"""
import pytest
import boto3
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from backend.providers.aws.common.services.credential_manager import CredentialManager
from backend.providers.aws.script_runner.schemas.account import AWSCredentials


@patch('app.services.aws.credential_manager.CredentialManager._load_credentials_from_settings')
def test_init_credential_manager(mock_load_credentials):
    """Test initializing the credential manager"""
    # Prevent loading credentials from settings during initialization
    mock_load_credentials.return_value = None
    
    manager = CredentialManager()
    assert manager.ttl_seconds == 3600
    assert manager._credentials_cache == {}


def test_get_env_config():
    """Test getting environment configuration"""
    manager = CredentialManager()
    
    # Test valid environments
    gov_config = manager._get_env_config("gov")
    assert gov_config["region"] == "us-gov-west-1"
    assert "endpoint" in gov_config
    
    com_config = manager._get_env_config("com")
    assert com_config["region"] == "us-east-1"
    assert "endpoint" in com_config
    
    # Test case insensitivity
    gov_config_upper = manager._get_env_config("GOV")
    assert gov_config_upper == gov_config
    
    # Test invalid environment
    with pytest.raises(ValueError):
        manager._get_env_config("invalid")


def test_check_expiry():
    """Test checking credential expiration"""
    manager = CredentialManager()
    
    # Test with no credentials
    assert manager._check_expiry(None) is True
    
    # Test with expired credentials
    expired_creds = AWSCredentials(
        access_key="test",
        secret_key="test",
        session_token="test",
        expiration=time.time() - 100,  # 100 seconds ago
        environment="gov"
    )
    assert manager._check_expiry(expired_creds) is True
    
    # Test with valid credentials
    valid_creds = AWSCredentials(
        access_key="test",
        secret_key="test",
        session_token="test",
        expiration=time.time() + 3600,  # 1 hour in the future
        environment="gov"
    )
    assert manager._check_expiry(valid_creds) is False
    
    # Test with credentials about to expire
    expiring_creds = AWSCredentials(
        access_key="test",
        secret_key="test",
        session_token="test",
        expiration=time.time() + 60,  # 1 minute in the future
        environment="gov"
    )
    assert manager._check_expiry(expiring_creds) is False  # Still valid but close to expiring
    
    # Test with credentials that have None expiration
    none_expiry_creds = AWSCredentials(
        access_key="test",
        secret_key="test",
        session_token="test",
        expiration=None,  # No expiration set
        environment="gov"
    )
    assert manager._check_expiry(none_expiry_creds) is False  # Should be treated as non-expired


def test_store_and_get_credentials():
    """Test storing and retrieving credentials"""
    manager = CredentialManager()
    
    # Create test credentials
    test_creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        session_token="test_token",
        expiration=time.time() + 3600,
        environment="gov"
    )
    
    # Store credentials
    manager.store_credentials(test_creds)
    
    # Retrieve credentials
    retrieved_creds = manager.get_credentials("gov")
    assert retrieved_creds is not None
    assert retrieved_creds.access_key == "test_key"
    assert retrieved_creds.secret_key == "test_secret"
    assert retrieved_creds.session_token == "test_token"
    assert retrieved_creds.environment == "gov"
    
    # Test case insensitivity
    upper_retrieved_creds = manager.get_credentials("GOV")
    assert upper_retrieved_creds is retrieved_creds
    
    # Test non-existent environment
    assert manager.get_credentials("non_existent") is None


def test_clear_credentials():
    """Test clearing credentials"""
    manager = CredentialManager()
    
    # Create and store test credentials
    test_creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        session_token="test_token",
        expiration=time.time() + 3600,
        environment="gov"
    )
    manager.store_credentials(test_creds)
    
    # Verify credentials are stored
    assert manager.get_credentials("gov") is not None
    
    # Clear credentials
    manager.clear_credentials("gov")
    
    # Verify credentials are cleared
    assert manager.get_credentials("gov") is None


@patch('app.services.aws.credential_manager.settings')
@patch("boto3.Session")
def test_create_session(mock_boto3_session, mock_settings):
    """Test creating a boto3 session"""
    # Configure mocks to avoid loading credentials from settings
    mock_settings.get_credentials.return_value = None
    
    # Setup manager and add test credentials
    manager = CredentialManager()
    manager.store_credentials(AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        session_token="test_token",
        expiration=time.time() + 3600,
        environment="gov"
    ))
    
    # Mock boto3 session
    mock_session = MagicMock()
    mock_boto3_session.return_value = mock_session
    
    # Call the method
    session = manager.create_session("gov")
    
    # Verify boto3.Session was called with correct arguments
    mock_boto3_session.assert_called_once_with(
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
        aws_session_token="test_token",
        region_name="us-gov-west-1"
    )
    
    # Verify session was returned - it should be the mock_session we configured
    assert session is mock_session
    
    # Test with no credentials
    mock_boto3_session.reset_mock()
    manager.clear_credentials("gov")
    # Make sure settings.get_credentials returns None to simulate no credentials
    mock_settings.get_credentials.return_value = None
    # Now the create_session should return None
    assert manager.create_session("gov") is None


@patch('app.services.aws.credential_manager.settings')
@patch("boto3.Session")
def test_validate_credentials_success(mock_boto3_session, mock_settings):
    """Test successful AWS credential validation"""
    # Mock settings to avoid side effects
    mock_settings.get_credentials.return_value = None
    
    # Setup a clean credential manager
    manager = CredentialManager()

    # Mock boto3 session and STS client for success case
    mock_session = MagicMock()
    mock_boto3_session.return_value = mock_session
    mock_sts = MagicMock()
    mock_session.client.return_value = mock_sts
    mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

    # Test successful validation
    success, message = manager.validate_credentials(
        access_key="test_key",
        secret_key="test_secret",
        session_token="test_token",
        environment="gov"
    )
    
    # Verify Session was created with correct arguments
    mock_boto3_session.assert_any_call(
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
        aws_session_token="test_token"
    )

    # Verify client was created with correct arguments
    mock_session.client.assert_called_with(
        "sts", 
        endpoint_url="https://sts.us-gov-west-1.amazonaws.com",
        region_name="us-gov-west-1"
    )

    # Verify successful result
    assert success is True
    assert "validated successfully" in message.lower()

    # Verify credentials were stored
    stored_creds = manager.get_credentials("gov")
    assert stored_creds is not None
    assert stored_creds.access_key == "test_key"


@patch('app.services.aws.credential_manager.settings')
def test_validate_credentials_failure(mock_settings):
    """Test failed AWS credential validation by mocking the boto3 client call"""
    # Mock settings to avoid side effects
    mock_settings.get_credentials.return_value = None
    
    # Create a credential manager
    manager = CredentialManager()
    
    # We need to patch the actual method in the validate_credentials function that's raising the exception
    # First patch boto3.Session to return our mock session
    with patch('boto3.Session') as mock_session_constructor:
        # Create our mock session
        mock_session = MagicMock()
        mock_session_constructor.return_value = mock_session
        
        # Create a mock client that will be returned by session.client('sts', ...)
        mock_sts_client = MagicMock()
        mock_session.client.return_value = mock_sts_client
        
        # Here's the critical part - make get_caller_identity raise an exception
        mock_sts_client.get_caller_identity.side_effect = Exception("Invalid credentials")
        
        # Now when we call validate_credentials, it should catch the exception raised by get_caller_identity
        success, message = manager.validate_credentials(
            access_key="invalid", 
            secret_key="invalid", 
            session_token="invalid",
            environment="gov"
        )
        
        # Verify that session.client was called with the expected arguments
        mock_session.client.assert_called_with(
            'sts',
            region_name='us-gov-west-1',
            endpoint_url='https://sts.us-gov-west-1.amazonaws.com'
        )
        
        # Verify the mock was used and get_caller_identity was called
        mock_sts_client.get_caller_identity.assert_called_once()
        
        # Verify the failure result
        assert success is False
        assert "failed" in message.lower()
