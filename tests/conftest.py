"""Shared pytest fixtures for jupyterhub-usage-quota-service tests"""

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response
from unittest.mock import AsyncMock
from itsdangerous import URLSafeTimedSerializer

from tests.fixtures.jupyterhub_responses import (
    JUPYTERHUB_TOKEN_RESPONSE,
    JUPYTERHUB_USER_RESPONSE,
)


def get_secret_key(app):
    """Extract the secret key from SessionMiddleware"""
    from starlette.middleware.sessions import SessionMiddleware

    for middleware in app.user_middleware:
        if middleware.cls == SessionMiddleware:
            return middleware.kwargs.get("secret_key")
    raise ValueError("SessionMiddleware not found in app")


def encode_session(app, session_data: dict) -> str:
    """
    Encode session data into a signed cookie value compatible with Starlette's SessionMiddleware.

    Args:
        app: The FastAPI application instance
        session_data: Dictionary of session data to encode

    Returns:
        Signed session cookie value
    """
    secret_key = get_secret_key(app)
    serializer = URLSafeTimedSerializer(secret_key, salt="cookie-session")
    return serializer.dumps(session_data)


def decode_session(app, cookie_value: str) -> dict:
    """
    Decode a signed session cookie value.

    Args:
        app: The FastAPI application instance
        cookie_value: The signed cookie value

    Returns:
        Dictionary of session data
    """
    secret_key = get_secret_key(app)
    serializer = URLSafeTimedSerializer(secret_key, salt="cookie-session")
    return serializer.loads(cookie_value)


def set_session(client: TestClient, app, session_data: dict):
    """
    Set session data in the TestClient by making a request that sets the session.

    This approach works better with Starlette's SessionMiddleware than manually
    setting cookies, as it ensures the session is properly initialized.

    Args:
        client: The TestClient instance
        app: The FastAPI application instance
        session_data: Dictionary of session data to set
    """
    # Create a temporary endpoint to set session data
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.get("/__test_set_session__")
    async def set_test_session(request: Request):
        for key, value in session_data.items():
            request.session[key] = value
        return JSONResponse({"status": "ok"})

    # Make a request to set the session
    response = client.get("/__test_set_session__")

    # Clean up the test endpoint
    # Find and remove the test route
    for i, route in enumerate(app.routes):
        if hasattr(route, 'path') and route.path == "/__test_set_session__":
            app.routes.pop(i)
            break


def get_session(client: TestClient, app) -> dict:
    """
    Get session data from the TestClient by making a request.

    Args:
        client: The TestClient instance
        app: The FastAPI application instance

    Returns:
        Dictionary of session data, or empty dict if no session
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.get("/__test_get_session__")
    async def get_test_session(request: Request):
        return JSONResponse(dict(request.session))

    # Make a request to get the session
    response = client.get("/__test_get_session__")

    # Clean up the test endpoint
    for i, route in enumerate(app.routes):
        if hasattr(route, 'path') and route.path == "/__test_get_session__":
            app.routes.pop(i)
            break

    return response.json()


@pytest.fixture
def app(mock_env_vars):
    """Provide the FastAPI application instance with reloaded environment variables"""
    import sys

    # Remove the app module from sys.modules to force a reload
    if 'jupyterhub_usage_quota_service.app.app' in sys.modules:
        del sys.modules['jupyterhub_usage_quota_service.app.app']

    # Now import the app with the new environment variables
    from jupyterhub_usage_quota_service.app.app import app

    return app


@pytest.fixture
def client(app):
    """Provide TestClient for making HTTP requests"""
    return TestClient(app)


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up standard environment variables for testing"""
    monkeypatch.setenv("JUPYTERHUB_API_TOKEN", "test-token-123")
    monkeypatch.setenv("JUPYTERHUB_API_URL", "http://test-hub:8081/hub/api")
    monkeypatch.setenv("JUPYTERHUB_SERVICE_PREFIX", "/services/usage/")
    monkeypatch.setenv("JUPYTERHUB_EXTERNAL_URL", "http://localhost:8000")
    monkeypatch.setenv("JUPYTERHUB_SERVICE_NAME", "usage-service")
    monkeypatch.setenv("PROMETHEUS_URL", "http://prometheus:9090")
    monkeypatch.setenv("PROMETHEUS_NAMESPACE", "prod")
    monkeypatch.setenv("SESSION_SECRET_KEY", "0" * 64)  # 64 hex characters for testing
    return monkeypatch


@pytest.fixture
def mock_session_user():
    """Mock authenticated user session data"""
    return {
        "name": "testuser",
        "admin": False,
        "groups": ["users"],
        "server": "/user/testuser/",
    }


