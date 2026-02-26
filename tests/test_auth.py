"""Tests for OAuth authentication and session management"""

from urllib.parse import parse_qs, urlparse

import pytest
import respx
from fastapi import HTTPException
from httpx import Response
from tests.conftest import set_session, get_session


class MockRequest:
    """Mock Request object for testing get_current_user"""

    def __init__(self, session_data=None):
        self.session = session_data or {}


class TestGetCurrentUserDependency:
    """Test the get_current_user dependency function"""

    @pytest.mark.asyncio
    async def test_oauth_redirect_uses_public_hub_url(self, mock_env_vars):
        """Redirect should use PUBLIC_HUB_URL (external URL)"""
        from jupyterhub_usage_quota_service.app.app import get_current_user

        request = MockRequest(session_data={})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request)

        location = exc_info.value.headers["Location"]
        # Should use http://localhost:8000 (PUBLIC_HUB_URL from mock_env_vars)
        assert location.startswith("http://localhost:8000/hub/api/oauth2/authorize")


class TestCompleteOAuthFlow:
    """Integration test for complete OAuth flow"""

    def test_full_oauth_flow_success(
        self, client, app, mock_env_vars, mock_prometheus_client
    ):
        """Test complete flow: redirect → callback → authenticated access"""
        with respx.mock:
            # Mock JupyterHub API
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(
                    200, json={"name": "testuser", "admin": False, "groups": ["users"]}
                )
            )

            with client:
                # Step 1: Request home without auth → get redirect
                response = client.get("/services/usage/", follow_redirects=False)
                assert response.status_code == 307

                # Extract state from redirect
                location = response.headers["Location"]
                state = parse_qs(urlparse(location).query)["state"][0]

                # Verify state stored in session
                session = get_session(client, app)
                assert session.get("oauth_state") == state

                # Step 2: Complete OAuth callback with state
                response = client.get(
                    f"/services/usage/oauth_callback?code=auth123&state={state}",
                    follow_redirects=False,
                )
                assert response.status_code == 307
                assert response.headers["Location"] == "/services/usage/"

                # Verify user stored in session
                session = get_session(client, app)
                assert "user" in session
                assert session["user"]["name"] == "testuser"
                assert "oauth_state" not in session  # State cleared

                # Step 3: Request home again → see usage data (no redirect)
                response = client.get("/services/usage/", follow_redirects=False)
                assert response.status_code == 200
                assert "Home storage" in response.text


class TestSessionWithRoutes:
    """Test session behavior with actual routes"""

    def test_session_cleared_user_must_reauthenticate(self, client, app, mock_env_vars):
        """User with cleared session should need to re-authenticate"""
        # Set user initially
        set_session(client, app, {"user": {"name": "testuser"}})

        # Clear session
        client.cookies.clear()

        # Should be redirected to OAuth
        response = client.get("/services/usage/", follow_redirects=False)
        assert response.status_code == 307
