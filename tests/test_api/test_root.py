"""Test API endpoints"""

import pytest
from httpx import AsyncClient


class TestRootEndpoints:
    """Test root and health endpoints"""

    async def test_root(self, client: AsyncClient):
        """Test root endpoint returns basic info"""
        response = await client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"

    async def test_health_endpoint(self, client: AsyncClient):
        """Test health check endpoint"""
        response = await client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "database_connected" in data
        assert "version" in data

    async def test_api_info(self, client: AsyncClient):
        """Test API information endpoint"""
        response = await client.get("/api")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "endpoints" in data
