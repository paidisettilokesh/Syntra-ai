# ==============================================================================
# STAGE 1: Build Dependencies
# ==============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ==============================================================================
# STAGE 2: Production Runtime
# ==============================================================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime dependencies (Tesseract OCR for attachments processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Copy installed python dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Create a low-privileged system user/group
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser

# Set up required persistent data & logging folders
RUN mkdir -p data data/temp logs && \
    chown -R appuser:appgroup /app

# Copy application source code
COPY src/ /app/src/
COPY main.py /app/
COPY pyproject.toml /app/
COPY scripts/ /app/scripts/
COPY dashboard/ /app/dashboard/

# Set file permissions for the non-root runner user
RUN chown -R appuser:appgroup /app

# Run as non-root user
USER appuser

# Configure runtime variables
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Expose dashboard port
EXPOSE 8080

# Health check runs local script checking SQLite repository and Scheduler status
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "scripts/health_check.py"]

ENTRYPOINT ["python", "main.py"]
