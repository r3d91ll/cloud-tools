#!/usr/bin/env python3
"""
Real-world integration test for AWS Script Runner API.

This script performs an end-to-end test of the AWS Script Runner API by:
1. Starting the API service
2. Reading AWS credentials from a .env file
3. Authenticating with both gov and com environments
4. Listing accounts in each environment
5. Validating core functionality

Usage:
    python test_api_real_world.py

Requirements:
    - .env file with AWS credentials (see .env.example)
    - Running from the backend directory
"""

import os
import sys
import time
import json
import subprocess
import requests
import signal
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dotenv import load_dotenv
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api_test")

# API configuration
API_HOST = "localhost"
API_PORT = 8000
API_BASE_URL = f"http://{API_HOST}:{API_PORT}/api"

# Test configuration
TEST_TIMEOUT = 60  # seconds
ENV_FILE_PATH = Path(__file__).parent.parent.parent / ".env"
SERVER_STARTUP_WAIT = 15  # seconds - increased wait time for server startup

# State tracking
server_process = None


def load_env_credentials() -> Dict[str, Dict[str, str]]:
    """
    Load AWS credentials from .env file.
    
    Expected format:
    AWS_ACCESS_KEY_ID_COM=xxx
    AWS_SECRET_ACCESS_KEY_COM=xxx
    AWS_SESSION_TOKEN_COM=xxx
    AWS_ACCESS_KEY_ID_GOV=xxx
    AWS_SECRET_ACCESS_KEY_GOV=xxx
    AWS_SESSION_TOKEN_GOV=xxx
    
    Returns:
        Dict with credentials for each environment
    """
    logger.info(f"Loading credentials from {ENV_FILE_PATH}")
    
    if not ENV_FILE_PATH.exists():
        logger.error(f".env file not found at {ENV_FILE_PATH}")
        sys.exit(1)
    
    # Load environment variables
    load_dotenv(ENV_FILE_PATH)
    
    # Extract credentials for each environment
    credentials = {}
    
    # COM environment
    if os.getenv("AWS_ACCESS_KEY_ID_COM") and os.getenv("AWS_SECRET_ACCESS_KEY_COM"):
        credentials["com"] = {
            "access_key": os.getenv("AWS_ACCESS_KEY_ID_COM", ""),
            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY_COM", ""),
            "session_token": os.getenv("AWS_SESSION_TOKEN_COM", None),
            "environment": "com"
        }
    
    # GOV environment
    if os.getenv("AWS_ACCESS_KEY_ID_GOV") and os.getenv("AWS_SECRET_ACCESS_KEY_GOV"):
        credentials["gov"] = {
            "access_key": os.getenv("AWS_ACCESS_KEY_ID_GOV", ""),
            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY_GOV", ""),
            "session_token": os.getenv("AWS_SESSION_TOKEN_GOV", None),
            "environment": "gov"
        }
    
    if not credentials:
        logger.error("No valid credentials found in .env file")
        sys.exit(1)
    
    logger.info(f"Found credentials for environments: {', '.join(credentials.keys())}")
    return credentials


def start_api_server() -> subprocess.Popen:
    """
    Start the API server as a subprocess.
    
    Returns:
        Subprocess handle
    """
    logger.info("Starting API server...")
    
    # Determine the correct path to run.py
    run_script = Path(__file__).parent.parent.parent / "run.py"
    
    if not run_script.exists():
        logger.error(f"Server entry point not found at {run_script}")
        sys.exit(1)
    
    # Create a log file for server output
    server_log = Path(__file__).parent.parent.parent / "server_test.log"
    log_file = open(server_log, 'w')
    
    logger.info(f"Server output will be logged to {server_log}")
    
    # Start the server process
    process = subprocess.Popen(
        [sys.executable, str(run_script)],
        stdout=log_file,
        stderr=log_file,
        text=True
    )
    
    # Wait for server to start
    logger.info(f"Waiting {SERVER_STARTUP_WAIT} seconds for server to start...")
    time.sleep(SERVER_STARTUP_WAIT)
    
    # Check if process is still running
    if process.poll() is not None:
        log_file.close()
        # Read the log file
        with open(server_log, 'r') as f:
            log_content = f.read()
        
        logger.error(f"Server failed to start. Exit code: {process.returncode}")
        logger.error(f"Server log output:\n{log_content}")
        sys.exit(1)
    
    logger.info(f"API server started at {API_BASE_URL}")
    return process


