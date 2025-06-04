"""
Organization traversal service for AWS accounts.
Based on proven pattern for role assumption across an organization.
"""

import logging
import time
import boto3
from contextlib import contextmanager
from typing import Dict, List, Any, Optional, Iterator, Callable, TypeVar, cast, Protocol
import boto3
from boto3.session import Session
from botocore.exceptions import ClientError
from botocore.config import Config
from botocore.client import BaseClient

# Type definition for OrganizationsClient
class OrganizationsClient(Protocol):
    def describe_organization(self) -> Dict[str, Any]: ...
    def list_accounts(self, **kwargs) -> Dict[str, Any]: ...
    def list_accounts_for_parent(self, **kwargs) -> Dict[str, Any]: ...
    def get_paginator(self, operation_name: str) -> Any: ...
    def describe_account(self, **kwargs) -> Dict[str, Any]: ...

from backend.providers.aws.common.services.credential_manager import CredentialManager

# Constants
AWS_PUBLIC = "aws"
AWS_GOVCLOUD = "aws-us-gov"

logger = logging.getLogger(__name__)


class OrgVisitor:
    """Service for traversing AWS organization and visiting accounts"""
    
    def __init__(self, credential_manager: CredentialManager):
        """Initialize the OrgVisitor
        
        Args:
            credential_manager: The credential manager to use for base credentials
        """
        self.credential_manager = credential_manager
    
    @contextmanager
    def switch_role(self, session: boto3.Session, account_id: str, role_name: str, 
                    partition: str, role_session_name: str = "API-Visitor-Session") -> Iterator[Optional[boto3.Session]]:
        """Switch to a role in another account
        
        Args:
            session: The boto3 session to use for assuming the role
            account_id: The account ID to assume the role in
            role_name: The name of the role to assume
            partition: The AWS partition (aws or aws-us-gov)
            role_session_name: The session name to use
            
        Yields:
            An assumed role session or None if assumption failed
        """
        try:
            arn_template = "arn:%s:iam::%s:role/%s"
            role_arn = arn_template % (partition, account_id, role_name)

            logger.debug(f"Assuming role: {role_arn}")
            sts = session.client("sts")
            resp = sts.assume_role(
                RoleArn=role_arn, 
                RoleSessionName=role_session_name
            )

            assumed_session = boto3.session.Session(
                aws_access_key_id=resp["Credentials"]["AccessKeyId"],
                aws_secret_access_key=resp["Credentials"]["SecretAccessKey"],
                aws_session_token=resp["Credentials"]["SessionToken"],
                region_name=session.region_name,
            )

            yield assumed_session
        except ClientError as err:
            logger.error(f"Error assuming role in account {account_id}: {str(err)}")
            yield None
    
    @contextmanager
    def get_organization_client(self, session: Session) -> Iterator[OrganizationsClient]:
        """Get a client for AWS Organizations
        
        Args:
            session: The boto3 session to use
            
        Yields:
            An AWS Organizations client
        """
        try:
            logger.debug(f"Getting handle on client for AWS Organizations")
            client = session.client("organizations", config=Config(
                region_name=session.region_name))
            yield client
        finally:
            logger.debug(f"Releasing handle on client for AWS Organizations")
            del client
    
    def get_accounts(self, org_client: OrganizationsClient, parent_id: Optional[str] = None) -> List[str]:
        """Get a list of account IDs in the organization
        
        Args:
            org_client: The AWS Organizations client
            parent_id: Optional parent ID to list accounts for
            
        Returns:
            A list of account IDs
        """
        if parent_id is not None:
            paginator = org_client.get_paginator("list_accounts_for_parent")
            iterator = paginator.paginate(ParentId=parent_id)
        else:
            paginator = org_client.get_paginator("list_accounts")
            iterator = paginator.paginate()

        account_ids = []
        for page in iterator:
            account_ids.extend([a["Id"] for a in page["Accounts"]])

        logger.debug(f"Found accounts: {account_ids}")
        return account_ids
    
    def get_us_regions(self, session: Session, include_gov: bool = False) -> List[str]:
        """Get a list of US regions
        
        Args:
            session: The boto3 session to use
            include_gov: Whether to include GovCloud regions
            
        Returns:
            A list of region names
        """
        logger.debug("Getting US regions")
        ec2_client = session.client("ec2")
        resp = ec2_client.describe_regions()

        if include_gov:
            return [r["RegionName"] for r in resp["Regions"] 
                    if r["RegionName"].startswith("us-")]
        else:
            return [r["RegionName"] for r in resp["Regions"] 
                    if r["RegionName"].startswith("us-") and not "gov" in r["RegionName"]]
    
    def walk_organization(self, session: Session, org_client: OrganizationsClient, 
                      role_name: str, account_visitor: Callable, region_visitor: Callable,
                      partition: str, parent_id: Optional[str]) -> Dict[str, Any]:
        """Walk the organization and visit accounts
        
        Args:
            session: The boto3 session to use
            org_client: The AWS Organizations client
            role_name: The name of the role to assume
            account_visitor: A callable to visit each account
            region_visitor: A callable to visit each region in each account
            partition: The AWS partition (aws or aws-us-gov)
            parent_id: Optional parent ID to start from
            
        Returns:
            A dictionary with visit results
        """
        logger.debug("Walking organization")
        include_gov = partition == AWS_GOVCLOUD
        regions = self.get_us_regions(session, include_gov)
        results: Dict[str, Dict[str, Any]] = {"accounts": {}}
        
        for account in self.get_accounts(org_client, parent_id):
            results["accounts"][account] = {"regions": {}}
            
            with self.switch_role(session, account, role_name, partition) as assumed_session:
                if assumed_session is None:
                    logger.warning(f"Failed to switch role for account {account}")
                    results["accounts"][account]["status"] = "error"
                    results["accounts"][account]["error"] = "Failed to assume role"
                    continue

                logger.info(f"Visiting account {account}")
                try:
                    account_result = account_visitor(assumed_session, account)
                    results["accounts"][account]["result"] = account_result 
                    results["accounts"][account]["status"] = "success"
                except Exception as e:
                    logger.error(f"Error in account visitor for {account}: {str(e)}")
                    results["accounts"][account]["status"] = "error" 
                    results["accounts"][account]["error"] = str(e)
                
                for region in regions:
                    results["accounts"][account]["regions"][region] = {}
                    try:
                        logger.info(f"Visiting region {region} for account {account}")
                        region_result = region_visitor(assumed_session, region, account)
                        results["accounts"][account]["regions"][region]["result"] = region_result
                        results["accounts"][account]["regions"][region]["status"] = "success"
                    except Exception as e:
                        logger.error(f"Error in region visitor for {account}/{region}: {str(e)}")
                        results["accounts"][account]["regions"][region]["status"] = "error"
                        results["accounts"][account]["regions"][region]["error"] = str(e)
        
        return results
    
    def visit_organization(self, environment: str, account_visitor: Callable, 
                      region_visitor: Callable, role_name: str = "OrganizationAccountAccessRole", 
                      parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Visit each account and region in an organization
        
        Args:
            environment: The AWS environment (gov or com)
            account_visitor: A callable to visit each account
            region_visitor: A callable to visit each region in each account
            role_name: The name of the role to assume
            parent_id: Optional parent ID to start from
            
        Returns:
            A dictionary with visit results
        """
        logger.info("Starting organization visit")
        start_time = time.time()
        results = {"status": "error", "time_elapsed": 0}

        try:
            # Get environment-specific values
            partition_name = AWS_GOVCLOUD if environment.lower() == "gov" else AWS_PUBLIC
            
            # Create a session from existing credentials
            session = self.credential_manager.create_session(environment)
            if not session:
                logger.error(f"Failed to create session for {environment}")
                results["error"] = f"Failed to create session for {environment}"
                return results
            
            # Visit the organization
            with self.get_organization_client(session) as org_client:
                visit_results = self.walk_organization(
                    session, org_client, role_name, account_visitor,
                    region_visitor, partition_name, parent_id)
                
                results.update(visit_results)
                results["status"] = "success"
        
        except Exception as e:
            logger.error(f"Error visiting organization: {str(e)}")
            results["error"] = str(e)
        
        # Update elapsed time
        elapsed_time = time.time() - start_time
        results["time_elapsed"] = elapsed_time
        logger.info(f"Organization visit completed in {elapsed_time:.2f} seconds")
        
        return results
