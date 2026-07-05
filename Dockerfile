FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OUTPUT_DIR=/data/output
ENV LOGS_DIR=/data/logs
ENV AUTOMATION_DB_PATH=/data/automation.sqlite

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-local.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-local.txt

COPY . .

RUN mkdir -p /data/output /data/logs

CMD ["python", "automation.py", "serve", "--region", "US", "--mode", "local"]