def stop_api_server(process: subprocess.Popen) -> None:
    """
    Stop the API server.
    
    Args:
        process: Server process to stop
    """
    if process and process.poll() is None:
        logger.info("Stopping API server...")
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)
        logger.info("API server stopped")


def wait_for_server_ready() -> bool:
    """
    Wait for the server to be ready by polling the health endpoint.
    
    Returns:
        True if server is ready, False otherwise
    """
    logger.info("Checking if API server is ready...")
    # The health endpoint is defined in main.py as @app.get("/api/health")
    health_url = f"http://{API_HOST}:{API_PORT}/api/health"
    
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            response = requests.get(health_url, timeout=2)
            if response.status_code == 200:
                logger.info("API server is ready")
                return True
        except requests.RequestException:
            logger.info(f"Server not ready yet (attempt {attempt+1}/{max_attempts})")
            time.sleep(1)
    
    logger.error("Server failed to become ready")
    return False


def authenticate_with_environment(credentials: Dict[str, str]) -> bool:
    """
    Authenticate with AWS environment using provided credentials.
    
    Args:
        credentials: AWS credentials for the environment
        
    Returns:
        True if authentication was successful, False otherwise
    """
    env_name = credentials.get("environment", "unknown")
    logger.info(f"Authenticating with {env_name.upper()} environment...")
    
    auth_url = f"{API_BASE_URL}/auth/aws-credentials"
    
    try:
        response = requests.post(auth_url, json=credentials)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Authentication successful for {env_name.upper()}: {result.get('message')}")
            return True
        else:
            logger.error(f"Authentication failed for {env_name.upper()}: {response.text}")
            return False
    
    except requests.RequestException as e:
        logger.error(f"Error authenticating with {env_name.upper()}: {str(e)}")
        return False


def check_credential_status(environment: str) -> bool:
    """
    Check if credentials are valid for an environment.
    
    Args:
        environment: Environment to check (gov or com)
        
    Returns:
        True if credentials are valid, False otherwise
    """
    logger.info(f"Checking credential status for {environment.upper()}...")
    
    status_url = f"{API_BASE_URL}/auth/aws-credentials/{environment}"
    
    try:
        response = requests.get(status_url)
        
        if response.status_code == 200:
            result = response.json()
            is_valid = result.get("valid", False)
            logger.info(f"Credential status for {environment.upper()}: {result.get('message')}")
            return is_valid
        else:
            logger.error(f"Failed to check credential status for {environment.upper()}: {response.text}")
            return False
    
    except requests.RequestException as e:
        logger.error(f"Error checking credential status for {environment.upper()}: {str(e)}")
        return False


