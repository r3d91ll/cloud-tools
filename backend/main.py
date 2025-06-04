from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Tuple, Any, Optional
import importlib
import pkgutil
import logging
from importlib import import_module

from backend.core.config import settings
from backend.db.base import Base
from backend.db.session import engine
from backend.api import auth, scripts, tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PCM-Ops Tools API",
    description="API for running operations across multiple cloud providers",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include core routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(scripts.router, prefix="/api/scripts", tags=["Scripts"])
app.include_router(tools.router, prefix="/api/tools", tags=["Tools"])

# Dynamically discover and include provider routers
def discover_provider_routers() -> Dict[str, List[Dict[str, Any]]]:
    """Discover and import all provider routers dynamically"""
    # Define providers to scan
    providers = ["aws", "azure", "gcp", "servicenow"]
    
    # Track discovered routers for the providers endpoint
    discovered_providers: Dict[str, List[Dict[str, Any]]] = {}
    
    for provider in providers:
        try:
            # Try to import the provider package
            provider_pkg = import_module(f"backend.providers.{provider}")
            logger.info(f"Discovered provider: {provider}")
            discovered_providers[provider] = []
            
            # Look for tools in this provider
            tools_path = provider_pkg.__path__
            for tool_mod in pkgutil.iter_modules(tools_path):
                tool_name = tool_mod.name
                
                # Skip the common module which isn't a tool
                if tool_name == "common":
                    continue
                    
                try:
                    # Import the tool module and check if it has routers
                    tool_pkg = import_module(f"backend.providers.{provider}.{tool_name}")
                    
                    if hasattr(tool_pkg, "routers"):
                        # Register all routers from this tool
                        for router, prefix in tool_pkg.routers:
                            tag = f"{provider.upper()} {tool_name.replace('_', ' ').title()}"
                            app.include_router(router, prefix=f"/api{prefix}", tags=[tag])
                            
                        # Add to discovered providers for the providers endpoint
                        tool_info = {
                            "name": tool_name,
                            "description": tool_pkg.__doc__.split('\n')[0] if tool_pkg.__doc__ else "",
                            "endpoints": [f"/api{prefix}" for _, prefix in tool_pkg.routers]
                        }
                        discovered_providers[provider].append(tool_info)
                        logger.info(f"Registered tool: {provider}.{tool_name}")
                except (ImportError, AttributeError) as e:
                    logger.warning(f"Could not load tool {provider}.{tool_name}: {e}")
        except ImportError as e:
            logger.debug(f"Provider {provider} not available: {e}")
    
    return discovered_providers

# Discover and import provider routers
provider_info = discover_provider_routers()

@app.get("/api/health")
def health_check() -> Dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/api/providers")
def list_providers() -> Dict[str, List[Dict[str, str]]]:
    """List all available providers and tools"""
    result: Dict[str, List[Dict[str, Any]]] = {"providers": []}
    
    # Convert the discovered provider info to the expected response format
    for provider_name, tools in provider_info.items():
        if tools:  # Only include providers with at least one tool
            provider_data = {
                "name": provider_name,
                "tools": tools
            }
            result["providers"].append(provider_data)
    
    return result
