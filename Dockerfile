FROM python:3.11-slim

WORKDIR /app

# Install ffmpeg and basic tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code (and tokens.json if present)
COPY . .

# Ensure downloads dir exists
RUN mkdir -p /app/downloads

# Environment so Pyrogram can run without TTY issues
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "did.py"]
