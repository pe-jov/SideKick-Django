from django.contrib.auth.hashers import make_password
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone

from app.middleware import ExtensionCsrfBypassMiddleware
from app.models import AuthToken, User


class ExtensionCsrfBypassMiddlewareTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.factory = RequestFactory()
        self.user = User.objects.create(
            email="middleware@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Middleware User",
            created_at=now,
            updated_at=now,
        )
        self.token = AuthToken.objects.create(
            user=self.user,
            token_value="middleware-extension-token",
            client_type=AuthToken.ClientType.EXTENSION,
            issued_at=now,
            expires_at=None,
            is_revoked=False,
        )
        self.middleware = ExtensionCsrfBypassMiddleware(lambda request: HttpResponse("ok"))

    def test_api_post_request_skips_csrf_without_extension_token(self):
        request = self.factory.post("/api/spaces/")

        self.middleware(request)

        self.assertTrue(request._dont_enforce_csrf_checks)

    def test_extension_token_post_request_skips_csrf_for_non_api_route(self):
        request = self.factory.post(
            "/items/create/",
            HTTP_AUTHORIZATION=f"Token {self.token.token_value}",
        )

        self.middleware(request)

        self.assertTrue(request._dont_enforce_csrf_checks)

    def test_regular_non_api_post_request_keeps_csrf_enabled(self):
        request = self.factory.post("/items/create/")

        self.middleware(request)

        self.assertFalse(hasattr(request, "_dont_enforce_csrf_checks"))
