"""Tests for Prometheus integration and client"""

import asyncio
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from jupyterhub_usage_quota_service.app.prometheus_client import PrometheusClient
from tests.fixtures.prometheus_responses import (
    PROMETHEUS_EMPTY_RESULT,
    PROMETHEUS_ERROR_RESPONSE,
    PROMETHEUS_MALFORMED_INVALID_VALUE,
    PROMETHEUS_MALFORMED_NO_DATA,
    PROMETHEUS_MALFORMED_NO_RESULT,
    PROMETHEUS_MALFORMED_NON_NUMERIC,
    PROMETHEUS_MULTIPLE_NAMESPACES_QUOTA,
    PROMETHEUS_QUOTA_50_PERCENT,
    PROMETHEUS_TIMESTAMP_50_PERCENT,
    PROMETHEUS_USAGE_50_PERCENT,
)

# Sample Prometheus response matching the real API structure
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
        # Mock all three queries: quota, usage, and timestamp
        sample_timestamp_response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {
                            "__name__": "dirsize_total_size_bytes",
                            "directory": "testuser",
                            "namespace": "staging",
                            "username": "testuser",
                        },
                        "value": [1771314216.003, "1771314216.003"],
                    },
                ],
            },
        }
        client.query = AsyncMock(
            side_effect=[SAMPLE_QUOTA_RESPONSE, SAMPLE_USAGE_RESPONSE, sample_timestamp_response]
        )

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


class TestPrometheusTimeouts:
    """Test timeout handling"""

    @pytest.mark.asyncio
    async def test_handles_connection_timeout(self, mocker):
        """Should return error on connection timeout"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock query to raise asyncio.TimeoutError
        client.query = AsyncMock(side_effect=asyncio.TimeoutError("Connection timeout"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"
        assert "Prometheus" in usage_data["error"]

        await client.close()

    @pytest.mark.asyncio
    async def test_handles_aiohttp_timeout(self, mocker):
        """Should handle aiohttp ClientTimeout"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock query to raise aiohttp.ServerTimeoutError
        client.query = AsyncMock(side_effect=aiohttp.ServerTimeoutError("Read timeout"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()


class TestPrometheusMalformedResponses:
    """Test handling of malformed Prometheus responses"""

    @pytest.mark.asyncio
    async def test_handles_missing_data_field(self):
        """Should handle response missing 'data' field"""
        client = PrometheusClient()
        client.namespace = "prod"

        result = client._parse_query_result(PROMETHEUS_MALFORMED_NO_DATA)

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_missing_result_field(self):
        """Should handle response missing 'result' field"""
        client = PrometheusClient()
        client.namespace = "prod"

        result = client._parse_query_result(PROMETHEUS_MALFORMED_NO_RESULT)

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_invalid_value_structure(self):
        """Should handle metrics with wrong value structure"""
        client = PrometheusClient()
        client.namespace = "prod"

        result = client._parse_value_result(PROMETHEUS_MALFORMED_INVALID_VALUE)

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_non_numeric_values(self):
        """Should handle non-numeric metric values"""
        client = PrometheusClient()
        client.namespace = "prod"

        # This should return None or handle the ValueError
        result = client._parse_value_result(PROMETHEUS_MALFORMED_NON_NUMERIC)

        # The implementation should handle this gracefully
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_empty_string_namespace(self):
        """Should fall back to mock data when namespace is empty"""
        client = PrometheusClient()
        client.namespace = ""  # Empty namespace triggers mock mode

        usage_data = await client.get_user_usage("testuser")

        # Should return mock data
        assert usage_data["username"] == "testuser"
        # Should have either usage data or error (mock mode returns random)
        assert "quota_bytes" in usage_data or "error" in usage_data

        await client.close()

    @pytest.mark.asyncio
    async def test_handles_invalid_json_response(self, mocker):
        """Should handle non-JSON responses"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock query to raise json decode error
        client.query = AsyncMock(side_effect=Exception("Invalid JSON"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()


class TestPrometheusMultipleNamespaces:
    """Test namespace filtering"""

    @pytest.mark.asyncio
    async def test_filters_correct_namespace_with_multiple_results(self):
        """Should select metric matching configured namespace"""
        client = PrometheusClient()
        client.namespace = "prod"

        result = client._parse_query_result(PROMETHEUS_MULTIPLE_NAMESPACES_QUOTA)

        assert result is not None
        value_bytes, _ = result
        assert value_bytes == 10737418240  # prod namespace value (10 GB)

    @pytest.mark.asyncio
    async def test_filters_staging_namespace(self):
        """Should correctly filter staging namespace"""
        client = PrometheusClient()
        client.namespace = "staging"

        result = client._parse_query_result(PROMETHEUS_MULTIPLE_NAMESPACES_QUOTA)

        assert result is not None
        value_bytes, _ = result
        assert value_bytes == 5368709120  # staging namespace value (5 GB)

    @pytest.mark.asyncio
    async def test_returns_none_when_namespace_not_found(self):
        """Should return None if namespace doesn't exist in results"""
        client = PrometheusClient()
        client.namespace = "nonexistent"

        result = client._parse_query_result(PROMETHEUS_MULTIPLE_NAMESPACES_QUOTA)

        assert result is None


class TestPrometheusUnavailability:
    """Test Prometheus unavailability scenarios"""

    @pytest.mark.asyncio
    async def test_handles_prometheus_server_down(self, mocker):
        """Should return error when Prometheus is unreachable"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock query to raise connection error
        client.query = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"
        assert "Prometheus" in usage_data["error"]

        await client.close()

    @pytest.mark.asyncio
    async def test_handles_prometheus_500_error(self):
        """Should handle Prometheus server errors"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock query to return error response
        client.query = AsyncMock(return_value=PROMETHEUS_ERROR_RESPONSE)

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()

    @pytest.mark.asyncio
    async def test_handles_prometheus_network_error(self, mocker):
        """Should handle network errors"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock query to raise general exception
        client.query = AsyncMock(side_effect=Exception("Network error"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()

    @pytest.mark.asyncio
    async def test_handles_partial_query_failure(self):
        """Should handle when one query succeeds but others fail"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock query to return different results
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_QUOTA_50_PERCENT,  # First query succeeds
                Exception("Query failed"),  # Second query fails
                PROMETHEUS_TIMESTAMP_50_PERCENT,  # Third query succeeds
            ]
        )

        usage_data = await client.get_user_usage("testuser")

        # Should return error because not all queries succeeded
        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()


