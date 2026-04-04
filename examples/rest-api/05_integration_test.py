#!/usr/bin/env python3
"""
Integration test example for planfile API.

This shows how to test your integration with planfile
using pytest and a test server.
"""

import pytest
import subprocess
import time
import signal
import sys
from pathlib import Path

# Try to import httpx, fallback to requests
try:
    import httpx
    Client = httpx.Client
except ImportError:
    import requests
    class Client:
        def __init__(self, base_url):
            self.base_url = base_url
            self.session = requests.Session()
        
        def request(self, method, url, **kwargs):
            full_url = f"{self.base_url}{url}"
            return self.session.request(method, full_url, **kwargs)
        
        def get(self, url, **kwargs):
            return self.request("GET", url, **kwargs)
        
        def post(self, url, **kwargs):
            return self.request("POST", url, **kwargs)
        
        def patch(self, url, **kwargs):
            return self.request("PATCH", url, **kwargs)
        
        def delete(self, url, **kwargs):
            return self.request("DELETE", url, **kwargs)


class TestPlanfileAPI:
    """Integration tests for planfile REST API."""
    
    @pytest.fixture(scope="class")
    def server(self):
        """Start test server."""
        # Check if server is already running
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', 8000))
            sock.close()
            
            if result == 0:
                # Server already running
                yield None
                return
        except:
            pass
        
        # Start server
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "planfile.api.server:app", "--port", "8001"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path.home())
        )
        
        # Wait for server
        time.sleep(3)
        
        yield proc
        
        # Cleanup
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
    
    @pytest.fixture
    def client(self, server):
        """Create API client."""
        port = 8000 if server is None else 8001
        return Client(f"http://localhost:{port}")
    
    def test_health_endpoint(self, client):
        """Test health check."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_create_and_get_ticket(self, client):
        """Test creating and retrieving a ticket."""
        # Create
        create_resp = client.post(
            "/tickets",
            json={
                "title": "Test Ticket",
                "description": "Test description",
                "priority": "high"
            }
        )
        assert create_resp.status_code == 201
        ticket = create_resp.json()
        assert ticket["title"] == "Test Ticket"
        
        # Get
        get_resp = client.get(f"/tickets/{ticket['id']}")
        assert get_resp.status_code == 200
        fetched = get_resp.json()
        assert fetched["id"] == ticket["id"]
    
    def test_update_ticket(self, client):
        """Test updating ticket."""
        # Create
        create_resp = client.post(
            "/tickets",
            json={"title": "Update Test", "priority": "low"}
        )
        ticket = create_resp.json()
        
        # Update
        update_resp = client.patch(
            f"/tickets/{ticket['id']}",
            json={"status": "in_progress", "priority": "critical"}
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["status"] == "in_progress"
        assert updated["priority"] == "critical"
    
    def test_list_tickets_with_filters(self, client):
        """Test listing with filters."""
        # Create tickets in different sprints
        client.post("/tickets", json={"title": "Sprint A", "sprint": "sprint-a"})
        client.post("/tickets", json={"title": "Sprint B", "sprint": "sprint-b"})
        
        # Filter
        resp = client.get("/tickets?sprint=sprint-a")
        assert resp.status_code == 200
        tickets = resp.json()
        assert all(t["sprint"] == "sprint-a" for t in tickets)
    
    def test_move_ticket(self, client):
        """Test moving ticket between sprints."""
        # Create
        create_resp = client.post(
            "/tickets",
            json={"title": "Move Test", "sprint": "source"}
        )
        ticket = create_resp.json()
        
        # Move
        move_resp = client.post(
            f"/tickets/{ticket['id']}/move?to_sprint=destination"
        )
        assert move_resp.status_code == 200
        
        # Verify
        get_resp = client.get(f"/tickets/{ticket['id']}")
        fetched = get_resp.json()
        assert fetched["sprint"] == "destination"


def run_tests():
    """Run integration tests."""
    print("Running integration tests...")
    print("Make sure planfile server is running on port 8000")
    print()
    
    # Run with pytest
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v"],
        cwd=str(Path(__file__).parent)
    )
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(run_tests())
