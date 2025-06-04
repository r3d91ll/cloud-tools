"""Unit tests for the organization visitor service"""
import pytest
import boto3
from unittest.mock import patch, MagicMock, call, ANY
from contextlib import contextmanager
from typing import Iterator, Optional

from backend.providers.aws.script_runner.services.org_visitor import OrgVisitor
from backend.providers.aws.common.services.credential_manager import CredentialManager
from backend.providers.aws.script_runner.schemas.account import AWSCredentials


@pytest.fixture
def mock_credential_manager():
    """Fixture for a mocked credential manager"""
    credential_manager = MagicMock(spec=CredentialManager)
    
    # Mock are_credentials_valid to return True
    credential_manager.are_credentials_valid.return_value = True
    
    # Mock create_session to return a session
    mock_session = MagicMock(spec=boto3.Session)
    credential_manager.create_session.return_value = mock_session
    
    return credential_manager, mock_session


def test_switch_role(mock_credential_manager):
    """Test the switch_role context manager"""
    # Unpack the fixture
    credential_manager, mock_session = mock_credential_manager
    
    # Create org visitor
    visitor = OrgVisitor(credential_manager)
    
    # Mock STS client
    mock_sts = MagicMock()
    mock_session.client.return_value = mock_sts
    
    # Mock assume_role response
    mock_sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "ASIA_ASSUMED_ROLE_KEY",
            "SecretAccessKey": "assumed_role_secret_key",
            "SessionToken": "assumed_role_session_token"
        }
    }
    
    # Mock boto3.session.Session
    with patch('boto3.session.Session') as mock_boto3_session:
        mock_assumed_session = MagicMock()
        mock_boto3_session.return_value = mock_assumed_session
        
        # Use the switch_role context manager
        with visitor.switch_role(mock_session, "123456789012", "TestRole", "aws") as assumed_session:
            assert assumed_session is mock_assumed_session
            
            # Verify STS client was created
            mock_session.client.assert_called_with("sts")
            
            # Verify assume_role was called with correct arguments
            mock_sts.assume_role.assert_called_with(
                RoleArn="arn:aws:iam::123456789012:role/TestRole", 
                RoleSessionName="API-Visitor-Session"
            )
            
            # Verify boto3.session.Session was called with correct arguments
            mock_boto3_session.assert_called_with(
                aws_access_key_id="ASIA_ASSUMED_ROLE_KEY",
                aws_secret_access_key="assumed_role_secret_key",
                aws_session_token="assumed_role_session_token",
                region_name=mock_session.region_name
            )


def test_get_accounts(mock_credential_manager):
    """Test getting accounts from an organization"""
    # Unpack the fixture
    credential_manager, mock_session = mock_credential_manager
    
    # Create org visitor
    visitor = OrgVisitor(credential_manager)
    
    # Create a mock org client
    mock_org_client = MagicMock()
    
    # Mock the list_accounts paginator
    mock_paginator = MagicMock()
    mock_org_client.get_paginator.return_value = mock_paginator
    
    # Mock paginate response
    mock_paginator.paginate.return_value = [
        {
            "Accounts": [
                {"Id": "111111111111"},
                {"Id": "222222222222"}
            ]
        },
        {
            "Accounts": [
                {"Id": "333333333333"}
            ]
        }
    ]
    
    # Call get_accounts with no parent ID
    accounts = visitor.get_accounts(mock_org_client)
    
    # Verify the paginator was created correctly
    mock_org_client.get_paginator.assert_called_with("list_accounts")
    
    # Verify paginate was called without a ParentId
    mock_paginator.paginate.assert_called_with()
    
    # Verify the returned accounts
    assert accounts == ["111111111111", "222222222222", "333333333333"]
    
    # Reset mocks
    mock_org_client.reset_mock()
    mock_paginator.reset_mock()
    
    # Now test with a parent ID
    parent_id = "ou-1234-abcdef"
    
    # Mock the paginator again
    mock_org_client.get_paginator.return_value = mock_paginator
    mock_paginator.paginate.return_value = [
        {
            "Accounts": [
                {"Id": "444444444444"},
                {"Id": "555555555555"}
            ]
        }
    ]
    
    # Call get_accounts with a parent ID
    accounts = visitor.get_accounts(mock_org_client, parent_id)
    
    # Verify the paginator was created correctly
    mock_org_client.get_paginator.assert_called_with("list_accounts_for_parent")
    
    # Verify paginate was called with the ParentId
    mock_paginator.paginate.assert_called_with(ParentId=parent_id)
    
    # Verify the returned accounts
    assert accounts == ["444444444444", "555555555555"]


