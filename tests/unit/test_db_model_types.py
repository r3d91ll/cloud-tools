"""Tests for database model types"""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from backend.db.models.types import ModelType

class TestModelType:
    """Test class for ModelType"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create a mock model class that inherits from ModelType
        class MockModel(ModelType):
            id = 1
            name = "test"
            
            def __init__(self, id=1, name="test"):
                self.id = id
                self.name = name
        
        self.MockModel = MockModel
        
        # Mock database session
        self.db = MagicMock(spec=Session)
        
        # Set up mock query results
        self.mock_instance = MockModel()
        self.mock_instances = [MockModel(id=1, name="test1"), MockModel(id=2, name="test2")]
    
    def test_get_by_id(self):
        """Test get_by_id method"""
        # Configure mock
        mock_query = self.db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = self.mock_instance
        
        # Call method
        result = self.MockModel.get_by_id(self.db, 1)
        
        # Verify
        self.db.query.assert_called_once_with(self.MockModel)
        mock_query.filter.assert_called_once()
        mock_filter.first.assert_called_once()
        
        assert result is self.mock_instance
        assert result.id == 1
        assert result.name == "test"
    
    def test_get_all(self):
        """Test get_all method"""
        # Configure mock
        mock_query = self.db.query.return_value
        mock_query.all.return_value = self.mock_instances
        
        # Call method
        result = self.MockModel.get_all(self.db)
        
        # Verify
        self.db.query.assert_called_once_with(self.MockModel)
        mock_query.all.assert_called_once()
        
        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2
    
    def test_filter(self):
        """Test filter method"""
        # Configure mock
        mock_query = self.db.query.return_value
        mock_filter_by = mock_query.filter_by.return_value
        mock_filter_by.all.return_value = [self.mock_instance]
        
        # Call method
        result = self.MockModel.filter(self.db, name="test")
        
        # Verify
        self.db.query.assert_called_once_with(self.MockModel)
        mock_query.filter_by.assert_called_once_with(name="test")
        mock_filter_by.all.assert_called_once()
        
        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].name == "test"
    
    def test_first(self):
        """Test first method"""
        # Configure mock
        mock_query = self.db.query.return_value
        mock_filter_by = mock_query.filter_by.return_value
        mock_filter_by.first.return_value = self.mock_instance
        
        # Call method
        result = self.MockModel.first(self.db, name="test")
        
        # Verify
        self.db.query.assert_called_once_with(self.MockModel)
        mock_query.filter_by.assert_called_once_with(name="test")
        mock_filter_by.first.assert_called_once()
        
        assert result is self.mock_instance
        assert result.id == 1
        assert result.name == "test"
