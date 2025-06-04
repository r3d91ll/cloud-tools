"""Integration test for credential management"""
import os
import sys
import unittest
import json
from datetime import datetime
from unittest.mock import patch

# Add the parent directory to the path so we can import the utils module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from tests.integration.utils.credential_manager import CredentialManager, DEFAULT_CREDS_PATH, DEFAULT_NEW_CREDS_PATH

class TestCredentialManagement(unittest.TestCase):
    """Test the credential management functionality"""

    @patch('boto3.client')
    def test_credential_loading(self, mock_boto_client):
        """Test that credentials are loaded correctly"""
        # Mock the AWS STS client
        mock_sts = mock_boto_client.return_value
        mock_sts.get_caller_identity.return_value = {
            'UserId': 'AIDATEST123456789',
            'Account': '123456789012',
            'Arn': 'arn:aws:iam::123456789012:user/test-user'
        }
        
        # Create a temporary credential file for testing
        test_creds_path = os.path.join(os.path.dirname(__file__), 'test_creds.json')
        test_output_path = os.path.join(os.path.dirname(__file__), 'test_output.json')
        
        try:
            # Create test credentials
            with open(test_creds_path, 'w') as f:
                json.dump({
                    'aws_access_key_id': 'AKIATEST123456789',
                    'aws_secret_access_key': 'test_secret_key',
                    'region': 'us-west-2'
                }, f)
            
            # Initialize credential manager with test credentials
            manager = CredentialManager(test_creds_path)
            
            # Test loading credentials
            creds = manager.load_credentials()
            self.assertEqual(creds['aws_access_key_id'], 'AKIATEST123456789')
            self.assertEqual(creds['aws_secret_access_key'], 'test_secret_key')
            
            # Test getting temporary credentials
            temp_creds = manager.get_temporary_credentials()
            self.assertEqual(temp_creds['aws_access_key_id'], 'AKIATEST123456789')
            self.assertEqual(temp_creds['aws_secret_access_key'], 'test_secret_key')
            self.assertEqual(temp_creds['account_id'], '123456789012')
            self.assertEqual(temp_creds['user_arn'], 'arn:aws:iam::123456789012:user/test-user')
            
            # Test saving temporary credentials
            output_path = manager.save_temporary_credentials(test_output_path)
            self.assertEqual(output_path, test_output_path)
            self.assertTrue(os.path.exists(test_output_path))
            
            # Verify the saved credentials
            with open(test_output_path, 'r') as f:
                saved_creds = json.load(f)
            
            self.assertEqual(saved_creds['aws_access_key_id'], 'AKIATEST123456789')
            self.assertEqual(saved_creds['aws_secret_access_key'], 'test_secret_key')
            
        finally:
            # Clean up test files
            if os.path.exists(test_creds_path):
                os.remove(test_creds_path)
            if os.path.exists(test_output_path):
                os.remove(test_output_path)

    @patch('boto3.client')
    def test_role_assumption(self, mock_boto_client):
        """Test role assumption with temporary credentials"""
        # Mock the AWS STS client for role assumption
        mock_sts = mock_boto_client.return_value
        expiration = datetime.now()
        mock_sts.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': 'ASTATEST123456789',
                'SecretAccessKey': 'assumed_secret_key',
                'SessionToken': 'assumed_session_token',
                'Expiration': expiration
            },
            'AssumedRoleUser': {
                'AssumedRoleId': 'AROATEST123456789:session',
                'Arn': 'arn:aws:sts::123456789012:assumed-role/TestRole/session'
            }
        }
        
        # Create a temporary credential file for testing
        test_creds_path = os.path.join(os.path.dirname(__file__), 'test_creds.json')
        test_output_path = os.path.join(os.path.dirname(__file__), 'test_output.json')
        
        try:
            # Create test credentials
            with open(test_creds_path, 'w') as f:
                json.dump({
                    'aws_access_key_id': 'AKIATEST123456789',
                    'aws_secret_access_key': 'test_secret_key',
                    'region': 'us-west-2'
                }, f)
            
            # Initialize credential manager with test credentials
            manager = CredentialManager(test_creds_path)
            manager.load_credentials()
            
            # Test role assumption
            role_arn = 'arn:aws:iam::123456789012:role/TestRole'
            temp_creds = manager.get_temporary_credentials(role_arn=role_arn)
            
            # Verify temporary credentials
            self.assertEqual(temp_creds['aws_access_key_id'], 'ASTATEST123456789')
            self.assertEqual(temp_creds['aws_secret_access_key'], 'assumed_secret_key')
            self.assertEqual(temp_creds['aws_session_token'], 'assumed_session_token')
            self.assertEqual(temp_creds['role_arn'], role_arn)
            
            # Verify AWS STS client was called correctly
            mock_sts.assume_role.assert_called_once_with(
                RoleArn=role_arn,
                RoleSessionName='IntegrationTest',
                DurationSeconds=3600
            )
            
        finally:
            # Clean up test files
            if os.path.exists(test_creds_path):
                os.remove(test_creds_path)
            if os.path.exists(test_output_path):
                os.remove(test_output_path)

    def test_real_credential_file_path(self):
        """Test that the default credential paths are correct"""
        # Verify the default credential path exists
        self.assertTrue(DEFAULT_CREDS_PATH.endswith('test/.creds'))
        
        # Verify the default output path is set correctly
        self.assertTrue(DEFAULT_NEW_CREDS_PATH.endswith('test/.new-creds/json'))


if __name__ == '__main__':
    unittest.main()
