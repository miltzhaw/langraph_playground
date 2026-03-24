FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Flowcept with MongoDB support
RUN pip install --no-cache-dir \
flowcept[mongo,llm_agent] \
prov \
"prov[rdf]" \
rdflib

# Copy source
COPY . .

# Initialize Flowcept settings
RUN flowcept --init-settings
# Set environment
ENV PYTHONUNBUFFERED=1
ENV FLOWCEPT_SETTINGS_PATH=/app/.flowcept/settings.yaml

# Default to interactive shell
CMD ["/bin/bash"]
