from fastapi.testclient import TestClient
import sys
import os

# Add the api directory to the path so we can import from it
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../api')))

from main import app

client = TestClient(app)

def test_health_check():
    """Test that the API health endpoint is responding correctly."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}