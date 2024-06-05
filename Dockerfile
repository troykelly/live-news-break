FROM python:3.12-slim

# Create a group and user with specific uid and gid
RUN groupadd -g 1000 newsreader && useradd -u 1000 -g newsreader -d /app -s /bin/bash newsreader

WORKDIR /app

# Install dependencies and create a virtual environment
COPY requirements.txt .
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy application code and default configuration with proper ownership
COPY --chown=newsreader:newsreader src /app/src
COPY --chown=newsreader:newsreader lexicon.json prompt.md /app/

# Ensure the working directory has correct ownership
RUN chown -R newsreader:newsreader /app

# Metadata labels for best practices
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG REPO_URL

LABEL maintainer="troy@troykelly.com" \
      org.opencontainers.image.title="AI Live News Reader" \
      org.opencontainers.image.description="Generates news content for radio stations" \
      org.opencontainers.image.authors="Troy Kelly <troy@troykellycom>" \
      org.opencontainers.image.vendor="Troy Kelly" \
      org.opencontainers.image.licenses="Apache 2.0" \
      org.opencontainers.image.url="${REPO_URL}" \
      org.opencontainers.image.source="${REPO_URL}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}"

# Switch to non-root user
USER newsreader

ENV PYTHONPATH=./src

CMD ["python", "src/main.py"]
