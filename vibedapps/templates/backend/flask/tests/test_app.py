import json
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_check(client):
    """Test the health check endpoint"""
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'

def test_get_contract_info(client):
    """Test the contract info endpoint"""
    response = client.get('/api/contract/info')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'address' in data['data']

# Add more tests as needed
