"""Linux provider package

Auto-imports all tool subpackages so they can register themselves with the core application.
"""
from importlib import import_module
from pkgutil import iter_modules
import logging

logger = logging.getLogger(__name__)

# Auto-import all tool subpackages so they can register themselves
for mod in iter_modules(__path__):
    try:
        import_module(f"{__name__}.{mod.name}")
        logger.debug(f"Imported Linux tool: {mod.name}")
    except ImportError as e:
        logger.warning(f"Failed to import Linux tool {mod.name}: {e}")
