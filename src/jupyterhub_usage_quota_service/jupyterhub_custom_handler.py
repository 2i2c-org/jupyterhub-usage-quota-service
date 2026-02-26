"""
Custom JupyterHub handler for the Usage wrapper page.
This handler renders an iframe that embeds the usage-quota service.
"""

from jupyterhub.handlers import BaseHandler
from tornado import web


class UsageHandler(BaseHandler):
    """Handler that displays the usage-quota service in an iframe."""

    @property
    def template_namespace(self):
        """Add current user to template namespace."""
        ns = super().template_namespace
        ns["user"] = self.current_user
        return ns

    @web.authenticated
    async def get(self):
        """Render the usage wrapper template."""
        html = await self.render_template("usage_wrapper.html")
        self.write(html)
