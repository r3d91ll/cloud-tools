from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    """Enum for execution status values"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionBase(BaseModel):
    """Base schema for Execution"""
    script_id: int = Field(..., description="ID of the script to execute")
    instance_id: int = Field(..., description="ID of the instance to run the script on")


class ExecutionCreate(ExecutionBase):
    """Schema for creating an Execution"""
    parameters: Optional[Dict[str, Any]] = Field(None, description="Optional parameters for script execution")


class Execution(ExecutionBase):
    """Schema for Execution response"""
    id: int
    status: ExecutionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    output: Optional[str] = None
    exit_code: Optional[int] = None
    command_id: Optional[str] = None
    
    class Config:
        from_attributes = True


class ExecutionList(BaseModel):
    """Schema for listing Executions"""
    executions: List[Execution]
    total: int
    
    class Config:
        from_attributes = True


class ExecutionBatchBase(BaseModel):
    """Base schema for ExecutionBatch"""
    name: str = Field(..., description="Batch name")
    description: Optional[str] = Field(None, description="Batch description")


class ExecutionBatchCreate(ExecutionBatchBase):
    """Schema for creating an ExecutionBatch"""
    script_id: int = Field(..., description="ID of the script to execute")
    instance_ids: List[int] = Field(..., description="List of instance IDs to run the script on")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Optional parameters for script execution")


class ExecutionBatch(ExecutionBatchBase):
    """Schema for ExecutionBatch response"""
    id: int
    status: ExecutionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    parameters: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class ExecutionProgress(BaseModel):
    """Schema for execution progress"""
    total_instances: int
    completed_instances: int
    failed_instances: int
    pending_instances: int
    overall_status: ExecutionStatus
