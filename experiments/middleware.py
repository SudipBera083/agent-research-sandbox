"""
Middleware for Step 33 — Production Simulation Orchestration.

Provides:
- JSONResponseNotFoundMiddleware: Converts Http404 to JSON instead of HTML.
- JSONServerErrorMiddleware: Converts 500 errors to JSON, no tracebacks to frontend.
- SimpleCORSMiddleware: Adds CORS headers for Vercel frontend.
"""

import json
import logging

from django.http import Http404, JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class JSONNotFoundMiddleware(MiddlewareMixin):
    """Convert Http404 responses into JSON for API endpoints."""

    def process_response(self, request, response):
        if response.status_code == 404 and request.path.startswith("/api/"):
            reason = response.reason_phrase or "Not Found"
            return JsonResponse(
                {"error": "not_found", "detail": reason},
                status=404,
            )
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, Http404) and request.path.startswith("/api/"):
            return JsonResponse(
                {"error": "not_found", "detail": "Resource not found."},
                status=404,
            )
        return None


class JSONServerErrorMiddleware(MiddlewareMixin):
    """Convert 500 errors into JSON, never exposing tracebacks to the frontend."""

    def process_exception(self, request, exception):
        if isinstance(exception, Http404):
            return None
        if request.path.startswith("/api/"):
            logger.exception(
                "internal_error path=%s error=%s",
                request.path,
                str(exception),
            )
            return JsonResponse(
                {
                    "error": "internal_server_error",
                    "detail": "An internal server error occurred.",
                },
                status=500,
            )
        return None


class SimpleCORSMiddleware(MiddlewareMixin):
    """Minimal CORS middleware for the Vercel frontend.

    Allows configurable origins via CORS_ALLOWED_ORIGINS setting.
    Does not require django-cors-headers.
    """

    sync_capable = True
    async_capable = False

    def __init__(self, get_response):
        super().__init__(get_response)
        self.allowed_origins = self._load_allowed_origins()

    def _load_allowed_origins(self):
        from django.conf import settings
        return set(getattr(settings, "CORS_ALLOWED_ORIGINS", []))

    def process_response(self, request, response):
        origin = request.headers.get("Origin")
        if origin and origin in self.allowed_origins:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response["Access-Control-Max-Age"] = "3600"
        return response

    def process_request(self, request):
        if request.method == "OPTIONS":
            from django.http import HttpResponse
            origin = request.headers.get("Origin")
            if origin and origin in self.allowed_origins:
                resp = HttpResponse(status=204)
                resp["Access-Control-Allow-Origin"] = origin
                resp["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                resp["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
                resp["Access-Control-Max-Age"] = "3600"
                return resp
        return None