class TestPrometheusUserWithNoData:
    """Test users without quota data"""

    @pytest.mark.asyncio
    async def test_returns_error_for_user_with_no_quota(self):
        """Should return 'No storage data found' error"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock all queries to return empty results
        client.query = AsyncMock(return_value=PROMETHEUS_EMPTY_RESULT)

        usage_data = await client.get_user_usage("unknownuser")

        assert "error" in usage_data
        assert usage_data["username"] == "unknownuser"
        assert "No storage data found" in usage_data["error"]

        await client.close()

    @pytest.mark.asyncio
    async def test_returns_error_when_quota_exists_but_usage_missing(self):
        """Should handle quota data without usage data"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock queries: quota exists, usage missing
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_QUOTA_50_PERCENT,  # Quota query succeeds
                PROMETHEUS_EMPTY_RESULT,  # Usage query returns empty
                PROMETHEUS_EMPTY_RESULT,  # Timestamp query returns empty
            ]
        )

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert "No storage data found" in usage_data["error"]

        await client.close()

    @pytest.mark.asyncio
    async def test_returns_error_when_usage_exists_but_quota_missing(self):
        """Should handle usage data without quota data"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock queries: quota missing, usage exists
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_EMPTY_RESULT,  # Quota query returns empty
                PROMETHEUS_USAGE_50_PERCENT,  # Usage query succeeds
                PROMETHEUS_TIMESTAMP_50_PERCENT,  # Timestamp query succeeds
            ]
        )

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert "No storage data found" in usage_data["error"]

        await client.close()

    @pytest.mark.asyncio
    async def test_returns_error_when_timestamp_missing(self):
        """Should handle missing timestamp data"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock queries: quota and usage exist, timestamp missing
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_QUOTA_50_PERCENT,  # Quota query succeeds
                PROMETHEUS_USAGE_50_PERCENT,  # Usage query succeeds
                PROMETHEUS_EMPTY_RESULT,  # Timestamp query returns empty
            ]
        )

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert "No storage data found" in usage_data["error"]

        await client.close()


class TestPrometheusEdgeCaseValues:
    """Test edge case values in Prometheus data"""

    @pytest.mark.asyncio
    async def test_handles_zero_quota(self):
        """Should handle zero quota value"""
        client = PrometheusClient()
        client.namespace = "prod"

        zero_quota_response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"namespace": "prod"},
                        "value": [1771314029.985, "0"],
                    }
                ],
            },
        }

        result = client._parse_value_result(zero_quota_response)
        assert result == 0

    @pytest.mark.asyncio
    async def test_handles_very_large_values(self):
        """Should handle very large byte values (petabytes)"""
        client = PrometheusClient()
        client.namespace = "prod"

        large_value_response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"namespace": "prod"},
                        "value": [1771314029.985, "1125899906842624"],  # 1 PB
                    }
                ],
            },
        }

        result = client._parse_value_result(large_value_response)
        assert result == 1125899906842624

    @pytest.mark.asyncio
    async def test_prevents_division_by_zero(self):
        """Should handle division by zero when quota is 0"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock queries to return 0 quota
        client.query = AsyncMock(
            side_effect=[
                {
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [
                            {
                                "metric": {"namespace": "prod"},
                                "value": [1771314029.985, "0"],  # Zero quota
                            }
                        ],
                    },
                },
                PROMETHEUS_USAGE_50_PERCENT,
                PROMETHEUS_TIMESTAMP_50_PERCENT,
            ]
        )

        usage_data = await client.get_user_usage("testuser")

        # Should handle gracefully - percentage should be 0 not divide by zero error
        if "error" not in usage_data:
            assert usage_data["percentage"] == 0

        await client.close()


class TestPrometheusQueryConstruction:
    """Test query construction and special characters"""

    @pytest.mark.asyncio
    async def test_handles_username_with_special_characters(self, mocker):
        """Should handle usernames with special characters"""
        client = PrometheusClient()
        client.namespace = "prod"

        # Mock the query method to capture what's called
        mock_query = AsyncMock(return_value=PROMETHEUS_EMPTY_RESULT)
        client.query = mock_query

        await client.get_user_usage("user.name-123_test")

        # Verify query was called (even if it returns empty)
        assert mock_query.call_count == 3  # quota, usage, timestamp queries

        await client.close()

    @pytest.mark.asyncio
    async def test_handles_long_username(self, mocker):
        """Should handle very long usernames"""
        client = PrometheusClient()
        client.namespace = "prod"

        mock_query = AsyncMock(return_value=PROMETHEUS_EMPTY_RESULT)
        client.query = mock_query

        long_username = "a" * 200  # Very long username
        await client.get_user_usage(long_username)

        # Should still attempt the query
        assert mock_query.call_count == 3

        await client.close()


def test_import():
    """Test that the package can be imported"""
    import jupyterhub_usage_quota_service

    assert jupyterhub_usage_quota_service.__version__ == "0.1.0"
