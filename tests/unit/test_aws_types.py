"""Tests for AWS type definitions"""
import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from app.types.aws import (
    Environment,
    RegionName,
    GovRegion,
    ComRegion,
    AWSRegion,
    AccountId,
    AWSCredentialsDict,
    InstanceId,
    InstanceState,
    Platform,
    EC2InstanceDict,
    CommandId,
    CommandStatus,
    SSMCommandDict,
    SSMCommandInvocationDict,
    SessionResult,
    CommandResult
)

class TestAWSCredentialsDict:
    """Test class for AWSCredentialsDict"""
    
    def test_credentials_dict_minimal(self):
        """Test AWSCredentialsDict with minimal fields"""
        # Create a credentials dict with required fields
        credentials: AWSCredentialsDict = {
            "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
            "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "SessionToken": "AQoEXAMPLEH4aoAH0gNCAPyJxz4BlCFFxWNE1OPTgk5TthT+FvwqnKw=="
        }
        
        assert credentials["AccessKeyId"] == "AKIAIOSFODNN7EXAMPLE"
        assert credentials["SecretAccessKey"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert credentials["SessionToken"] == "AQoEXAMPLEH4aoAH0gNCAPyJxz4BlCFFxWNE1OPTgk5TthT+FvwqnKw=="
        assert "Expiration" not in credentials
    
    def test_credentials_dict_complete(self):
        """Test AWSCredentialsDict with all fields"""
        expiration = datetime.utcnow()
        
        # Create a credentials dict with all fields
        credentials: AWSCredentialsDict = {
            "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
            "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "SessionToken": "AQoEXAMPLEH4aoAH0gNCAPyJxz4BlCFFxWNE1OPTgk5TthT+FvwqnKwRcOIfrRh3c/LTo6UDdyJwOOvEVPvLXCrrrUtdnniCEXAMPLE/IvU1dYUg2RVAJBanLiHb4IgRmpRV3zrkuWJOgQs8IZZaIv2BXIa2R4OlgkBN9bkUDNCJiBeb/AXlzBBko7b15fjrBs2+cTQtpZ3CYWFXG8C5zqx37wnOE49mRl/+OtkIKGO7fAE",
            "Expiration": expiration
        }
        
        assert credentials["AccessKeyId"] == "AKIAIOSFODNN7EXAMPLE"
        assert credentials["SecretAccessKey"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert credentials["SessionToken"] == "AQoEXAMPLEH4aoAH0gNCAPyJxz4BlCFFxWNE1OPTgk5TthT+FvwqnKwRcOIfrRh3c/LTo6UDdyJwOOvEVPvLXCrrrUtdnniCEXAMPLE/IvU1dYUg2RVAJBanLiHb4IgRmpRV3zrkuWJOgQs8IZZaIv2BXIa2R4OlgkBN9bkUDNCJiBeb/AXlzBBko7b15fjrBs2+cTQtpZ3CYWFXG8C5zqx37wnOE49mRl/+OtkIKGO7fAE"
        assert credentials["Expiration"] == expiration

class TestEC2InstanceDict:
    """Test class for EC2InstanceDict"""
    
    def test_ec2_instance_dict_minimal(self):
        """Test EC2InstanceDict with minimal fields"""
        # Create an EC2 instance dict with minimal fields
        instance: EC2InstanceDict = {
            "InstanceId": "i-1234567890abcdef0",
            "State": {"Name": "running", "Code": 16},
            "Tags": []
        }
        
        assert instance["InstanceId"] == "i-1234567890abcdef0"
        assert instance["State"]["Name"] == "running"
        assert instance["State"]["Code"] == 16
        assert instance["Tags"] == []
        assert "PrivateIpAddress" not in instance
        assert "PublicIpAddress" not in instance
        assert "Platform" not in instance
    
    def test_ec2_instance_dict_complete(self):
        """Test EC2InstanceDict with all fields"""
        # Create an EC2 instance dict with all fields
        instance: EC2InstanceDict = {
            "InstanceId": "i-1234567890abcdef0",
            "State": {"Name": "running", "Code": 16},
            "PrivateIpAddress": "10.0.0.1",
            "PublicIpAddress": "203.0.113.1",
            "Platform": "linux",
            "Tags": [
                {"Key": "Name", "Value": "TestInstance"},
                {"Key": "Environment", "Value": "Test"}
            ]
        }
        
        assert instance["InstanceId"] == "i-1234567890abcdef0"
        assert instance["State"]["Name"] == "running"
        assert instance["PrivateIpAddress"] == "10.0.0.1"
        assert instance["PublicIpAddress"] == "203.0.113.1"
        assert instance["Platform"] == "linux"
        assert len(instance["Tags"]) == 2
        assert instance["Tags"][0]["Key"] == "Name"
        assert instance["Tags"][0]["Value"] == "TestInstance"

class TestSSMCommandDict:
    """Test class for SSMCommandDict"""
    
    def test_ssm_command_dict(self):
        """Test SSMCommandDict"""
        now = datetime.utcnow()
        expires = now + timedelta(hours=1)
        
        # Create an SSM command dict
        command: SSMCommandDict = {
            "CommandId": "11111111-2222-3333-4444-555555555555",
            "Status": "InProgress",
            "InstanceId": "i-1234567890abcdef0",
            "DocumentName": "AWS-RunShellScript",
            "RequestedDateTime": now,
            "ExpiresAfter": expires
        }
        
        assert command["CommandId"] == "11111111-2222-3333-4444-555555555555"
        assert command["Status"] == "InProgress"
        assert command["InstanceId"] == "i-1234567890abcdef0"
        assert command["DocumentName"] == "AWS-RunShellScript"
        assert command["RequestedDateTime"] == now
        assert command["ExpiresAfter"] == expires

class TestSSMCommandInvocationDict:
    """Test class for SSMCommandInvocationDict"""
    
    def test_ssm_command_invocation_dict(self):
        """Test SSMCommandInvocationDict"""
        # Create an SSM command invocation dict
        invocation: SSMCommandInvocationDict = {
            "CommandId": "11111111-2222-3333-4444-555555555555",
            "InstanceId": "i-1234567890abcdef0",
            "Status": "Success",
            "StatusDetails": "Success",
            "StandardOutputContent": "Hello, World!",
            "StandardErrorContent": "",
            "ResponseCode": 0
        }
        
        assert invocation["CommandId"] == "11111111-2222-3333-4444-555555555555"
        assert invocation["InstanceId"] == "i-1234567890abcdef0"
        assert invocation["Status"] == "Success"
        assert invocation["StatusDetails"] == "Success"
        assert invocation["StandardOutputContent"] == "Hello, World!"
        assert invocation["StandardErrorContent"] == ""
        assert invocation["ResponseCode"] == 0

class TestSessionResult:
    """Test class for SessionResult"""
    
    def test_session_result_success(self):
        """Test SessionResult for success case"""
        # Create a session result for success
        result: SessionResult = {
            "status": "success",
            "session": {"token": "sample-token"},
            "message": "Session created successfully"
        }
        
        assert result["status"] == "success"
        assert result["session"] == {"token": "sample-token"}
        assert result["message"] == "Session created successfully"
    
    def test_session_result_failure(self):
        """Test SessionResult for failure case"""
        # Create a session result for failure
        result: SessionResult = {
            "status": "error",
            "session": None,
            "message": "Failed to create session"
        }
        
        assert result["status"] == "error"
        assert result["session"] is None
        assert result["message"] == "Failed to create session"

class TestCommandResult:
    """Test class for CommandResult"""
    
    def test_command_result_success(self):
        """Test CommandResult for success case"""
        # Create a command result for success
        result: CommandResult = {
            "CommandId": "11111111-2222-3333-4444-555555555555",
            "InstanceId": "i-1234567890abcdef0",
            "Status": "Success",
            "StatusDetails": "Command completed successfully",
            "Output": "Hello, World!",
            "Error": "",
            "ExitCode": 0
        }
        
        assert result["CommandId"] == "11111111-2222-3333-4444-555555555555"
        assert result["InstanceId"] == "i-1234567890abcdef0"
        assert result["Status"] == "Success"
        assert result["StatusDetails"] == "Command completed successfully"
        assert result["Output"] == "Hello, World!"
        assert result["Error"] == ""
        assert result["ExitCode"] == 0
    
    def test_command_result_failure(self):
        """Test CommandResult for failure case"""
        # Create a command result for failure
        result: CommandResult = {
            "CommandId": "11111111-2222-3333-4444-555555555555",
            "InstanceId": "i-1234567890abcdef0",
            "Status": "Failed",
            "StatusDetails": "Command execution failed",
            "Output": "",
            "Error": "Permission denied",
            "ExitCode": 1
        }
        
        assert result["CommandId"] == "11111111-2222-3333-4444-555555555555"
        assert result["InstanceId"] == "i-1234567890abcdef0"
        assert result["Status"] == "Failed"
        assert result["StatusDetails"] == "Command execution failed"
        assert result["Output"] == ""
        assert result["Error"] == "Permission denied"
        assert result["ExitCode"] == 1
