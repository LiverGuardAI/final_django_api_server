#!/bin/bash
set -e

# Wait for external PostgreSQL (with timeout)
echo "Waiting for PostgreSQL at $POSTGRES_HOST:$POSTGRES_PORT..."
timeout=60
elapsed=0
until nc -z $POSTGRES_HOST $POSTGRES_PORT || [ $elapsed -ge $timeout ]; do
  sleep 1
  elapsed=$((elapsed + 1))
done
if [ $elapsed -ge $timeout ]; then
  echo "Warning: PostgreSQL not reachable after ${timeout}s, continuing anyway..."
else
  echo "PostgreSQL connected"
fi

echo "Waiting for Redis..."
while ! nc -z $REDIS_HOST $REDIS_PORT; do
  sleep 0.5
done
echo "Redis started"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput || true

echo "Starting server..."
exec "$@"