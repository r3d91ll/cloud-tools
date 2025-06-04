from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, Integer, DateTime, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

from backend.db.base import Base

# Handle circular imports
if TYPE_CHECKING:
    from backend.db.models.script import Script
    from backend.db.models.account import Instance


class Execution(Base):
    """Model for script execution records"""
    
    # Typed columns
    script_id: Mapped[int] = mapped_column(Integer, ForeignKey("script.id"), nullable=False)
    instance_id: Mapped[int] = mapped_column(Integer, ForeignKey("instance.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")  # pending, running, completed, failed
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    command_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # SSM command ID
    batch_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("executionbatch.id"), nullable=True)
    
    # Relationships
    script: Mapped["Script"] = relationship("Script", back_populates="executions")
    instance: Mapped["Instance"] = relationship("Instance", back_populates="executions")
    batch: Mapped[Optional["ExecutionBatch"]] = relationship("ExecutionBatch", back_populates="executions")
    
    def __repr__(self) -> str:
        return f"<Execution(id={self.id}, script_id={self.script_id}, instance_id={self.instance_id}, status='{self.status}')>"


class ExecutionBatch(Base):
    """Model for grouping multiple executions together"""
    
    # Typed columns
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")  # pending, running, completed, failed
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Store execution parameters
    
    # Relationships
    executions: Mapped[List["Execution"]] = relationship("Execution", back_populates="batch", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<ExecutionBatch(id={self.id}, name='{self.name}', status='{self.status}')>"
