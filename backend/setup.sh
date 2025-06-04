#!/bin/bash

echo "Setting up AWS Script Runner Backend..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create logs directory
echo "Creating logs directory..."
mkdir -p logs

echo "Setup complete! You can now run the backend with:"
echo "source venv/bin/activate && python run.py"
