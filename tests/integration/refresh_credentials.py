#!/usr/bin/env python3
"""
Script to refresh AWS credentials for integration testing.
This script reads credentials from the specified file, requests new temporary
credentials via AWS STS, and saves them to the output file.
"""

import sys
import os
import argparse
from app.services.aws import credential_manager

def main():
    """Main function to refresh credentials"""
    parser = argparse.ArgumentParser(description="Refresh AWS credentials for integration testing")
    parser.add_argument("--input", "-i", default=DEFAULT_CREDS_PATH,
                        help=f"Path to input credentials file (default: {DEFAULT_CREDS_PATH})")
    parser.add_argument("--output", "-o", default=DEFAULT_NEW_CREDS_PATH,
                        help=f"Path to save new credentials (default: {DEFAULT_NEW_CREDS_PATH})")
    parser.add_argument("--role-arn", "-r",
                        help="ARN of role to assume (optional)")
    parser.add_argument("--region", default="us-west-2",
                        help="AWS region (default: us-west-2)")
    
    args = parser.parse_args()
    
    try:
        print(f"Loading credentials from: {args.input}")
        
        # Initialize and use credential manager
        manager = CredentialManager(args.input)
        manager.load_credentials()
        
        print("Requesting temporary credentials...")
        temp_creds = manager.get_temporary_credentials(
            role_arn=args.role_arn,
            region=args.region
        )
        
        # Save the new credentials
        output_path = manager.save_temporary_credentials(args.output)
        print(f"Successfully saved temporary credentials to: {output_path}")
        
        # Print information about the credentials
        if 'user_arn' in temp_creds:
            print(f"User ARN: {temp_creds['user_arn']}")
            print(f"Account ID: {temp_creds['account_id']}")
        elif 'role_arn' in temp_creds:
            print(f"Assumed Role: {temp_creds['role_arn']}")
            print(f"Expiration: {temp_creds['expiration']}")
            
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1
        

if __name__ == "__main__":
    exit(main())