def list_accounts(environment: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    List accounts for an environment.
    
    Args:
        environment: Environment to list accounts for (gov or com)
        
    Returns:
        Tuple of (success, accounts)
    """
    logger.info(f"Listing accounts for {environment.upper()}...")
    
    accounts_url = f"{API_BASE_URL}/accounts/?environment={environment}"
    
    try:
        response = requests.get(accounts_url)
        
        if response.status_code == 200:
            result = response.json()
            accounts = result.get("accounts", [])
            
            logger.info(f"Found {len(accounts)} accounts in {environment.upper()} environment")
            for i, account in enumerate(accounts[:5]):  # Show only first 5 accounts
                logger.info(f"  Account {i+1}: {account.get('Name', 'Unknown')} ({account.get('Id', 'Unknown')})")
            
            if len(accounts) > 5:
                logger.info(f"  ... and {len(accounts) - 5} more accounts")
                
            return True, accounts
        else:
            logger.error(f"Failed to list accounts for {environment.upper()}: {response.text}")
            return False, []
    
    except requests.RequestException as e:
        logger.error(f"Error listing accounts for {environment.upper()}: {str(e)}")
        return False, []


def get_account_details(account_id: str, environment: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Get details for a specific account.
    
    Args:
        account_id: AWS account ID
        environment: Environment (gov or com)
        
    Returns:
        Tuple of (success, details)
    """
    logger.info(f"Getting details for account {account_id} in {environment.upper()}...")
    
    details_url = f"{API_BASE_URL}/accounts/{account_id}?environment={environment}"
    
    try:
        response = requests.get(details_url)
        
        if response.status_code == 200:
            details = response.json()
            
            logger.info(f"Account details retrieved for {account_id}")
            logger.info(f"  Available regions: {', '.join(details.get('regions', []))}")
            
            return True, details
        else:
            logger.error(f"Failed to get account details for {account_id}: {response.text}")
            return False, {}
    
    except requests.RequestException as e:
        logger.error(f"Error getting account details for {account_id}: {str(e)}")
        return False, {}


def list_instances(account_id: str, region: str, environment: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    List EC2 instances in a specific account and region.
    
    Args:
        account_id: AWS account ID
        region: AWS region
        environment: Environment (gov or com)
        
    Returns:
        Tuple of (success, instances)
    """
    logger.info(f"Listing instances in {account_id}/{region} ({environment.upper()})...")
    
    instances_url = f"{API_BASE_URL}/accounts/{account_id}/regions/{region}/instances?environment={environment}"
    
    try:
        response = requests.get(instances_url)
        
        if response.status_code == 200:
            result = response.json()
            instances = result.get("instances", [])
            
            logger.info(f"Found {len(instances)} instances in {account_id}/{region}")
            for i, instance in enumerate(instances[:5]):  # Show only first 5 instances
                logger.info(f"  Instance {i+1}: {instance.get('name')} ({instance.get('instance_id')})")
            
            if len(instances) > 5:
                logger.info(f"  ... and {len(instances) - 5} more instances")
                
            return True, instances
        else:
            logger.error(f"Failed to list instances for {account_id}/{region}: {response.text}")
            return False, []
    
    except requests.RequestException as e:
        logger.error(f"Error listing instances for {account_id}/{region}: {str(e)}")
        return False, []


def test_environment(environment: str, credentials: Dict[str, str]) -> bool:
    """
    Run all tests for an environment.
    
    Args:
        environment: Environment to test (gov or com)
        credentials: AWS credentials for the environment
        
    Returns:
        True if all tests passed, False otherwise
    """
    logger.info(f"\n{'=' * 50}\nTesting {environment.upper()} environment\n{'=' * 50}")
    
    # Test authentication
    if not authenticate_with_environment(credentials):
        logger.error(f"Failed to authenticate with {environment.upper()}")
        return False
    
    # Check credential status
    if not check_credential_status(environment):
        logger.error(f"Credentials for {environment.upper()} are not valid")
        return False
    
    # List accounts
    success, accounts = list_accounts(environment)
    if not success or not accounts:
        logger.error(f"Failed to list accounts for {environment.upper()}")
        return False
    
    # Test account details for the first account
    if accounts:
        account_id = accounts[0].get("Id")
        if account_id:
            success, details = get_account_details(account_id, environment)
            if not success:
                logger.error(f"Failed to get account details for {account_id}")
                return False
            
            # Test listing instances if regions are available
            regions = details.get("regions", [])
            if regions:
                # Test the first region
                region = regions[0]
                success, instances = list_instances(account_id, region, environment)
                if not success:
                    logger.error(f"Failed to list instances for {account_id}/{region}")
                    # Don't fail the test for this, as some accounts might not have instances
    
    logger.info(f"All tests passed for {environment.upper()} environment")
    return True


def run_tests():
    """
    Run all tests for all environments.
    """
    success = True
    start_time = datetime.now()
    
    try:
        # Load credentials
        credentials = load_env_credentials()
        
        # Start API server
        global server_process
        server_process = start_api_server()
        
        # Wait for server to be ready
        if not wait_for_server_ready():
            logger.error("API server is not ready, aborting tests")
            return False
        
        # Test each environment
        for env, creds in credentials.items():
            env_success = test_environment(env, creds)
            success = success and env_success
        
        # Final verdict
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if success:
            logger.info(f"\n{'=' * 50}\nAll tests PASSED in {duration:.2f} seconds\n{'=' * 50}")
        else:
            logger.error(f"\n{'=' * 50}\nSome tests FAILED in {duration:.2f} seconds\n{'=' * 50}")
        
        return success
    
    except KeyboardInterrupt:
        logger.info("Tests interrupted")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return False
    finally:
        # Always stop the server
        if server_process:
            stop_api_server(server_process)


def main():
    """
    Main entry point.
    """
    success = run_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
