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

# Run the application
python main.py -i