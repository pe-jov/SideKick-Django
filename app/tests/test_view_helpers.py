from django.contrib.auth.hashers import make_password
from django.test import RequestFactory, TestCase
from django.utils import timezone

from app.context import get_or_create_universal_space
from app.models import Item, Membership, ResearchSpace, User
from app.views import (
    active_share_link,
    append_request_auth,
    can_add_items,
    can_delete_item_record,
    can_manage_members,
    can_move_item_record,
    create_collaboration_request,
    looks_like_absolute_url,
    normalized_url,
    password_validation_error,
    sanitize_next_url,
    serialize_request_state,
    url_with_query,
)
from app.models import AuthToken, CollaborationRequest, ShareLink


class ViewHelperTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.factory = RequestFactory()

        self.owner = User.objects.create(
            email="owner-view-helpers@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Owner View Helpers",
            created_at=now,
            updated_at=now,
        )
        self.collaborator = User.objects.create(
            email="collaborator-view-helpers@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Collaborator View Helpers",
            created_at=now,
            updated_at=now,
        )
        self.viewer = User.objects.create(
            email="viewer-view-helpers@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Viewer View Helpers",
            created_at=now,
            updated_at=now,
        )

        self.space = ResearchSpace.objects.create(
            owner=self.owner,
            name="Main Space",
            description="Main working space",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        self.target_space = ResearchSpace.objects.create(
            owner=self.owner,
            name="Target Space",
            description="Target space",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        self.extension_token = AuthToken.objects.create(
            user=self.owner,
            token_value="view-helper-extension-token",
            client_type=AuthToken.ClientType.EXTENSION,
            issued_at=now,
            expires_at=None,
            is_revoked=False,
        )
        self.active_link = ShareLink.objects.create(
            space=self.space,
            created_by=self.owner,
            token="view-helper-active-link",
            created_at=now,
            expires_at=None,
            is_active=True,
        )
        self.expired_link = ShareLink.objects.create(
            space=self.space,
            created_by=self.owner,
            token="view-helper-expired-link",
            created_at=now,
            expires_at=now - timezone.timedelta(days=1),
            is_active=True,
        )
        Membership.objects.create(
            space=self.space,
            user=self.collaborator,
            joined_via=None,
            role=Membership.Role.COLLABORATOR,
            status=Membership.Status.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        Membership.objects.create(
            space=self.target_space,
            user=self.collaborator,
            joined_via=None,
            role=Membership.Role.COLLABORATOR,
            status=Membership.Status.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        Membership.objects.create(
            space=self.space,
            user=self.viewer,
            joined_via=None,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
            created_at=now,
            updated_at=now,
        )

        self.owner_item = Item.objects.create(
            space=self.space,
            added_by=self.owner,
            item_type=Item.ItemType.TEXT,
            content_text="Owner text",
            source_url="",
            image_path="",
            title="",
            note="",
            source_platform=Item.SourcePlatform.WEB,
            captured_url="",
            page_title="",
            created_at=now,
            updated_at=now,
        )
        self.collaborator_item = Item.objects.create(
            space=self.space,
            added_by=self.collaborator,
            item_type=Item.ItemType.TEXT,
            content_text="Collaborator text",
            source_url="",
            image_path="",
            title="",
            note="",
            source_platform=Item.SourcePlatform.WEB,
            captured_url="",
            page_title="",
            created_at=now,
            updated_at=now,
        )

    def test_normalized_url_and_absolute_url_detection(self):
        self.assertEqual(normalized_url("example.com/article"), "https://example.com/article")
        self.assertEqual(normalized_url("https://example.com/article"), "https://example.com/article")
        self.assertEqual(normalized_url(""), "")
        self.assertTrue(looks_like_absolute_url("https://example.com/article"))
        self.assertFalse(looks_like_absolute_url("example.com/article"))

    def test_password_validation_error_returns_first_failing_rule(self):
        self.assertEqual(
            password_validation_error("short"),
            "Password must have at least 8 characters.",
        )
        self.assertIsNone(password_validation_error("StrongPass123!"))

    def test_sanitize_next_url_accepts_internal_and_rejects_external(self):
        internal_request = self.factory.post("/login/", {"next_url": "/profile/"})
        external_request = self.factory.post("/login/", {"next_url": "https://evil.example.com"})

        self.assertEqual(sanitize_next_url(internal_request, "/"), "/profile/")
        self.assertEqual(sanitize_next_url(external_request, "/"), "/")

    def test_permission_helpers_respect_owner_collaborator_and_viewer_roles(self):
        self.assertTrue(can_add_items(self.space, self.owner))
        self.assertTrue(can_add_items(self.space, self.collaborator))
        self.assertFalse(can_add_items(self.space, self.viewer))

        self.assertTrue(can_delete_item_record(self.owner_item, self.owner))
        self.assertTrue(can_delete_item_record(self.collaborator_item, self.collaborator))
        self.assertFalse(can_delete_item_record(self.owner_item, self.collaborator))
        self.assertFalse(can_delete_item_record(self.collaborator_item, self.viewer))

        self.assertTrue(can_manage_members(self.space, self.owner))
        self.assertFalse(can_manage_members(self.space, self.collaborator))

    def test_can_move_item_record_requires_delete_and_target_add_permissions(self):
        self.assertTrue(can_move_item_record(self.collaborator_item, self.collaborator, self.target_space))
        self.assertFalse(can_move_item_record(self.owner_item, self.collaborator, self.target_space))
        self.assertFalse(can_move_item_record(self.collaborator_item, self.viewer, self.target_space))

    def test_can_move_item_record_from_universal_space_only_for_owner_item_owner(self):
        now = timezone.now()
        universal_space = get_or_create_universal_space(self.owner)
        inbox_item = Item.objects.create(
            space=universal_space,
            added_by=self.owner,
            item_type=Item.ItemType.TEXT,
            content_text="Inbox note",
            source_url="",
            image_path="",
            title="",
            note="",
            source_platform=Item.SourcePlatform.WEB,
            captured_url="",
            page_title="",
            created_at=now,
            updated_at=now,
        )

        self.assertTrue(can_move_item_record(inbox_item, self.owner, self.space))
        self.assertFalse(can_move_item_record(inbox_item, self.collaborator, self.target_space))

    def test_append_request_auth_and_url_with_query_preserve_extension_token(self):
        request = self.factory.get(
            "/spaces/1/",
            {"authToken": self.extension_token.token_value, "mock": "login"},
            HTTP_AUTHORIZATION=f"Token {self.extension_token.token_value}",
        )
        request.session = {}

        appended = append_request_auth("/profile/", request)
        updated = url_with_query(request, dialog="create-space", mock=None)

        self.assertEqual(appended, "/profile/?authToken=view-helper-extension-token")
        self.assertIn("authToken=view-helper-extension-token", updated)
        self.assertIn("dialog=create-space", updated)
        self.assertNotIn("mock=login", updated)

    def test_active_share_link_ignores_expired_and_returns_latest_valid(self):
        newer_link = ShareLink.objects.create(
            space=self.space,
            created_by=self.owner,
            token="view-helper-new-link",
            created_at=timezone.now() + timezone.timedelta(seconds=1),
            expires_at=None,
            is_active=True,
        )

        result = active_share_link(self.space)

        self.assertEqual(result.share_link_id, newer_link.share_link_id)

    def test_create_collaboration_request_prevents_duplicate_pending_request(self):
        first_request, level, message = create_collaboration_request(
            space=self.space,
            requester=self.viewer,
            message="Please upgrade me.",
        )
        second_request, second_level, second_message = create_collaboration_request(
            space=self.space,
            requester=self.viewer,
            message="Please upgrade me again.",
        )

        self.assertIsNotNone(first_request)
        self.assertEqual(level, "success")
        self.assertEqual(message, "Collaborator request sent.")
        self.assertIsNone(second_request)
        self.assertEqual(second_level, "info")
        self.assertEqual(second_message, "Your collaborator request is already pending.")
        self.assertEqual(
            CollaborationRequest.objects.filter(space=self.space, requester=self.viewer).count(),
            1,
        )

    def test_serialize_request_state_uses_default_note_when_message_missing(self):
        request_record = CollaborationRequest.objects.create(
            space=self.space,
            requester=self.viewer,
            resolved_by=None,
            status=CollaborationRequest.Status.PENDING,
            message="",
            requested_at=timezone.now(),
            resolved_at=None,
        )

        payload = serialize_request_state(request_record)

        self.assertEqual(payload["status"], "Pending")
        self.assertEqual(payload["status_class"], "status-pending")
        self.assertEqual(payload["note"], "Your request is recorded in SideKick.")
