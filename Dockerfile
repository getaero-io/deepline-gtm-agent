FROM python:3.12-slim

WORKDIR /app

# Install system deps + curl (for Deepline CLI install)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Deepline CLI from prod
RUN bash <(curl -sS https://code.deepline.com/api/v2/cli/install) --yes

# Make sure deepline is on PATH
ENV PATH="/root/.local/bin:$PATH"

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[server]"

# Copy source
COPY deepline_gtm_agent/ ./deepline_gtm_agent/
COPY server.py ./

EXPOSE 8000

CMD ["python", "server.py"]
