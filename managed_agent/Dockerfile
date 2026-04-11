FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install deepline CLI from production
RUN curl -fsSL https://code.deepline.com/api/v2/cli/python -o /usr/local/bin/deepline && \
    chmod +x /usr/local/bin/deepline

# Docker build context is repo root, so paths are relative to that
COPY managed_agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY managed_agent/setup.py managed_agent/session.py managed_agent/server.py \
     managed_agent/cli.py managed_agent/chat.html ./

EXPOSE 8000

CMD ["sh", "-c", "mkdir -p ~/.local/deepline/code-deepline-com && printf 'DEEPLINE_API_KEY=%s\\nDEEPLINE_CLAIM_TOKEN=%s\\n' \"$DEEPLINE_API_KEY\" \"${DEEPLINE_CLAIM_TOKEN:-}\" > ~/.local/deepline/code-deepline-com/.env && python server.py"]
