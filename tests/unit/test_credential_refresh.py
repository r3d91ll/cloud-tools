"""Unit tests for credential refresh functionality"""
import pytest
import boto3
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from backend.providers.aws.common.services.credential_manager import CredentialManager
from backend.providers.aws.script_runner.schemas.account import AWSCredentials


@patch('app.services.aws.credential_manager.boto3.Session')
def test_refresh_credentials_without_role(mock_boto3_session):
    """Test refreshing credentials without assuming a role"""
    # Setup manager with existing credentials
    manager = CredentialManager()
    
    # Create test credentials
    test_creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        session_token="test_token",
        expiration=time.time() + 3600,
        environment="com"
    )
    
    # Store the credentials
    manager.store_credentials(test_creds)
    
    # Setup mock session
    mock_session = MagicMock()
    mock_boto3_session.return_value = mock_session
    
    # Setup mock STS client
    mock_sts = MagicMock()
    mock_session.client.return_value = mock_sts
    
    # Mock get_session_token response
    session_token_response = {
        'Credentials': {
            'AccessKeyId': 'ASIA_REFRESHED_KEY',
            'SecretAccessKey': 'refreshed_secret_key',
            'SessionToken': 'refreshed_session_token',
            'Expiration': datetime.now() + timedelta(hours=1)
        }
    }
    mock_sts.get_session_token.return_value = session_token_response
    
    # Call refresh_credentials
    success, message, fresh_creds = manager.refresh_credentials('com')
    
    # Verify success
    assert success is True
    assert "successfully refreshed" in message.lower()
    assert fresh_creds is not None
    assert fresh_creds.access_key == 'ASIA_REFRESHED_KEY'
    assert fresh_creds.secret_key == 'refreshed_secret_key'
    assert fresh_creds.session_token == 'refreshed_session_token'
    assert fresh_creds.environment == 'com'
    
    # Verify STS client was created with the right params
    mock_session.client.assert_called_with(
        'sts',
        region_name='us-east-1',
        endpoint_url='https://sts.us-east-1.amazonaws.com'
    )
    
    # Verify get_session_token was called
    mock_sts.get_session_token.assert_called_with(DurationSeconds=3600)


@patch('app.services.aws.credential_manager.boto3.Session')
def test_refresh_credentials_with_role(mock_boto3_session):
    """Test refreshing credentials with role assumption"""
    # Setup manager with existing credentials
    manager = CredentialManager()
    
    # Create test credentials
    test_creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        session_token="test_token",
        expiration=time.time() + 3600,
        environment="com"
    )
    
    # Store the credentials
    manager.store_credentials(test_creds)
    
    # Setup mock session
    mock_session = MagicMock()
    mock_boto3_session.return_value = mock_session
    
    # Setup mock STS client
    mock_sts = MagicMock()
    mock_session.client.return_value = mock_sts
    
    # Mock assume_role response
    assume_role_response = {
        'Credentials': {
            'AccessKeyId': 'ASIA_ASSUMED_ROLE_KEY',
            'SecretAccessKey': 'assumed_role_secret_key',
            'SessionToken': 'assumed_role_session_token',
            'Expiration': datetime.now() + timedelta(hours=1)
        },
        'AssumedRoleUser': {
            'AssumedRoleId': 'AROA:session',
            'Arn': 'arn:aws:sts::123456789012:assumed-role/TestRole/session'
        }
    }
    mock_sts.assume_role.return_value = assume_role_response
    
    # Call refresh_credentials with a role
    role_arn = 'arn:aws:iam::123456789012:role/TestRole'
    success, message, fresh_creds = manager.refresh_credentials('com', role_arn)
    
    # Verify success
    assert success is True
    assert "successfully refreshed" in message.lower()
    assert fresh_creds is not None
    assert fresh_creds.access_key == 'ASIA_ASSUMED_ROLE_KEY'
    assert fresh_creds.secret_key == 'assumed_role_secret_key'
    assert fresh_creds.session_token == 'assumed_role_session_token'
    assert fresh_creds.environment == 'com'
    assert hasattr(fresh_creds, 'assumed_role')
    assert fresh_creds.assumed_role == role_arn
    
    # Verify assume_role was called with the right parameters
    mock_sts.assume_role.assert_called_with(
        RoleArn=role_arn,
        RoleSessionName=pytest.approx(f"API-Refresh-{int(time.time())}", abs=10),
        DurationSeconds=3600
    )


@patch('app.services.aws.credential_manager.boto3.Session')
def test_refresh_credentials_no_existing_creds(mock_boto3_session):
    """Test refreshing credentials when no valid credentials exist"""
    # Setup manager with no existing credentials
    manager = CredentialManager()
    
    # Call refresh_credentials
    success, message, fresh_creds = manager.refresh_credentials('com')
    
    # Verify failure
    assert success is False
    assert "no valid base credentials" in message.lower()
    assert fresh_creds is None
    
    # Verify boto3.Session was not called
    mock_boto3_session.assert_not_called()


@patch('app.services.aws.credential_manager.boto3.Session')
def test_refresh_credentials_invalid_environment(mock_boto3_session):
    """Test refreshing credentials with an invalid environment"""
    # Setup manager
    manager = CredentialManager()
    
    # Call refresh_credentials with invalid environment
    success, message, fresh_creds = manager.refresh_credentials('invalid')
    
    # Verify failure
    assert success is False
    assert "invalid environment" in message.lower()
    assert fresh_creds is None
    
    # Verify boto3.Session was not called
    mock_boto3_session.assert_not_called()


@patch('app.services.aws.credential_manager.boto3.Session')
def test_refresh_credentials_exception(mock_boto3_session):
    """Test refreshing credentials when an exception occurs"""
    # Setup manager with existing credentials
    manager = CredentialManager()
    
    # Create test credentials
    test_creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        session_token="test_token",
        expiration=time.time() + 3600,
        environment="com"
    )
    
    # Store the credentials
    manager.store_credentials(test_creds)
    
    # Setup mock session
    mock_session = MagicMock()
    mock_boto3_session.return_value = mock_session
    
    # Setup mock STS client that raises an exception
    mock_sts = MagicMock()
    mock_session.client.return_value = mock_sts
    mock_sts.get_session_token.side_effect = Exception("STS error")
    
    # Call refresh_credentials
    success, message, fresh_creds = manager.refresh_credentials('com')
    
    # Verify failure
    assert success is False
    assert "failed to refresh" in message.lower()
    assert fresh_creds is None
    
    # Verify STS client was created
    mock_session.client.assert_called_once()
    mock_sts.get_session_token.assert_called_once()
