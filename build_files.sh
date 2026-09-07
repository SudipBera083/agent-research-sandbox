#!/bin/bash
set -e

export PIP_BREAK_SYSTEM_PACKAGES=1

echo "==> Detecting Python environment..."
if command -v python3 >/dev/null 2>&1; then
    PY_BIN=python3
else
    PY_BIN=python
fi

echo "==> Installing Python dependencies..."
if command -v uv >/dev/null 2>&1; then
    uv pip install --system -r requirements.txt
else
    $PY_BIN -m pip install --break-system-packages -r requirements.txt 2>/dev/null || pip install --break-system-packages -r requirements.txt
fi

echo "==> Collecting static files..."
$PY_BIN manage.py collectstatic --noinput

echo "==> Applying database migrations..."
$PY_BIN manage.py migrate --noinput || true

echo "==> Seeding demo simulation data..."
$PY_BIN manage.py seed_demo --noinput || true

echo "==> Build complete!"
