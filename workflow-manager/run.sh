#!/bin/bash
# Run script for Workflow Manager

set -e

# Change to script directory
cd "$(dirname "$0")"

# Install dependencies
echo "Installing dependencies..."
uv sync

# Run the application
echo "Starting Workflow Manager..."
uv run python -m workflow_manager
