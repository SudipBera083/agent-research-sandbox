import logging
import os

from config.wsgi import application

logger = logging.getLogger(__name__)

# Run lightweight migration/seed check on worker cold-start if DATABASE_URL is set
_initialized = False


def _ensure_db_initialized():
    global _initialized
    if _initialized:
        return
    _initialized = True

    if os.getenv("DATABASE_URL"):
        try:
            from django.core.management import call_command

            call_command("migrate", interactive=False)
            call_command("seed_demo", interactive=False)
        except Exception as e:
            logger.warning(
                "Database auto-init during startup skipped or failed: %s", e
            )


try:
    _ensure_db_initialized()
except Exception:
    pass

# Vercel Python serverless runtime entry point
app = application
