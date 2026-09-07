#!/bin/bash
set -e

echo "==> Installing Python dependencies..."
python -m pip install -r requirements.txt

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Applying database migrations..."
python manage.py migrate --noinput

echo "==> Seeding demo simulation data..."
python manage.py seed_demo --noinput || true

echo "==> Build complete!"
