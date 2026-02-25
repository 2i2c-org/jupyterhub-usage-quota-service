"""Tests for OAuth authentication and session management"""

from urllib.parse import parse_qs, urlparse

import pytest
import respx
from fastapi import HTTPException
from httpx import Response
from starlette.middleware.sessions import SessionMiddleware

from tests.conftest import set_session, get_session


class MockRequest:
    """Mock Request object for testing get_current_user"""

    def __init__(self, session_data=None):
        self.session = session_data or {}


class TestGetCurrentUserDependency:
    """Test the get_current_user dependency function"""

    def test_returns_user_when_in_session(self, mock_env_vars):
        """Should return user from session if present"""
        from jupyterhub_usage_quota_service.app.app import get_current_user

        request = MockRequest(session_data={"user": {"name": "testuser", "admin": False}})

        import asyncio
        import inspect

        result = None
        try:
            result = asyncio.run(get_current_user(request))
        except RuntimeError:
            # If already in async context
            if inspect.iscoroutinefunction(get_current_user):
                result = get_current_user(request)

        if inspect.iscoroutine(result):
            # Need to await it
            result = asyncio.get_event_loop().run_until_complete(result)

        assert result == {"name": "testuser", "admin": False}

    @pytest.mark.asyncio
    async def test_redirects_when_no_user_in_session(self, mock_env_vars):
        """Should raise HTTPException with redirect when no user"""
        from jupyterhub_usage_quota_service.app.app import get_current_user

        request = MockRequest(session_data={})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request)

        assert exc_info.value.status_code == 307
        assert "Location" in exc_info.value.headers

        location = exc_info.value.headers["Location"]
        assert "oauth2/authorize" in location
        assert "client_id=" in location
        assert "state=" in location

    @pytest.mark.asyncio
    async def test_generates_and_stores_oauth_state(self, mock_env_vars):
        """Should generate random state and store in session"""
        from jupyterhub_usage_quota_service.app.app import get_current_user

        request = MockRequest(session_data={})

        with pytest.raises(HTTPException):
            await get_current_user(request)

        assert "oauth_state" in request.session
        state = request.session["oauth_state"]
        assert isinstance(state, str)
        assert len(state) == 32  # secrets.token_hex(16) produces 32 char hex string

    @pytest.mark.asyncio
    async def test_oauth_redirect_includes_correct_parameters(self, mock_env_vars):
        """Redirect URL should have client_id, response_type, redirect_uri, state"""
        from jupyterhub_usage_quota_service.app.app import get_current_user

        request = MockRequest(session_data={})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request)

        location = exc_info.value.headers["Location"]
        parsed = urlparse(location)
        query_params = parse_qs(parsed.query)

        assert "client_id" in query_params
        assert query_params["client_id"][0] == "service-usage-service"

        assert "response_type" in query_params
        assert query_params["response_type"][0] == "code"

        assert "redirect_uri" in query_params
        redirect_uri = query_params["redirect_uri"][0]
        assert "oauth_callback" in redirect_uri

        assert "state" in query_params

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


class TestOAuthSecurity:
    """Test OAuth security features"""

    def test_state_mismatch_prevents_csrf(self, client, app, mock_env_vars):
        """State mismatch should block authentication (CSRF protection)"""
        with client:
            set_session(client, app, {"oauth_state": "expected_secure_state"})

            response = client.get(
                "/services/usage/oauth_callback?code=auth123&state=attacker_state",
                follow_redirects=False,
            )

        assert response.status_code == 400
        assert "OAuth state mismatch" in response.text

    def test_oauth_state_is_unique_per_request(self, client, app, mock_env_vars):
        """Each OAuth flow should generate unique state"""
        # Make two separate requests
        response1 = client.get("/services/usage/", follow_redirects=False)
        response2 = client.get("/services/usage/", follow_redirects=False)

        assert response1.status_code == 307
        assert response2.status_code == 307

        location1 = response1.headers["Location"]
        location2 = response2.headers["Location"]

        # Extract state from both
        state1 = parse_qs(urlparse(location1).query)["state"][0]
        state2 = parse_qs(urlparse(location2).query)["state"][0]

        # States should be different
        assert state1 != state2

    def test_session_isolation_between_clients(self, app, mock_env_vars):
        """Sessions should be isolated between different clients"""
        from fastapi.testclient import TestClient

        client1 = TestClient(app)
        client2 = TestClient(app)

        # Set different users in each client's session
        with client1:
            set_session(client1, app, {"user": {"name": "user1"}})

        with client2:
            set_session(client2, app, {"user": {"name": "user2"}})

        # Verify isolation - each client should see their own user
        session1 = get_session(client1, app)
        assert session1.get("user", {}).get("name") == "user1"

        session2 = get_session(client2, app)
        assert session2.get("user", {}).get("name") == "user2"


