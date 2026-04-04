#!/bin/bash
# Run all REST API examples

set -e

echo "=========================================="
echo "Planfile REST API Examples"
echo "=========================================="
echo

cd "$(dirname "$0")"

# Check dependencies
if ! python3 -c "import planfile" 2>/dev/null; then
    echo "Installing planfile..."
    pip install planfile
fi

if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "Installing FastAPI..."
    pip install fastapi uvicorn
fi

echo "1. Starting server in background..."
./01_start_server.sh &
SERVER_PID=$!

# Wait for server
sleep 3

cleanup() {
    echo
    echo "Stopping server..."
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
}
trap cleanup EXIT

echo "2. Running curl examples..."
./02_curl_examples.sh

echo
echo "3. Running Python client examples..."
python3 03_python_client.py

echo
echo "=========================================="
echo "All REST API examples completed!"
echo "=========================================="
