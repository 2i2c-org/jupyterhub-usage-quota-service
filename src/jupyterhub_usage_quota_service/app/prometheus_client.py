"""
Async Prometheus client for querying user usage quota and usage
"""

import asyncio
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

    def _parse_value_result(self, data: dict[str, Any]) -> int | None:
        """
        Parse a Prometheus query response for a metric value, filtering by namespace.

        Returns:
            The value in bytes or None if no matching result found.
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
                    value_bytes = int(float(value_pair[1]))
                    return value_bytes
                return None

        return None

    def _parse_timestamp_result(self, data: dict[str, Any]) -> datetime | None:
        """
        Parse a Prometheus timestamp() query response, filtering by namespace.

        Returns:
            The actual scrape timestamp or None if no matching result found.
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
                    # The value from timestamp() query is the actual scrape timestamp
                    scrape_timestamp = datetime.fromtimestamp(
                        float(value_pair[1]), tz=timezone.utc
                    )
                    return scrape_timestamp
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

        base_quota_metric = (
            f'dirsize_hard_limit_bytes{{namespace!="", directory="{username}"}}'
        )
        base_usage_metric = (
            f'dirsize_total_size_bytes{{namespace!="", directory="{username}"}}'
        )

        # Query for raw values
        quota_value_query = (
            f"label_replace({base_quota_metric},"
            f' "username", "$1", "directory", "(.*)")'
        )
        usage_value_query = (
            f"label_replace({base_usage_metric},"
            f' "username", "$1", "directory", "(.*)")'
        )

        # Query for actual scrape timestamp using timestamp() on the raw vector
        usage_timestamp_query = (
            f"label_replace(timestamp({base_usage_metric}),"
            f' "username", "$1", "directory", "(.*)")'
        )

        try:
            # Execute all three Prometheus queries concurrently
            quota_value_data, usage_value_data, usage_timestamp_data = (
                await asyncio.gather(
                    self.query(quota_value_query),
                    self.query(usage_value_query),
                    self.query(usage_timestamp_query),
                )
            )
        except Exception as e:
            logger.error(f"Error fetching usage data concurrently for {username}: {e}")
            return {
                "username": username,
                "error": "Unable to reach Prometheus. Please try again later.",
            }

        quota_bytes = self._parse_value_result(quota_value_data)
        usage_bytes = self._parse_value_result(usage_value_data)
        last_updated_dt = self._parse_timestamp_result(usage_timestamp_data)

        if quota_bytes is None or usage_bytes is None or last_updated_dt is None:
            return {
                "username": username,
                "error": "No storage data found for your account.",
            }

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
