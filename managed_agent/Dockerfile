FROM python:3.12-slim

WORKDIR /app

# Docker build context is repo root, so paths are relative to that
COPY pyproject.toml README.md ./
COPY deepline_gtm_agent/ ./deepline_gtm_agent/
COPY managed_agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY managed_agent/setup.py managed_agent/session.py managed_agent/server.py \
     managed_agent/cli.py managed_agent/chat.html ./

EXPOSE 8000

CMD ["python", "server.py"]