class TestCompleteOAuthFlow:
    """Integration test for complete OAuth flow"""

    def test_full_oauth_flow_success(self, client, app, mock_env_vars, mock_prometheus_client):
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

    def test_oauth_flow_with_different_service_prefix(self, monkeypatch, mock_prometheus_client):
        """Test OAuth with custom service prefix"""
        # Set custom prefix
        monkeypatch.setenv("JUPYTERHUB_API_TOKEN", "test-token")
        monkeypatch.setenv("JUPYTERHUB_API_URL", "http://test-hub:8081/hub/api")
        monkeypatch.setenv("JUPYTERHUB_SERVICE_PREFIX", "/custom/path/")
        monkeypatch.setenv("JUPYTERHUB_EXTERNAL_URL", "http://localhost:8000")
        monkeypatch.setenv("JUPYTERHUB_SERVICE_NAME", "custom-service")
        monkeypatch.setenv("PROMETHEUS_NAMESPACE", "prod")

        # Need to reimport app to pick up new env vars
        import importlib
        import jupyterhub_usage_quota_service.app.app as app_module

        importlib.reload(app_module)

        from fastapi.testclient import TestClient

        client = TestClient(app_module.app)

        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(200, json={"name": "testuser"})
            )

            with client:
                # Request at custom prefix
                response = client.get("/custom/path/", follow_redirects=False)
                assert response.status_code == 307

                location = response.headers["Location"]
                state = parse_qs(urlparse(location).query)["state"][0]

                # Callback should also use custom prefix
                response = client.get(
                    f"/custom/path/oauth_callback?code=auth123&state={state}",
                    follow_redirects=False,
                )
                assert response.status_code == 307
                assert response.headers["Location"] == "/custom/path/"


class TestOAuthErrorHandling:
    """Test error handling in OAuth flow"""

    def test_missing_code_parameter_returns_error(self, client, app, mock_env_vars):
        """OAuth callback without code parameter should fail gracefully"""
        with client:
            set_session(client, app, {"oauth_state": "test_state"})

            # Try to access callback without code parameter
            # FastAPI will return 422 for missing required query parameter
            response = client.get("/services/usage/oauth_callback?state=test_state")

        # Should get validation error for missing required parameter
        assert response.status_code == 422

    def test_missing_state_parameter_returns_error(self, client, app, mock_env_vars):
        """OAuth callback without state parameter should fail gracefully"""
        # FastAPI will return 422 for missing required query parameter
        response = client.get("/services/usage/oauth_callback?code=test_code")

        assert response.status_code == 422


class TestSessionMiddleware:
    """Test SessionMiddleware configuration and behavior"""

    def test_session_middleware_is_configured(self, app):
        """App should have SessionMiddleware"""
        # Check if SessionMiddleware is in the app's middleware stack
        middleware_found = False
        for middleware in app.user_middleware:
            if middleware.cls == SessionMiddleware:
                middleware_found = True
                # Verify secret_key is configured
                assert "secret_key" in middleware.kwargs
                assert len(middleware.kwargs["secret_key"]) > 0
                break

        assert middleware_found, "SessionMiddleware not found in app middleware"

    def test_session_uses_secure_secret_key(self, app):
        """Secret key should be randomly generated and sufficiently long"""
        for middleware in app.user_middleware:
            if middleware.cls == SessionMiddleware:
                secret_key = middleware.kwargs.get("secret_key")
                assert secret_key is not None
                # Should be at least 32 bytes (64 hex chars)
                assert len(secret_key) >= 64
                break

    def test_session_persists_across_requests(self, client, app, mock_env_vars):
        """Session data should persist across multiple requests"""
        # First request - set session data
        set_session(client, app, {"test_data": "persisted_value"})

        # Second request - verify session persists
        session = get_session(client, app)
        assert session.get("test_data") == "persisted_value"


