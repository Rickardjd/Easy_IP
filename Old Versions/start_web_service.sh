#!/bin/bash

echo "========================================"
echo "Camera Monitor Web Service - Quick Start"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.7 or higher"
    exit 1
fi

echo "Python version:"
python3 --version
echo ""

# Check if Flask is installed
if ! python3 -c "import flask" &> /dev/null; then
    echo "Flask not found. Installing dependencies..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        exit 1
    fi
fi

echo "Checking required files..."

# Check for required files
if [ ! -f "Easy_IP_3.py" ]; then
    echo "ERROR: Easy_IP_3.py not found"
    echo "Please ensure all files are in the same directory"
    exit 1
fi

if [ ! -f "camera_tracker.py" ]; then
    echo "ERROR: camera_tracker.py not found"
    echo "Please ensure all files are in the same directory"
    exit 1
fi

if [ ! -f "templates/index.html" ]; then
    echo "ERROR: templates/index.html not found"
    echo "Please ensure the templates folder exists"
    exit 1
fi

echo ""
echo "All checks passed!"
echo ""
echo "Starting web service..."
echo "Open your browser to: http://localhost:5000"
echo "Press Ctrl+C to stop the service"
echo ""
echo "========================================"
echo ""

python3 camera_web_service.py
