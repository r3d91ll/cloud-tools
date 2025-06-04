from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import AnyHttpUrl, Field, validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AWSEnvironment(str, Enum):
    """Enum for AWS environments"""
    COM = "com"
    GOV = "gov"


class AWSCredentials(BaseSettings):
    """Settings model for AWS credentials"""
    access_key: str
    secret_key: str
    session_token: Optional[str] = None  # Optional for non-STS credentials
    expiration: Optional[int] = None
    environment: AWSEnvironment
    assumed_role: Optional[str] = None  # ARN of assumed role if using STS
    
    @validator('environment', pre=True)
    def validate_environment(cls, v):
        """Convert string environment to enum if needed"""
        if isinstance(v, str):
            return AWSEnvironment(v)
        return v
        
    @validator('expiration', pre=True)
    def validate_expiration(cls, v):
        """Convert float expiration to int if needed"""
        if isinstance(v, float):
            return int(v)
        return v
    
    class Config:
        extra = "allow"


class Settings(BaseSettings):
    PROJECT_NAME: str = "AWS Script Runner API"
    API_V1_STR: str = "/api"
    
    # BACKEND_CORS_ORIGINS is a comma-separated list of origins
    # e.g: "http://localhost,http://localhost:4200,http://localhost:3000"
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database settings
    SQLITE_DATABASE_URI: str = "sqlite:///./data/aws_script_runner.db"
    
    # AWS Settings
    AWS_SESSION_DURATION: int = 3600  # 1 hour
    AWS_REGIONS_GOV: List[str] = ["us-gov-west-1", "us-gov-east-1"]
    AWS_REGIONS_COM: List[str] = ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]
    
    # AWS Credentials for COM environment
    AWS_ACCESS_KEY_ID_COM: Optional[str] = None
    AWS_SECRET_ACCESS_KEY_COM: Optional[str] = None
    AWS_SESSION_TOKEN_COM: Optional[str] = None
    
    # AWS Credentials for GOV environment
    AWS_ACCESS_KEY_ID_GOV: Optional[str] = None
    AWS_SECRET_ACCESS_KEY_GOV: Optional[str] = None
    AWS_SESSION_TOKEN_GOV: Optional[str] = None
    
    # Script execution settings
    MAX_CONCURRENT_EXECUTIONS: int = 5
    EXECUTION_TIMEOUT: int = 1800  # 30 minutes
    
    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="allow"  # Allow extra fields in settings
    )
    
    def get_credentials(self, environment: AWSEnvironment) -> Optional[AWSCredentials]:
        """Get credentials for a specific environment"""
        env = environment.value.upper()
        
        if environment == AWSEnvironment.COM:
            if not self.AWS_ACCESS_KEY_ID_COM or not self.AWS_SECRET_ACCESS_KEY_COM:
                return None
                
            return AWSCredentials(
                access_key=self.AWS_ACCESS_KEY_ID_COM,
                secret_key=self.AWS_SECRET_ACCESS_KEY_COM,
                session_token=self.AWS_SESSION_TOKEN_COM,
                environment=AWSEnvironment.COM
            )
            
        elif environment == AWSEnvironment.GOV:
            if not self.AWS_ACCESS_KEY_ID_GOV or not self.AWS_SECRET_ACCESS_KEY_GOV:
                return None
                
            return AWSCredentials(
                access_key=self.AWS_ACCESS_KEY_ID_GOV,
                secret_key=self.AWS_SECRET_ACCESS_KEY_GOV,
                session_token=self.AWS_SESSION_TOKEN_GOV,
                environment=AWSEnvironment.GOV
            )
            
        return None
    
    def get_available_environments(self) -> List[AWSEnvironment]:
        """Get list of environments with available credentials"""
        environments = []
        
        if self.AWS_ACCESS_KEY_ID_COM and self.AWS_SECRET_ACCESS_KEY_COM:
            environments.append(AWSEnvironment.COM)
            
        if self.AWS_ACCESS_KEY_ID_GOV and self.AWS_SECRET_ACCESS_KEY_GOV:
            environments.append(AWSEnvironment.GOV)
            
        return environments


settings = Settings()
