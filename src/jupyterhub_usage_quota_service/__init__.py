"""
JupyterHub Usage Quota Service

A JupyterHub service to display user storage quota and usage.
"""

import os

__version__ = "0.1.0"

from jupyterhub_usage_quota_service.jupyterhub_custom_handler import UsageHandler

__all__ = ["UsageHandler", "__version__", "get_template_path"]


def get_template_path():
    """Get the path to the templates directory."""
    return os.path.join(os.path.dirname(__file__), "templates")
