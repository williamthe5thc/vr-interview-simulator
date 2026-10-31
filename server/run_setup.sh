#!/bin/bash
# Setup script for VR Interview System (Linux/macOS)

echo "Setting up VR Interview System..."
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3.9 or higher"
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python $python_version is installed, but Python $required_version or higher is required"
    exit 1
fi

# Run the setup script
echo "Running setup script..."
python3 setup.py "$@"

if [ $? -ne 0 ]; then
    echo
    echo "Setup failed"
    exit 1
fi

echo
echo "Setup completed successfully!"
echo
echo "To start the server, run: ./run_server.sh"
echo
