#!/usr/bin/env python3
"""
AWS Credential Manager for integration testing
This script handles reading credentials, getting temporary credentials via STS,
and saving the new credentials for use in API testing.
"""

import os
import json
import boto3
from datetime import datetime
from typing import Dict, Any, Optional

# Constants
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
DEFAULT_CREDS_PATH = os.path.join(PROJECT_ROOT, "test/.creds")
DEFAULT_NEW_CREDS_PATH = os.path.join(PROJECT_ROOT, "test/.new-creds/json")
DEFAULT_SESSION_DURATION = 3600  # 1 hour


class CredentialManager:
    """Manages AWS credentials for integration testing"""
    
    def __init__(self, creds_path: str = DEFAULT_CREDS_PATH):
        """Initialize the credential manager
        
        Args:
            creds_path: Path to the credentials file
        """
        self.creds_path = creds_path
        self.creds = None
        self.temp_creds = None
    
    def load_credentials(self) -> Dict[str, str]:
        """Load credentials from the credentials file
        
        Returns:
            Dict containing the credentials
        
        Raises:
            FileNotFoundError: If the credentials file does not exist
            ValueError: If the credentials file is invalid
        """
        if not os.path.exists(self.creds_path):
            raise FileNotFoundError(f"Credentials file not found: {self.creds_path}")
        
        try:
            with open(self.creds_path, 'r') as f:
                self.creds = json.load(f)
                
            # Validate credentials
            required_keys = ['aws_access_key_id', 'aws_secret_access_key']
            if not all(key in self.creds for key in required_keys):
                missing = [key for key in required_keys if key not in self.creds]
                raise ValueError(f"Missing required credentials: {', '.join(missing)}")
                
            return self.creds
            
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in credentials file: {self.creds_path}")
    
    def get_temporary_credentials(
        self, 
        role_arn: Optional[str] = None, 
        session_name: str = "IntegrationTest", 
        duration_seconds: int = DEFAULT_SESSION_DURATION,
        region: str = "us-west-2"
    ) -> Dict[str, Any]:
        """Get temporary credentials using STS
        
        Args:
            role_arn: Optional ARN of role to assume, if None uses original credentials
            session_name: Name of the session
            duration_seconds: Duration of the temporary credentials in seconds
            region: AWS region
            
        Returns:
            Dict containing the temporary credentials
            
        Raises:
            ValueError: If credentials are not loaded
            Exception: If STS request fails
        """
        if not self.creds:
            self.load_credentials()
            
        # Create STS client
        sts_client = boto3.client(
            'sts',
            aws_access_key_id=self.creds['aws_access_key_id'],
            aws_secret_access_key=self.creds['aws_secret_access_key'],
            region_name=region
        )
        
        try:
            # If session token is provided, use it
            if 'aws_session_token' in self.creds:
                sts_client = boto3.client(
                    'sts',
                    aws_access_key_id=self.creds['aws_access_key_id'],
                    aws_secret_access_key=self.creds['aws_secret_access_key'],
                    aws_session_token=self.creds['aws_session_token'],
                    region_name=region
                )
            
            # If role ARN is provided, assume role
            if role_arn:
                print(f"Assuming role: {role_arn}")
                response = sts_client.assume_role(
                    RoleArn=role_arn,
                    RoleSessionName=session_name,
                    DurationSeconds=duration_seconds
                )
                
                credentials = response['Credentials']
                self.temp_creds = {
                    'aws_access_key_id': credentials['AccessKeyId'],
                    'aws_secret_access_key': credentials['SecretAccessKey'],
                    'aws_session_token': credentials['SessionToken'],
                    'expiration': credentials['Expiration'].isoformat(),
                    'region': region,
                    'role_arn': role_arn,
                    'assumed_at': datetime.now().isoformat()
                }
            else:
                # If no role ARN, just get caller identity to verify credentials
                response = sts_client.get_caller_identity()
                
                print(f"Using credentials for: {response['Arn']}")
                self.temp_creds = {
                    'aws_access_key_id': self.creds['aws_access_key_id'],
                    'aws_secret_access_key': self.creds['aws_secret_access_key'],
                    'region': region,
                    'user_arn': response['Arn'],
                    'account_id': response['Account'],
                    'verified_at': datetime.now().isoformat()
                }
                
                # Include session token if it was in original creds
                if 'aws_session_token' in self.creds:
                    self.temp_creds['aws_session_token'] = self.creds['aws_session_token']
                
            return self.temp_creds
            
        except Exception as e:
            raise Exception(f"Failed to get temporary credentials: {str(e)}")
    
    def save_temporary_credentials(
        self, 
        output_path: str = DEFAULT_NEW_CREDS_PATH
    ) -> str:
        """Save temporary credentials to a file
        
        Args:
            output_path: Path to save the credentials
            
        Returns:
            Path to the saved credentials file
            
        Raises:
            ValueError: If temporary credentials are not available
        """
        if not self.temp_creds:
            raise ValueError("No temporary credentials available. Call get_temporary_credentials first.")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save credentials to file
        with open(output_path, 'w') as f:
            json.dump(self.temp_creds, f, indent=2)
            
        print(f"Temporary credentials saved to: {output_path}")
        return output_path


def main():
    """Command-line interface for the credential manager"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AWS Credential Manager for integration testing")
    parser.add_argument("--input", "-i", default=DEFAULT_CREDS_PATH,
                        help=f"Path to input credentials file (default: {DEFAULT_CREDS_PATH})")
    parser.add_argument("--output", "-o", default=DEFAULT_NEW_CREDS_PATH,
                        help=f"Path to save new credentials (default: {DEFAULT_NEW_CREDS_PATH})")
    parser.add_argument("--role-arn", "-r",
                        help="ARN of role to assume (optional)")
    parser.add_argument("--session-name", "-s", default="IntegrationTest",
                        help="Name of the session (default: IntegrationTest)")
    parser.add_argument("--duration", "-d", type=int, default=DEFAULT_SESSION_DURATION,
                        help=f"Duration of temporary credentials in seconds (default: {DEFAULT_SESSION_DURATION})")
    parser.add_argument("--region", default="us-west-2",
                        help="AWS region (default: us-west-2)")
    
    args = parser.parse_args()
    
    try:
        # Initialize credential manager
        manager = CredentialManager(args.input)
        
        # Load credentials
        print(f"Loading credentials from: {args.input}")
        manager.load_credentials()
        
        # Get temporary credentials
        print("Getting temporary credentials...")
        manager.get_temporary_credentials(
            role_arn=args.role_arn,
            session_name=args.session_name,
            duration_seconds=args.duration,
            region=args.region
        )
        
        # Save temporary credentials
        manager.save_temporary_credentials(args.output)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
        
    return 0


if __name__ == "__main__":
    exit(main())
