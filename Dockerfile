FROM python:3.12-slim

WORKDIR /app

# Copy source first (hatchling needs the package to build)
COPY pyproject.toml README.md ./
COPY deepline_gtm_agent/ ./deepline_gtm_agent/
COPY server.py ./

# Install package with server extras
RUN pip install --no-cache-dir ".[server]"

EXPOSE 8000

CMD ["python", "server.py"]
