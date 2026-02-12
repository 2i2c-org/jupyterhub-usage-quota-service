FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src ./src

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Expose service port
EXPOSE 9000

# Run the application
CMD ["fastapi", "run", "src/jupyterhub_usage_quota/service/app.py", "--port", "9000"]
