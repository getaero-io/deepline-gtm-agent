FROM python:3.12-slim

WORKDIR /app

# Install the deepline CLI from production
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY setup.py session.py server.py cli.py chat.html ./

EXPOSE 8000

CMD ["python", "server.py"]
