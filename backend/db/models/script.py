from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, Integer, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column

from backend.db.base import Base

# Handle circular imports
if TYPE_CHECKING:
    from backend.db.models.execution import Execution


class Script(Base):
    """Model for scripts that can be executed on AWS instances"""
    
    # Typed columns
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    script_type: Mapped[str] = mapped_column(String, nullable=False)  # "bash", "powershell", etc.
    tool_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tool.id"), nullable=True)
    
    # Relationships
    tool: Mapped[Optional["Tool"]] = relationship("Tool", back_populates="scripts")
    executions: Mapped[List["Execution"]] = relationship("Execution", back_populates="script", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Script(id={self.id}, name='{self.name}', script_type='{self.script_type}')>"


class Tool(Base):
    """Model for tools that can be associated with scripts"""
    
    # Typed columns
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_type: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # OS platform: linux, windows, etc.
    script_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Path to the script file
    
    # Relationships
    scripts: Mapped[List["Script"]] = relationship("Script", back_populates="tool")
    
    def __repr__(self) -> str:
        return f"<Tool(id={self.id}, name='{self.name}', tool_type='{self.tool_type}')>"
