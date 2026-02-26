"""Tests for JupyterHub custom handler"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from jupyterhub.handlers import BaseHandler
from jupyterhub_usage_quota_service.jupyterhub_custom_handler import UsageHandler


class TestUsageHandler:
    """Tests for UsageHandler without requiring a full Tornado application"""

    def test_template_namespace_includes_current_user(self):
        """template_namespace should add current_user under 'user' key"""
        mock_user = {"name": "testuser", "admin": False}

        # Patch BaseHandler properties so super() resolves without
        # needing a live Tornado application.
        with (
            patch.object(
                BaseHandler,
                "template_namespace",
                new_callable=PropertyMock,
                return_value={"hub": "mock"},
            ),
            patch.object(
                BaseHandler,
                "current_user",
                new_callable=PropertyMock,
                return_value=mock_user,
            ),
        ):
            handler = UsageHandler.__new__(UsageHandler)
            ns = handler.template_namespace

        assert ns["user"] == mock_user
        assert "hub" in ns

    @pytest.mark.asyncio
    async def test_get_renders_and_writes_template(self):
        """get() should render usage_wrapper.html and write the result"""
        mock_html = "<html>usage</html>"
        handler = MagicMock()
        handler.current_user = {"name": "testuser"}
        handler.render_template = AsyncMock(return_value=mock_html)
        handler.write = MagicMock()

        await UsageHandler.get(handler)

        handler.render_template.assert_called_once_with("usage_wrapper.html")
        handler.write.assert_called_once_with(mock_html)

    def test_unauthenticated_user_redirected_to_login(self):
        """Unauthenticated users should be redirected to login, not served content"""
        handler = MagicMock()
        handler.current_user = None
        handler.request.method = "GET"
        handler.get_login_url.return_value = "/hub/login"
        handler.request.uri = "/services/usage/"

        UsageHandler.get(handler)

        handler.redirect.assert_called_once()
        redirect_url = handler.redirect.call_args[0][0]
        assert redirect_url.startswith("/hub/login")
        handler.render_template.assert_not_called()
