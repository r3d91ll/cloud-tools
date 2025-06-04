import boto3
from botocore.exceptions import ClientError
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
import json

from backend.providers.aws.common.services.credential_manager import CredentialManager

logger = logging.getLogger(__name__)


class SSMExecutor:
    """Service for executing commands via AWS Systems Manager (SSM)"""
    
    def __init__(self, credential_manager: CredentialManager):
        self.credential_manager = credential_manager
    
    def send_command(
        self,
        instance_id: str,
        command: str,
        account_id: str,
        region: str,
        environment: str,
        comment: str = "",
        timeout_seconds: int = 3600,
        parameters: Optional[Dict[str, List[str]]] = None
    ) -> Optional[str]:
        """
        Send a command to an EC2 instance using SSM.
        
        Args:
            instance_id: EC2 instance ID
            command: Command content to execute
            account_id: AWS account ID
            region: AWS region
            environment: AWS environment (gov or com)
            comment: Optional comment for the command
            timeout_seconds: Command timeout in seconds
            parameters: Optional parameters for the command
            
        Returns:
            Command ID if successful, None otherwise
        """
        try:
            # Create SSM client
            ssm = self.credential_manager.create_client('ssm', environment, region)
            if not ssm:
                logger.error(f"Failed to create SSM client for {environment} in {region}")
                return None
            
            # Build command document
            document_name = "AWS-RunShellScript" if not command.startswith("powershell") else "AWS-RunPowerShellScript"
            cmd_parameters = parameters or {}
            
            # If no custom parameters provided, set the default Commands parameter
            if "Commands" not in cmd_parameters:
                cmd_parameters["Commands"] = [command]
            
            logger.info(f"Sending command to instance {instance_id} in account {account_id}, region {region}")
            
            # Send the command - boto3 clients have dynamically generated methods
            # that mypy can't statically verify
            response = ssm.send_command(  # type: ignore[attr-defined]
                InstanceIds=[instance_id],
                DocumentName=document_name,
                Comment=comment,
                TimeoutSeconds=timeout_seconds,
                Parameters=cmd_parameters
            )
            
            # Extract command ID and ensure it's a string for type safety
            command_id = str(response['Command']['CommandId'])
            logger.info(f"Successfully sent command. Command ID: {command_id}")
            return command_id
            
        except Exception as e:
            logger.error(f"Error sending command to instance {instance_id}: {str(e)}")
            return None
    
    def get_command_status(
        self,
        command_id: str,
        instance_id: str,
        account_id: str,
        region: str,
        environment: str
    ) -> Dict[str, Any]:
        """
        Get the status of a command execution.
        
        Args:
            command_id: SSM command ID
            instance_id: EC2 instance ID
            account_id: AWS account ID
            region: AWS region
            environment: AWS environment (gov or com)
            
        Returns:
            Dictionary with command status information
        """
        try:
            # Create SSM client
            ssm = self.credential_manager.create_client('ssm', environment, region)
            if not ssm:
                logger.error(f"Failed to create SSM client for {environment} in {region}")
                return {"Status": "Failed", "Error": "Failed to create SSM client"}
            
            # Get command invocation details - boto3 clients have dynamically generated methods
            # that mypy can't statically verify
            response = ssm.get_command_invocation(  # type: ignore[attr-defined]
                CommandId=command_id,
                InstanceId=instance_id
            )
            
            status = response.get('Status', 'Unknown')
            logger.info(f"Command {command_id} status: {status}")
            
            return {
                "CommandId": command_id,
                "InstanceId": instance_id,
                "Status": status,
                "StatusDetails": response.get('StatusDetails', ''),
                "Output": response.get('StandardOutputContent', ''),
                "Error": response.get('StandardErrorContent', ''),
                "ExitCode": response.get('ResponseCode', -1)
            }
            
        except Exception as e:
            logger.error(f"Error getting command status for command {command_id}: {str(e)}")
            return {
                "CommandId": command_id,
                "InstanceId": instance_id,
                "Status": "Failed",
                "StatusDetails": str(e),
                "Output": "",
                "Error": str(e),
                "ExitCode": -1
            }
    
    def wait_for_command_completion(
        self,
        command_id: str,
        instance_id: str,
        account_id: str,
        region: str,
        environment: str,
        timeout_seconds: int = 3600,
        poll_interval_seconds: int = 5
    ) -> Dict[str, Any]:
        """
        Wait for a command to complete and return its status.
        
        Args:
            command_id: SSM command ID
            instance_id: EC2 instance ID
            account_id: AWS account ID
            region: AWS region
            environment: AWS environment (gov or com)
            timeout_seconds: Maximum time to wait for completion
            poll_interval_seconds: Time between status checks
            
        Returns:
            Dictionary with final command status
        """
        terminal_states = ["Success", "Failed", "Cancelled", "TimedOut", "Cancelling"]
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            status = self.get_command_status(command_id, instance_id, account_id, region, environment)
            
            if status["Status"] in terminal_states:
                logger.info(f"Command {command_id} completed with status: {status['Status']}")
                return status
            
            logger.debug(f"Command {command_id} still running. Status: {status['Status']}")
            time.sleep(poll_interval_seconds)
        
        logger.warning(f"Timeout waiting for command {command_id} to complete")
        return {
            "CommandId": command_id,
            "InstanceId": instance_id,
            "Status": "TimedOut",
            "StatusDetails": "Timed out waiting for command completion",
            "Output": "",
            "Error": "Command execution timed out",
            "ExitCode": -1
        }
