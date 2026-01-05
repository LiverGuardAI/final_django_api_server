# Django API Server Dockerfile
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    netcat-traditional \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY final_django_api_server/ /app/

# Create static files directory
RUN mkdir -p /app/staticfiles /app/mediafiles

# Collect static files (ignore errors for now)
RUN python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 8000

# Default command (will be overridden by docker-compose)
CMD ["gunicorn", "liverguard_api_server.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]