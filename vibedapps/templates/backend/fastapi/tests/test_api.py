import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"

def test_get_contract_info():
    """Test the contract info endpoint"""
    response = client.get("/api/contract/info")
    assert response.status_code == 200
    data = response.json()
    assert "address" in data

# Add more tests as needed
