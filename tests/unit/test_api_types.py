"""Tests for API type definitions"""
import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.types.api import (
    PaginationParams,
    StatusResponse,
    ErrorResponse,
    ItemListResponse,
    TokenData
)

class TestPaginationParams:
    """Test class for PaginationParams"""
    
    def test_init_default_values(self):
        """Test initialization with default values"""
        params = PaginationParams()
        assert params.skip == 0
        assert params.limit == 100
    
    def test_init_custom_values(self):
        """Test initialization with custom values"""
        params = PaginationParams(skip=10, limit=50)
        assert params.skip == 10
        assert params.limit == 50

class TestStatusResponse:
    """Test class for StatusResponse"""
    
    def test_model_validation_success(self):
        """Test successful model validation"""
        response = StatusResponse(success=True, message="Operation successful")
        assert response.success is True
        assert response.message == "Operation successful"
    
    def test_model_dict_conversion(self):
        """Test conversion to dictionary"""
        response = StatusResponse(success=True, message="Operation successful")
        response_dict = response.dict()
        
        assert isinstance(response_dict, dict)
        assert response_dict["success"] is True
        assert response_dict["message"] == "Operation successful"

class TestErrorResponse:
    """Test class for ErrorResponse"""
    
    def test_model_validation_required_fields(self):
        """Test model validation with required fields"""
        response = ErrorResponse(error="Not Found", status_code=404)
        assert response.error == "Not Found"
        assert response.detail is None
        assert response.status_code == 404
    
    def test_model_validation_all_fields(self):
        """Test model validation with all fields"""
        response = ErrorResponse(
            error="Not Found", 
            detail="Resource with id 123 not found",
            status_code=404
        )
        assert response.error == "Not Found"
        assert response.detail == "Resource with id 123 not found"
        assert response.status_code == 404
    
    def test_model_dict_conversion(self):
        """Test conversion to dictionary"""
        response = ErrorResponse(
            error="Bad Request", 
            detail="Invalid input data",
            status_code=400
        )
        response_dict = response.dict()
        
        assert isinstance(response_dict, dict)
        assert response_dict["error"] == "Bad Request"
        assert response_dict["detail"] == "Invalid input data"
        assert response_dict["status_code"] == 400

class TestItemListResponse:
    """Test class for ItemListResponse"""
    
    def test_model_validation(self):
        """Test model validation"""
        # Create a list of simple items
        items = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        
        response = ItemListResponse(items=items, total=2, skip=0, limit=10)
        assert response.items == items
        assert response.total == 2
        assert response.skip == 0
        assert response.limit == 10
    
    def test_model_dict_conversion(self):
        """Test conversion to dictionary"""
        items = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        
        response = ItemListResponse(items=items, total=2, skip=0, limit=10)
        response_dict = response.dict()
        
        assert isinstance(response_dict, dict)
        assert response_dict["items"] == items
        assert response_dict["total"] == 2
        assert response_dict["skip"] == 0
        assert response_dict["limit"] == 10

class TestTokenData:
    """Test class for TokenData"""
    
    def test_model_validation_minimal(self):
        """Test model validation with minimal fields"""
        now = datetime.utcnow()
        exp = now + timedelta(hours=1)
        
        token_data = TokenData(
            sub="user123",
            exp=exp,
            iat=now
        )
        
        assert token_data.sub == "user123"
        assert token_data.exp == exp
        assert token_data.iat == now
        assert token_data.scope == []
    
    def test_model_validation_with_scope(self):
        """Test model validation with scope"""
        now = datetime.utcnow()
        exp = now + timedelta(hours=1)
        
        token_data = TokenData(
            sub="user123",
            exp=exp,
            iat=now,
            scope=["read", "write"]
        )
        
        assert token_data.sub == "user123"
        assert token_data.exp == exp
        assert token_data.iat == now
        assert token_data.scope == ["read", "write"]
    
    def test_model_dict_conversion(self):
        """Test conversion to dictionary"""
        now = datetime.utcnow()
        exp = now + timedelta(hours=1)
        
        token_data = TokenData(
            sub="user123",
            exp=exp,
            iat=now,
            scope=["read", "write"]
        )
        
        token_dict = token_data.dict()
        
        assert isinstance(token_dict, dict)
        assert token_dict["sub"] == "user123"
        assert token_dict["exp"] == exp
        assert token_dict["iat"] == now
        assert token_dict["scope"] == ["read", "write"]
