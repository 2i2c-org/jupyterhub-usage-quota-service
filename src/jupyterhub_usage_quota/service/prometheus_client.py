"""
Async Prometheus client for querying user usage quota and usage
"""

import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class PrometheusClient:
    """
    Client for querying Prometheus metrics
    """

    def __init__(self):
        """
        Initialize the Prometheus client
        """
        self.prometheus_url = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create an aiohttp session
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def query(self, query: str) -> dict[str, Any]:
        """
        Execute a PromQL query

        Args:
            query: PromQL query string

        Returns:
            Query results as a dictionary
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

    async def get_user_usage(self, username: str) -> dict[str, Any]:
        """
        Get storage usage and quota for a specific user

        Args:
            username: Username to query

        Returns:
            Dictionary with usage information:
            {
                'username': str,
                'usage_bytes': int,
                'quota_bytes': int,
                'usage_gb': float,
                'quota_gb': float,
                'percentage': float,
            }
        """
        # For initial development, return mock data
        # In production, replace with actual Prometheus queries:
        # - sum(kubelet_volume_stats_used_bytes{persistentvolumeclaim=~"claim-<user>.*"})
        # - sum(kubelet_volume_stats_capacity_bytes{persistentvolumeclaim=~"claim-<user>.*"})

        logger.info(f"Fetching usage data for user: {username}")

        # Mock data for development
        mock_usage_bytes = 5_368_709_120  # 5 GB
        mock_quota_bytes = 10_737_418_240  # 10 GB

        usage_gb = mock_usage_bytes / (1024**3)
        quota_gb = mock_quota_bytes / (1024**3)
        percentage = (mock_usage_bytes / mock_quota_bytes) * 100 if mock_quota_bytes > 0 else 0

        return {
            "username": username,
            "usage_bytes": mock_usage_bytes,
            "quota_bytes": mock_quota_bytes,
            "usage_gb": round(usage_gb, 2),
            "quota_gb": round(quota_gb, 2),
            "percentage": round(percentage, 2),
        }

    async def close(self):
        """
        Close the aiohttp session
        """
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        """
        Async context manager entry
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit
        """
        await self.close()