def test_get_us_regions(mock_credential_manager):
    """Test getting US regions"""
    # Unpack the fixture
    credential_manager, mock_session = mock_credential_manager
    
    # Create org visitor
    visitor = OrgVisitor(credential_manager)
    
    # Mock EC2 client
    mock_ec2 = MagicMock()
    mock_session.client.return_value = mock_ec2
    
    # Mock describe_regions response
    mock_ec2.describe_regions.return_value = {
        "Regions": [
            {"RegionName": "us-east-1"},
            {"RegionName": "us-east-2"},
            {"RegionName": "us-west-1"},
            {"RegionName": "us-west-2"},
            {"RegionName": "us-gov-west-1"},
            {"RegionName": "eu-west-1"},
            {"RegionName": "ap-southeast-1"}
        ]
    }
    
    # Get US regions excluding GovCloud
    regions = visitor.get_us_regions(mock_session)
    
    # Verify EC2 client was created
    mock_session.client.assert_called_with("ec2")
    
    # Verify describe_regions was called
    mock_ec2.describe_regions.assert_called_once()
    
    # Verify only US non-gov regions are returned
    assert sorted(regions) == ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]
    
    # Reset mock
    mock_ec2.reset_mock()
    
    # Get US regions including GovCloud
    regions = visitor.get_us_regions(mock_session, include_gov=True)
    
    # Verify describe_regions was called again
    mock_ec2.describe_regions.assert_called_once()
    
    # Verify all US regions including gov are returned
    assert sorted(regions) == ["us-east-1", "us-east-2", "us-gov-west-1", "us-west-1", "us-west-2"]


@patch('app.services.aws.org_visitor.OrgVisitor.walk_organization')
@patch('app.services.aws.org_visitor.OrgVisitor.get_organization_client')
def test_visit_organization(mock_get_org_client, mock_walk_org, mock_credential_manager):
    """Test the visit_organization method"""
    # Unpack the fixture
    credential_manager, mock_session = mock_credential_manager
    
    # Create org visitor
    visitor = OrgVisitor(credential_manager)
    
    # Mock context manager for organization client
    @contextmanager
    def mock_context_manager() -> Iterator[MagicMock]:
        mock_org_client = MagicMock()
        yield mock_org_client
    
    mock_get_org_client.return_value = mock_context_manager()
    
    # Define mock visitors
    def account_visitor(session, account_id):
        return {"account": account_id}
    
    def region_visitor(session, region, account_id):
        return {"region": region, "account": account_id}
    
    # Mock walk_organization response
    mock_walk_org.return_value = {
        "accounts": {
            "111111111111": {"status": "success"},
            "222222222222": {"status": "error"}
        }
    }
    
    # Call visit_organization
    results = visitor.visit_organization(
        environment="com",
        account_visitor=account_visitor,
        region_visitor=region_visitor,
        role_name="TestRole",
        parent_id="ou-1234-abcdef"
    )
    
    # Verify credential_manager.create_session was called with the right environment
    credential_manager.create_session.assert_called_with("com")
    
    # Verify get_organization_client was called with the session
    mock_get_org_client.assert_called_with(mock_session)
    
    # Verify walk_organization was called with the right arguments
    mock_walk_org.assert_called_with(
        mock_session, 
        ANY,  # The mock org client from the context manager
        "TestRole", 
        account_visitor, 
        region_visitor, 
        "aws",  # The AWS partition for com environment
        "ou-1234-abcdef"
    )
    
    # Verify results contain both walk_org results and metadata
    assert "accounts" in results
    assert "status" in results
    assert "time_elapsed" in results
    assert results["status"] == "success"
