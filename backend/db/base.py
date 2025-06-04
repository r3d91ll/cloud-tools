from typing import Any, ClassVar, Annotated
from sqlalchemy import Integer, String, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry
from sqlalchemy.ext.declarative import declared_attr

# Define naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
mapper_registry = registry(metadata=metadata)


class Base(DeclarativeBase):
    """Base class for all database models."""
    
    # Use the mapper registry
    registry = mapper_registry
    metadata = metadata
    
    # Tablename is automatically derived from the class name
    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
    
    # Common columns for all models
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
