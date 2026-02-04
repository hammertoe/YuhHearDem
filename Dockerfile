# Multi-stage build for YuhHearDem
# Single image serves the FastAPI web application

FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Production image
FROM python:3.13-slim

WORKDIR /app

# Install runtime dependencies (for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app/ ./app/
COPY api/ ./api/
COPY core/ ./core/
COPY models/ ./models/
COPY parsers/ ./parsers/
COPY services/ ./services/
COPY storage/ ./storage/
COPY static/ ./static/
COPY migrations/ ./migrations/
COPY alembic.ini .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/storage /app/processed && \
    chown -R appuser:appuser /app

USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app:${PATH}"

# Health check for web service
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Web server entrypoint
# --proxy-headers trusts X-Forwarded-Proto header for correct HTTPS URL generation
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
