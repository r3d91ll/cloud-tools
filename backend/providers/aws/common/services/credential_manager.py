import time
from typing import Dict, Optional, Tuple, Union, cast, Any
import boto3
from botocore.exceptions import ClientError
from botocore.client import BaseClient
import logging

from backend.core.config import AWSCredentials, AWSEnvironment, settings

# For backward compatibility - aliasing AWSCredentials to CredentialSchema
CredentialSchema = AWSCredentials

# Configure environment-specific settings
ENV_CONFIGS = {
    "gov": {
        "region": "us-gov-west-1",
        "endpoint": "https://sts.us-gov-west-1.amazonaws.com",
    },
    "com": {
        "region": "us-east-1",
        "endpoint": "https://sts.us-east-1.amazonaws.com",
    }
}

logger = logging.getLogger(__name__)


class CredentialManager:
    """Service for managing AWS credentials"""
    
    def __init__(self, ttl_seconds: int = 3600):
        """Initialize the credential manager
        
        Args:
            ttl_seconds: Time-to-live for credentials in seconds
        """
        self.ttl_seconds = ttl_seconds
        self._credentials_cache: Dict[str, CredentialSchema] = {}
        
        # Load initial credentials from settings if available
        self._load_credentials_from_settings()
        
    def _load_credentials_from_settings(self) -> None:
        """Load initial credentials from application settings"""
        logger.debug("Loading credentials from application settings")
        
        # Check for available environments in settings
        available_envs = settings.get_available_environments()
        
        for env in available_envs:
            env_name = env.value
            logger.info(f"Found credentials for {env_name.upper()} in settings")
            
            # Get credentials from settings
            creds = settings.get_credentials(env)
            if creds:
                # Only create credentials if access_key and secret_key are not None
                if creds.access_key is not None and creds.secret_key is not None:
                    # Convert to CredentialSchema and store
                    schema_creds = CredentialSchema(
                        access_key=creds.access_key,
                        secret_key=creds.secret_key,
                        session_token=creds.session_token,
                        expiration=int(time.time() + self.ttl_seconds),  # Set initial expiration as int
                        environment=AWSEnvironment(env_name)  # Convert to enum
                    )
                    self.store_credentials(schema_creds)
    
    def _get_env_config(self, environment: str) -> Dict[str, str]:
        """Get environment configuration"""
        environment = environment.lower()
        if environment not in ENV_CONFIGS:
            raise ValueError(f"Invalid environment: {environment}")
        return ENV_CONFIGS[environment]
    
    def _check_expiry(self, creds: Optional[CredentialSchema]) -> bool:
        """Check if credentials have expired"""
        if not creds:
            logger.debug("No credentials found to check expiry")
            return True
        
        # Handle case when expiration is None
        if creds.expiration is None:
            logger.debug(f"No expiration set for {creds.environment} credentials")
            return False
            
        current_time = time.time()
        time_remaining = creds.expiration - current_time
        logger.debug(f"Checking expiry for {creds.environment} credentials. Time remaining: {time_remaining:.2f}s")
        
        # Add warning if credentials are about to expire
        if 0 < time_remaining <= 300:  # 5 minutes
            logger.warning(f"Credentials for {creds.environment} will expire in {time_remaining:.2f} seconds")
        
        is_expired = time_remaining <= 0
        if is_expired:
            logger.warning(f"Credentials for {creds.environment} have expired")
        
        return is_expired
    
    def store_credentials(self, credentials: CredentialSchema) -> None:
        """Store credentials for an environment"""
        logger.info(f"Storing credentials for {credentials.environment.upper()} environment")
        self._credentials_cache[credentials.environment.lower()] = credentials
        logger.debug(f"Credentials stored for {credentials.environment.upper()}")
    
    def get_credentials(self, environment: str) -> Optional[CredentialSchema]:
        """Get stored credentials if they exist and haven't expired"""
        environment = environment.lower()
        creds = self._credentials_cache.get(environment)
        
        if self._check_expiry(creds):
            self.clear_credentials(environment)
            return None
            
        return creds
    
    def validate_credentials(
        self, 
        access_key: str, 
        secret_key: str, 
        session_token: Optional[str] = None, 
        environment: str = "com"
    ) -> Tuple[bool, str]:
        """Validate AWS credentials and store if valid"""
        environment = environment.lower()
        logger.info(f"Validating credentials for {environment.upper()} environment")
        
        try:
            env_config = self._get_env_config(environment)
            logger.debug(f"Using endpoint: {env_config['endpoint']}")
            
            # Check if we already have valid credentials
            existing_creds = self.get_credentials(environment)
            if existing_creds and not self._check_expiry(existing_creds):
                logger.info(f"Using existing valid credentials for {environment.upper()}")
                return True, f"{environment.capitalize()} credentials already valid."
                
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token
            )
            
            sts = session.client(
                'sts',
                region_name=env_config['region'],
                endpoint_url=env_config['endpoint']
            )
            
            logger.debug("Attempting to get caller identity...")
            response = sts.get_caller_identity()
            
            # Try to determine the actual expiration time of these credentials
            try:
                # Check if these are temporary credentials from STS (handle both commercial and GovCloud ARN formats)
                arn = response.get('Arn', '')
                if (arn.startswith('arn:aws:sts:') or arn.startswith('arn:aws-us-gov:sts:')) and session_token:
                    # For temporary credentials, use get_session_token to find the real expiration
                    try:
                        # First, try a direct approach - get a fresh credential report from STS
                        # This is more reliable than trying to decode the token
                        logger.info("Querying STS directly for token expiration")
                        
                        # Create a new GetCallerIdentity call to check the token info
                        # Use sts:GetSessionToken to get actual token expiration
                        try:
                            # Try to use get-access-key-info to understand the credentials
                            logger.info("Checking get-access-key-info")
                            import subprocess
                            import json
                            import os
                            
                            # Save credentials to temp env vars
                            env = os.environ.copy()
                            env['AWS_ACCESS_KEY_ID'] = access_key
                            env['AWS_SECRET_ACCESS_KEY'] = secret_key
                            if session_token:
                                env['AWS_SESSION_TOKEN'] = session_token
                            
                            # Call AWS CLI to get credential details
                            result = subprocess.run(
                                ['aws', 'sts', 'get-caller-identity'],
                                capture_output=True,
                                text=True,
                                env=env
                            )
                            
                            logger.info(f"STS call completed with status: {result.returncode}")
                            
                            # Only proceed if this succeeded
                            if result.returncode == 0:
                                caller_identity = json.loads(result.stdout)
                                logger.info(f"Caller identity: {caller_identity}")
                                
                                # Try to get token expiration using aws sts get-access-key-info
                                logger.info("Getting actual token expiration")
                                
                                # For AWS temporary credentials, try to use AWS STS directly to get token info
                                # Use boto3 to directly decode session token info
                                import json
                                import base64
                                
                                # Determine remaining credential validity using boto3 introspection
                                # First try to get IAM info about the credentials
                                try:
                                    # Create IAM client
                                    iam = boto3.client(
                                        'iam',
                                        aws_access_key_id=access_key,
                                        aws_secret_access_key=secret_key,
                                        aws_session_token=session_token,
                                        region_name=env_config.get('region', 'us-east-1')
                                    )
                                    
                                    # Get user info which can indicate when credentials were created
                                    resp = iam.get_user()
                                    logger.info(f"IAM get_user response: {resp}")
                                    
                                    # Extract creation date from user info if available
                                    if 'User' in resp and 'CreateDate' in resp['User']:
                                        create_date = resp['User']['CreateDate']
                                        # Calculate approx remaining time (AWS temp creds typically last 12 hours)
                                        import datetime
                                        if isinstance(create_date, datetime.datetime):
                                            # Assume 12 hour validity from creation
                                            max_expiry = create_date + datetime.timedelta(hours=12)
                                            expiration = max_expiry.timestamp()
                                            logger.info(f"Estimated expiry from IAM create date: {expiration}")
                                except Exception as iam_error:
                                    logger.warning(f"Could not get IAM info: {iam_error}")
                                
                                # Next try parsing the session token directly
                                try:
                                    # Some AWS session tokens contain encoded expiration info
                                    # Try each segment of the token
                                    if session_token:
                                        logger.info("Attempting to decode session token")
                                        # Session tokens sometimes have base64-decodable sections
                                        parts = session_token.split('.')
                                        for i, part in enumerate(parts):
                                            try:
                                                # Add proper padding
                                                padding = 4 - (len(part) % 4) if len(part) % 4 else 0
                                                part_padded = part + ("=" * padding)
                                                decoded = base64.b64decode(part_padded)
                                                # Try to parse as JSON
                                                try:
                                                    data = json.loads(decoded)
                                                    logger.info(f"Decoded token part {i}: {data}")
                                                    # Look for expiration fields
                                                    if isinstance(data, dict):
                                                        for key in ['exp', 'expiration', 'expires']:
                                                            if key in data and isinstance(data[key], (int, float)):
                                                                exp_val = data[key]
                                                                # Ensure it's a reasonable future timestamp
                                                                if exp_val > time.time() and exp_val < time.time() + 86400:
                                                                    expiration = exp_val
                                                                    logger.info(f"Found explicit expiration in token: {expiration}")
                                                except json.JSONDecodeError:
                                                    # Not JSON, try to extract timestamps
                                                    import re
                                                    # Look for timestamps in the decoded data
                                                    timestamp_pattern = rb'\d{10,13}'
                                                    timestamps = re.findall(timestamp_pattern, decoded)
                                                    for ts in timestamps:
                                                        ts_val = int(ts[:10])  # Use first 10 digits as Unix timestamp
                                                        if ts_val > time.time() and ts_val < time.time() + 86400:
                                                            # If it's a future timestamp within 24 hours, it's likely expiry
                                                            expiration = ts_val
                                                            logger.info(f"Found timestamp in token binary data: {expiration}")
                                            except Exception as decode_error:
                                                logger.debug(f"Could not decode token part {i}: {decode_error}")
                                except Exception as token_parse_error:
                                    logger.warning(f"Error parsing token: {token_parse_error}")
                                
                                # If we haven't set expiration yet, use boto3's Session approach
                                if 'expiration' not in locals():
                                    # Fall back to boto3's Session credentials
                                    try:
                                        temp_session = boto3.Session(
                                            aws_access_key_id=access_key,
                                            aws_secret_access_key=secret_key,
                                            aws_session_token=session_token
                                        )
                                        
                                        # Get credentials from session
                                        credentials = temp_session._session.get_credentials()
                                        if hasattr(credentials, 'expiry_time'):
                                            # Convert from datetime to unix timestamp
                                            import datetime
                                            logger.info(f"Found expiry_time: {credentials.expiry_time}")
                                            if isinstance(credentials.expiry_time, datetime.datetime):
                                                expiration = credentials.expiry_time.timestamp()
                                                logger.info(f"Using expiration from boto3 Session: {expiration}")
                                            else:
                                                logger.warning("expiry_time is not a datetime object")
                                                # Default to 50 minutes remaining (assume tokens are 1hr and ~10min old)
                                                expiration = time.time() + 3000
                                        else:
                                            # If we can't get expiration from boto3, use a more conservative estimate
                                            logger.warning("Could not extract expiration from boto3 Session")
                                            # Assume 50 minutes remaining for already-created temp credentials
                                            expiration = time.time() + 3000
                                    except Exception as session_error:
                                        logger.warning(f"Error with boto3 Session: {session_error}")
                                        # Use a conservative default (50 minutes)
                                        expiration = time.time() + 3000
                            else:
                                logger.warning(f"AWS CLI call failed: {result.stderr}")
                                # Default to 1 hour for temporary credentials if we can't determine exactly
                                expiration = time.time() + 3600
                                
                        except Exception as subprocess_error:
                            logger.warning(f"Error using AWS CLI: {str(subprocess_error)}")
                            # Default to 1 hour for temporary credentials if we can't determine exactly
                            expiration = time.time() + 3600
                    except Exception as sts_error:
                        logger.warning(f"Error determining expiration from STS: {str(sts_error)}")
                        # Default to 1 hour for temporary credentials
                        expiration = time.time() + 3600
                else:
                    # These appear to be long-term credentials
                    logger.debug("Detected long-term credentials")
                    expiration = time.time() + self.ttl_seconds
            except Exception as e:
                logger.debug(f"Could not determine credential type: {str(e)}")
                # Fall back to default expiration
                expiration = time.time() + 1800  # Be conservative (30 minutes)
            
            # Store valid credentials
            self.store_credentials(CredentialSchema(
                access_key=access_key,
                secret_key=secret_key,
                session_token=session_token,
                expiration=int(expiration) if expiration is not None else None,
                environment=AWSEnvironment(environment)
            ))
            
            # Also update the settings model if possible
            if environment == "com":
                settings.AWS_ACCESS_KEY_ID_COM = access_key
                settings.AWS_SECRET_ACCESS_KEY_COM = secret_key
                settings.AWS_SESSION_TOKEN_COM = session_token
            elif environment == "gov":
                settings.AWS_ACCESS_KEY_ID_GOV = access_key
                settings.AWS_SECRET_ACCESS_KEY_GOV = secret_key
                settings.AWS_SESSION_TOKEN_GOV = session_token
            
            logger.info(f"Successfully validated {environment.upper()} credentials for account: {response['Account']}")
            return True, f"{environment.capitalize()} credentials validated successfully."
            
        except Exception as e:
            logger.error(f"Failed to validate {environment.upper()} credentials: {str(e)}")
            return False, f"Credential validation failed: {str(e)}"
    
    def clear_credentials(self, environment: str) -> None:
        """Clear stored credentials for an environment"""
        environment = environment.lower()
        logger.info(f"Clearing credentials for {environment.upper()}")
        
        # Remove from in-memory cache
        if environment in self._credentials_cache:
            del self._credentials_cache[environment]
        
        # Also clear from application settings
        if environment == "com":
            settings.AWS_ACCESS_KEY_ID_COM = None
            settings.AWS_SECRET_ACCESS_KEY_COM = None
            settings.AWS_SESSION_TOKEN_COM = None
            logger.info("Cleared COM credentials from application settings")
        elif environment == "gov":
            settings.AWS_ACCESS_KEY_ID_GOV = None
            settings.AWS_SECRET_ACCESS_KEY_GOV = None
            settings.AWS_SESSION_TOKEN_GOV = None
            logger.info("Cleared GOV credentials from application settings")
    
    def create_session(self, environment: str) -> Optional[boto3.Session]:
        """Create a boto3 session for an environment"""
        environment = environment.lower()
        creds = self.get_credentials(environment)
        
        # If no cached credentials, try to load from settings
        if not creds and (environment == "com" or environment == "gov"):
            # Try to get credentials from settings directly
            env_enum = AWSEnvironment.COM if environment == "com" else AWSEnvironment.GOV
            settings_creds = settings.get_credentials(env_enum)
            
            if settings_creds and settings_creds.access_key is not None and settings_creds.secret_key is not None:
                # Convert to CredentialSchema and cache
                creds = CredentialSchema(
                    access_key=settings_creds.access_key,
                    secret_key=settings_creds.secret_key,
                    session_token=settings_creds.session_token,
                    expiration=int(time.time() + self.ttl_seconds),
                    environment=AWSEnvironment(environment)
                )
                self.store_credentials(creds)
        
        if not creds:
            logger.error(f"No valid credentials found for {environment}")
            return None
            
        env_config = self._get_env_config(environment)
        return boto3.Session(
            aws_access_key_id=creds.access_key,
            aws_secret_access_key=creds.secret_key,
            aws_session_token=creds.session_token,
            region_name=env_config['region']
        )
    
    def create_client(self, service: str, environment: str, region: Optional[str] = None) -> Optional[BaseClient]:
        """Create a boto3 client for a service and environment"""
        environment = environment.lower()
        session = self.create_session(environment)
        if not session:
            return None
            
        env_config = self._get_env_config(environment)
        # Using type ignore here because boto3's client method has too many overloads
        # for mypy to match correctly, but we know this is safe at runtime
        client = session.client(  # type: ignore[call-overload]
            service_name=service,
            region_name=region or env_config['region']
        )
        return cast(BaseClient, client)
        
    def are_credentials_valid(self, environment: str) -> bool:
        """Check if valid credentials exist for an environment"""
        creds = self.get_credentials(environment)
        return creds is not None
    
    def list_active_environments(self) -> Dict[str, bool]:
        """List environments and their credential validity"""
        result = {}
        
        # Check all known environments
        for env in ENV_CONFIGS.keys():
            result[env] = self.are_credentials_valid(env)
        
        return result
        
    def refresh_credentials(self, environment: str, role_arn: Optional[str] = None) -> Tuple[bool, str, Optional[CredentialSchema]]:
        """Request fresh temporary credentials for an environment via STS
        
        Args:
            environment: AWS environment (gov or com)
            role_arn: Optional role ARN to assume
            
        Returns:
            Tuple containing:
              - success flag (bool)
              - message (str)
              - Optional credential schema if successful
        """
        environment = environment.lower()
        logger.info(f"Refreshing credentials for {environment.upper()} environment")
        
        # Check if environment is valid
        try:
            env_config = self._get_env_config(environment)
        except ValueError as e:
            return False, str(e), None
        
        # Get existing credentials
        existing_creds = self.get_credentials(environment)
        if not existing_creds:
            return False, f"No valid base credentials found for {environment}", None
            
        try:
            # Create session with existing credentials
            session = boto3.Session(
                aws_access_key_id=existing_creds.access_key,
                aws_secret_access_key=existing_creds.secret_key,
                aws_session_token=existing_creds.session_token
            )
            
            # Create STS client
            sts = session.client(
                'sts',
                region_name=env_config['region'],
                endpoint_url=env_config['endpoint']
            )
            
            if role_arn:
                logger.info(f"Assuming role {role_arn} for {environment.upper()} environment")
                # Assume role to get fresh credentials
                response = sts.assume_role(
                    RoleArn=role_arn,
                    RoleSessionName=f"API-Refresh-{int(time.time())}",
                    DurationSeconds=3600  # 1 hour
                )
                
                # Extract credentials
                credentials = response['Credentials']
                fresh_creds = CredentialSchema(
                    access_key=credentials['AccessKeyId'],
                    secret_key=credentials['SecretAccessKey'],
                    session_token=credentials['SessionToken'],
                    expiration=int(time.time() + 3600),  # 1 hour
                    environment=AWSEnvironment(environment)
                )
                
            else:
                try:
                    # Try to get a session token (only works with long-term credentials)
                    logger.info(f"Getting session token for {environment.upper()} environment")
                    response = sts.get_session_token(DurationSeconds=3600)
                    
                    # Extract credentials
                    credentials = response['Credentials']
                    fresh_creds = CredentialSchema(
                        access_key=response['Credentials']['AccessKeyId'],
                        secret_key=response['Credentials']['SecretAccessKey'],
                        session_token=response['Credentials']['SessionToken'],
                        expiration=int(time.time() + 3600),  # 1 hour
                        environment=AWSEnvironment(environment)
                    )
                except Exception as e:
                    if "with session credentials" in str(e):
                        # The credentials are already temporary - can't refresh with GetSessionToken
                        # Return the existing credentials with an explanatory message
                        return False, "Cannot refresh temporary credentials without assuming a role. Temporary credentials must be refreshed through your identity provider (e.g., AWS SSO).", existing_creds
                    else:
                        # Some other error occurred
                        raise
            
            # Store the fresh credentials
            self.store_credentials(fresh_creds)
            
            return True, f"Successfully refreshed credentials for {environment}", fresh_creds
            
        except Exception as e:
            logger.error(f"Failed to refresh {environment.upper()} credentials: {str(e)}")
            return False, f"Failed to refresh credentials: {str(e)}", None
