from .context import get_request_auth_token
from .models import AuthToken


class ExtensionCsrfBypassMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            if request.path.startswith("/api/"):
                request._dont_enforce_csrf_checks = True
            else:
                auth_token = get_request_auth_token(request)
                if auth_token is not None and auth_token.client_type == AuthToken.ClientType.EXTENSION:
                    request._dont_enforce_csrf_checks = True

        return self.get_response(request)
