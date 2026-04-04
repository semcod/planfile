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

# Find available port starting from 8000
PORT=${1:-8000}
while netstat -tuln 2>/dev/null | grep -q ":$PORT " || ss -tuln 2>/dev/null | grep -q ":$PORT "; do
    echo "Port $PORT is in use, trying next..."
    PORT=$((PORT + 1))
    if [ $PORT -gt 8010 ]; then
        echo "Could not find available port between 8000-8010"
        exit 1
    fi
done

echo "Starting server on port $PORT..."
echo "API will be available at: http://localhost:$PORT"
echo "Health check: http://localhost:$PORT/health"
echo "Press Ctrl+C to stop"
echo

# Save port for other scripts
echo $PORT > /tmp/planfile_server_port

# Start server
uvicorn planfile.api.server:app \
    --reload \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level info
