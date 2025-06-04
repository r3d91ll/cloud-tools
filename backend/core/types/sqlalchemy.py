"""Type definitions for SQLAlchemy models"""
from typing import Any, TypeVar, Generic, Type, cast, Optional, List, Dict, Union, Protocol
from datetime import datetime

from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import Session, Query
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text, ForeignKey

# Define type variables for generic typing
T = TypeVar('T')
ModelType = TypeVar('ModelType')

# SQLAlchemy Column types
ColumnInt = Union[Column[int], int]
ColumnStr = Union[Column[str], str]
ColumnBool = Union[Column[bool], bool]
ColumnDateTime = Union[Column[datetime], datetime]
ColumnJSON = Union[Column[Dict[str, Any]], Dict[str, Any]]
ColumnText = Union[Column[str], str]

# Type for SQL filter conditions
FilterType = Dict[str, Any]

class ModelProtocol(Protocol):
    """Protocol for SQLAlchemy models"""
    id: ColumnInt
    
    @classmethod
    def query(cls) -> Query:
        ...
        
class CRUDBase(Generic[ModelType]):
    """Base class for CRUD operations"""
    
    def __init__(self, model: Type[ModelType]):
        """Initialize with SQLAlchemy model class"""
        self.model = model
        
    def get(self, db: Session, id: int) -> Optional[ModelType]:
        """Get a model instance by ID"""
        # Use type ignore for dynamic attribute access - model classes will have an id attribute
        result = db.query(self.model).filter(self.model.id == id).first()  # type: ignore[attr-defined]
        # Use explicit cast to fix the return type
        return cast(Optional[ModelType], result)
        
    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Get multiple model instances with pagination"""
        result = db.query(self.model).offset(skip).limit(limit).all()
        # Use explicit cast to fix the return type
        return cast(List[ModelType], result)
        
    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> ModelType:
        """Create a model instance"""
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
        
    def update(
        self, db: Session, *, db_obj: ModelType, obj_in: Dict[str, Any]
    ) -> ModelType:
        """Update a model instance"""
        for field in obj_in:
            if obj_in[field] is not None:
                setattr(db_obj, field, obj_in[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
        
    def remove(self, db: Session, id: int) -> ModelType:
        """Delete a model instance"""
        obj = db.query(self.model).get(id)
        if obj is None:
            raise ValueError(f"Object with ID {id} not found")
        db.delete(obj)
        db.commit()
        # Use explicit cast to fix the return type
        return cast(ModelType, obj)
