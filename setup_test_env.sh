#!/bin/bash
# Setup script for Jenkins MCP test environment

# Exit on error
set -e

echo "Setting up test environment for Jenkins MCP..."

# Create a fresh virtual environment
echo "Creating virtual environment..."
uv venv .venv

# Activate the virtual environment
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows
    source .venv/Scripts/activate
else
    # Unix-like
    source .venv/bin/activate
fi

# Install dependencies
echo "Installing dependencies..."
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt
uv pip install -e .

echo "Test environment setup complete!"
echo "To run tests, use: ./run_tests.sh"
