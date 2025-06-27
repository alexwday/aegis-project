#!/bin/bash

# AEGIS Setup Script
# This script sets up the AEGIS Financial Market Data Assistant

echo "🚀 Setting up AEGIS Financial Market Data Assistant..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Found Python $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install the package in development mode
echo "📚 Installing AEGIS and dependencies..."
pip install -e .

# Check if installation was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 AEGIS setup completed successfully!"
    echo ""
    echo "To run AEGIS:"
    echo "1. Activate the virtual environment: source venv/bin/activate"
    echo "2. Start the server: python start_server.py"
    echo "3. Open your browser to: http://localhost:8000"
    echo ""
    echo "Or simply run: python start_server.py (virtual environment will be activated automatically)"
    echo ""
    echo "📖 See README.md for more detailed instructions and usage examples."
else
    echo "❌ Installation failed. Please check the error messages above."
    exit 1
fi