# SprintStrat CI/CD Runner Docker Image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama for local LLM support
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install SprintStrat with all integrations
RUN pip install --no-cache-dir strategy-pm[all]

# Install LLX
RUN pip install --no-cache-dir llx

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create directories
RUN mkdir -p /workspace /app/results

# Set environment variables
ENV PYTHONPATH=/app
ENV WORKSPACE=/workspace
ENV RESULTS_DIR=/app/results

# Expose port for Ollama
EXPOSE 11434

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD strategy-pm --version || exit 1

# Entry point
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["auto", "loop"]