@pytest.fixture
def mock_prometheus_client(mocker):
    """Mock PrometheusClient for route tests"""
    mock_client = AsyncMock()

    # Mock context manager protocol
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    # Default successful response (50% usage)
    mock_client.get_user_usage.return_value = {
        "username": "testuser",
        "usage_bytes": 5368709120,
        "quota_bytes": 10737418240,
        "usage_gb": 5.0,
        "quota_gb": 10.0,
        "percentage": 50.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }

    mocker.patch(
        "jupyterhub_usage_quota_service.app.app.PrometheusClient", return_value=mock_client
    )
    return mock_client


@pytest.fixture
def mock_prometheus_client_with_error(mocker):
    """Mock PrometheusClient that returns an error"""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    mock_client.get_user_usage.return_value = {
        "username": "testuser",
        "error": "Unable to reach Prometheus. Please try again later.",
    }

    mocker.patch(
        "jupyterhub_usage_quota_service.app.app.PrometheusClient", return_value=mock_client
    )
    return mock_client


@pytest.fixture
def mock_prometheus_client_no_data(mocker):
    """Mock PrometheusClient that returns no data error"""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    mock_client.get_user_usage.return_value = {
        "username": "testuser",
        "error": "No storage data found for your account.",
    }

    mocker.patch(
        "jupyterhub_usage_quota_service.app.app.PrometheusClient", return_value=mock_client
    )
    return mock_client


@pytest.fixture
def mock_prometheus_client_high_usage(mocker):
    """Mock PrometheusClient that returns high usage (95%)"""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    mock_client.get_user_usage.return_value = {
        "username": "testuser",
        "usage_bytes": 10200547328,
        "quota_bytes": 10737418240,
        "usage_gb": 9.5,
        "quota_gb": 10.0,
        "percentage": 95.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }

    mocker.patch(
        "jupyterhub_usage_quota_service.app.app.PrometheusClient", return_value=mock_client
    )
    return mock_client


@pytest.fixture
def mock_oauth_state():
    """Generate mock OAuth state token"""
    return "abc123def456ghi789"


@pytest.fixture
def mock_oauth_code():
    """Generate mock OAuth authorization code"""
    return "auth_code_xyz789"


@pytest.fixture
def mock_jupyterhub_api():
    """Mock JupyterHub API endpoints using respx"""
    with respx.mock:
        # Token exchange endpoint
        respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
            return_value=Response(200, json=JUPYTERHUB_TOKEN_RESPONSE)
        )

        # User info endpoint
        respx.get("http://test-hub:8081/hub/api/user").mock(
            return_value=Response(200, json=JUPYTERHUB_USER_RESPONSE)
        )

        yield respx


@pytest.fixture
def usage_data_50_percent():
    """Usage data dict for 50% usage (normal)"""
    return {
        "username": "testuser",
        "usage_bytes": 5368709120,
        "quota_bytes": 10737418240,
        "usage_gb": 5.0,
        "quota_gb": 10.0,
        "percentage": 50.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }


@pytest.fixture
def usage_data_90_percent():
    """Usage data dict for 90% usage (warning threshold)"""
    return {
        "username": "testuser",
        "usage_bytes": 9663676416,
        "quota_bytes": 10737418240,
        "usage_gb": 9.0,
        "quota_gb": 10.0,
        "percentage": 90.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }


@pytest.fixture
def usage_data_95_percent():
    """Usage data dict for 95% usage (high warning)"""
    return {
        "username": "testuser",
        "usage_bytes": 10200547328,
        "quota_bytes": 10737418240,
        "usage_gb": 9.5,
        "quota_gb": 10.0,
        "percentage": 95.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }


@pytest.fixture
def usage_data_0_percent():
    """Usage data dict for 0% usage"""
    return {
        "username": "testuser",
        "usage_bytes": 0,
        "quota_bytes": 10737418240,
        "usage_gb": 0.0,
        "quota_gb": 10.0,
        "percentage": 0.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }


@pytest.fixture
def usage_data_100_percent():
    """Usage data dict for 100% usage"""
    return {
        "username": "testuser",
        "usage_bytes": 10737418240,
        "quota_bytes": 10737418240,
        "usage_gb": 10.0,
        "quota_gb": 10.0,
        "percentage": 100.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }


@pytest.fixture
def usage_data_prometheus_error():
    """Usage data dict with Prometheus error"""
    return {
        "username": "testuser",
        "error": "Unable to reach Prometheus. Please try again later.",
    }


@pytest.fixture
def usage_data_no_quota():
    """Usage data dict with no quota data error"""
    return {
        "username": "testuser",
        "error": "No storage data found for your account.",
    }


@pytest.fixture
def usage_data_terabytes():
    """Usage data dict with terabyte values"""
    return {
        "username": "testuser",
        "usage_bytes": 549755813888,
        "quota_bytes": 1099511627776,
        "usage_gb": 512.0,
        "quota_gb": 1024.0,
        "percentage": 50.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }
