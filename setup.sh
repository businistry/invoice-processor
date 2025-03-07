#!/bin/bash

# Install system dependencies
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  # Ubuntu/Debian
  sudo apt-get update
  sudo apt-get install -y libjpeg-dev libpoppler-cpp-dev poppler-utils
elif [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  brew install poppler
else
  echo "Please install Poppler manually for your OS"
  echo "For Windows, download from: https://blog.alivate.com.au/poppler-windows/"
fi

# Install Python dependencies
pip install -r requirements.txt

# Check if --web flag is passed
if [[ "$1" == "--web" ]]; then
  echo "Starting Invoice Pro web application..."
  python run.py
else
  # Run the CLI application
  echo "Starting Invoice Pro command-line application..."
  python main.py -i
fi