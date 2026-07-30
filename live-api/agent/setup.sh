#!/bin/bash
# setup.sh - Setup virtual environment and install dependencies for physical-agent

set -e

# Get the directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

VENV_DIR=".venv"

echo "=== Physical Agent Setup ==="

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists."
fi

echo "Activating virtual environment..."
source "$VENV_DIR"/bin/activate

echo "Upgrading pip..."
pip install --index-url https://pypi.org/simple --upgrade pip

echo "Installing setuptools..."
pip install --index-url https://pypi.org/simple "setuptools>=61.0.0"

echo "Installing physical-agent in editable mode with dependencies..."
pip install --index-url https://pypi.org/simple --no-build-isolation -e .

echo "=== Setup Complete ==="
echo "To activate the virtual environment, run:"
echo "source .venv/bin/activate"
