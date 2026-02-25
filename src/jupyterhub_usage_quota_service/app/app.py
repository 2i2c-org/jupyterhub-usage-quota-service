import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from starlette.middleware.sessions import SessionMiddleware

from .. import get_template_path
from .prometheus_client import PrometheusClient

app = FastAPI()
jinja_env = Environment(loader=FileSystemLoader(get_template_path()), autoescape=True)

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
# The API token to talk to the Hub
HUB_TOKEN = os.environ.get("JUPYTERHUB_API_TOKEN")
# The URL for the Hub API; could be an internal URL (e.g., http://hub:8081/hub/api)
HUB_API_URL = os.environ.get("JUPYTERHUB_API_URL", "http://jupyterhub:8081/hub/api")
# The prefix for this service (e.g., /services/my-service/)
SERVICE_PREFIX = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
# The external URL users use to access the Hub (e.g., http://localhost:8000)
PUBLIC_HUB_URL = os.environ.get(
    "JUPYTERHUB_EXTERNAL_URL", "http://localhost:8000"
).rstrip("/")
# OAuth client ID for this service
CLIENT_ID = f"service-{os.environ.get('JUPYTERHUB_SERVICE_NAME', 'fastapi-service')}"

# Authorization URL (External/Browser-facing)
AUTH_URL = f"{PUBLIC_HUB_URL}/hub/api/oauth2/authorize"

# Callback URL (The path within your service)
CALLBACK_PATH = "oauth_callback"

# The computed Redirect URI (MUST match what the browser sees)
# Example: http://localhost:8000/services/my-service/oauth_callback
REDIRECT_URI = f"{PUBLIC_HUB_URL}{SERVICE_PREFIX}{CALLBACK_PATH}"

# Add Session Middleware to store the OAuth state
# 'secret_key' should be random in production, but can be set via SESSION_SECRET_KEY for testing
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)


# -----------------------------------------------------------------------------
# OAUTH DEPENDENCY
# -----------------------------------------------------------------------------
async def get_current_user(request: Request):
    """
    Dependency that checks if the user is logged in.
    If not, it redirects them to JupyterHub to login.
    """
    user = request.session.get("user")
    if user:
        return user

    # If no user in session, we need to authenticate.
    # Generate a random state and save it in the session (cookie)
    state = secrets.token_hex(16)
    request.session["oauth_state"] = state

    # Build the authorization URL with the state and redirect URI
    # Note: We should always make sure REDIRECT_URI and AUTH_URL use PUBLIC_HUB_URL
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }

    # Raise an exception to trigger a redirect
    # We construct the full URL query string
    redirect_url = f"{AUTH_URL}?{urlencode(params)}"
    # We use a custom exception to break the flow and redirect immediately
    raise HTTPException(status_code=307, headers={"Location": redirect_url})


# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------


@app.get(SERVICE_PREFIX)
async def home(request: Request):
    """
    Home page that shows usage quota information.

    If the user is not logged in, they will be redirected to JupyterHub to log in
    through get_current_user redirect flow.
    """
    user = request.session.get("user")
    if not user:
        # Trigger the login flow
        return await get_current_user(request)

    # Get usage data from Prometheus
    async with PrometheusClient() as prom_client:
        usage_data = await prom_client.get_user_usage(user["name"])

    template = jinja_env.get_template("usage.html")
    html_content = template.render(
        usage_data=usage_data,
    )
    return HTMLResponse(html_content)


@app.get(f"{SERVICE_PREFIX}{CALLBACK_PATH}")
async def oauth_callback(request: Request, code: str, state: str):
    """
    The Hub redirects back here after the user logs in.
    """
    # 1. Verify State (CSRF Protection)
    saved_state = request.session.get("oauth_state")
    if not saved_state or saved_state != state:
        raise HTTPException(status_code=400, detail="OAuth state mismatch or missing")

    # 2. Exchange Code for Token, then 3. Get User Details
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUB_API_URL}/oauth2/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": HUB_TOKEN,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
        )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve access token"
            )

        token_data = resp.json()
        access_token = token_data["access_token"]

        # 3. Get User Details
        resp = await client.get(
            f"{HUB_API_URL}/user",
            headers={"Authorization": f"token {access_token}"},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to retrieve user data")

    user = resp.json()

    # 4. Save User to Session
    request.session["user"] = user
    request.session.pop("oauth_state", None)  # Clean up state

    # 5. Redirect to Home
    return RedirectResponse(url=SERVICE_PREFIX)
