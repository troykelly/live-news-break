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

# Switch to non-root user
USER newsreader

ENV PYTHONPATH=./src

CMD ["python", "src/main.py"]
