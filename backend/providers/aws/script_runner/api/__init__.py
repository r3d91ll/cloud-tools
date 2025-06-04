"""
AWS Script Runner API endpoints
"""
from fastapi import APIRouter

router = APIRouter()

# Import all API endpoints
from . import accounts, executions, aws_operations

# Export router for main app to discover
__all__ = ["router"]
