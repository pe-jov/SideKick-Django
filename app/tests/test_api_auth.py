import json

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app.models import AuthToken, Item, ResearchSpace, User


class ApiAuthTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.owner = User.objects.create(
            email="owner@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Owner User",
            created_at=now,
            updated_at=now,
        )
        self.space = ResearchSpace.objects.create(
            owner=self.owner,
            name="API Space",
            description="Space used for API tests.",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )

    def auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_register_returns_token_and_persists_user(self):
        response = self.client.post(
            reverse("app:api_register"),
            data=json.dumps(
                {
                    "fullName": "New User",
                    "email": "new@example.com",
                    "password": "Sidekick123!",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["user"]["email"], "new@example.com")
        self.assertTrue(AuthToken.objects.filter(token_value=body["token"], is_revoked=False).exists())

    def test_register_rejects_weak_password(self):
        response = self.client.post(
            reverse("app:api_register"),
            data=json.dumps(
                {
                    "fullName": "Weak User",
                    "email": "weak@example.com",
                    "password": "password",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "weak_password")

    def test_protected_endpoint_requires_token(self):
        response = self.client.get(reverse("app:api_spaces"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "missing_token")

    def test_login_and_access_protected_resources(self):
        login_response = self.client.post(
            reverse("app:api_login"),
            data=json.dumps(
                {
                    "email": "owner@example.com",
                    "password": "Sidekick123!",
                    "clientType": "web",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(login_response.status_code, 200)
        token = login_response.json()["token"]

        me_response = self.client.get(reverse("app:api_me"), **self.auth_header(token))
        spaces_response = self.client.get(reverse("app:api_spaces"), **self.auth_header(token))

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["user"]["email"], "owner@example.com")
        self.assertEqual(spaces_response.status_code, 200)
        returned_names = {space["name"] for space in spaces_response.json()["spaces"]}
        self.assertIn("API Space", returned_names)

    def test_logout_revokes_token(self):
        token = AuthToken.objects.create(
            user=self.owner,
            token_value="logout-token",
            client_type=AuthToken.ClientType.WEB,
            issued_at=timezone.now(),
            expires_at=None,
            is_revoked=False,
        )

        logout_response = self.client.post(reverse("app:api_logout"), **self.auth_header(token.token_value))
        me_response = self.client.get(reverse("app:api_me"), **self.auth_header(token.token_value))

        self.assertEqual(logout_response.status_code, 204)
        self.assertEqual(me_response.status_code, 401)
        token.refresh_from_db()
        self.assertTrue(token.is_revoked)

    def test_create_and_delete_item_with_token(self):
        login_response = self.client.post(
            reverse("app:api_login"),
            data=json.dumps(
                {
                    "email": "owner@example.com",
                    "password": "Sidekick123!",
                }
            ),
            content_type="application/json",
        )
        token = login_response.json()["token"]

        create_response = self.client.post(
            reverse("app:api_create_item"),
            data=json.dumps(
                {
                    "spaceId": self.space.space_id,
                    "type": "text",
                    "content": "API-created note",
                    "note": "Saved through token auth.",
                }
            ),
            content_type="application/json",
            **self.auth_header(token),
        )

        self.assertEqual(create_response.status_code, 201)
        item_id = create_response.json()["item"]["id"]
        self.assertTrue(Item.objects.filter(item_id=item_id).exists())

        delete_response = self.client.delete(
            reverse("app:api_delete_item", args=[item_id]),
            **self.auth_header(token),
        )

        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(Item.objects.filter(item_id=item_id).exists())
