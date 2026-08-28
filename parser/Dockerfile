FROM python:3.10-slim

# Set environment settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (e.g. for any pdf libraries or helper utilities if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code files
COPY . /app/

# Create folders for uploads, logs, and outputs
RUN mkdir -p /app/uploads /app/logs /app/output

# Set entrypoint
CMD ["tail", "-f", "/dev/null"]
