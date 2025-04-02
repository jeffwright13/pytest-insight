# This is a realistic API testing module that simulates testing a RESTful API
import json
import random
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.exceptions import ConnectionError, Timeout

# Mock API base URL
API_BASE_URL = "https://api.example.com/v1"

# Fixtures for API testing
@pytest.fixture
def api_client():
    """Create a configured API client with auth headers."""
    session = requests.Session()
    session.headers.update({
        "Authorization": "Bearer mock-token-for-testing",
        "Content-Type": "application/json",
        "Accept": "application/json"
    })
    return session

@pytest.fixture
def mock_user_data():
    """Generate mock user data for testing."""
    user_id = f"user_{random.randint(1000, 9999)}"
    return {
        "id": user_id,
        "username": f"testuser_{user_id}",
        "email": f"{user_id}@example.com",
        "created_at": datetime.now().isoformat(),
        "status": random.choice(["active", "inactive", "pending"])
    }

# Fast tests that should always pass
def test_api_get_user(api_client, mock_user_data):
    """Test retrieving a user by ID."""
    with patch.object(api_client, 'get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_user_data

        # Simulate realistic API call duration
        time.sleep(0.05)

        response = api_client.get(f"{API_BASE_URL}/users/{mock_user_data['id']}")

        assert response.status_code == 200
        assert response.json()["id"] == mock_user_data["id"]
        assert response.json()["username"] == mock_user_data["username"]

def test_api_list_users(api_client):
    """Test listing all users with pagination."""
    with patch.object(api_client, 'get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "data": [{"id": f"user_{i}", "username": f"user_{i}"} for i in range(1, 11)],
            "page": 1,
            "per_page": 10,
            "total": 42
        }

        # Simulate realistic API call duration - slightly longer for list endpoint
        time.sleep(0.12)

        response = api_client.get(f"{API_BASE_URL}/users?page=1&per_page=10")

        assert response.status_code == 200
        assert len(response.json()["data"]) == 10
        assert response.json()["total"] == 42

# Slow test that occasionally times out
def test_api_search_users(api_client):
    """Test searching users with complex criteria."""
    with patch.object(api_client, 'get') as mock_get:
        # Randomly simulate a timeout about 10% of the time
        if random.random() < 0.1:
            mock_get.side_effect = Timeout("Request timed out after 5 seconds")
            time.sleep(0.3)  # Simulate a slow request that times out
            pytest.fail("API request timed out")

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "data": [{"id": f"user_{i}", "username": f"user_{i}"} for i in range(1, 5)],
            "page": 1,
            "per_page": 10,
            "total": 4
        }

        # Simulate a complex search that takes longer
        time.sleep(0.25)

        response = api_client.get(
            f"{API_BASE_URL}/users/search?query=active&role=admin&department=engineering"
        )

        assert response.status_code == 200
        assert "data" in response.json()

# Test with authentication failures
def test_api_create_user_auth(api_client, mock_user_data):
    """Test creating a new user with authentication edge cases."""
    # Simulate auth token expiration randomly (about 15% of the time)
    if random.random() < 0.15:
        with patch.object(api_client, 'post') as mock_post:
            mock_post.return_value.status_code = 401
            mock_post.return_value.json.return_value = {
                "error": "Authentication failed",
                "message": "Token expired or invalid"
            }

            time.sleep(0.08)

            response = api_client.post(f"{API_BASE_URL}/users", json=mock_user_data)

            # This should fail with auth error
            assert response.status_code == 401
            pytest.fail("Authentication token expired")
    else:
        with patch.object(api_client, 'post') as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = mock_user_data

            time.sleep(0.15)

            response = api_client.post(f"{API_BASE_URL}/users", json=mock_user_data)

            assert response.status_code == 201
            assert response.json()["id"] == mock_user_data["id"]

