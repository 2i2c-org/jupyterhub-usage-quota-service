"""
Tests for the main application
"""

from unittest.mock import AsyncMock, patch

import pytest

from jupyterhub_usage_quota_service.app.prometheus_client import PrometheusClient

# Sample Prometheus response matching the real API structure from notes/README.md
SAMPLE_QUOTA_RESPONSE = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314029.985, "214748364800"],
            },
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "staging",
                    "username": "testuser",
                },
                "value": [1771314029.985, "10737418240"],
            },
        ],
    },
}

SAMPLE_USAGE_RESPONSE = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314216.003, "6615040"],
            },
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "staging",
                    "username": "testuser",
                },
                "value": [1771314216.003, "243240960"],
            },
        ],
    },
}


class TestPrometheusClientMockFallback:
    """Test mock data fallback when PROMETHEUS_NAMESPACE is not set"""

    @pytest.mark.asyncio
    @patch("jupyterhub_usage_quota_service.app.prometheus_client.random.choice", return_value=0.50)
    async def test_get_user_usage_returns_mock_50_percent(self, mock_choice):
        client = PrometheusClient()
        client.namespace = ""
        usage_data = await client.get_user_usage("testuser")

        assert usage_data["username"] == "testuser"
        assert usage_data["percentage"] == 50.0
        assert "last_updated" in usage_data
        assert "error" not in usage_data

        await client.close()

    @pytest.mark.asyncio
    @patch("jupyterhub_usage_quota_service.app.prometheus_client.random.choice", return_value=0.95)
    async def test_get_user_usage_returns_mock_95_percent(self, mock_choice):
        client = PrometheusClient()
        client.namespace = ""
        usage_data = await client.get_user_usage("testuser")

        assert usage_data["username"] == "testuser"
        assert usage_data["percentage"] == 95.0
        assert "last_updated" in usage_data
        assert "error" not in usage_data

        await client.close()

    @pytest.mark.asyncio
    @patch(
        "jupyterhub_usage_quota_service.app.prometheus_client.random.choice",
        return_value="error",
    )
    async def test_get_user_usage_returns_mock_error(self, mock_choice):
        client = PrometheusClient()
        client.namespace = ""
        usage_data = await client.get_user_usage("testuser")

        assert usage_data["username"] == "testuser"
        assert "error" in usage_data

        await client.close()

    @pytest.mark.asyncio
    @patch("jupyterhub_usage_quota_service.app.prometheus_client.random.choice", return_value=0.50)
    async def test_context_manager(self, mock_choice):
        async with PrometheusClient() as client:
            client.namespace = ""
            usage_data = await client.get_user_usage("testuser")
            assert usage_data is not None


class TestParseQueryResult:
    """Test the _parse_query_result helper"""

    def test_parses_correct_namespace(self):
        client = PrometheusClient()
        client.namespace = "staging"
        result = client._parse_query_result(SAMPLE_QUOTA_RESPONSE)

        assert result is not None
        value_bytes, timestamp = result
        assert value_bytes == 10737418240
        assert timestamp.year == 2026

    def test_parses_prod_namespace(self):
        client = PrometheusClient()
        client.namespace = "prod"
        result = client._parse_query_result(SAMPLE_QUOTA_RESPONSE)

        assert result is not None
        value_bytes, _ = result
        assert value_bytes == 214748364800

    def test_returns_none_for_unknown_namespace(self):
        client = PrometheusClient()
        client.namespace = "nonexistent"
        result = client._parse_query_result(SAMPLE_QUOTA_RESPONSE)

        assert result is None

    def test_returns_none_for_failed_status(self):
        client = PrometheusClient()
        client.namespace = "prod"
        result = client._parse_query_result({"status": "error", "error": "bad query"})

        assert result is None

    def test_returns_none_for_empty_results(self):
        client = PrometheusClient()
        client.namespace = "prod"
        result = client._parse_query_result(
            {"status": "success", "data": {"resultType": "vector", "result": []}}
        )

        assert result is None


class TestGetUserUsageWithPrometheus:
    """Test get_user_usage with mocked Prometheus responses"""

    @pytest.mark.asyncio
    async def test_returns_usage_data(self):
        client = PrometheusClient()
        client.namespace = "staging"
        client.query = AsyncMock(side_effect=[SAMPLE_QUOTA_RESPONSE, SAMPLE_USAGE_RESPONSE])

        usage_data = await client.get_user_usage("testuser")

        assert usage_data["username"] == "testuser"
        assert usage_data["quota_bytes"] == 10737418240
        assert usage_data["usage_bytes"] == 243240960
        assert usage_data["percentage"] > 0
        assert "last_updated" in usage_data
        assert "error" not in usage_data

        await client.close()

    @pytest.mark.asyncio
    async def test_returns_error_when_prometheus_unreachable(self):
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(side_effect=Exception("Connection refused"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()

    @pytest.mark.asyncio
    async def test_returns_error_when_no_results_for_user(self):
        empty_response = {
            "status": "success",
            "data": {"resultType": "vector", "result": []},
        }
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(return_value=empty_response)

        usage_data = await client.get_user_usage("unknownuser")

        assert "error" in usage_data
        assert usage_data["username"] == "unknownuser"

        await client.close()


def test_import():
    """Test that the package can be imported"""
    import jupyterhub_usage_quota_service

    assert jupyterhub_usage_quota_service.__version__ == "0.1.0"
