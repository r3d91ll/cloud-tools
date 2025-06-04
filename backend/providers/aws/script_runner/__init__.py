"""AWS Script Runner tool package

Exposes API routers and services for the AWS Script Runner tool.
"""
import logging

# Import API routers
try:
    from backend.providers.aws.script_runner.api import accounts, executions, org, aws_operations
    
    # Export routers for discovery
    routers = [
        (accounts.router, "/tools/aws/script-runner/accounts"),
        (executions.router, "/tools/aws/script-runner/executions"),
        (org.router, "/tools/aws/script-runner/org"),
        (aws_operations.router, "/tools/aws/script-runner/operations")
    ]
    
    logger = logging.getLogger(__name__)
    logger.info("AWS Script Runner API routers loaded successfully")
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to load AWS Script Runner API routers: {e}")
    routers = []