# Flaky test that fails intermittently due to rate limiting
def test_api_batch_operations(api_client):
    """Test batch operations that might hit rate limits."""
    # Simulate rate limiting errors randomly (about 20% of the time)
    if random.random() < 0.2:
        with patch.object(api_client, 'post') as mock_post:
            mock_post.return_value.status_code = 429
            mock_post.return_value.json.return_value = {
                "error": "Too Many Requests",
                "message": "Rate limit exceeded. Try again in 30 seconds."
            }

            time.sleep(0.18)

            batch_data = {"operations": [{"type": "create", "data": {"username": f"batch_user_{i}"}} for i in range(10)]}
            response = api_client.post(f"{API_BASE_URL}/batch", json=batch_data)

            # This should fail with rate limit error
            assert response.status_code != 429, "Rate limit exceeded"
    else:
        with patch.object(api_client, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "success": True,
                "operations_completed": 10,
                "operations_failed": 0
            }

            # Batch operations take longer
            time.sleep(0.3)

            batch_data = {"operations": [{"type": "create", "data": {"username": f"batch_user_{i}"}} for i in range(10)]}
            response = api_client.post(f"{API_BASE_URL}/batch", json=batch_data)

            assert response.status_code == 200
            assert response.json()["success"] is True
            assert response.json()["operations_completed"] == 10

# Test that occasionally fails due to server errors
def test_api_update_user(api_client, mock_user_data):
    """Test updating user information."""
    # Simulate random server errors (about 8% of the time)
    if random.random() < 0.08:
        with patch.object(api_client, 'put') as mock_put:
            mock_put.return_value.status_code = 500
            mock_put.return_value.json.return_value = {
                "error": "Internal Server Error",
                "message": "An unexpected error occurred"
            }

            time.sleep(0.1)

            user_id = mock_user_data["id"]
            update_data = {"status": "inactive"}
            response = api_client.put(f"{API_BASE_URL}/users/{user_id}", json=update_data)

            # This should fail with server error
            assert response.status_code != 500, "Server error occurred"
    else:
        with patch.object(api_client, 'put') as mock_put:
            mock_put.return_value.status_code = 200
            updated_data = mock_user_data.copy()
            updated_data["status"] = "inactive"
            mock_put.return_value.json.return_value = updated_data

            time.sleep(0.07)

            user_id = mock_user_data["id"]
            update_data = {"status": "inactive"}
            response = api_client.put(f"{API_BASE_URL}/users/{user_id}", json=update_data)

            assert response.status_code == 200
            assert response.json()["status"] == "inactive"

# Test with network connectivity issues
def test_api_delete_user(api_client, mock_user_data):
    """Test deleting a user account."""
    # Simulate connectivity issues (about 5% of the time)
    if random.random() < 0.05:
        with patch.object(api_client, 'delete') as mock_delete:
            mock_delete.side_effect = ConnectionError("Connection refused")

            time.sleep(0.05)

            user_id = mock_user_data["id"]

            # This should raise a connection error
            with pytest.raises(ConnectionError):
                api_client.delete(f"{API_BASE_URL}/users/{user_id}")
                pytest.fail("Connection error occurred")
    else:
        with patch.object(api_client, 'delete') as mock_delete:
            mock_delete.return_value.status_code = 204

            time.sleep(0.06)

            user_id = mock_user_data["id"]
            response = api_client.delete(f"{API_BASE_URL}/users/{user_id}")

            assert response.status_code == 204

# Dependent tests to show correlation
@pytest.mark.dependency()
def test_api_user_login():
    """Test user login endpoint."""
    # This test will pass 90% of the time
    if random.random() < 0.1:
        time.sleep(0.1)
        pytest.fail("Login service unavailable")

    time.sleep(0.08)
    assert True

@pytest.mark.dependency(depends=["test_api_user_login"])
def test_api_user_profile():
    """Test user profile endpoint (depends on login)."""
    # This will be skipped if login fails
    time.sleep(0.05)
    assert True

@pytest.mark.dependency(depends=["test_api_user_profile"])
def test_api_user_preferences():
    """Test user preferences endpoint (depends on profile)."""
    # This will be skipped if profile fails
    time.sleep(0.07)
    assert True
