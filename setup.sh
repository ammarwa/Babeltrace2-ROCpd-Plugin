#!/bin/bash

# Setup script for ROCm Babeltrace2 Plugin

set -e

echo "Setting up ROCm Babeltrace2 Plugin..."

# Check if we're on macOS or Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "Detected macOS"
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "Homebrew not found. Please install Homebrew first:"
        echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    
    # Install babeltrace2
    echo "Installing babeltrace2..."
    brew install babeltrace2
    
    # Check if Python babeltrace2 bindings are available
    if ! python3 -c "import bt2" &> /dev/null; then
        echo "Warning: Python babeltrace2 bindings not found."
        echo "You may need to install them manually or use a different method."
        echo "Try: pip3 install babeltrace2"
    fi
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "Detected Linux"
    
    # Check distribution
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        echo "Installing babeltrace2 (Debian/Ubuntu)..."
        sudo apt-get update
        sudo apt-get install -y babeltrace2 python3-babeltrace2
        
    elif command -v yum &> /dev/null; then
        # Red Hat/CentOS/Fedora
        echo "Installing babeltrace2 (Red Hat/CentOS/Fedora)..."
        sudo yum install -y babeltrace2 python3-babeltrace2
        
    elif command -v pacman &> /dev/null; then
        # Arch Linux
        echo "Installing babeltrace2 (Arch Linux)..."
        sudo pacman -S babeltrace2 python-babeltrace2
        
    else
        echo "Unsupported Linux distribution. Please install babeltrace2 manually."
        exit 1
    fi
    
else
    echo "Unsupported operating system: $OSTYPE"
    echo "Please install babeltrace2 manually."
    exit 1
fi

# Test babeltrace2 installation
echo "Testing babeltrace2 installation..."
if ! command -v babeltrace2 &> /dev/null; then
    echo "Error: babeltrace2 command not found"
    exit 1
fi

# Test Python bindings
echo "Testing Python babeltrace2 bindings..."
if ! python3 -c "import bt2; print('bt2 version:', bt2.__version__)" 2>/dev/null; then
    echo "Warning: Python babeltrace2 bindings not working properly"
    echo "The plugin may not work correctly."
else
    echo "Python babeltrace2 bindings are working!"
fi

# Create a test database
echo "Creating test database..."
python3 test_rocm_plugin.py

echo ""
echo "Setup complete!"
echo ""
echo "To test the plugin:"
echo "1. Run: python3 test_rocm_plugin.py"
echo "2. Use the generated database file with babeltrace2"
echo ""
echo "Example usage:"
echo "babeltrace2 --plugin-path=. -c source.rocm.RocmSource --params='db-path=/tmp/test.db' -c sink.text.pretty"
