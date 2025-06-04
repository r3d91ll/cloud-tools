from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.providers.aws.script_runner.schemas.account import Account, AccountCreate, Region, Instance
from backend.providers.aws.common.services.credential_manager import CredentialManager
from backend.providers.aws.common.services import credential_manager as cm_module
from backend.providers.aws.common.services.account_manager import AWSAccountManager
from backend.providers.aws.script_runner.services.ec2_manager import EC2Manager
from typing import cast

# Create router
router = APIRouter()

# Initialize services with the shared credential manager
cm = cast(CredentialManager, cm_module)
account_manager = AWSAccountManager(cm)
ec2_manager = EC2Manager(cm)


@router.get("/", response_model=Dict[str, Any])
def list_accounts(
    environment: str = Query(..., description="AWS environment (gov or com)"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List all AWS accounts for a specific environment.
    
    This endpoint retrieves accounts from AWS Organizations API or
    from the current credentials if Organizations access is not available.
    """
    # Ensure credentials are valid
    if not cm.are_credentials_valid(environment):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No valid credentials found for {environment} environment"
        )
    
    # List accounts from AWS
    accounts = account_manager.list_accounts(environment)
    
    return {
        "environment": environment,
        "accounts": accounts
    }


@router.get("/{account_id}", response_model=Dict[str, Any])
def get_account_details(
    account_id: str,
    environment: str = Query(..., description="AWS environment (gov or com)"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get details for a specific AWS account.
    
    This endpoint retrieves account details and available regions.
    """
    # Ensure credentials are valid
    if not cm.are_credentials_valid(environment):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No valid credentials found for {environment} environment"
        )
    
    # Get available regions for this account
    regions = account_manager.list_available_regions(environment)
    
    return {
        "account_id": account_id,
        "environment": environment,
        "regions": regions
    }


@router.get("/{account_id}/regions/{region}/instances", response_model=Dict[str, Any])
def list_instances(
    account_id: str,
    region: str,
    environment: str = Query(..., description="AWS environment (gov or com)"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List EC2 instances in a specific account and region.
    
    This endpoint retrieves instances and their details.
    """
    # Ensure credentials are valid
    if not cm.are_credentials_valid(environment):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No valid credentials found for {environment} environment"
        )
    
    # Get instances from AWS
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"API: Requesting instances for account {account_id} in region {region} with environment {environment}")
    
    # Create a boto3 session directly for visiting the organization
    import boto3
    from backend.providers.aws.script_runner.services.org_visitor import OrgVisitor, AWS_PUBLIC, AWS_GOVCLOUD
    from contextlib import contextmanager
    from botocore.exceptions import ClientError
    
    visitor = OrgVisitor(cm)
    found_instances = []
    
    def account_visitor(session, acct):
        logger.info(f"Visiting account: {acct}")
        return True
        
    def region_visitor(session, reg, acct):
        # Only process the specific account and region we're interested in
        if acct != account_id or reg != region:
            return None
            
        logger.info(f"Processing target account {acct} in region {reg}")
        try:
            ec2 = session.client('ec2', region_name=reg)
            instances = []
            paginator = ec2.get_paginator('describe_instances')
            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    instances.extend(reservation['Instances'])
                    
            logger.info(f"Found {len(instances)} instances in account {acct}, region {reg}")
            nonlocal found_instances
            found_instances = instances
            return instances
        except Exception as e:
            logger.error(f"Error accessing instances in {acct}/{reg}: {str(e)}")
            return []
    
    # Instead of visiting all accounts, just create a session and directly assume the role
    # for the target account
    role_name = "OrganizationAccountAccessRole"
    session = cm.create_session(environment)
    if not session:
        logger.error(f"Failed to create boto3 session for {environment}")
        found_instances = []
    else:
        # Only target the specific account we want
        logger.info(f"Creating direct session for account {account_id}")
        partition = AWS_GOVCLOUD if environment.lower() == "gov" else AWS_PUBLIC
        
        with visitor.switch_role(session, account_id, role_name, partition) as assumed_session:
            if not assumed_session:
                logger.error(f"Failed to assume role into account {account_id}")
            else:
                logger.info(f"Successfully assumed role into account {account_id}")
                # Call the region visitor directly with the assumed session
                region_visitor(assumed_session, region, account_id)
    
    # If we found instances, use them
    if found_instances:
        logger.info(f"Successfully retrieved {len(found_instances)} instances using org visitor")
        instances = found_instances
    else:
        # Otherwise fall back to the ec2 manager
        logger.warning(f"Org visitor returned no instances, falling back to EC2 manager")
        instances = ec2_manager.describe_instances(account_id, region, environment)
    
    # Process instances to include platform info
    processed_instances = []
    for instance in instances:
        platform = ec2_manager.get_instance_platform(instance)
        tags = ec2_manager.get_instance_tags(instance)
        name = tags.get('Name', f"Instance-{instance.get('InstanceId', 'Unknown')}")
        
        processed_instances.append({
            "instance_id": instance.get('InstanceId'),
            "name": name,
            "platform": platform,
            "state": instance.get('State', {}).get('Name'),
            "private_ip": instance.get('PrivateIpAddress'),
            "tags": tags
        })
    
    return {
        "account_id": account_id,
        "region": region,
        "environment": environment,
        "instances": processed_instances,
        "count": len(processed_instances)
    }


@router.get("/{account_id}/regions/{region}/instances/{instance_id}", response_model=Dict[str, Any])
def get_instance_details(
    account_id: str,
    region: str,
    instance_id: str,
    environment: str = Query(..., description="AWS environment (gov or com)"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific EC2 instance.
    
    This endpoint retrieves comprehensive instance details including SSM status.
    """
    # Ensure credentials are valid
    if not cm.are_credentials_valid(environment):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No valid credentials found for {environment} environment"
        )
    
    # Get instance status from AWS
    instance_status = ec2_manager.get_instance_status(instance_id, account_id, region, environment)
    
    if instance_status.get('Status') == 'NotFound':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance {instance_id} not found in account {account_id}, region {region}"
        )
    
    return instance_status
