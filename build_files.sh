#!/bin/bash
set -e

export PIP_BREAK_SYSTEM_PACKAGES=1

echo "==> Setting up Python 3.12 environment..."
if command -v uv >/dev/null 2>&1; then
    echo "==> Using uv with Python 3.12..."
    uv python install 3.12
    uv venv --python 3.12 .venv
    source .venv/bin/activate
    echo "==> Installing dependencies with uv..."
    uv pip install -r requirements.txt
else
    echo "==> Falling back to system python..."
    if command -v python3 >/dev/null 2>&1; then
        PY_BIN=python3
    else
        PY_BIN=python
    fi
    $PY_BIN -m pip install --break-system-packages -r requirements.txt 2>/dev/null || pip install --break-system-packages -r requirements.txt
fi

echo "==> Python version in build environment:"
python --version

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Applying database migrations..."
python manage.py migrate --noinput || true

echo "==> Seeding demo simulation data..."
python manage.py seed_demo --noinput || true

echo "==> Build complete!"
