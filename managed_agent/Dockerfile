FROM python:3.12-slim

WORKDIR /app

# Docker build context is repo root, so paths are relative to that
COPY pyproject.toml README.md ./
COPY managed_agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY deepline_gtm_agent/ ./deepline_gtm_agent/
COPY managed_agent/ ./managed_agent/
COPY server.py ./

EXPOSE 8000

CMD ["python", "server.py"]
