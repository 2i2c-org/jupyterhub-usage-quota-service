"""
Tests for the main application
"""

import pytest

from jupyterhub_usage_quota_service.app.prometheus_client import PrometheusClient


class TestPrometheusClient:
    """
    Test the Prometheus client
    """

    @pytest.mark.asyncio
    async def test_get_user_usage_mock_data(self):
        """
        Test that get_user_usage returns mock data
        """
        client = PrometheusClient()
        usage_data = await client.get_user_usage("testuser")

        assert usage_data is not None
        assert usage_data["username"] == "testuser"
        assert "usage_bytes" in usage_data
        assert "quota_bytes" in usage_data
        assert "usage_gb" in usage_data
        assert "quota_gb" in usage_data
        assert "percentage" in usage_data

        # Check that mock data is reasonable
        assert usage_data["usage_bytes"] > 0
        assert usage_data["quota_bytes"] > 0
        assert 0 <= usage_data["percentage"] <= 100

        await client.close()

    @pytest.mark.asyncio
    async def test_prometheus_client_context_manager(self):
        """
        Test that PrometheusClient works as a context manager
        """
        async with PrometheusClient() as client:
            usage_data = await client.get_user_usage("testuser")
            assert usage_data is not None


def test_import():
    """
    Test that the package can be imported
    """
    import jupyterhub_usage_quota_service

    assert jupyterhub_usage_quota_service.__version__ == "0.1.0"
