FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir "deepagents>=0.4" "langchain-anthropic>=1.4" "langchain-openai>=0.3" "httpx>=0.28" "fastapi>=0.115" "uvicorn>=0.32" "python-multipart>=0.0.12"

# Copy source
COPY deepline_gtm_agent/ ./deepline_gtm_agent/
COPY server.py ./

EXPOSE 8000

CMD ["python", "server.py"]
