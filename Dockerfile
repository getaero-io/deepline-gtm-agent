FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[server]"

# Copy source
COPY deepline_gtm_agent/ ./deepline_gtm_agent/
COPY server.py ./

EXPOSE 8000

CMD ["python", "server.py"]
