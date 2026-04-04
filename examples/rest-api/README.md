# REST API Examples

Examples of using planfile as a REST API server.

## Files

- `01_start_server.sh` - Start the FastAPI server
- `02_curl_examples.sh` - Basic curl commands for all endpoints
- `03_python_client.py` - Python client using httpx/requests
- `04_javascript_client.js` - JavaScript/Node.js client example
- `05_integration_test.py` - Integration test example

## Prerequisites

```bash
pip install planfile
pip install fastapi uvicorn
# For Python client examples
pip install httpx
```

## Quick Start

```bash
# 1. Start the server
./01_start_server.sh

# 2. In another terminal, run curl examples
./02_curl_examples.sh

# 3. Or use Python client
python 03_python_client.py
```

## Server Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/tickets` | List tickets (query: sprint, status) |
| POST | `/tickets` | Create ticket |
| GET | `/tickets/{id}` | Get single ticket |
| PATCH | `/tickets/{id}` | Update ticket |
| DELETE | `/tickets/{id}` | Delete ticket |
| POST | `/tickets/{id}/move` | Move to sprint (query: to_sprint) |
