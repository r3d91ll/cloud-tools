#!/usr/bin/env python3
"""
Script to update import statements in Python files to match the new directory structure.
"""
import os
import re
import sys
from pathlib import Path

# Import mappings - old import pattern to new import pattern
IMPORT_MAPPINGS = [
    # Core imports
    (r'from app\.core', r'from backend.core'),
    (r'import app\.core', r'import backend.core'),
    
    # DB imports
    (r'from app\.db', r'from backend.db'),
    (r'import app\.db', r'import backend.db'),
    
    # Schema imports - core
    (r'from app\.schemas\.script', r'from backend.core.schemas.script'),
    (r'import app\.schemas\.script', r'import backend.core.schemas.script'),
    
    # Schema imports - AWS script runner
    (r'from app\.schemas\.account', r'from backend.providers.aws.script_runner.schemas.account'),
    (r'import app\.schemas\.account', r'import backend.providers.aws.script_runner.schemas.account'),
    (r'from app\.schemas\.execution', r'from backend.providers.aws.script_runner.schemas.execution'),
    (r'import app\.schemas\.execution', r'import backend.providers.aws.script_runner.schemas.execution'),
    
    # AWS common services imports
    (r'from app\.services\.aws\.credential_manager', r'from backend.providers.aws.common.services.credential_manager'),
    (r'import app\.services\.aws\.credential_manager', r'import backend.providers.aws.common.services.credential_manager'),
    (r'from app\.services\.aws\.account_manager', r'from backend.providers.aws.common.services.account_manager'),
    (r'import app\.services\.aws\.account_manager', r'import backend.providers.aws.common.services.account_manager'),
    
    # AWS script runner services imports
    (r'from app\.services\.aws\.execution_state_manager', r'from backend.providers.aws.script_runner.services.execution_state_manager'),
    (r'import app\.services\.aws\.execution_state_manager', r'import backend.providers.aws.script_runner.services.execution_state_manager'),
    (r'from app\.services\.aws\.ssm_executor', r'from backend.providers.aws.script_runner.services.ssm_executor'),
    (r'import app\.services\.aws\.ssm_executor', r'import backend.providers.aws.script_runner.services.ssm_executor'),
    (r'from app\.services\.aws\.ec2_manager', r'from backend.providers.aws.script_runner.services.ec2_manager'),
    (r'import app\.services\.aws\.ec2_manager', r'import backend.providers.aws.script_runner.services.ec2_manager'),
    (r'from app\.services\.aws\.org_visitor', r'from backend.providers.aws.script_runner.services.org_visitor'),
    (r'import app\.services\.aws\.org_visitor', r'import backend.providers.aws.script_runner.services.org_visitor'),
    
    # API imports
    (r'from app\.api', r'from backend.api'),
    (r'import app\.api', r'import backend.api'),
    
    # Utils imports
    (r'from app\.utils', r'from backend.core.utils'),
    (r'import app\.utils', r'import backend.core.utils'),
]

def update_imports(file_path):
    """Update import statements in a single Python file."""
    with open(file_path, 'r') as file:
        content = file.read()
    
    original_content = content
    
    for old_pattern, new_pattern in IMPORT_MAPPINGS:
        content = re.sub(old_pattern, new_pattern, content)
    
    if content != original_content:
        with open(file_path, 'w') as file:
            file.write(content)
        return True
    return False

def main():
    """Main function to traverse the codebase and update imports."""
    base_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/home/todd/git/PCM-Ops_Tools/backend')
    updated_files = 0
    
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if update_imports(file_path):
                    print(f"Updated imports in {file_path}")
                    updated_files += 1
    
    print(f"Finished updating imports in {updated_files} files")

if __name__ == "__main__":
    main()