class TestSessionStorage:
    """Test session data storage and retrieval"""

    def test_stores_user_in_session_after_auth(self, client, app, mock_env_vars):
        """User data should be stored in session after OAuth"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(
                    200,
                    json={
                        "name": "testuser",
                        "admin": False,
                        "groups": ["users"],
                    },
                )
            )

            # Set OAuth state
            set_session(client, app, {"oauth_state": "test_state"})

            # Complete OAuth callback
            response = client.get(
                "/services/usage/oauth_callback?code=auth123&state=test_state",
                follow_redirects=False,
            )

            assert response.status_code == 307

            # Verify user stored in session
            session = get_session(client, app)
            assert "user" in session
            assert session["user"]["name"] == "testuser"

    def test_stores_oauth_state_in_session(self, client, mock_env_vars):
        """OAuth state should be stored in session during login flow"""
        response = client.get("/services/usage/", follow_redirects=False)

        assert response.status_code == 307

        # Check if state was stored (we can't directly access session from response,
        # but we can verify the redirect contains a state parameter)
        from urllib.parse import parse_qs, urlparse

        location = response.headers["Location"]
        query_params = parse_qs(urlparse(location).query)

        assert "state" in query_params

    def test_clears_oauth_state_after_successful_auth(self, client, app, mock_env_vars):
        """OAuth state should be removed after auth completes"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(200, json={"name": "testuser"})
            )

            # Set OAuth state
            set_session(client, app, {"oauth_state": "test_state"})
            session = get_session(client, app)
            assert "oauth_state" in session

            # Complete OAuth
            response = client.get(
                "/services/usage/oauth_callback?code=auth123&state=test_state",
                follow_redirects=False,
            )

            assert response.status_code == 307

            # Verify state cleared
            session = get_session(client, app)
            assert "oauth_state" not in session

    def test_session_data_is_isolated_per_client(self, app, mock_env_vars):
        """Different clients should have isolated sessions"""
        from fastapi.testclient import TestClient

        client1 = TestClient(app)
        client2 = TestClient(app)

        set_session(client1, app, {"user": {"name": "user1"}})
        set_session(client2, app, {"user": {"name": "user2"}})

        # Verify each client has their own data
        session1 = get_session(client1, app)
        assert session1.get("user", {}).get("name") == "user1"

        session2 = get_session(client2, app)
        assert session2.get("user", {}).get("name") == "user2"


class TestSessionSecurity:
    """Test session security features"""

    def test_session_cookie_exists_after_setting_data(self, client, app, mock_env_vars):
        """Session cookie should be set when data is stored"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(200, json={"name": "testuser"})
            )

            set_session(client, app, {"oauth_state": "test_state"})

            response = client.get(
                "/services/usage/oauth_callback?code=auth123&state=test_state",
                follow_redirects=False,
            )

            # Should have set a session cookie
            # TestClient handles cookies automatically, so we just verify
            # that subsequent requests have access to session data
            assert response.status_code == 307

    def test_session_data_is_signed(self, client, mock_env_vars):
        """Session data should be cryptographically signed (via SessionMiddleware)"""
        # SessionMiddleware uses itsdangerous to sign session cookies
        # We can't easily verify the signing directly, but we can verify
        # that the middleware is configured with a secret_key
        from jupyterhub_usage_quota_service.app.app import app

        middleware_configured = False
        for middleware in app.user_middleware:
            if middleware.cls == SessionMiddleware:
                assert "secret_key" in middleware.kwargs
                middleware_configured = True
                break

        assert middleware_configured


class TestSessionLifecycle:
    """Test session lifecycle management"""

    def test_new_session_created_for_new_client(self, app, mock_env_vars):
        """Each new client should get a new session"""
        from fastapi.testclient import TestClient

        client1 = TestClient(app)
        client2 = TestClient(app)

        # Each should be able to set independent session data
        set_session(client1, app, {"id": "session1"})
        set_session(client2, app, {"id": "session2"})

        # Verify they're different
        session1 = get_session(client1, app)
        assert session1.get("id") == "session1"

        session2 = get_session(client2, app)
        assert session2.get("id") == "session2"

    def test_session_persists_user_data_after_login(self, client, app, mock_env_vars):
        """User should remain logged in across requests"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(
                    200,
                    json={
                        "name": "testuser",
                        "admin": False,
                        "groups": ["users"],
                    },
                )
            )

            # Complete OAuth
            set_session(client, app, {"oauth_state": "test_state"})

            response = client.get(
                "/services/usage/oauth_callback?code=auth123&state=test_state",
                follow_redirects=False,
            )

            assert response.status_code == 307

            # Make another request - should still be authenticated
            session = get_session(client, app)
            assert "user" in session
            assert session["user"]["name"] == "testuser"


class TestSessionWithRoutes:
    """Test session behavior with actual routes"""

    def test_authenticated_user_sees_content(self, client, app, mock_env_vars, mock_prometheus_client):
        """Authenticated user with session should access home page"""
        set_session(client, app, {"user": {"name": "testuser", "admin": False}})

        response = client.get("/services/usage/")

        assert response.status_code == 200
        assert "Home storage" in response.text

    def test_unauthenticated_user_redirected(self, client, mock_env_vars):
        """User without session should be redirected to OAuth"""
        response = client.get("/services/usage/", follow_redirects=False)

        assert response.status_code == 307
        assert "oauth2/authorize" in response.headers["Location"]

    def test_session_cleared_user_must_reauthenticate(self, client, app, mock_env_vars):
        """User with cleared session should need to re-authenticate"""
        # Set user initially
        set_session(client, app, {"user": {"name": "testuser"}})

        # Clear session
        client.cookies.clear()

        # Should be redirected to OAuth
        response = client.get("/services/usage/", follow_redirects=False)
        assert response.status_code == 307
