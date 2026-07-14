"""Testovi za opoziv deljenih linkova i posledice po viewer pristup."""

import json

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app.models import AuthToken, Membership, ResearchSpace, ShareLink, User


class ShareLinkRevokeTests(TestCase):
    """Proverava da opoziv deljenog linka uklanja viewer pristup, ali ne i saradnike."""

    def setUp(self):
        """Priprema vlasnika, članove, prostor i deljeni link za test opoziva."""
        now = timezone.now()
        self.owner = User.objects.create(
            email="owner-share@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Space Owner",
            created_at=now,
            updated_at=now,
        )
        self.viewer = User.objects.create(
            email="viewer@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Linked Viewer",
            created_at=now,
            updated_at=now,
        )
        self.collaborator = User.objects.create(
            email="collab@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Real Collaborator",
            created_at=now,
            updated_at=now,
        )
        self.space = ResearchSpace.objects.create(
            owner=self.owner,
            name="Revokable Space",
            description="Share link revoke tests.",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        self.share_link = ShareLink.objects.create(
            space=self.space,
            created_by=self.owner,
            token="revokable-link-token",
            created_at=now,
            expires_at=None,
            is_active=True,
        )
        self.viewer_membership = Membership.objects.create(
            space=self.space,
            user=self.viewer,
            joined_via=self.share_link,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        self.collaborator_membership = Membership.objects.create(
            space=self.space,
            user=self.collaborator,
            joined_via=None,
            role=Membership.Role.COLLABORATOR,
            status=Membership.Status.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        self.owner_token = AuthToken.objects.create(
            user=self.owner,
            token_value="owner-share-token",
            client_type=AuthToken.ClientType.WEB,
            issued_at=now,
            expires_at=None,
            is_revoked=False,
        )
        self.viewer_token = AuthToken.objects.create(
            user=self.viewer,
            token_value="viewer-share-token",
            client_type=AuthToken.ClientType.WEB,
            issued_at=now,
            expires_at=None,
            is_revoked=False,
        )
        self.collaborator_token = AuthToken.objects.create(
            user=self.collaborator,
            token_value="collaborator-share-token",
            client_type=AuthToken.ClientType.WEB,
            issued_at=now,
            expires_at=None,
            is_revoked=False,
        )

    def auth_header(self, token):
        """Vraća Authorization zaglavlje za prosleđeni test token."""
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_revoke_share_link_removes_viewer_access_but_keeps_collaborator(self):
        viewer_before = self.client.get(
            reverse("app:api_space_detail", args=[self.space.space_id]),
            **self.auth_header(self.viewer_token.token_value),
        )
        collaborator_before = self.client.get(
            reverse("app:api_space_detail", args=[self.space.space_id]),
            **self.auth_header(self.collaborator_token.token_value),
        )

        revoke_response = self.client.delete(
            reverse("app:api_space_share_link", args=[self.space.space_id]),
            **self.auth_header(self.owner_token.token_value),
        )

        viewer_after = self.client.get(
            reverse("app:api_space_detail", args=[self.space.space_id]),
            **self.auth_header(self.viewer_token.token_value),
        )
        collaborator_after = self.client.get(
            reverse("app:api_space_detail", args=[self.space.space_id]),
            **self.auth_header(self.collaborator_token.token_value),
        )

        self.assertEqual(viewer_before.status_code, 200)
        self.assertEqual(collaborator_before.status_code, 200)
        self.assertEqual(revoke_response.status_code, 200)
        self.assertEqual(revoke_response.json()["revokedLinks"], 1)
        self.assertEqual(viewer_after.status_code, 404)
        self.assertEqual(collaborator_after.status_code, 200)

        self.share_link.refresh_from_db()
        self.viewer_membership.refresh_from_db()
        self.collaborator_membership.refresh_from_db()
        self.assertFalse(self.share_link.is_active)
        self.assertEqual(self.viewer_membership.status, Membership.Status.REMOVED)
        self.assertEqual(self.collaborator_membership.status, Membership.Status.ACTIVE)

    def test_joined_viewer_cannot_reuse_revoked_link(self):
        revoke_response = self.client.delete(
            reverse("app:api_space_share_link", args=[self.space.space_id]),
            **self.auth_header(self.owner_token.token_value),
        )
        self.assertEqual(revoke_response.status_code, 200)

        share_page_response = self.client.get(reverse("app:share_link_access", args=[self.share_link.token]))
        self.assertEqual(share_page_response.status_code, 404)
