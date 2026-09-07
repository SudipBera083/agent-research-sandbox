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
    """CORS middleware for frontend API requests.

    Supports:
    - CORS_ALLOW_ALL_ORIGINS (bool)
    - CORS_ALLOWED_ORIGINS (list/set of origins, supports '*' and wildcard checks)
    - Automatic handling of OPTIONS preflight requests (204 No Content)
    - Safe handling of all standard API methods and headers
    - Dynamic configuration via django.conf.settings (friendly with override_settings)
    """

    sync_capable = True
    async_capable = False

    def _is_origin_allowed(self, origin: str | None) -> bool:
        if not origin:
            return False

        from django.conf import settings

        if getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False):
            return True

        allowed = set(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
        if "*" in allowed:
            return True

        if origin in allowed:
            return True

        # Automatically allow localhost and 127.0.0.1 on any port in development
        if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
            return True

        return False

    def _apply_cors_headers(self, response, origin: str, request=None):
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD"
        req_headers = request.headers.get("Access-Control-Request-Headers") if request else None
        response["Access-Control-Allow-Headers"] = (
            req_headers
            if req_headers
            else "Content-Type, Authorization, X-Requested-With, Accept, Origin, Cache-Control, Last-Event-ID"
        )
        response["Access-Control-Max-Age"] = "86400"
        return response

    def process_request(self, request):
        if request.method == "OPTIONS":
            from django.http import HttpResponse

            origin = request.headers.get("Origin")
            if self._is_origin_allowed(origin):
                resp = HttpResponse(status=204)
                return self._apply_cors_headers(resp, origin, request)
        return None

    def process_response(self, request, response):
        origin = request.headers.get("Origin")
        if self._is_origin_allowed(origin):
            self._apply_cors_headers(response, origin, request)
        return response
