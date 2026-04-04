#!/bin/bash
# Run all Python API examples

set -e

echo "=========================================="
echo "Planfile Python API Examples"
echo "=========================================="
echo

cd "$(dirname "$0")"

# Check if planfile is installed
if ! python3 -c "import planfile" 2>/dev/null; then
    echo "Installing planfile..."
    pip install planfile
fi

echo "Running examples..."
echo

python3 01_basic_usage.py
python3 02_ticket_management.py
python3 03_integration.py
python3 04_advanced_filtering.py

echo
echo "=========================================="
echo "All examples completed!"
echo "=========================================="
