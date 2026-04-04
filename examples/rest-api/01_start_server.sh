#!/bin/bash
# Start the planfile REST API server

set -e

echo "=========================================="
echo "Starting Planfile REST API Server"
echo "=========================================="
echo

# Check dependencies
if ! python3 -c "import planfile" 2>/dev/null; then
    echo "Installing planfile..."
    pip install planfile
fi

if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "Installing FastAPI..."
    pip install fastapi uvicorn
fi

# Default port
PORT=${1:-8000}

echo "Starting server on port $PORT..."
echo "API will be available at: http://localhost:$PORT"
echo "Health check: http://localhost:$PORT/health"
echo
echo "Press Ctrl+C to stop"
echo

# Start server
uvicorn planfile.api.server:app \
    --reload \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level info
