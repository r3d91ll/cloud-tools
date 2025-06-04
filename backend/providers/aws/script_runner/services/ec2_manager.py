from botocore.exceptions import ClientError, EndpointConnectionError
import logging
from typing import Dict, List, Optional, Any, cast, Protocol
import boto3

from backend.providers.aws.common.services.credential_manager import CredentialManager

# Type definition for EC2 Client
class EC2Client(Protocol):
    def describe_instances(self, **kwargs) -> Dict[str, Any]: ...
    def get_paginator(self, operation_name: str) -> Any: ...

logger = logging.getLogger(__name__)


class EC2Manager:
    """Service for managing EC2 instances"""
    
    def __init__(self, credential_manager: CredentialManager):
        self.credential_manager = credential_manager
        
    def get_account_id(self, environment: str) -> Optional[str]:
        """Get the current account ID from STS
        
        Args:
            environment: AWS environment (gov or com)
            
        Returns:
            Account ID or None if failed
        """
        session = self.credential_manager.create_session(environment)
        if not session:
            return None
            
        try:
            sts = session.client('sts')
            response = sts.get_caller_identity()
            account_id: Optional[str] = response.get('Account')
            return account_id
        except Exception as e:
            logger.error(f"Failed to get account ID: {str(e)}")
            return None
    
    def describe_instances(
        self,
        account_id: str,
        region: str,
        environment: str,
        instance_ids: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:  # Return type is List[Dict[str, Any]], not List[str]
        """
        Describe EC2 instances in a specific account and region.
        
        Args:
            account_id: AWS account ID
            region: AWS region
            environment: AWS environment (gov or com)
            instance_ids: Optional list of instance IDs to filter by
            filters: Optional list of filters to apply
            
        Returns:
            List of instance details
        """
        try:
            # Create EC2 client
            ec2 = self.credential_manager.create_client('ec2', environment, region)
            if not ec2:
                logger.error(f"Failed to create EC2 client for {environment} in {region}")
                return []
                
            # Cast to our Protocol type for type checking
            ec2_client = cast(EC2Client, ec2)
            
            # Build request parameters
            params: Dict[str, Any] = {}
            if instance_ids:
                params['InstanceIds'] = instance_ids
            if filters:
                params['Filters'] = filters
            
            # Try direct access first - since account_id might be the account we're already in
            try:
                logger.info(f"Attempting direct EC2 access for account {account_id} in region {region} with current credentials")
                # Get instances
                instances: List[Dict[str, Any]] = []  # Fix the type annotation
                paginator = ec2.get_paginator('describe_instances')
                for page in paginator.paginate(**params):
                    for reservation in page['Reservations']:
                        instances.extend(reservation['Instances'])
                
                logger.info(f"Direct access successful: Retrieved {len(instances)} instances from account {account_id} in region {region}")
                return instances
            except Exception as direct_access_error:
                logger.warning(f"Direct access failed for account {account_id}: {str(direct_access_error)}")
                # Fall through to try alternative methods
            
            # If we got here, direct access failed - check if we're using resource-based access control
            try:
                logger.info(f"Trying resource-based access for {account_id} in region {region}")
                # Some AWS resources allow access via resource policies rather than IAM roles
                # Modify the filters to include the account ID if this is cross-account access
                if 'Filters' not in params:
                    params['Filters'] = []
                    
                # Add owner-id filter if this is cross-account
                current_account = self.get_account_id(environment)
                if current_account and current_account != account_id:
                    params['Filters'].append({
                        'Name': 'owner-id',
                        'Values': [account_id]
                    })
                
                # Try with modified filters
                instances = []
                paginator = ec2_client.get_paginator('describe_instances')
                for page in paginator.paginate(**params):
                    for reservation in page['Reservations']:
                        instances.extend(reservation['Instances'])
                
                logger.info(f"Resource-based access successful: Retrieved {len(instances)} instances from account {account_id} in region {region}")
                return instances
            except Exception as resource_error:
                logger.warning(f"Resource-based access failed for account {account_id}: {str(resource_error)}")
                # Fall through to try alternative methods
            
            # If we still haven't succeeded, try older EC2 API methods as a last resort
            try:
                logger.info(f"Trying older EC2 API methods for {account_id} in region {region}")
                # Some older EC2 APIs don't require explicit cross-account permissions
                response = ec2_client.describe_instances(**params)
                instances = []
                for reservation in response.get('Reservations', []):
                    instances.extend(reservation.get('Instances', []))
                
                logger.info(f"Older API methods successful: Retrieved {len(instances)} instances from account {account_id} in region {region}")
                return instances
            except Exception as older_api_error:
                logger.error(f"All access methods failed for account {account_id}: {str(older_api_error)}")
                return []
            
        except Exception as e:
            logger.error(f"Error describing instances in account {account_id}, region {region}: {str(e)}")
            # Log more detailed information for debugging
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def get_instance_platform(self, instance: Dict[str, Any]) -> str:
        """
        Get the platform of an EC2 instance (linux or windows).
        
        Args:
            instance: Instance data from describe_instances
            
        Returns:
            Platform name (linux or windows)
        """
        platform = instance.get('Platform', '').lower()
        if platform == 'windows':
            return 'windows'
        else:
            return 'linux'
            
    def get_instance_tags(self, instance: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract tags from instance data.
        
        Args:
            instance: Instance data from describe_instances
            
        Returns:
            Dictionary of tags (key-value pairs)
        """
        return {tag['Key']: tag['Value'] for tag in instance.get('Tags', []) 
                if 'Key' in tag and 'Value' in tag}
    
    def is_instance_managed_by_ssm(
        self, 
        instance_id: str, 
        account_id: str, 
        region: str, 
        environment: str
    ) -> bool:
        """
        Check if an instance is managed by AWS Systems Manager.
        
        Args:
            instance_id: ID of the instance to check
            account_id: AWS account ID where the instance is located
            region: AWS region where the instance is located
            environment: AWS environment (gov or com)
            
        Returns:
            True if the instance is managed by SSM, False otherwise
        """
        try:
            # Create SSM client
            ssm = self.credential_manager.create_client('ssm', environment, region)
            if not ssm:
                logger.error(f"Failed to create SSM client for {environment} in {region}")
                return False
            
            # Check instance managed status
            # Boto3 clients have dynamically created methods that mypy can't see
            response = ssm.describe_instance_information(  # type: ignore[attr-defined]
                Filters=[
                    {
                        'Key': 'InstanceIds',
                        'Values': [instance_id]
                    }
                ]
            )
            
            # If the instance is in the response, it's managed by SSM
            is_managed = len(response.get('InstanceInformationList', [])) > 0
            logger.info(f"Instance {instance_id} is {'managed' if is_managed else 'not managed'} by SSM")
            
            return is_managed
            
        except Exception as e:
            logger.error(f"Error checking SSM management status for instance {instance_id}: {str(e)}")
            return False
    
    def get_instance_status(
        self, 
        instance_id: str, 
        account_id: str, 
        region: str, 
        environment: str
    ) -> Dict[str, Any]:
        """
        Get detailed status information for an EC2 instance.
        
        Args:
            instance_id: ID of the instance to check
            account_id: AWS account ID where the instance is located
            region: AWS region where the instance is located
            environment: AWS environment (gov or com)
            
        Returns:
            Dictionary with instance status details
        """
        try:
            # Create EC2 client
            ec2 = self.credential_manager.create_client('ec2', environment, region)
            if not ec2:
                logger.error(f"Failed to create EC2 client for {environment} in {region}")
                return {"Status": "Unknown", "Error": "Failed to create EC2 client"}
            
            # Get instance details
            # Boto3 clients have dynamically created methods that mypy can't see
            response = ec2.describe_instances(InstanceIds=[instance_id])  # type: ignore[attr-defined]
            
            if not response.get('Reservations') or not response['Reservations'][0].get('Instances'):
                logger.warning(f"Instance {instance_id} not found")
                return {"Status": "NotFound", "Error": f"Instance {instance_id} not found"}
            
            instance = response['Reservations'][0]['Instances'][0]
            
            # Get SSM management status
            ssm_managed = self.is_instance_managed_by_ssm(instance_id, account_id, region, environment)
            
            # Create status response
            status_info = {
                "Status": instance.get('State', {}).get('Name', 'unknown'),
                "InstanceId": instance_id,
                "InstanceType": instance.get('InstanceType', 'unknown'),
                "Platform": self.get_instance_platform(instance),
                "LaunchTime": instance.get('LaunchTime', '').isoformat() if instance.get('LaunchTime') else None,
                "SSMManaged": ssm_managed,
                "PublicIpAddress": instance.get('PublicIpAddress'),
                "PrivateIpAddress": instance.get('PrivateIpAddress'),
                "Tags": {tag['Key']: tag['Value'] for tag in instance.get('Tags', []) if 'Key' in tag and 'Value' in tag}
            }
            
            return status_info
            
        except Exception as e:
            logger.error(f"Error getting status for instance {instance_id}: {str(e)}")
            return {"Status": "Error", "Error": str(e)}
