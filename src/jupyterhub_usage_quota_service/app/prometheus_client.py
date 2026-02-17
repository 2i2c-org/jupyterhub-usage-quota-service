"""
Async Prometheus client for querying user usage quota and usage
"""

import logging
import os
import random
from datetime import datetime, timezone
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class PrometheusClient:
    """
    Client for querying Prometheus metrics
    """

    def __init__(self):
        self.prometheus_url = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
        self.namespace = os.environ.get("PROMETHEUS_NAMESPACE", "")
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def query(self, query: str) -> dict[str, Any]:
        """
        Execute a PromQL query
        """
        session = await self._get_session()
        url = f"{self.prometheus_url}/api/v1/query"
        params = {"query": query}

        try:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                return data
        except aiohttp.ClientError as e:
            logger.error(f"Error querying Prometheus: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def _parse_query_result(self, data: dict[str, Any]) -> tuple[int, datetime] | None:
        """
        Parse a Prometheus query response, filtering by namespace.

        Returns:
            Tuple of (value_bytes, timestamp) or None if no matching result found.
        """
        if data.get("status") != "success":
            return None

        results = data.get("data", {}).get("result", [])
        if not results:
            return None

        for result in results:
            metric = result.get("metric", {})
            if metric.get("namespace") == self.namespace:
                value_pair = result.get("value", [])
                if len(value_pair) == 2:
                    timestamp = datetime.fromtimestamp(value_pair[0], tz=timezone.utc)
                    value_bytes = int(value_pair[1])
                    return value_bytes, timestamp
                return None

        return None

    def _get_mock_data(self, username: str) -> dict[str, Any]:
        """
        Return mock data for development when PROMETHEUS_NAMESPACE is not set.
        Randomly returns 50% usage, 95% usage, or an error state.
        """
        scenario = random.choice([0.50, 0.95, "error"])

        if scenario == "error":
            return {
                "username": username,
                "error": "Unable to reach Prometheus. Please try again later.",
            }

        mock_quota_bytes = 10_737_418_240  # 10 GiB
        mock_usage_bytes = int(mock_quota_bytes * scenario)
        usage_gb = mock_usage_bytes / (1024**3)
        quota_gb = mock_quota_bytes / (1024**3)
        percentage = (mock_usage_bytes / mock_quota_bytes) * 100

        return {
            "username": username,
            "usage_bytes": mock_usage_bytes,
            "quota_bytes": mock_quota_bytes,
            "usage_gb": round(usage_gb, 2),
            "quota_gb": round(quota_gb, 2),
            "percentage": round(percentage, 2),
            "last_updated": datetime.now(tz=timezone.utc).isoformat(),
        }

    async def get_user_usage(self, username: str) -> dict[str, Any]:
        """
        Get storage usage and quota for a specific user.

        Returns:
            Dictionary with usage information, or an error dict if data is unavailable.
        """
        if not self.namespace:
            logger.warning(
                "PROMETHEUS_NAMESPACE is not set — returning mock data for development"
            )
            return self._get_mock_data(username)

        logger.info(f"Fetching usage data for user: {username}")

        quota_query = (
            f'label_replace(last_over_time(dirsize_hard_limit_bytes'
            f'{{namespace!="", directory="{username}"}}[7d]),'
            f' "username", "$1", "directory", "(.*)")'
        )
        usage_query = (
            f'label_replace(last_over_time(dirsize_total_size_bytes'
            f'{{namespace!="", directory="{username}"}}[7d]),'
            f' "username", "$1", "directory", "(.*)")'
        )

        try:
            quota_data = await self.query(quota_query)
            usage_data = await self.query(usage_query)
        except Exception:
            return {
                "username": username,
                "error": "Unable to reach Prometheus. Please try again later.",
            }

        quota_result = self._parse_query_result(quota_data)
        usage_result = self._parse_query_result(usage_data)

        if quota_result is None or usage_result is None:
            return {
                "username": username,
                "error": "No storage data found for your account.",
            }

        quota_bytes, _ = quota_result
        usage_bytes, last_updated_dt = usage_result

        usage_gb = usage_bytes / (1024**3)
        quota_gb = quota_bytes / (1024**3)
        percentage = (usage_bytes / quota_bytes) * 100 if quota_bytes > 0 else 0

        return {
            "username": username,
            "usage_bytes": usage_bytes,
            "quota_bytes": quota_bytes,
            "usage_gb": round(usage_gb, 2),
            "quota_gb": round(quota_gb, 2),
            "percentage": round(percentage, 2),
            "last_updated": last_updated_dt.isoformat(),
        }

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
