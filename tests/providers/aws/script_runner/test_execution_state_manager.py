"""
Unit tests for the AWS Execution State Manager
"""
import unittest
from unittest.mock import MagicMock, patch
import time
from datetime import datetime, timedelta
import json

from backend.providers.aws.script_runner.services.execution_state_manager import (
    AWSExecutionStateManager, 
    ExecutionState, 
    ExecutionStep,
    ExecutionStatus
)

class TestAWSExecutionStateManager(unittest.TestCase):
    """Test cases for AWSExecutionStateManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock credential manager
        self.mock_credential_manager = MagicMock()
        
        # By default, credentials are valid
        self.mock_credential_manager.are_credentials_valid.return_value = True
        
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
    
    def test_create_execution(self):
        """Test creating a new execution"""
        # Create execution
        execution_id = self.manager.create_execution(
            execution_type="test_type",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        
        # Verify execution ID format (UUID)
        self.assertIsNotNone(execution_id)
        self.assertEqual(len(execution_id), 36)  # UUID4 length
        
        # Get execution
        execution = self.manager.get_execution(execution_id)
        
        # Verify execution details
        self.assertEqual(execution["execution_type"], "test_type")
        self.assertEqual(execution["environment"], self.test_env)
        self.assertEqual(execution["status"], ExecutionStatus.PENDING)
        self.assertEqual(len(execution["steps"]), 3)
        self.assertEqual(execution["current_step_idx"], 0)
        
        # Verify steps
        for i, step in enumerate(execution["steps"]):
            self.assertEqual(step["name"], f"step{i+1}")
            self.assertEqual(step["status"], "pending")
    
    def test_create_execution_invalid_credentials(self):
        """Test creating an execution with invalid credentials"""
        # Set credentials as invalid
        self.mock_credential_manager.are_credentials_valid.return_value = False
        
        # Attempt to create execution, should raise ValueError
        with self.assertRaises(ValueError):
            self.manager.create_execution(
                execution_type="test_type",
                environment=self.test_env,
                params=self.test_params,
                steps=self.test_steps
            )
    
    def test_start_execution(self):
        """Test starting an execution"""
        # Create execution
        execution_id = self.manager.create_execution(
            execution_type="test_type",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        
        # Start execution
        result = self.manager.start_execution(execution_id)
        
        # Verify result
        self.assertTrue(result)
        
        # Get execution
        execution = self.manager.get_execution(execution_id)
        
        # Verify status
        self.assertEqual(execution["status"], ExecutionStatus.RUNNING)
        
        # Verify first step is running
        self.assertEqual(execution["steps"][0]["status"], "running")
        self.assertIsNotNone(execution["steps"][0]["started_at"])
    
    def test_start_execution_invalid_id(self):
        """Test starting an execution with an invalid ID"""
        # Attempt to start execution with invalid ID
        result = self.manager.start_execution("invalid-id")
        
        # Verify result
        self.assertFalse(result)
    
    def test_start_execution_invalid_credentials(self):
        """Test starting an execution with invalid credentials"""
        # Create execution
        execution_id = self.manager.create_execution(
            execution_type="test_type",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        
        # Set credentials as invalid
        self.mock_credential_manager.are_credentials_valid.return_value = False
        
        # Attempt to start execution
        result = self.manager.start_execution(execution_id)
        
        # Verify result
        self.assertFalse(result)
        
        # Get execution
        execution = self.manager.get_execution(execution_id)
        
        # Verify status
        self.assertEqual(execution["status"], ExecutionStatus.CREDENTIALS_EXPIRED)
    
    def test_check_credentials(self):
        """Test checking credentials during execution"""
        # Create and start execution
        execution_id = self.manager.create_execution(
            execution_type="test_type",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        self.manager.start_execution(execution_id)
        
        # Check credentials, should be valid
        result = self.manager.check_credentials(execution_id)
        self.assertTrue(result)
        
        # Get execution to verify state
        execution = self.manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.RUNNING)
        
        # Set credentials as invalid
        self.mock_credential_manager.are_credentials_valid.return_value = False
        
        # Modify credential check time to force check
        execution_state = self.manager._executions[execution_id]
        execution_state.credential_check_time = time.time() - 600  # 10 minutes ago
        
        # Check credentials again, should be invalid
        result = self.manager.check_credentials(execution_id)
        self.assertFalse(result)
        
        # Get execution to verify state
        execution = self.manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.CREDENTIALS_EXPIRED)
        
        # Verify step status
        self.assertEqual(execution["steps"][0]["status"], "paused")
    
    @patch('time.time')
    def test_credential_check_throttling(self, mock_time):
        """Test that credential checks are throttled"""
        # Set up mock time
        initial_time = 1600000000.0
        mock_time.return_value = initial_time
        
        # Skip the complex test and directly test the throttling behavior
        # Create a fresh execution state manager with mocked credential manager
        mock_cred_manager = MagicMock()
        mock_cred_manager.are_credentials_valid.return_value = True
        manager = AWSExecutionStateManager(mock_cred_manager)
        
        # Create test execution
        execution_id = manager.create_execution(
            execution_type="test_type",
            environment="com",
            params={},
            steps=[{"name": "step1"}]
        )
        
        # Start execution
        manager.start_execution(execution_id)
        
        # Reset call count after setup
        mock_cred_manager.reset_mock()
        
        # First check - should call credential manager
        result1 = manager.check_credentials(execution_id)
        self.assertTrue(result1)
        self.assertEqual(mock_cred_manager.are_credentials_valid.call_count, 1)
        
        # Immediate second check - should be throttled
        mock_cred_manager.reset_mock()
        result2 = manager.check_credentials(execution_id)
        self.assertTrue(result2)
        self.assertEqual(mock_cred_manager.are_credentials_valid.call_count, 0)
        
        # Move clock forward 6 minutes (beyond the throttle window)
        mock_time.return_value = initial_time + 360
        
        # Check again - should call credential manager again
        mock_cred_manager.reset_mock()
        result3 = manager.check_credentials(execution_id)
        self.assertTrue(result3)
        self.assertEqual(mock_cred_manager.are_credentials_valid.call_count, 1)
    
    def test_resume_execution(self):
        """Test resuming an execution after credentials expire"""
        # Create and start execution
        execution_id = self.manager.create_execution(
            execution_type="test_type",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        self.manager.start_execution(execution_id)
        
        # Set credentials as invalid
        self.mock_credential_manager.are_credentials_valid.return_value = False
        
        # Modify credential check time to force check
        execution_state = self.manager._executions[execution_id]
        execution_state.credential_check_time = time.time() - 600  # 10 minutes ago
        
        # Check credentials to mark as expired
        self.manager.check_credentials(execution_id)
        
        # Verify status
        execution = self.manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.CREDENTIALS_EXPIRED)
        
        # Set credentials as valid again
        self.mock_credential_manager.are_credentials_valid.return_value = True
        
        # Resume execution
        result = self.manager.resume_execution(execution_id)
        
        # Verify result
        self.assertTrue(result)
        
        # Get execution to verify state
        execution = self.manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.RUNNING)
        
        # Verify step status
        self.assertEqual(execution["steps"][0]["status"], "running")
    
    def test_resume_execution_invalid_id(self):
        """Test resuming an execution with an invalid ID"""
        # Attempt to resume execution with invalid ID
        result = self.manager.resume_execution("invalid-id")
        
        # Verify result
        self.assertFalse(result)
    
    def test_resume_execution_wrong_state(self):
        """Test resuming an execution that is not in CREDENTIALS_EXPIRED state"""
        # Create and start execution
        execution_id = self.manager.create_execution(
            execution_type="test_type",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        self.manager.start_execution(execution_id)
        
        # Attempt to resume a running execution
        result = self.manager.resume_execution(execution_id)
        
        # Verify result
        self.assertFalse(result)
    
    def test_resume_execution_invalid_credentials(self):
        """Test resuming an execution with invalid credentials"""
        # Create and start execution
        execution_id = self.manager.create_execution(
            execution_type="test_type",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        self.manager.start_execution(execution_id)
        
        # Set credentials as invalid
        self.mock_credential_manager.are_credentials_valid.return_value = False
        
        # Modify credential check time to force check
        execution_state = self.manager._executions[execution_id]
        execution_state.credential_check_time = time.time() - 600  # 10 minutes ago
        
        # Check credentials to mark as expired
        self.manager.check_credentials(execution_id)
        
        # Attempt to resume with still-invalid credentials
        result = self.manager.resume_execution(execution_id)
        
        # Verify result
        self.assertFalse(result)
        
        # Get execution to verify state
        execution = self.manager.get_execution(execution_id)
        self.assertEqual(execution["status"], ExecutionStatus.CREDENTIALS_EXPIRED)
    
    def test_complete_step(self):
        """Test completing a step in an execution"""
        # Create and start execution
        execution_id = self.manager.create_execution(
            execution_type="test_type",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        self.manager.start_execution(execution_id)
        
        # Complete first step
        result = self.manager.complete_step(execution_id, {"result_key": "result_value"})
        
        # Verify result (more steps remaining)
        self.assertTrue(result)
        
        # Get execution to verify state
        execution = self.manager.get_execution(execution_id)
        
        # Verify step status
        self.assertEqual(execution["steps"][0]["status"], "completed")
        self.assertIsNotNone(execution["steps"][0]["completed_at"])
        self.assertEqual(execution["steps"][0]["result"], {"result_key": "result_value"})
        
        # Verify current step index
        self.assertEqual(execution["current_step_idx"], 1)
        
        # Verify next step is running
        self.assertEqual(execution["steps"][1]["status"], "running")
        self.assertIsNotNone(execution["steps"][1]["started_at"])
        
        # Complete second step
        self.manager.complete_step(execution_id, {"step2_result": "value2"})
        
        # Complete final step
        result = self.manager.complete_step(execution_id, {"final_result": "done"})
        
        # Verify result (no more steps)
        self.assertFalse(result)
        
        # Get execution to verify state
        execution = self.manager.get_execution(execution_id)
        
        # Verify execution is completed
        self.assertEqual(execution["status"], ExecutionStatus.COMPLETED)
        
        # Verify results are stored
        self.assertEqual(execution["results"]["step1"], {"result_key": "result_value"})
        self.assertEqual(execution["results"]["step2"], {"step2_result": "value2"})
        self.assertEqual(execution["results"]["step3"], {"final_result": "done"})
    
    def test_complete_step_invalid_id(self):
        """Test completing a step with an invalid execution ID"""
        # Attempt to complete step with invalid ID
        result = self.manager.complete_step("invalid-id")
        
        # Verify result
        self.assertFalse(result)
    
    def test_complete_step_wrong_state(self):
        """Test completing a step when execution is not in RUNNING state"""
        # Create execution (PENDING state)
        execution_id = self.manager.create_execution(
            execution_type="test_type",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        
        # Attempt to complete step
        result = self.manager.complete_step(execution_id)
        
        # Verify result
        self.assertFalse(result)
    
    def test_fail_step(self):
        """Test failing a step in an execution"""
        # Create and start execution
        execution_id = self.manager.create_execution(
            execution_type="test_type",
            environment=self.test_env,
            params=self.test_params,
            steps=self.test_steps
        )
        self.manager.start_execution(execution_id)
        
        # Fail the step
        self.manager.fail_step(execution_id, "Test error message")
        
        # Get execution to verify state
        execution = self.manager.get_execution(execution_id)
        
        # Verify execution is failed
        self.assertEqual(execution["status"], ExecutionStatus.FAILED)
        
        # Verify step status
        self.assertEqual(execution["steps"][0]["status"], "failed")
        self.assertEqual(execution["steps"][0]["error"], "Test error message")
    
    def test_fail_step_invalid_id(self):
        """Test failing a step with an invalid execution ID"""
        # Attempt to fail step with invalid ID (should not raise exception)
        try:
            self.manager.fail_step("invalid-id", "Test error")
            # If we get here, no exception was raised
            self.assertTrue(True)
        except Exception:
            self.fail("fail_step raised exception with invalid ID")
    
    def test_list_executions(self):
        """Test listing executions"""
        # Create several executions with different statuses
        execution1 = self.manager.create_execution(
            execution_type="type1",
            environment="com",
            params={"param1": "value1"},
            steps=[{"name": "step1"}]
        )
        self.manager.start_execution(execution1)
        
        execution2 = self.manager.create_execution(
            execution_type="type2",
            environment="gov",
            params={"param2": "value2"},
            steps=[{"name": "step2"}]
        )
        
        execution3 = self.manager.create_execution(
            execution_type="type1",
            environment="com",
            params={"param3": "value3"},
            steps=[{"name": "step3"}]
        )
        self.manager.start_execution(execution3)
        self.manager.complete_step(execution3)
        
        # List all executions
        executions = self.manager.list_executions()
        
        # Verify all executions are listed
        self.assertEqual(len(executions), 3)
        
        # List running executions
        running_executions = self.manager.list_executions(status=ExecutionStatus.RUNNING)
        
        # Verify only running executions are listed
        self.assertEqual(len(running_executions), 1)
        self.assertEqual(running_executions[0]["id"], execution1)
        
        # List pending executions
        pending_executions = self.manager.list_executions(status=ExecutionStatus.PENDING)
        
        # Verify only pending executions are listed
        self.assertEqual(len(pending_executions), 1)
        self.assertEqual(pending_executions[0]["id"], execution2)
        
        # List completed executions
        completed_executions = self.manager.list_executions(status=ExecutionStatus.COMPLETED)
        
        # Verify only completed executions are listed
        self.assertEqual(len(completed_executions), 1)
        self.assertEqual(completed_executions[0]["id"], execution3)

if __name__ == "__main__":
    unittest.main()
