#!/bin/bash
# Cleanup script for Jenkins MCP test environment

echo "Cleaning up test environment for Jenkins MCP..."

# Remove pytest cache
if [ -d ".pytest_cache" ]; then
    echo "Removing pytest cache..."
    rm -rf .pytest_cache
fi

# Remove __pycache__ directories
echo "Removing __pycache__ directories..."
find . -type d -name "__pycache__" -exec rm -rf {} +

# Remove .pyc files
echo "Removing .pyc files..."
find . -name "*.pyc" -delete

# Remove coverage data
if [ -f ".coverage" ]; then
    echo "Removing coverage data..."
    rm -f .coverage
fi

if [ -d "htmlcov" ]; then
    echo "Removing HTML coverage report..."
    rm -rf htmlcov
fi

echo "Cleanup complete! To set up a fresh environment, use: ./setup_test_env.sh"
