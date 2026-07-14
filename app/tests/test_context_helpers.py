from django.contrib.auth.hashers import make_password
from django.test import RequestFactory, TestCase
from django.utils import timezone

from app.context import (
    accessible_spaces,
    current_space_role,
    filter_spaces,
    get_current_user,
    get_or_create_universal_space,
    get_request_auth_token_value,
    membership_grants_access,
)
from app.models import AuthToken, Membership, ResearchSpace, ShareLink, User


class ContextHelperTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.factory = RequestFactory()

        self.owner = User.objects.create(
            email="owner-context@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Owner Context",
            created_at=now,
            updated_at=now,
        )
        self.collaborator = User.objects.create(
            email="collaborator-context@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Collaborator Context",
            created_at=now,
            updated_at=now,
        )
        self.viewer = User.objects.create(
            email="viewer-context@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Viewer Context",
            created_at=now,
            updated_at=now,
        )
        self.other = User.objects.create(
            email="other-context@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Other Context",
            created_at=now,
            updated_at=now,
        )

        self.owned_space = ResearchSpace.objects.create(
            owner=self.owner,
            name="Owned Space",
            description="Visible owned space",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        self.shared_space = ResearchSpace.objects.create(
            owner=self.owner,
            name="Shared Space",
            description="Visible shared space",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        self.revoked_space = ResearchSpace.objects.create(
            owner=self.owner,
            name="Revoked Space",
            description="Revoked viewer access",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )

        self.active_share_link = ShareLink.objects.create(
            space=self.shared_space,
            created_by=self.owner,
            token="context-active-share",
            created_at=now,
            expires_at=None,
            is_active=True,
        )
        self.revoked_share_link = ShareLink.objects.create(
            space=self.revoked_space,
            created_by=self.owner,
            token="context-revoked-share",
            created_at=now,
            expires_at=None,
            is_active=False,
        )

        Membership.objects.create(
            space=self.shared_space,
            user=self.collaborator,
            joined_via=None,
            role=Membership.Role.COLLABORATOR,
            status=Membership.Status.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        self.viewer_membership = Membership.objects.create(
            space=self.shared_space,
            user=self.viewer,
            joined_via=self.active_share_link,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        self.revoked_viewer_membership = Membership.objects.create(
            space=self.revoked_space,
            user=self.viewer,
            joined_via=self.revoked_share_link,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        self.token = AuthToken.objects.create(
            user=self.viewer,
            token_value="context-token",
            client_type=AuthToken.ClientType.EXTENSION,
            issued_at=now,
            expires_at=None,
            is_revoked=False,
        )

    def test_get_request_auth_token_value_prefers_query_parameter(self):
        request = self.factory.get(
            "/spaces/",
            {"authToken": "from-query"},
            HTTP_AUTHORIZATION="Token from-header",
        )

        self.assertEqual(get_request_auth_token_value(request), "from-query")

    def test_get_current_user_prefers_session_user_over_token_user(self):
        request = self.factory.get(
            "/spaces/",
            HTTP_AUTHORIZATION=f"Token {self.token.token_value}",
        )
        request.session = {"sidekick_user_id": self.owner.user_id}

        current_user = get_current_user(request)

        self.assertEqual(current_user.user_id, self.owner.user_id)

    def test_membership_grants_access_requires_active_share_link_for_viewer(self):
        self.assertTrue(membership_grants_access(self.viewer_membership))
        self.assertFalse(membership_grants_access(self.revoked_viewer_membership))

    def test_current_space_role_returns_owner_collaborator_viewer_and_none(self):
        owned_space = ResearchSpace.objects.prefetch_related("memberships__joined_via").get(
            space_id=self.owned_space.space_id
        )
        shared_space = ResearchSpace.objects.prefetch_related("memberships__joined_via").get(
            space_id=self.shared_space.space_id
        )

        self.assertEqual(current_space_role(owned_space, self.owner), "Owner")
        self.assertEqual(current_space_role(shared_space, self.collaborator), "Collaborator")
        self.assertEqual(current_space_role(shared_space, self.viewer), "Viewer")
        self.assertIsNone(current_space_role(shared_space, self.other))
        self.assertEqual(current_space_role(shared_space, None), "Preview")

    def test_filter_spaces_excludes_universal_and_separates_owned_shared(self):
        get_or_create_universal_space(self.owner)

        owned_names = [space.name for space in filter_spaces("Owned", self.owner)]
        shared_names = [space.name for space in filter_spaces("Shared", self.viewer)]
        all_viewer_names = [space.name for space in filter_spaces("All", self.viewer)]

        self.assertEqual(owned_names, ["Revoked Space", "Shared Space", "Owned Space"])
        self.assertEqual(shared_names, ["Shared Space"])
        self.assertEqual(all_viewer_names, ["Shared Space"])
        self.assertNotIn("Inbox", owned_names)

    def test_accessible_spaces_returns_only_owned_and_valid_shared_spaces(self):
        owner_space_ids = set(accessible_spaces(self.owner).values_list("space_id", flat=True))
        viewer_space_ids = set(accessible_spaces(self.viewer).values_list("space_id", flat=True))

        self.assertEqual(
            owner_space_ids,
            {self.owned_space.space_id, self.shared_space.space_id, self.revoked_space.space_id},
        )
        self.assertEqual(viewer_space_ids, {self.shared_space.space_id})

    def test_get_or_create_universal_space_is_idempotent(self):
        first = get_or_create_universal_space(self.owner)
        second = get_or_create_universal_space(self.owner)

        self.assertEqual(first.space_id, second.space_id)
        self.assertEqual(first.name, "Inbox")
