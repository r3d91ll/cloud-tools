#!/usr/bin/env python3
"""
Direct test runner for credential manager functionality
"""
import sys
import time
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.config import AWSCredentials, AWSEnvironment
from backend.providers.aws.common.services.credential_manager import CredentialManager

def test_aws_credentials():
    """Test AWSCredentials class with our fixes"""
    print("\n=== Testing AWSCredentials class ===")
    
    # Test environment validator
    creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        environment="com"
    )
    assert isinstance(creds.environment, AWSEnvironment)
    assert creds.environment == AWSEnvironment.COM
    print("✓ Environment validator works correctly")
    
    # Test expiration validator with float
    creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        environment="com",
        expiration=1234567890.5
    )
    assert isinstance(creds.expiration, int)
    assert creds.expiration == 1234567890
    print("✓ Expiration float-to-int conversion works correctly")
    
    # Test with None expiration
    creds = AWSCredentials(
        access_key="test_key",
        secret_key="test_secret",
        environment="com",
        expiration=None
    )
    assert creds.expiration is None
    print("✓ None expiration handling works correctly")
    
    print("All AWSCredentials tests passed!\n")

def test_check_expiry():
    """Test _check_expiry method with our fixes"""
    print("\n=== Testing _check_expiry method ===")
    manager = CredentialManager()
    
    # Test with no credentials
    assert manager._check_expiry(None) is True
    print("✓ Handles None credentials correctly")
    
    # Test with None expiration
    none_expiry_creds = AWSCredentials(
        access_key="test",
        secret_key="test",
        session_token="test",
        expiration=None,
        environment="gov"
    )
    assert manager._check_expiry(none_expiry_creds) is False
    print("✓ Handles None expiration correctly")
    
    # Test with valid credentials
    valid_creds = AWSCredentials(
        access_key="test",
        secret_key="test",
        session_token="test",
        expiration=time.time() + 3600,
        environment="gov"
    )
    assert manager._check_expiry(valid_creds) is False
    print("✓ Handles valid credentials correctly")
    
    # Test with expired credentials
    expired_creds = AWSCredentials(
        access_key="test",
        secret_key="test",
        session_token="test",
        expiration=time.time() - 100,
        environment="gov"
    )
    assert manager._check_expiry(expired_creds) is True
    print("✓ Handles expired credentials correctly")
    
    print("All _check_expiry tests passed!\n")

if __name__ == "__main__":
    try:
        test_aws_credentials()
        test_check_expiry()
        print("✅ All tests passed successfully!")
        sys.exit(0)
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        sys.exit(1)
