"""
Simplified tests for the AWS Execution State Manager
"""
import unittest
from unittest.mock import MagicMock, patch
import time
import json
import boto3
from datetime import datetime, timedelta

from backend.providers.aws.script_runner.services.execution_state_manager import (
    AWSExecutionStateManager, 
    ExecutionState, 
    ExecutionStep,
    ExecutionStatus
)

class TestExecutionStateManagerSimplified(unittest.TestCase):
    """Simplified test cases for AWSExecutionStateManager focusing on practical usage"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock credential manager
        self.mock_credential_manager = MagicMock()
        
        # Create execution state manager
        self.manager = AWSExecutionStateManager(self.mock_credential_manager)
        
        # Test parameters
        self.test_env = "com"
        self.test_steps = [
            {"name": "step1"},
            {"name": "step2"},
            {"name": "step3"}
        ]
        self.test_params = {
            "account_ids": ["123456789012", "234567890123"],
            "regions": ["us-east-1", "us-west-2"]
        }
    
    def test_execution_lifecycle(self):
        """Test the complete lifecycle of an execution including credential expiration and resumption"""
        # Credentials start as valid
        self.mock_credential_manager.are_credentials_valid.return_value = True
        
        # 1. Create execution
        execution_id = self.manager.create_execution(
            execution_type="account_scan",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        
        # 2. Start execution
        self.manager.start_execution(execution_id)
        
        # Verify execution is running
        execution = self.manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.RUNNING)
        self.assertEqual(execution["steps"][0]["status"], "running")
        
        # 3. Complete first step
        self.manager.complete_step(execution_id, {"step1_result": "success"})
        
        # Verify second step is running
        execution = self.manager.get_execution(execution_id)
        self.assertEqual(execution["current_step_idx"], 1)
        self.assertEqual(execution["steps"][1]["status"], "running")
        
        # 4. Credentials become invalid
        self.mock_credential_manager.are_credentials_valid.return_value = False
        
        # 5. Force credential check (bypass throttling)
        state = self.manager._executions[execution_id]
        state.credential_check_time = time.time() - 600  # 10 minutes ago
        
        # 6. Check credentials
        valid = self.manager.check_credentials(execution_id)
        
        # Verify credentials are invalid
        self.assertFalse(valid)
        
        # Verify execution is paused
        execution = self.manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.CREDENTIALS_EXPIRED)
        self.assertEqual(execution["steps"][1]["status"], "paused")
        
        # 7. Credentials become valid again
        self.mock_credential_manager.are_credentials_valid.return_value = True
        
        # 8. Resume execution
        resumed = self.manager.resume_execution(execution_id)
        
        # Verify execution was resumed
        self.assertTrue(resumed)
        
        # Verify execution is running again
        execution = self.manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.RUNNING)
        self.assertEqual(execution["steps"][1]["status"], "running")
        
        # 9. Complete remaining steps
        self.manager.complete_step(execution_id, {"step2_result": "success"})
        self.manager.complete_step(execution_id, {"step3_result": "success"})
        
        # Verify execution is completed
        execution = self.manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.COMPLETED)
        self.assertEqual(execution["steps"][0]["status"], "completed")
        self.assertEqual(execution["steps"][1]["status"], "completed")
        self.assertEqual(execution["steps"][2]["status"], "completed")
        
        # Verify results were stored
        self.assertEqual(execution["results"]["step1"], {"step1_result": "success"})
        self.assertEqual(execution["results"]["step2"], {"step2_result": "success"})
        self.assertEqual(execution["results"]["step3"], {"step3_result": "success"})
    
    def test_throttled_credential_checks_simple(self):
        """Simplified test for credential check throttling behavior using direct manipulation"""
        # Let's test the throttling behavior by directly manipulating the execution state
        # instead of patching time.time
        
        # Create and start execution
        execution_id = self.manager.create_execution(
            execution_type="test_type",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        self.manager.start_execution(execution_id)
        
        # Get direct access to the execution state
        execution_state = self.manager._executions[execution_id]
        
        # Get current time
        current_time = time.time()
        
        # Explicitly set the credential check time to now
        execution_state.credential_check_time = current_time
        
        # Clear any previous calls to credential manager
        self.mock_credential_manager.reset_mock()
        
        # First test: Within throttling window
        # Execution state shows credential check was just done
        execution_state.credential_check_time = current_time
        
        # When we check credentials within throttle window, the manager should
        # return True without calling the credential manager
        result = self.manager.check_credentials(execution_id)
        self.assertTrue(result)
        self.assertEqual(self.mock_credential_manager.are_credentials_valid.call_count, 0,
                         "Should not call credential manager within throttle window")
        
        # Second test: Outside throttling window
        # Set credential check time to more than 5 minutes ago
        execution_state.credential_check_time = current_time - 301  # 5 minutes + 1 second ago
        
        # Reset the mock
        self.mock_credential_manager.reset_mock()
        
        # This time, the manager should call the credential manager
        result = self.manager.check_credentials(execution_id)
        self.assertTrue(result)
        self.assertEqual(self.mock_credential_manager.are_credentials_valid.call_count, 1,
                         "Should call credential manager outside throttle window")
        
        # Third test: Test that throttling works again after a check
        # After the previous check, the credential_check_time should be updated
        self.assertGreater(execution_state.credential_check_time, current_time - 301,
                           "Check time should be updated after check")
        
        # Reset the mock
        self.mock_credential_manager.reset_mock()
        
        # And now checking again should not call the credential manager
        result = self.manager.check_credentials(execution_id)
        self.assertTrue(result)
        self.assertEqual(self.mock_credential_manager.are_credentials_valid.call_count, 0,
                         "Should not call credential manager after recent check")

if __name__ == "__main__":
    unittest.main()
