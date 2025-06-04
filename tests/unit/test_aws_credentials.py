"""
Unit tests for the AWSCredentials class and its validators.
"""
import pytest
from typing import Optional
from backend.core.config import AWSCredentials, AWSEnvironment


def test_environment_validator():
    """Test that the environment validator properly converts string to enum"""
    # String value for "com" environment
    creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        environment="com"
    )
    assert isinstance(creds.environment, AWSEnvironment)
    assert creds.environment == AWSEnvironment.COM
    
    # String value for "gov" environment
    creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        environment="gov"
    )
    assert isinstance(creds.environment, AWSEnvironment)
    assert creds.environment == AWSEnvironment.GOV
    
    # Using the enum directly
    creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        environment=AWSEnvironment.COM
    )
    assert isinstance(creds.environment, AWSEnvironment)
    assert creds.environment == AWSEnvironment.COM


def test_expiration_validator():
    """Test that the expiration validator properly converts float to int"""
    # Float expiration
    creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        environment="com",
        expiration=1234567890.5
    )
    assert isinstance(creds.expiration, int)
    assert creds.expiration == 1234567890
    
    # Integer expiration
    creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        environment="com",
        expiration=1234567890
    )
    assert isinstance(creds.expiration, int)
    assert creds.expiration == 1234567890
    
    # None expiration
    creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        environment="com",
        expiration=None
    )
    assert creds.expiration is None


def test_optional_parameters():
    """Test the optional parameters of AWSCredentials"""
    # Minimal configuration
    creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        environment="com"
    )
    assert creds.access_key == "test_key"
    assert creds.secret_key == "test_secret"
    assert creds.environment == AWSEnvironment.COM
    assert creds.session_token is None
    assert creds.expiration is None
    assert creds.assumed_role is None
    
    # Full configuration
    creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        environment="gov",
        session_token="test_token",
        expiration=1234567890,
        assumed_role="arn:aws:iam::123456789012:role/test-role"
    )
    assert creds.access_key == "test_key"
    assert creds.secret_key == "test_secret"
    assert creds.environment == AWSEnvironment.GOV
    assert creds.session_token == "test_token"
    assert creds.expiration == 1234567890
    assert creds.assumed_role == "arn:aws:iam::123456789012:role/test-role"
