"""
JupyterHub configuration for local development with usage-quota service
"""

import os

from jupyterhub_usage_quota_service import UsageHandler, get_template_path

# Basic configuration
c.JupyterHub.ip = "0.0.0.0"
c.JupyterHub.port = 8000
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.hub_port = 8081

# Register custom handler for the usage page
c.JupyterHub.extra_handlers = [
    (r"/usage", UsageHandler),
]

# Register custom templates folder
c.JupyterHub.template_paths = [get_template_path()]

# Use DummyAuthenticator for easy local testing (no password required)
c.JupyterHub.authenticator_class = "dummy"

# Use SimpleLocalProcessSpawner for local development
c.JupyterHub.spawner_class = "simple"

# Allow users to access services without spawning servers
c.JupyterHub.allow_named_servers = False

# Since we're focusing on services, disable automatic redirect to spawn
c.JupyterHub.redirect_to_server = False

# Configure the usage-quota service
c.JupyterHub.services = [
    {
        "name": "usage-quota",
        "url": "http://usage-quota-service:9000",
        "display": False,  # Don't show in Services menu - we have a custom navbar link
        "api_token": os.environ.get(
            "JUPYTERHUB_API_TOKEN", "your-service-token-change-in-production"
        ),
        "oauth_client_id": "service-usage-quota",  # OAuth client ID for the service
        "oauth_no_confirm": True,  # Skip OAuth confirmation for managed services
        # Absolute browser-facing URL
        "oauth_redirect_uri": "http://localhost:8000/services/usage-quota/oauth_callback",
    }
]

# Load predefined API tokens and permissions
c.JupyterHub.load_roles = [
    {
        # Role for the service itself to access Hub API
        "name": "usage-quota-service",
        "scopes": [
            "read:users",
            "read:servers",
            "list:users",
        ],
        "services": ["usage-quota"],
    },
    {
        # Role to grant all users access to the usage-quota service
        "name": "user",
        "scopes": [
            "access:services!service=usage-quota",
            "self",
        ],
    },
]

# Database configuration (use SQLite for local development)
c.JupyterHub.db_url = "sqlite:////data/jupyterhub.sqlite"

# Base URL configuration
c.JupyterHub.base_url = "/"

# Debug logging for development
c.JupyterHub.log_level = "DEBUG"
c.Application.log_level = "DEBUG"
