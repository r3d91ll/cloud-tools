"""
Helper functions for ensuring type safety with mypy.
"""
from typing import Any, List, Optional, TypeVar, cast, Sequence, TypeVar, Union

T = TypeVar('T')
U = TypeVar('U')

def safe_str(value: Optional[Any]) -> str:
    """
    Convert a value to string safely, with explicit cast for mypy.
    
    Args:
        value: Value to convert to string
        
    Returns:
        String representation of value, or empty string if None
    """
    if value is None:
        return ""  # Return empty string instead of None
    return str(value)

def safe_list(value: Optional[List[T]]) -> List[T]:
    """
    Ensure a list is never None for mypy.
    
    Args:
        value: List to make safe
        
    Returns:
        Original list or empty list if None
    """
    if value is None:
        return []
    return value

def safe_int(value: Any) -> int:
    """
    Ensure a value is an integer for mypy.
    
    Args:
        value: Value to convert to int
        
    Returns:
        Integer value, or 0 if None or conversion fails
    """
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
        
def safe_sqlalchemy_in(value: Optional[Sequence[U]]) -> List[U]:
    """
    Create a safe list for SQLAlchemy in_() operations that won't cause mypy errors.
    
    Args:
        value: A sequence (list, tuple, etc.) or None
        
    Returns:
        A list guaranteed to be non-None for SQLAlchemy in_() operations
    """
    # Return an empty list if None which will work with SQLAlchemy's in_()
    if value is None:
        return []
    # Convert to list to ensure it's the expected type
    return list(value)
