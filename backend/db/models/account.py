from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, String, ForeignKey, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column

from backend.db.base import Base

# Handle circular imports
if TYPE_CHECKING:
    from backend.db.models.execution import Execution


class Account(Base):
    """Model for AWS accounts"""
    
    # Typed columns
    account_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    environment: Mapped[str] = mapped_column(String, nullable=False)  # "gov" or "com"
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    regions: Mapped[List["Region"]] = relationship("Region", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Account(id={self.id}, account_id='{self.account_id}', environment='{self.environment}')>"


class Region(Base):
    """Model for AWS regions associated with accounts"""
    
    # Typed columns
    name: Mapped[str] = mapped_column(String, nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("account.id"), nullable=False)
    
    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="regions")
    instances: Mapped[List["Instance"]] = relationship("Instance", back_populates="region", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Region(id={self.id}, name='{self.name}', account_id={self.account_id})>"


class Instance(Base):
    """Model for EC2 instances"""
    
    # Typed columns
    instance_id: Mapped[str] = mapped_column(String, nullable=False)
    region_id: Mapped[int] = mapped_column(Integer, ForeignKey("region.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)  # "linux" or "windows"
    
    # Relationships
    region: Mapped["Region"] = relationship("Region", back_populates="instances")
    executions: Mapped[List["Execution"]] = relationship("Execution", back_populates="instance", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Instance(id={self.id}, instance_id='{self.instance_id}', region_id={self.region_id})>"
