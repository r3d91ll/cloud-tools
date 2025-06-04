import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any, Tuple
import logging
import time

from backend.providers.aws.script_runner.schemas.account import AWSCredentials
from backend.providers.aws.common.services.credential_manager import CredentialManager
from backend.providers.aws.script_runner.services.execution_state_manager import AWSExecutionStateManager

logger = logging.getLogger(__name__)


class AWSAccountManager:
    """Service for AWS account management operations"""
    
    def __init__(self, credential_manager: CredentialManager):
        self.credential_manager = credential_manager
        self.default_region = 'us-east-1'
        self.retry_regions = {
            'gov': 'us-gov-west-1',
            'com': 'us-east-1'
        }
        # Initialize the execution state manager
        self.execution_state_manager = AWSExecutionStateManager(credential_manager)
    
    def assume_role(
        self, 
        account_id: str, 
        region_name: str, 
        credentials: Optional[AWSCredentials] = None
    ) -> Optional[Dict[str, Any]]:
        """Assume role in specified account and region using provided credentials if given."""
        arn_prefix = "arn:aws-us-gov" if "us-gov" in region_name else "arn:aws"
        role_arn = f"{arn_prefix}:iam::{account_id}:role/OrganizationAccountAccessRole"
        
        try:
            # Create an STS client using provided credentials or default
            if credentials:
                sts_client = boto3.client(
                    'sts',
                    region_name=region_name,
                    aws_access_key_id=credentials.access_key,
                    aws_secret_access_key=credentials.secret_key,
                    aws_session_token=credentials.session_token
                )
            else:
                # Use environment credentials from credential manager
                environment = "gov" if "us-gov" in region_name else "com"
                sts_client = self.credential_manager.create_client('sts', environment, region_name)
                if not sts_client:
                    logger.error(f"Failed to create STS client for {environment} in {region_name}")
                    return None

            # Assume the role
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="OrganizationAccessSession"
            )
            # Convert to Dict[str, Any] to match the return type
            if 'Credentials' in response:
                creds = response['Credentials']
                return {
                    "AccessKeyId": creds['AccessKeyId'],
                    "SecretAccessKey": creds['SecretAccessKey'],
                    "SessionToken": creds['SessionToken'],
                    "Expiration": creds['Expiration']
                }
            return None

        except Exception as e:
            logger.error(f"Error assuming role in account {account_id}: {str(e)}")
            # Log more detailed information for debugging
            import traceback
            logger.error(f"Traceback for assume_role: {traceback.format_exc()}")
            logger.error(f"Attempted to assume role: {role_arn}")
            return None
    
    def list_available_regions(self, environment: str, service: str = 'ec2') -> List[str]:
        """List available AWS regions for a service"""
        try:
            logger.debug(f"Listing available regions for service: {service} in {environment}")
            regions: List[str] = []
            
            # Use environment-specific region for API calls
            region = self.retry_regions.get(environment.lower(), self.default_region)
            
            # Get client using credential manager
            client = self.credential_manager.create_client(service, environment, region)
            if not client:
                logger.error(f"Failed to create client for listing regions")
                return []
                
            try:
                # Boto3 clients have dynamically created methods that mypy can't see
                response = client.describe_regions()  # type: ignore[attr-defined]
                if environment.lower() == 'gov':
                    regions = [r['RegionName'] for r in response['Regions'] if 'gov' in r['RegionName']]
                else:
                    regions = [r['RegionName'] for r in response['Regions'] if r['RegionName'].startswith('us-') and 'gov' not in r['RegionName']]
                logger.info(f"Retrieved {len(regions)} regions from {region}")
            except (ClientError, EndpointConnectionError) as e:
                logger.warning(f"Failed to list regions from {region}: {str(e)}")
                
            if not regions:
                logger.error("Failed to retrieve regions from any endpoint")
                
            return regions

        except Exception as e:
            logger.error(f"Error listing available regions: {str(e)}")
            return []
    
    def get_caller_identity(self, environment: str) -> Optional[Dict[str, Any]]:
        """Get identity information for the caller"""
        try:
            client = self.credential_manager.create_client('sts', environment)
            if not client:
                logger.error(f"Failed to create STS client for {environment}")
                return None
                
            # Boto3 clients have dynamically created methods that mypy can't see
            response = client.get_caller_identity()  # type: ignore[attr-defined]
            logger.info(f"Successfully retrieved caller identity: {response['Account']}")
            # Explicitly cast the response to fix the Any return type
            return dict(response)
        except Exception as e:
            logger.error(f"Error getting caller identity: {str(e)}")
            return None
            
    def list_accounts(self, environment: str) -> List[Dict[str, Any]]:
        """List AWS accounts accessible to the caller"""
        try:
            client = self.credential_manager.create_client('organizations', environment)
            if not client:
                logger.error(f"Failed to create Organizations client for {environment}")
                return []
                
            # Try to list accounts in the organization
            accounts = []
            paginator = client.get_paginator('list_accounts')
            for page in paginator.paginate():
                accounts.extend(page['Accounts'])
                
            logger.info(f"Retrieved {len(accounts)} accounts from organizations API")
            return accounts
        except Exception as e:
            # If organizations API fails, just return the caller's account
            logger.warning(f"Failed to list accounts using organizations API: {str(e)}")
            
            identity = self.get_caller_identity(environment)
            if identity:
                return [{
                    'Id': identity['Account'],
                    'Name': f"Account {identity['Account']}",
                    'Status': 'ACTIVE'
                }]
            return []
            
    def describe_instances(
        self, 
        account_id: str, 
        region: str, 
        environment: str
    ) -> List[Dict[str, Any]]:
        """Describe EC2 instances in specified account and region using OrgVisitor pattern"""
        try:
            # Import OrgVisitor
            from backend.providers.aws.script_runner.services.org_visitor import OrgVisitor
            
            logger.info(f"Using OrgVisitor to access instances in account {account_id}, region {region}")
            
            # Create a visitor instance
            visitor = OrgVisitor(self.credential_manager)
            
            # Define visitor functions
            def account_visitor(session, acct_id):
                logger.info(f"Account visitor called for {acct_id}")
                return {"visited": True}
                
            def region_visitor(session, reg, acct_id):
                if acct_id != account_id or reg != region:
                    # Skip accounts/regions we're not interested in
                    return None
                    
                logger.info(f"Region visitor called for {acct_id}/{reg}")
                try:
                    # Create EC2 client from the session
                    ec2 = session.client('ec2', region_name=reg)
                    
                    # Describe instances
                    instances = []
                    paginator = ec2.get_paginator('describe_instances')
                    for page in paginator.paginate():
                        for reservation in page['Reservations']:
                            instances.extend(reservation['Instances'])
                    
                    logger.info(f"Retrieved {len(instances)} instances from account {acct_id} in region {reg}")
                    return instances
                except Exception as e:
                    logger.error(f"Error in region visitor for {acct_id}/{reg}: {str(e)}")
                    return []
            
            # Find the root ID of the organization
            session = self.credential_manager.create_session(environment)
            if not session:
                logger.error(f"Failed to create session for {environment}")
                return []
                
            # Visit just the specific account we're interested in
            logger.info(f"Using direct role assumption for account {account_id}")
            result = visitor.visit_organization(
                environment, 
                account_visitor, 
                region_visitor
            )
            
            # Extract instances from the result
            if result.get("status") == "success" and "accounts" in result:
                for acct_id, acct_data in result.get("accounts", {}).items():
                    if acct_id == account_id and "regions" in acct_data:
                        for reg, reg_data in acct_data.get("regions", {}).items():
                            if reg == region and reg_data.get("status") == "success":
                                result_data: List[Dict[str, Any]] = reg_data.get("result", [])
                                return result_data
            
            # Fall back to direct access if the visitor didn't work
            logger.warning(f"Visitor pattern didn't yield results, trying direct access")
            
            # Try direct role assumption
            assumed_creds = self.assume_role(account_id, region)
            if assumed_creds:
                logger.info(f"Successfully assumed role directly in account {account_id}")
                # Create EC2 client with assumed role credentials
                ec2 = boto3.client(
                    'ec2',
                    region_name=region,
                    aws_access_key_id=assumed_creds['AccessKeyId'],
                    aws_secret_access_key=assumed_creds['SecretAccessKey'],
                    aws_session_token=assumed_creds['SessionToken']
                )
            else:
                logger.warning(f"Could not assume role in account {account_id}, falling back to environment credentials")
                # Try to use environment credentials directly
                ec2 = self.credential_manager.create_client('ec2', environment, region)
                if not ec2:
                    logger.error(f"Failed to create EC2 client for {account_id} in {region}")
                    return []
                logger.info(f"Using environment credentials for {environment} to access account {account_id}")
            
            # Describe instances
            instances = []
            paginator = ec2.get_paginator('describe_instances')
            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    instances.extend(reservation['Instances'])
            
            logger.info(f"Retrieved {len(instances)} instances from account {account_id} in region {region}")
            return instances
            
        except Exception as e:
            logger.error(f"Error describing instances in account {account_id}, region {region}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
