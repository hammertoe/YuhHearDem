"""Test API endpoints"""

import pytest
from fastapi.testclient import TestClient


class TestRootEndpoints:
    """Test root and health endpoints"""

    def test_root(self, client: TestClient):
        """Test root endpoint returns basic info"""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"

    def test_health_endpoint(self, client: TestClient):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "database_connected" in data
        assert "version" in data

    def test_api_info(self, client: TestClient):
        """Test API information endpoint"""
        response = client.get("/api")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "endpoints" in data
