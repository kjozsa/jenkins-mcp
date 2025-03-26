#!/bin/bash
# Script to run tests for Jenkins MCP

# Set script to exit on any error
set -e

# Check if we have a virtual environment, if not create one
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment with uv..."
    uv venv
fi

# Use the virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate || source .venv/Scripts/activate

# Make sure dev dependencies are installed
echo "Installing development dependencies..."
uv pip install -r requirements.txt -r requirements-dev.txt

# Check for coverage flag
if [ "$1" == "--coverage" ] || [ "$2" == "--coverage" ]; then
    echo "Running tests with coverage..."

    # If a specific test file is provided
    if [ -n "$1" ] && [ "$1" != "--coverage" ]; then
        python -m pytest -v "$1" --cov=jenkins_mcp --cov-report=term
    else
        python -m pytest -v --cov=jenkins_mcp --cov-report=term
    fi

    # Generate HTML report if requested
    if [ "$2" == "--html" ] || [ "$3" == "--html" ]; then
        python -m pytest --cov=jenkins_mcp --cov-report=html
        echo "HTML coverage report generated in htmlcov/ directory"
    fi
else
    # Run all tests by default
    if [ -z "$1" ]; then
        echo "Running all tests..."
        python -m pytest -v
    else
        # Run specific tests if provided
        echo "Running tests in $1..."
        python -m pytest -v "$1"
    fi
fi
