"""Unit tests for the EC2 manager service"""
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, List, Any

from backend.providers.aws.script_runner.services.ec2_manager import EC2Manager
from backend.providers.aws.common.services.credential_manager import CredentialManager


class TestEC2Manager:
    """Test class for EC2Manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.credential_manager = MagicMock(spec=CredentialManager)
        self.ec2_manager = EC2Manager(self.credential_manager)
        
    def test_init(self):
        """Test initialization of EC2Manager"""
        assert self.ec2_manager.credential_manager == self.credential_manager
    
    def test_describe_instances(self):
        """Test describing EC2 instances"""
        # Mock EC2 client
        mock_ec2 = MagicMock()
        mock_paginator = MagicMock()
        mock_ec2.get_paginator.return_value = mock_paginator
        
        # Setup paginator to return sample instances
        instance1 = {
            'InstanceId': 'i-12345',
            'State': {'Name': 'running'},
            'Tags': [{'Key': 'Name', 'Value': 'Test Instance 1'}],
            'Platform': 'linux'
        }
        instance2 = {
            'InstanceId': 'i-67890',
            'State': {'Name': 'running'},
            'Tags': [{'Key': 'Name', 'Value': 'Test Instance 2'}],
            'Platform': None,
            'PlatformDetails': 'Linux/UNIX'
        }
        
        mock_paginator.paginate.return_value = [
            {
                'Reservations': [
                    {'Instances': [instance1, instance2]}
                ]
            }
        ]
        
        # Mock credential manager to return EC2 client
        self.credential_manager.create_client.return_value = mock_ec2
        
        # Test with no filters
        instances = self.ec2_manager.describe_instances(
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov'
        )
        
        # Verify credential manager called correctly
        self.credential_manager.create_client.assert_called_once_with(
            'ec2', 'gov', 'us-gov-west-1'
        )
        
        # Verify paginator called correctly
        mock_ec2.get_paginator.assert_called_once_with('describe_instances')
        mock_paginator.paginate.assert_called_once_with()
        
        # Verify results
        assert len(instances) == 2
        assert instances[0]['InstanceId'] == 'i-12345'
        assert instances[1]['InstanceId'] == 'i-67890'
        
        # Test with instance_ids and filters
        self.credential_manager.create_client.reset_mock()
        mock_ec2.get_paginator.reset_mock()
        mock_paginator.paginate.reset_mock()
        
        instance_ids = ['i-12345']
        filters = [{'Name': 'instance-state-name', 'Values': ['running']}]
        
        self.ec2_manager.describe_instances(
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov',
            instance_ids=instance_ids,
            filters=filters
        )
        
        # Verify paginator called with correct params
        mock_paginator.paginate.assert_called_once_with(
            InstanceIds=instance_ids,
            Filters=filters
        )
        
        # Test with failed client creation
        self.credential_manager.create_client.return_value = None
        
        instances = self.ec2_manager.describe_instances(
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov'
        )
        
        assert instances == []
    
    def test_get_instance_details_by_id(self):
        """Test getting details for a specific EC2 instance"""
        # Mock EC2 client
        mock_ec2 = MagicMock()

        # Setup response with one instance
        instance = {
            'InstanceId': 'i-12345',
            'State': {'Name': 'running'},
            'Tags': [{'Key': 'Name', 'Value': 'Test Instance'}],
            'Platform': 'linux'
        }

        mock_ec2.describe_instances.return_value = {
            'Reservations': [
                {'Instances': [instance]}
            ]
        }

        # Mock credential manager to return EC2 client
        self.credential_manager.create_client.return_value = mock_ec2

        # Mock the is_instance_managed_by_ssm method
        with patch.object(self.ec2_manager, 'is_instance_managed_by_ssm', return_value=True):
            # Test getting instance details
            result = self.ec2_manager.get_instance_status(
                instance_id='i-12345',
                account_id='123456789012',
                region='us-gov-west-1',
                environment='gov'
            )

            # Verify credential manager called correctly
            self.credential_manager.create_client.assert_called_once_with(
                'ec2', 'gov', 'us-gov-west-1'
            )

            # Verify EC2 client called correctly
            mock_ec2.describe_instances.assert_called_once_with(
                InstanceIds=['i-12345']
            )

            # Verify result - using the actual keys from the implementation
            assert result['InstanceId'] == 'i-12345'
            assert result['Status'] == 'running'  # Changed from 'State' to 'Status'
            assert result['SSMManaged'] is True
        
        # Test with no results
        mock_ec2.describe_instances.reset_mock()
        mock_ec2.describe_instances.return_value = {'Reservations': []}
        
        result = self.ec2_manager.get_instance_status(
            instance_id='i-12345',
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov'
        )
        
        assert result['Status'] == 'NotFound'
        assert 'not found' in result['Error']
        
        # Test with failed client creation
        self.credential_manager.create_client.return_value = None
        
        result = self.ec2_manager.get_instance_status(
            instance_id='i-12345',
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov'
        )
        
        assert result['Status'] == 'Unknown'
        assert 'Failed to create EC2 client' in result['Error']
    
    def test_get_instance_platform(self):
        """Test getting the platform of an EC2 instance"""
        # Test Windows platform
        instance = {'Platform': 'windows'}
        platform = self.ec2_manager.get_instance_platform(instance)
        assert platform == 'windows'
        
        # Test Linux platform via PlatformDetails
        instance = {'PlatformDetails': 'Linux/UNIX'}
        platform = self.ec2_manager.get_instance_platform(instance)
        assert platform == 'linux'
        
        # Test Linux platform via ImageId
        instance = {'ImageId': 'ami-12345'}
        platform = self.ec2_manager.get_instance_platform(instance)
        assert platform == 'linux'  # Default
        
        # Test with platform and PlatformDetails
        instance = {
            'Platform': 'windows',
            'PlatformDetails': 'Windows Server 2019'
        }
        platform = self.ec2_manager.get_instance_platform(instance)
        assert platform == 'windows'
    
    def test_get_instance_tags(self):
        """Test getting tags from an EC2 instance"""
        # Test with tags
        instance = {
            'Tags': [
                {'Key': 'Name', 'Value': 'Test Instance'},
                {'Key': 'Environment', 'Value': 'Production'}
            ]
        }
        tags = self.ec2_manager.get_instance_tags(instance)
        assert tags == {
            'Name': 'Test Instance',
            'Environment': 'Production'
        }
        
        # Test with no tags
        instance = {}
        tags = self.ec2_manager.get_instance_tags(instance)
        assert tags == {}
        
        # Test with empty tags
        instance = {'Tags': []}
        tags = self.ec2_manager.get_instance_tags(instance)
        assert tags == {}
    
    def test_is_instance_managed_by_ssm(self):
        """Test checking if an instance is managed by SSM"""
        # Mock SSM client
        mock_ssm = MagicMock()
        
        # Setup response with managed instance
        mock_ssm.describe_instance_information.return_value = {
            'InstanceInformationList': [
                {'InstanceId': 'i-12345', 'PingStatus': 'Online'}
            ]
        }
        
        # Mock credential manager to return SSM client
        self.credential_manager.create_client.return_value = mock_ssm
        
        # Test with managed instance
        result = self.ec2_manager.is_instance_managed_by_ssm(
            instance_id='i-12345',
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov'
        )
        
        # Verify credential manager called correctly
        self.credential_manager.create_client.assert_called_once_with(
            'ssm', 'gov', 'us-gov-west-1'
        )
        
        # Verify SSM client called correctly
        mock_ssm.describe_instance_information.assert_called_once_with(
            Filters=[{'Key': 'InstanceIds', 'Values': ['i-12345']}]
        )
        
        # Verify result
        assert result is True
        
        # Test with unmanaged instance
        mock_ssm.describe_instance_information.return_value = {
            'InstanceInformationList': []
        }
        
        result = self.ec2_manager.is_instance_managed_by_ssm(
            instance_id='i-67890',
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov'
        )
        
        assert result is False
        
        # Test with failed client creation
        self.credential_manager.create_client.return_value = None
        
        result = self.ec2_manager.is_instance_managed_by_ssm(
            instance_id='i-12345',
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov'
        )
        
        assert result is False
        
        # Test with SSM exception
        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.side_effect = Exception("SSM error")
        self.credential_manager.create_client.return_value = mock_ssm
        
        result = self.ec2_manager.is_instance_managed_by_ssm(
            instance_id='i-12345',
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov'
        )
        
        assert result is False
    
    def test_get_instance_status(self):
        """Test getting the status of an EC2 instance"""
        # Mock EC2 client
        mock_ec2 = MagicMock()
        
        # Setup response with one instance - use datetime object for LaunchTime
        from datetime import datetime
        launch_time = datetime.now()
        instance = {
            'InstanceId': 'i-12345',
            'State': {'Name': 'running'},
            'Tags': [{'Key': 'Name', 'Value': 'Test Instance'}],
            'Platform': 'linux',
            'PrivateIpAddress': '10.0.0.1',
            'PublicIpAddress': '54.123.45.67',
            'LaunchTime': launch_time,
            'InstanceType': 't2.micro'
        }
        
        mock_ec2.describe_instances.return_value = {
            'Reservations': [
                {'Instances': [instance]}
            ]
        }
        
        # Mock credential manager to return EC2 client
        self.credential_manager.create_client.return_value = mock_ec2
        
        # Mock is_instance_managed_by_ssm
        with patch.object(self.ec2_manager, 'is_instance_managed_by_ssm', return_value=True):
            # Test getting instance status
            result = self.ec2_manager.get_instance_status(
                instance_id='i-12345',
                account_id='123456789012',
                region='us-gov-west-1',
                environment='gov'
            )
            
            # Verify EC2 client called correctly
            mock_ec2.describe_instances.assert_called_once_with(
                InstanceIds=['i-12345']
            )
            
            # Verify is_instance_managed_by_ssm called correctly
            self.ec2_manager.is_instance_managed_by_ssm.assert_called_once_with(
                'i-12345', '123456789012', 'us-gov-west-1', 'gov'
            )
            
            # Verify result - use the correct keys from the implementation
            assert result['InstanceId'] == 'i-12345'
            assert result['Status'] == 'running'
            assert result['SSMManaged'] is True
            assert result['PrivateIpAddress'] == '10.0.0.1'
            assert result['PublicIpAddress'] == '54.123.45.67'
            assert result['InstanceType'] == 't2.micro'
            assert result['Tags'] == {'Name': 'Test Instance'}
        
        # Test with instance not found
        mock_ec2.describe_instances.reset_mock()
        mock_ec2.describe_instances.return_value = {
            'Reservations': []
        }
        
        result = self.ec2_manager.get_instance_status(
            instance_id='i-12345',
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov'
        )
        
        assert result['Status'] == 'NotFound'
        assert 'not found' in result['Error']
        
        # Test with exception
        mock_ec2.describe_instances.side_effect = Exception("EC2 error")
        
        result = self.ec2_manager.get_instance_status(
            instance_id='i-12345',
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov'
        )
        
        assert result['Status'] == 'Error'
        assert 'EC2 error' in result['Error']
        
        # Test with failed client creation
        self.credential_manager.create_client.return_value = None
        
        result = self.ec2_manager.get_instance_status(
            instance_id='i-12345',
            account_id='123456789012',
            region='us-gov-west-1',
            environment='gov'
        )
        
        assert result['Status'] == 'Unknown'
        assert 'Failed to create EC2 client' in result['Error']
