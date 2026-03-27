#!/bin/bash
# Unified example runner for planfile
# This script is a wrapper around the 'planfile examples run --all' command

# Check if planfile is installed
if ! command -v planfile &> /dev/null; then
    echo "❌ planfile command not found. Please install it first:"
    echo "  pip install -e ."
    exit 1
fi

# Run all examples
planfile examples run --all
