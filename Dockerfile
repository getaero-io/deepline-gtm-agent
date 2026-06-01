FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY deepline_gtm_agent/ ./deepline_gtm_agent/
COPY managed_agent/ ./managed_agent/
COPY server.py ./

RUN pip install --no-cache-dir ".[server]" "anthropic>=0.93.0"

EXPOSE 8000

CMD ["python", "server.py"]
