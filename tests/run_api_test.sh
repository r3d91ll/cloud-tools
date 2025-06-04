#!/bin/bash
# Run the real-world API test script
# This script sets up the environment and runs the test

# Set the script to exit on error
set -e

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found"
    echo "Please create a .env file with AWS credentials (see .env.example)"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements if needed
if [ ! -f "venv/.requirements_installed" ]; then
    echo "Installing requirements..."
    pip install -r requirements.txt
    touch venv/.requirements_installed
fi

# Run the test
echo "Running API test..."
python tests/integration/test_api_real_world.py

# Exit with the same status code as the test
exit $?
