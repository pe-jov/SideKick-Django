"""Testovi za P1 tokove: profil, saradnja, deljenje i dozvole pristupa."""

import json

from django.contrib.auth.hashers import check_password, make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app.context import get_or_create_universal_space
from app.models import AuthToken, CollaborationRequest, Item, Membership, ResearchSpace, ShareLink, User


class P1FlowTests(TestCase):
    """Proverava ključne P1 funkcionalnosti i pravila dozvola u aplikaciji."""

    def setUp(self):
        """Priprema korisnike, tokenе, prostor i deljeni link za P1 scenarije."""
        now = timezone.now()
        self.owner = User.objects.create(
            email="p1-owner@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="P1 Owner",
            created_at=now,
            updated_at=now,
        )
        self.other = User.objects.create(
            email="other@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Other User",
            created_at=now,
            updated_at=now,
        )
        self.viewer = User.objects.create(
            email="p1-viewer@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="P1 Viewer",
            created_at=now,
            updated_at=now,
        )
        self.collaborator = User.objects.create(
            email="p1-collaborator@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="P1 Collaborator",
            created_at=now,
            updated_at=now,
        )
        self.space = ResearchSpace.objects.create(
            owner=self.owner,
            name="P1 Space",
            description="Original description",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        self.share_link = ShareLink.objects.create(
            space=self.space,
            created_by=self.owner,
            token="p1-share-token",
            created_at=now,
            expires_at=None,
            is_active=True,
        )
        self.owner_token = AuthToken.objects.create(
            user=self.owner,
            token_value="p1-owner-token",
            client_type=AuthToken.ClientType.WEB,
            issued_at=now,
            expires_at=None,
            is_revoked=False,
        )
        self.other_token = AuthToken.objects.create(
            user=self.other,
            token_value="p1-other-token",
            client_type=AuthToken.ClientType.WEB,
            issued_at=now,
            expires_at=None,
            is_revoked=False,
        )
        self.viewer_token = AuthToken.objects.create(
            user=self.viewer,
            token_value="p1-viewer-token",
            client_type=AuthToken.ClientType.WEB,
            issued_at=now,
            expires_at=None,
            is_revoked=False,
        )
        self.collaborator_token = AuthToken.objects.create(
            user=self.collaborator,
            token_value="p1-collaborator-token",
            client_type=AuthToken.ClientType.WEB,
            issued_at=now,
            expires_at=None,
            is_revoked=False,
        )

    def auth_header(self, token):
        """Vraća Authorization zaglavlje za prosleđeni API token."""
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def login_session(self, user):
        """Postavlja sesiju prijavljenog korisnika za web tokove u testovima."""
        session = self.client.session
        session["sidekick_user_id"] = user.user_id
        session.save()

    def test_api_me_patch_updates_profile_and_keeps_unique_email(self):
        response = self.client.patch(
            reverse("app:api_me"),
            data=json.dumps({"fullName": "Owner Updated", "email": "updated-owner@example.com"}),
            content_type="application/json",
            **self.auth_header(self.owner_token.token_value),
        )

        self.assertEqual(response.status_code, 200)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.full_name, "Owner Updated")
        self.assertEqual(self.owner.email, "updated-owner@example.com")

    def test_api_change_password_updates_hash_and_old_password_stops_working(self):
        response = self.client.post(
            reverse("app:api_change_password"),
            data=json.dumps(
                {
                    "currentPassword": "Sidekick123!",
                    "newPassword": "Stronger456!",
                    "confirmPassword": "Stronger456!",
                }
            ),
            content_type="application/json",
            **self.auth_header(self.owner_token.token_value),
        )

        self.assertEqual(response.status_code, 200)
        self.owner.refresh_from_db()
        self.assertTrue(check_password("Stronger456!", self.owner.password_hash))

        old_login = self.client.post(
            reverse("app:api_login"),
            data=json.dumps({"email": "p1-owner@example.com", "password": "Sidekick123!"}),
            content_type="application/json",
        )
        new_login = self.client.post(
            reverse("app:api_login"),
            data=json.dumps({"email": "p1-owner@example.com", "password": "Stronger456!"}),
            content_type="application/json",
        )
        self.assertEqual(old_login.status_code, 401)
        self.assertEqual(new_login.status_code, 200)

    def test_owner_can_edit_space_via_api(self):
        response = self.client.patch(
            reverse("app:api_space_detail", args=[self.space.space_id]),
            data=json.dumps({"name": "Renamed Space", "description": "Updated description"}),
            content_type="application/json",
            **self.auth_header(self.owner_token.token_value),
        )

        self.assertEqual(response.status_code, 200)
        self.space.refresh_from_db()
        self.assertEqual(self.space.name, "Renamed Space")
        self.assertEqual(self.space.description, "Updated description")

    def test_rejected_collaboration_request_cannot_be_resent(self):
        CollaborationRequest.objects.create(
            space=self.space,
            requester=self.viewer,
            resolved_by=self.owner,
            status=CollaborationRequest.Status.REJECTED,
            message="Owner rejected the request.",
            requested_at=timezone.now(),
            resolved_at=timezone.now(),
        )
        self.login_session(self.viewer)

        response = self.client.post(reverse("app:request_shared_space_access", args=[self.share_link.token]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            CollaborationRequest.objects.filter(space=self.space, requester=self.viewer).count(),
            1,
        )
        existing = CollaborationRequest.objects.get(space=self.space, requester=self.viewer)
        self.assertEqual(existing.status, CollaborationRequest.Status.REJECTED)

    def test_existing_member_cannot_request_collaboration_again(self):
        Membership.objects.create(
            space=self.space,
            user=self.viewer,
            joined_via=None,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.login_session(self.viewer)

        response = self.client.post(reverse("app:request_shared_space_access", args=[self.share_link.token]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            CollaborationRequest.objects.filter(space=self.space, requester=self.viewer).exists()
        )

    def test_viewer_can_request_collaboration_from_space_team(self):
        Membership.objects.create(
            space=self.space,
            user=self.viewer,
            joined_via=self.share_link,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.login_session(self.viewer)

        response = self.client.post(
            reverse("app:request_space_collaboration", args=[self.space.space_id]),
            data={"next_url": f'{reverse("app:space_detail", args=[self.space.space_id])}?modal=team'},
        )

        self.assertEqual(response.status_code, 302)
        request_record = CollaborationRequest.objects.get(space=self.space, requester=self.viewer)
        self.assertEqual(request_record.status, CollaborationRequest.Status.PENDING)
        self.assertEqual(request_record.message, "Requested collaborator access from the Team panel.")

    def test_collaborator_request_from_space_team_is_blocked(self):
        Membership.objects.create(
            space=self.space,
            user=self.collaborator,
            joined_via=None,
            role=Membership.Role.COLLABORATOR,
            status=Membership.Status.ACTIVE,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.login_session(self.collaborator)

        response = self.client.post(
            reverse("app:request_space_collaboration", args=[self.space.space_id]),
            data={"next_url": f'{reverse("app:space_detail", args=[self.space.space_id])}?modal=team'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            CollaborationRequest.objects.filter(space=self.space, requester=self.collaborator).exists()
        )

    def test_api_create_item_accepts_remote_image_url(self):
        response = self.client.post(
            reverse("app:api_create_item"),
            data=json.dumps(
                {
                    "spaceId": self.space.space_id,
                    "type": "image",
                    "imageSourceUrl": "https://example.com/reference-board.jpg",
                    "title": "Reference board",
                    "note": "Captured from the web.",
                }
            ),
            content_type="application/json",
            **self.auth_header(self.owner_token.token_value),
        )

        self.assertEqual(response.status_code, 201)
        item = Item.objects.get(item_id=response.json()["item"]["id"])
        self.assertEqual(item.item_type, Item.ItemType.IMAGE)
        self.assertEqual(item.source_url, "https://example.com/reference-board.jpg")

    def test_space_direct_upload_endpoint_accepts_ajax_image_url_capture(self):
        self.login_session(self.owner)

        response = self.client.post(
            reverse("app:create_item"),
            data={
                "space_id": self.space.space_id,
                "item_type": "image",
                "image_source_url": "https://example.com/dropped-image.png",
                "image_title": "Dropped image",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "ok")
        item = Item.objects.latest("item_id")
        self.assertEqual(item.item_type, Item.ItemType.IMAGE)
        self.assertEqual(item.source_url, "https://example.com/dropped-image.png")

    def test_non_member_does_not_see_unrelated_space_in_api_list(self):
        response = self.client.get(
            reverse("app:api_spaces"),
            **self.auth_header(self.other_token.token_value),
        )

        self.assertEqual(response.status_code, 200)
        returned_names = {space["name"] for space in response.json()["spaces"]}
        self.assertNotIn("P1 Space", returned_names)

    def test_universal_space_is_hidden_from_space_listing(self):
        get_or_create_universal_space(self.owner)

        response = self.client.get(
            reverse("app:api_spaces"),
            **self.auth_header(self.owner_token.token_value),
        )

        self.assertEqual(response.status_code, 200)
        returned_names = {space["name"] for space in response.json()["spaces"]}
        self.assertNotIn("Inbox", returned_names)

    def test_collaborator_can_add_items_but_cannot_manage_space_settings(self):
        Membership.objects.create(
            space=self.space,
            user=self.collaborator,
            joined_via=None,
            role=Membership.Role.COLLABORATOR,
            status=Membership.Status.ACTIVE,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        create_item = self.client.post(
            reverse("app:api_create_item"),
            data=json.dumps(
                {
                    "spaceId": self.space.space_id,
                    "type": "text",
                    "content": "Collaborator note",
                }
            ),
            content_type="application/json",
            **self.auth_header(self.collaborator_token.token_value),
        )
        update_space = self.client.patch(
            reverse("app:api_space_detail", args=[self.space.space_id]),
            data=json.dumps({"name": "Not allowed"}),
            content_type="application/json",
            **self.auth_header(self.collaborator_token.token_value),
        )
        share_link = self.client.post(
            reverse("app:api_space_share_link", args=[self.space.space_id]),
            **self.auth_header(self.collaborator_token.token_value),
        )

        self.assertEqual(create_item.status_code, 201)
        self.assertEqual(update_space.status_code, 403)
        self.assertEqual(share_link.status_code, 403)

    def test_viewer_can_read_but_cannot_add_item(self):
        Membership.objects.create(
            space=self.space,
            user=self.viewer,
            joined_via=self.share_link,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        detail_response = self.client.get(
            reverse("app:api_space_detail", args=[self.space.space_id]),
            **self.auth_header(self.viewer_token.token_value),
        )
        create_item = self.client.post(
            reverse("app:api_create_item"),
            data=json.dumps(
                {
                    "spaceId": self.space.space_id,
                    "type": "text",
                    "content": "Viewer note",
                }
            ),
            content_type="application/json",
            **self.auth_header(self.viewer_token.token_value),
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(create_item.status_code, 403)

    def test_owner_can_move_item_from_universal_space_into_regular_space(self):
        universal_space = get_or_create_universal_space(self.owner)
        item = Item.objects.create(
            space=universal_space,
            added_by=self.owner,
            item_type=Item.ItemType.TEXT,
            content_text="Sort later",
            source_url="",
            image_path="",
            title="",
            note="",
            source_platform=Item.SourcePlatform.WEB,
            captured_url="",
            page_title="",
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.login_session(self.owner)

        response = self.client.post(
            reverse("app:move_item"),
            data={"item_id": item.item_id, "target_space_id": self.space.space_id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.space_id, self.space.space_id)
