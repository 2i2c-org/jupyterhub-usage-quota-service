# JupyterHub Usage Quota Service

A JupyterHub service that allows users to check their current storage (and eventually compute) quota and usage. This service integrates with JupyterHub as a menu item and displays usage information by querying Prometheus metrics.


## Project Overview

This project implements a JupyterHub external service that:
1. Registers as a service in JupyterHub and appears in the Services dropdown menu
2. Authenticates users via JupyterHub's OAuth flow
3. Queries Prometheus for storage usage metrics (or uses mock data in development)
4. Displays usage information in a user-friendly web interface inside JupyterHub

For more details, see the [GitHub issue #7159](https://github.com/2i2c-org/infrastructure/issues/7159).


## Quick Start


### Development Workflows

**Quick Start:**
```bash
# Start all services
docker compose up --build

# Access JupyterHub at http://localhost:8000
```

### Accessing the Application

1. **Open JupyterHub**: http://localhost:8000
2. **Login**: Use any username (DummyAuthenticator - use any password)
3. **Navigate**: Click "Usage" in the menu
4. **View usage**: The service displays mock storage usage (5 GB / 10 GB quota)

## License

This project is licensed under the BSD 3-Clause License.
