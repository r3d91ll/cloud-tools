"""
Mock integration tests for the AWS Execution State Manager
"""
import unittest
from unittest.mock import MagicMock, patch, call
import time
import json
import boto3
import pytest
from datetime import datetime, timedelta

from backend.providers.aws.script_runner.services.execution_state_manager import (
    AWSExecutionStateManager, 
    ExecutionState, 
    ExecutionStep,
    ExecutionStatus
)
from backend.providers.aws.common.services.credential_manager import CredentialManager
from backend.providers.aws.common.services.account_manager import AWSAccountManager
from backend.api.aws_operations import perform_account_scan_task


class MockAWSResponse:
    """Mock AWS response for testing"""
    def __init__(self, data):
        self.data = data
        
    def get(self, key, default=None):
        return self.data.get(key, default)


class TestExecutionStateManagerIntegration(unittest.TestCase):
    """Integration tests for the AWS Execution State Manager"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock credential manager with controlled behavior
        self.mock_credential_manager = MagicMock(spec=CredentialManager)
        
        # Mock credentials validation - starts valid, then expires, then valid again after refresh
        self.credential_valid_calls = 0
        
        def mock_are_credentials_valid(environment):
            if environment not in ["com", "gov"]:
                return False
                
            # First call: valid
            # Second call: invalid (expired)
            # Third call: valid again (after refresh)
            self.credential_valid_calls += 1
            if self.credential_valid_calls == 2:
                return False
            return True
            
        self.mock_credential_manager.are_credentials_valid.side_effect = mock_are_credentials_valid
        
        # Create mock account manager
        self.mock_account_manager = MagicMock(spec=AWSAccountManager)
        
        # Setup mock AWS clients and responses
        self.mock_boto3_client = MagicMock()
        
        # Mock EC2 describe_instances response
        self.mock_ec2_response = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-12345678",
                            "State": {"Name": "running"},
                            "InstanceType": "t2.micro",
                            "PrivateIpAddress": "10.0.0.1",
                            "PublicIpAddress": "54.123.45.67"
                        }
                    ]
                }
            ]
        }
        
        # Create execution state manager
        self.execution_state_manager = AWSExecutionStateManager(self.mock_credential_manager)
        
    @patch('boto3.client')
    @patch('app.services.aws.account_manager.AWSAccountManager.assume_role')
    async def test_account_scan_with_credential_expiry(self, mock_assume_role, mock_boto3_client):
        """Test account scan that encounters credential expiry and resumes"""
        # Setup mocks
        # Mock assume_role to return credentials
        mock_assume_role.return_value = {
            "AccessKeyId": "test-access-key",
            "SecretAccessKey": "test-secret-key",
            "SessionToken": "test-session-token",
            "Expiration": datetime.now() + timedelta(hours=1)
        }
        
        # Mock boto3.client to return our mock client
        mock_boto3_client.return_value = self.mock_boto3_client
        
        # Mock EC2 describe_instances
        self.mock_boto3_client.describe_instances.return_value = self.mock_ec2_response
        
        # Create test execution
        execution_id = self.execution_state_manager.create_execution(
            execution_type="account_scan",
            environment="com",
            params={
                "account_ids": ["123456789012", "234567890123"],
                "regions": ["us-east-1", "us-west-2"],
                "role_name": "OrganizationAccountAccessRole"
            },
            steps=[
                {"name": "scan_account_123456789012"},
                {"name": "scan_account_234567890123"},
                {"name": "finalize_results"}
            ]
        )
        
        # Start the background task
        # This will process the first account, then credentials will expire
        await perform_account_scan_task(execution_id)
        
        # Verify that execution is in CREDENTIALS_EXPIRED state
        execution = self.execution_state_manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.CREDENTIALS_EXPIRED)
        
        # Verify that only the first account was processed
        self.assertEqual(execution["current_step_idx"], 1)
        self.assertEqual(execution["steps"][0]["status"], "completed")
        self.assertEqual(execution["steps"][1]["status"], "paused")
        
        # Reset credential validation behavior to simulate refresh
        self.credential_valid_calls = 0
        
        # Resume the execution
        result = self.execution_state_manager.resume_execution(execution_id)
        self.assertTrue(result)
        
        # Continue the background task
        await perform_account_scan_task(execution_id)
        
        # Verify that execution completed successfully
        execution = self.execution_state_manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.COMPLETED)
        
        # Verify that all steps were processed
        self.assertEqual(execution["current_step_idx"], 3)  # Past the last step
        self.assertEqual(execution["steps"][0]["status"], "completed")
        self.assertEqual(execution["steps"][1]["status"], "completed")
        self.assertEqual(execution["steps"][2]["status"], "completed")
        
        # Verify that mock_assume_role was called for both accounts
        expected_calls = [
            call("123456789012", "us-east-1"),
            call("123456789012", "us-west-2"),
            call("234567890123", "us-east-1"),
            call("234567890123", "us-west-2")
        ]
        mock_assume_role.assert_has_calls(expected_calls, any_order=True)
        
    @patch('time.time')
    def test_credential_check_timing(self, mock_time):
        """Test credential check timing during long-running operations"""
        # Setup initial time
        initial_time = 1600000000.0  # Some fixed timestamp
        mock_time.return_value = initial_time
        
        # Create and start execution
        execution_id = self.execution_state_manager.create_execution(
            execution_type="long_operation",
            environment="com",
            params={},
            steps=[{"name": "long_step"}]
        )
        self.execution_state_manager.start_execution(execution_id)
        
        # Reset credential validation counter
        self.credential_valid_calls = 0
        
        # Initial credential check
        result = self.execution_state_manager.check_credentials(execution_id)
        self.assertTrue(result)
        self.assertEqual(self.credential_valid_calls, 1)
        
        # Check again immediately - should be throttled
        result = self.execution_state_manager.check_credentials(execution_id)
        self.assertTrue(result)
        self.assertEqual(self.credential_valid_calls, 1)  # No additional calls
        
        # Move time forward by 4 minutes (240 seconds)
        mock_time.return_value = initial_time + 240
        
        # Check again - should still be throttled
        result = self.execution_state_manager.check_credentials(execution_id)
        self.assertTrue(result)
        self.assertEqual(self.credential_valid_calls, 1)  # No additional calls
        
        # Move time forward by 6 minutes (total 10 minutes)
        mock_time.return_value = initial_time + 600
        
        # Check again - throttling should expire
        result = self.execution_state_manager.check_credentials(execution_id)
        self.assertFalse(result)  # Now credentials are invalid (2nd call)
        self.assertEqual(self.credential_valid_calls, 2)
        
        # Verify execution is paused
        execution = self.execution_state_manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.CREDENTIALS_EXPIRED)
        
        # Move time forward by 5 more minutes
        mock_time.return_value = initial_time + 900
        
        # Try to resume - credentials should be valid again (3rd call)
        result = self.execution_state_manager.resume_execution(execution_id)
        self.assertTrue(result)
        self.assertEqual(self.credential_valid_calls, 3)
        
        # Verify execution is running again
        execution = self.execution_state_manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.RUNNING)

if __name__ == "__main__":
    unittest.main()
