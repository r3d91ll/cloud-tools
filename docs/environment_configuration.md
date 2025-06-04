# AWS Script Runner - Environment Configuration

This document explains how to configure different environments for the AWS Script Runner application.

## Environment Variables

The AWS Script Runner backend uses environment variables for configuration. These can be set in a `.env` file for development or through environment variables in production deployments.

### Core Configuration Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | None | Yes |
| `SECRET_KEY` | Secret key for token signing | None | Yes |
| `DEBUG` | Enable debug mode | `False` | No |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts | `localhost,127.0.0.1` | No |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |

### AWS Configuration Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AWS_REGION` | Default AWS region | `us-west-2` | Yes |
| `AWS_PROFILE` | AWS CLI profile name | `default` | No |
| `AWS_ACCESS_KEY_ID` | AWS access key ID | None | No* |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key | None | No* |
| `AWS_SESSION_TOKEN` | AWS session token | None | No* |
| `AWS_ROLE_ARN` | AWS IAM role ARN to assume | None | No |

*Either AWS profile or access key/secret must be provided.

### Database Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DB_HOST` | Database hostname | `localhost` | No* |
| `DB_PORT` | Database port | `5432` | No* |
| `DB_NAME` | Database name | `aws_script_runner` | No* |
| `DB_USER` | Database username | None | No* |
| `DB_PASSWORD` | Database password | None | No* |

*Not required if `DATABASE_URL` is provided.

### API Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `API_PREFIX` | API URL prefix | `/api/v1` | No |
| `TOKEN_EXPIRE_MINUTES` | Token expiration time in minutes | `60` | No |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins | `http://localhost:3000` | No |

## Environment Types

### Development Environment

For local development, create a `.env` file in the `backend` directory:

```
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost/aws_script_runner

# AWS
AWS_REGION=us-west-2
AWS_PROFILE=default

# Application
DEBUG=True
SECRET_KEY=development_secret_key
LOG_LEVEL=DEBUG
```

Or set individual database components:

```
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=aws_script_runner
DB_USER=postgres
DB_PASSWORD=postgres

# AWS
AWS_REGION=us-west-2
AWS_PROFILE=default

# Application
DEBUG=True
SECRET_KEY=development_secret_key
LOG_LEVEL=DEBUG
```

### Testing Environment

For automated testing:

```
# Database - Use SQLite for tests
DATABASE_URL=sqlite:///./test.db

# AWS
AWS_REGION=us-west-2
AWS_PROFILE=default

# Application
DEBUG=True
SECRET_KEY=testing_secret_key
LOG_LEVEL=INFO
TESTING=True
```

### Staging Environment

For staging environments:

```
# Database
DATABASE_URL=postgresql://user:password@staging-db.example.com/aws_script_runner

# AWS
AWS_REGION=us-west-2
AWS_ROLE_ARN=arn:aws:iam::123456789012:role/ScriptRunnerRole

# Application
DEBUG=False
SECRET_KEY=staging_secret_key
LOG_LEVEL=INFO
ALLOWED_HOSTS=staging.example.com,localhost
```

### Production Environment

For production environments:

```
# Database
DATABASE_URL=postgresql://user:password@production-db.example.com/aws_script_runner

# AWS
AWS_REGION=us-west-2
AWS_ROLE_ARN=arn:aws:iam::123456789012:role/ScriptRunnerRole

# Application
DEBUG=False
SECRET_KEY=your_secure_production_key
LOG_LEVEL=WARNING
ALLOWED_HOSTS=api.example.com,www.example.com
CORS_ORIGINS=https://app.example.com
```

## AWS IAM Configuration

### Required IAM Permissions

The application requires the following AWS IAM permissions:

1. **EC2 Permissions**:
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Action": [
                   "ec2:DescribeInstances",
                   "ec2:DescribeInstanceStatus"
               ],
               "Resource": "*"
           }
       ]
   }
   ```

2. **SSM Permissions**:
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Action": [
                   "ssm:SendCommand",
                   "ssm:GetCommandInvocation",
                   "ssm:CancelCommand"
               ],
               "Resource": "*"
           }
       ]
   }
   ```

3. **STS Permissions** (for cross-account access):
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Action": [
                   "sts:AssumeRole"
               ],
               "Resource": "arn:aws:iam::*:role/ScriptRunnerRole"
           }
       ]
   }
   ```

### Example IAM Role for Production

Create a role named `ScriptRunnerRole` with the following trust relationship:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::123456789012:role/ECSTaskExecutionRole"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

Attach the required policy permissions to this role.

## Environment-Specific AWS Account Setup

### Development/Testing

For development and testing environments:
- Use a non-production AWS account
- Create IAM users with appropriate permissions
- Configure AWS profiles locally

### Staging/Production

For staging and production environments:
- Use separate AWS accounts for isolation
- Implement cross-account role assumption
- Store AWS credentials securely (e.g., AWS Secrets Manager)
- Restrict IAM permissions to minimum required

## Database Configuration

### Database Migration

When migrating between environments:

1. Generate migration scripts:
   ```bash
   alembic revision --autogenerate -m "Migration description"
   ```

2. Apply migrations:
   ```bash
   alembic upgrade head
   ```

### Connection Pooling

For production environments, configure database connection pooling:

```python
# In database settings
engine = create_engine(
    DATABASE_URL,
    pool_size=10,  # Maximum connections in pool
    max_overflow=20,  # Maximum overflow connections
    pool_timeout=30,  # Connection timeout in seconds
    pool_recycle=1800  # Recycle connections after 30 minutes
)
```

## Logging Configuration

Configure logging based on environment:

```python
import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log") if not os.getenv("TESTING") else logging.NullHandler()
    ]
)
```

## Security Configuration

### CORS Settings

Configure CORS settings for frontend integration:

```python
from fastapi.middleware.cors import CORSMiddleware

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### JWT Authentication

Configure JWT token settings:

```python
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", 60))
```

## Performance Tuning

### Worker Configuration

For production deployments, configure Gunicorn workers:

```bash
# Start with workers based on CPU cores
gunicorn -w $(( 2 * $(nproc) + 1 )) -k uvicorn.workers.UvicornWorker app.main:app
```

### Cache Configuration

Set up Redis caching for frequently accessed data:

```
# Redis cache settings
REDIS_HOST=redis.example.com
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_redis_password
```

## Troubleshooting Environment Issues

### Common Configuration Problems

1. **Database Connection Issues**
   - Check DATABASE_URL format
   - Verify network connectivity
   - Ensure database user has proper permissions

2. **AWS Credential Problems**
   - Verify IAM permissions
   - Check credential expiration
   - Test with AWS CLI: `aws sts get-caller-identity`

3. **Environment Variable Loading Issues**
   - Verify .env file location
   - Check for syntax errors in .env file
   - Ensure environment variables are properly exported in production
