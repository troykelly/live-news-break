FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy application code
COPY src /app/src

# Copy application default configuration
COPY lexicon.json prompt.md /app/

CMD ["python", "src/main.py"]