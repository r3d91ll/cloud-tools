"""Test configuration and fixtures for pytest"""
import os
import sys
import pytest
from typing import Dict, Generator, Any
from pathlib import Path

import sqlalchemy
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Add the backend directory to sys.path to make app imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.main import app  # Updated to use backend module
from backend.db.base import Base
from backend.db.session import get_db
from backend.core.config import settings


# Create a test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_db.db"
engine = sqlalchemy.create_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """
    Create a clean database for each test and tear it down afterward.
    """
    # Create the test database and tables
    Base.metadata.create_all(bind=engine)
    
    # Create a new session for each test
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up after the test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """
    Create a FastAPI TestClient with the test database.
    """
    # Override the get_db dependency to use the test database
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    # Override the dependency in the app
    app.dependency_overrides[get_db] = override_get_db
    
    # Create a test client
    with TestClient(app) as client:
        yield client
    
    # Clean up dependency overrides
    app.dependency_overrides = {}


@pytest.fixture(scope="function")
def mock_aws_credentials() -> Dict[str, Any]:
    """
    Provide mock AWS credentials for testing.
    """
    return {
        "access_key": "test_access_key",
        "secret_key": "test_secret_key",
        "session_token": "test_session_token",
        "expiration": 9999999999,  # Far future timestamp
        "environment": "gov"
    }
