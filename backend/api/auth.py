from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, Optional
import time
from pydantic import BaseModel

from backend.core.config import AWSCredentials
from backend.providers.aws.common.services.credential_manager import CredentialManager
from backend.providers.aws.common.services import credential_manager as cm_module
from typing import cast

# Cast the module to the actual class instance
cm = cast(CredentialManager, cm_module)

# Create router
router = APIRouter()


class CredentialRequest(BaseModel):
    """Request model for credential validation"""
    access_key: str
    secret_key: str
    session_token: Optional[str] = None
    environment: str
    expiration: Optional[int] = None


class CredentialResponse(BaseModel):
    """Response model for credential operations"""
    success: bool
    message: str
    environment: str
    expiration: Optional[float] = None
    expires_in_seconds: Optional[int] = None
    expires_in_minutes: Optional[float] = None
    temporary: Optional[bool] = None


@router.post("/aws-credentials", response_model=CredentialResponse)
def validate_aws_credentials(request: CredentialRequest) -> CredentialResponse:
    """
    Validate AWS credentials and store them for future use.
    
    This endpoint validates AWS credentials for a specific environment (gov or com)
    and stores them in memory for subsequent API calls.
    """
    success, message = cm.validate_credentials(
        access_key=request.access_key,
        secret_key=request.secret_key,
        session_token=request.session_token,
        environment=request.environment
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message
        )
    
    # Get the stored credentials to include expiration info
    creds = cm.get_credentials(request.environment)
    response = {
        "success": True,
        "message": message,
        "environment": request.environment
    }
    
    # Add expiration information if credentials exist
    expiration_value = None
    expires_in_seconds_value = None
    expires_in_minutes_value = None
    temporary_value = None
    
    if creds and creds.expiration is not None:
        now = time.time()
        seconds_remaining = max(0, creds.expiration - now)
        expiration_value = creds.expiration
        expires_in_seconds_value = int(seconds_remaining)
        expires_in_minutes_value = round(seconds_remaining / 60, 1)
        temporary_value = creds.session_token is not None
    
    return CredentialResponse(
        success=bool(response["success"]),
        message=str(response["message"]),
        environment=str(response["environment"]),
        expiration=expiration_value,
        expires_in_seconds=expires_in_seconds_value,
        expires_in_minutes=expires_in_minutes_value,
        temporary=temporary_value
    )


@router.get("/aws-credentials/{environment}", response_model=Dict[str, Any])
def get_aws_credential_status(environment: str) -> Dict[str, Any]:
    """
    Get status of AWS credentials for a specific environment.
    
    This endpoint checks if valid credentials exist for the specified environment
    and returns their expiration time if available.
    """
    is_valid = cm.are_credentials_valid(environment)
    creds = cm.get_credentials(environment) if is_valid else None
    
    response = {
        "environment": environment,
        "valid": is_valid,
        "message": f"Credentials for {environment} are {'valid' if is_valid else 'invalid or expired'}"
    }
    
    # Add expiration information if credentials exist
    if creds and creds.expiration is not None:
        now = time.time()
        seconds_remaining = max(0, creds.expiration - now)
        response.update({
            "expiration": creds.expiration,
            "expires_in_seconds": int(seconds_remaining),
            "expires_in_minutes": round(seconds_remaining / 60, 1),
            "temporary": creds.session_token is not None
        })
    
    return response


@router.delete("/aws-credentials/{environment}", response_model=Dict[str, Any])
def clear_aws_credentials(environment: str) -> Dict[str, Any]:
    """
    Clear AWS credentials for a specific environment.
    
    This endpoint removes stored credentials for the specified environment.
    """
    cm.clear_credentials(environment)
    
    return {
        "success": True,
        "message": f"Credentials for {environment} have been cleared"
    }


@router.get("/aws-credentials", response_model=Dict[str, Any])
def list_aws_credential_environments() -> Dict[str, Any]:
    """
    List all AWS credential environments and their validity status.
    
    This endpoint returns a list of all available environments and whether
    valid credentials exist for each.
    """
    environments = cm.list_active_environments()
    
    return {
        "environments": environments
    }


# The refresh endpoint has been removed as it's no longer needed.
# Credential validation now returns expiration information directly,
# allowing the frontend to manage credential lifecycles without a separate refresh endpoint.
