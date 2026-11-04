FROM python:3.12-slim

# Links the image published on ghcr.io to this repository (shows up under "Packages" on GitHub).
LABEL org.opencontainers.image.source="https://github.com/haciyil38/tp-integration-continue"

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

RUN useradd --system --uid 10001 pipeline
USER pipeline

# Default command: process every CSV found in the S3 bucket (settings come from the environment).
CMD ["python", "-m", "pipeline.run"]
