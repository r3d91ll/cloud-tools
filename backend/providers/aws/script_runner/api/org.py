"""
API endpoints for AWS organization traversal.
"""

from fastapi import APIRouter, HTTPException, status, Query
from typing import Dict, Any, Optional, List, Callable
from pydantic import BaseModel
import boto3
import json
import logging

from backend.providers.aws.common.services.credential_manager import CredentialManager
from backend.providers.aws.script_runner.services.org_visitor import OrgVisitor

# Create router
router = APIRouter()

# Create service instances
credential_manager = CredentialManager()
org_visitor = OrgVisitor(credential_manager)

# Configure logging
logger = logging.getLogger(__name__)


class OrgVisitRequest(BaseModel):
    """Request model for organization traversal"""
    environment: str = "com"
    role_name: str = "OrganizationAccountAccessRole"
    parent_id: Optional[str] = None
    visitor_type: str = "instances" # Options: "instances", "buckets", "custom"
    custom_account_query: Optional[str] = None
    custom_region_query: Optional[str] = None
    

@router.post("/visit-organization", response_model=Dict[str, Any])
def visit_organization(request: OrgVisitRequest) -> Dict[str, Any]:
    """
    Traverse an AWS organization structure and execute visitor functions.
    
    This endpoint traverses the AWS organization structure, assumes roles in each account,
    and executes visitor functions for each account and region. It returns results from
    all accounts and regions visited.
    
    The visitor_type parameter determines what visitors are used:
    - "instances": List EC2 instances in each account/region
    - "buckets": List S3 buckets in each account/region
    - "custom": Execute custom query provided in request
    
    For custom queries, the account_query and region_query parameters must be valid
    Python expressions that can be executed with the following variables:
    - session: boto3.Session object
    - account_id: The account ID being visited
    - region: The region being visited (for region_query only)
    """
    # Check if credentials are valid
    if not credential_manager.are_credentials_valid(request.environment):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No valid credentials found for {request.environment} environment"
        )
    
    # Define visitor functions based on request type
    if request.visitor_type == "instances":
        # List EC2 instances in each account/region
        def account_visitor(session: boto3.Session, account_id: str) -> Dict[str, Any]:
            identity = session.client('sts').get_caller_identity()
            return {"account_id": account_id, "caller_identity": identity}
        
        def region_visitor(session: boto3.Session, region: str, account_id: str) -> Dict[str, Any]:
            ec2 = session.client('ec2', region_name=region)
            instances = []
            try:
                paginator = ec2.get_paginator('describe_instances')
                for page in paginator.paginate():
                    for reservation in page['Reservations']:
                        instances.extend(reservation['Instances'])
                return {"count": len(instances), "instances": [{"id": i["InstanceId"], "type": i.get("InstanceType", "unknown")} for i in instances]}
            except Exception as e:
                logger.error(f"Error listing instances in {account_id}/{region}: {str(e)}")
                raise
    
    elif request.visitor_type == "buckets":
        # List S3 buckets in each account/region
        def account_visitor(session: boto3.Session, account_id: str) -> Dict[str, Any]:
            identity = session.client('sts').get_caller_identity()
            s3 = session.client('s3')
            try:
                buckets = s3.list_buckets()
                return {"account_id": account_id, "bucket_count": len(buckets.get('Buckets', [])), 
                        "caller_identity": identity}
            except Exception as e:
                logger.error(f"Error listing buckets in {account_id}: {str(e)}")
                raise
        
        def region_visitor(session: boto3.Session, region: str, account_id: str) -> Dict[str, Any]:
            # S3 buckets are global, but we can list the ones in this region
            s3 = session.client('s3', region_name=region)
            regional_buckets: List[Dict[str, Any]] = []
            try:
                # This requires additional logic to filter buckets by region
                # We're simplifying this for the example
                return {"region": region, "message": "S3 buckets are global resources"}
            except Exception as e:
                logger.error(f"Error in S3 operation for {account_id}/{region}: {str(e)}")
                raise
    
    elif request.visitor_type == "custom":
        # Execute custom query
        if not request.custom_account_query or not request.custom_region_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom visitor type requires both custom_account_query and custom_region_query"
            )
        
        # Create dynamic visitors using provided queries
        # WARNING: This approach has significant security implications
        # In a production environment, you'd want to sanitize and validate these queries
        try:
            # Create account visitor function
            account_code = f"def dynamic_account_visitor(session, account_id):\n    result = {request.custom_account_query}\n    return result"
            region_code = f"def dynamic_region_visitor(session, region, account_id):\n    result = {request.custom_region_query}\n    return result"
            
            account_locals: Dict[str, Any] = {}
            region_locals: Dict[str, Any] = {}
            
            exec(account_code, globals(), account_locals)
            exec(region_code, globals(), region_locals)
            
            account_visitor = account_locals["dynamic_account_visitor"]
            region_visitor = region_locals["dynamic_region_visitor"]
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid custom query: {str(e)}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid visitor_type: {request.visitor_type}"
        )
    
    # Execute the organization traversal
    results = org_visitor.visit_organization(
        environment=request.environment,
        account_visitor=account_visitor,
        region_visitor=region_visitor,
        role_name=request.role_name,
        parent_id=request.parent_id
    )
    
    return results


@router.get("/organization-accounts", response_model=Dict[str, Any])
def list_organization_accounts(
    environment: str = Query("com", description="AWS environment (gov or com)"),
    parent_id: Optional[str] = Query(None, description="Optional parent ID to list accounts under")
) -> Dict[str, Any]:
    """
    List accounts in an AWS organization.
    
    This endpoint lists accounts in an AWS organization, optionally filtered by parent ID.
    """
    # Check if credentials are valid
    if not credential_manager.are_credentials_valid(environment):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No valid credentials found for {environment} environment"
        )
    
    try:
        # Create session
        session = credential_manager.create_session(environment)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create session for {environment}"
            )
        
        # List accounts
        with org_visitor.get_organization_client(session) as org_client:
            accounts = org_visitor.get_accounts(org_client, parent_id)
            
            # Get detailed information for each account
            detailed_accounts = []
            for account_id in accounts:
                try:
                    # Get account details
                    response = org_client.describe_account(AccountId=account_id)
                    detailed_accounts.append(response["Account"])
                except Exception as e:
                    logger.error(f"Error getting details for account {account_id}: {str(e)}")
                    detailed_accounts.append({
                        "Id": account_id,
                        "Status": "UNKNOWN",
                        "Error": str(e)
                    })
            
            return {
                "status": "success",
                "account_count": len(detailed_accounts),
                "accounts": detailed_accounts
            }
    
    except Exception as e:
        logger.error(f"Error listing organization accounts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing organization accounts: {str(e)}"
        )
