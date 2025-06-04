# AWS Script Runner - Backend API

## Architecture Overview

This is the backend API for the AWS Script Runner service. It provides a RESTful API for managing and executing scripts on AWS EC2 instances across multiple accounts and regions.

### Key Features

- Stateless REST API with FastAPI
- SQLite database for persistent storage with SQLAlchemy 2.0-style type annotations
- AWS credentials management
- Script storage and versioning
- EC2 instance discovery and filtering
- Script execution via AWS Systems Manager (SSM)
- Extensible tooling interface
- Comprehensive unit and integration tests

## Directory Structure

```
backend/
├── app/                    # Main application package
│   ├── api/                # API endpoints
│   │   ├── accounts.py     # AWS account management 
│   │   ├── auth.py         # Authentication endpoints
│   │   ├── executions.py   # Script execution endpoints
│   │   ├── scripts.py      # Script management
│   │   └── tools.py        # Tool registry and interface
│   ├── core/               # Core application code
│   │   ├── config.py       # App configuration
│   ├── db/                 # Database models and operations
│   │   ├── models/         # SQLAlchemy models
│   │   ├── base.py         # Base database model
│   │   └── session.py      # Database session management
│   ├── schemas/            # Pydantic models (API schemas)
│   ├── services/           # Business logic services
│   │   ├── aws/            # AWS-specific services
│   └── main.py             # FastAPI app entry point
├── run.py                  # Application entry point
├── setup.sh                # Setup script
└── requirements.txt        # Dependencies
```

## Setup Instructions

1. Make sure you have Python 3.8+ installed
2. Run the setup script:

```bash
cd backend
chmod +x setup.sh
./setup.sh
```

3. Start the API server:

```bash
source venv/bin/activate
python run.py
```

4. Access the API documentation at http://localhost:8000/docs

## API Endpoints

### Authentication

- `POST /api/auth/aws-credentials` - Validate and store AWS credentials
- `GET /api/auth/aws-credentials/{environment}` - Check credential status
- `DELETE /api/auth/aws-credentials/{environment}` - Clear credentials

### AWS Accounts

- `GET /api/accounts` - List AWS accounts
- `GET /api/accounts/{account_id}` - Get account details
- `GET /api/accounts/{account_id}/regions/{region}/instances` - List instances

### Scripts

- `GET /api/scripts` - List all scripts
- `POST /api/scripts` - Create a new script
- `GET /api/scripts/{script_id}` - Get a specific script
- `PUT /api/scripts/{script_id}` - Update a script
- `DELETE /api/scripts/{script_id}` - Delete a script

### Executions

- `POST /api/executions` - Execute a script on an instance
- `GET /api/executions` - List all executions
- `GET /api/executions/{execution_id}` - Get execution details
- `GET /api/executions/{execution_id}/status` - Check execution status
- `POST /api/executions/batch` - Create a batch execution

### Tools

- `GET /api/tools` - List available tools
- `GET /api/tools/{tool_id}` - Get tool details
- `POST /api/tools/{tool_id}/execute` - Execute a tool

## Development

- The API is built with FastAPI
- Database models use SQLAlchemy ORM with SQLAlchemy 2.0-style type annotations
- API schemas use Pydantic models
- Background tasks use FastAPI background tasks

## Testing

### Running Tests

```bash
cd backend
python -m pytest
```

Run with coverage report:

```bash
cd backend
python -m pytest --cov=app tests/
```

### Test Types

- **Unit Tests**: Test individual components in isolation (e.g., services)
- **Integration Tests**: Test API endpoints with mocked services

### Test Organization

```
tests/
├── conftest.py        # Test fixtures and configuration
├── unit/              # Unit tests
│   ├── test_credential_manager.py
│   └── test_models.py
└── integration/       # Integration tests
    ├── test_auth_api.py
    ├── test_accounts_api.py
    ├── test_scripts_api.py
    └── test_executions_api.py
```
