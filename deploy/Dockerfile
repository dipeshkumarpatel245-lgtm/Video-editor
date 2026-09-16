FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py edit.py ffutils.py ./
COPY analysis analysis
COPY template template
COPY recreate recreate
COPY export export
COPY server server
COPY workers workers
COPY web web

EXPOSE 8000