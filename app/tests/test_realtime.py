# Autor: Milan Neskovic, 545/19
"""Testovi za realtime pristup i izbor primalaca Socket.IO događaja."""

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.utils import timezone

from app.models import Membership, ResearchSpace, ShareLink, User
from app.realtime import _current_space_recipients


class RealtimeRecipientTests(TestCase):
    """Proverava da realtime događaji idu samo korisnicima sa važećim pristupom."""

    def setUp(self):
        """Priprema vlasnika, članove i deljeni link za testove realtime dozvola."""
        now = timezone.now()
        self.owner = User.objects.create(
            email="rt-owner@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Realtime Owner",
            created_at=now,
            updated_at=now,
        )
        self.collaborator = User.objects.create(
            email="rt-collab@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Realtime Collaborator",
            created_at=now,
            updated_at=now,
        )
        self.viewer = User.objects.create(
            email="rt-viewer@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Realtime Viewer",
            created_at=now,
            updated_at=now,
        )
        self.removed_user = User.objects.create(
            email="rt-removed@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Removed User",
            created_at=now,
            updated_at=now,
        )
        self.space = ResearchSpace.objects.create(
            owner=self.owner,
            name="Realtime Space",
            description="Realtime permissions checks.",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        self.share_link = ShareLink.objects.create(
            space=self.space,
            created_by=self.owner,
            token="rt-share-token",
            created_at=now,
            expires_at=None,
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
            space=self.space,
            user=self.viewer,
            joined_via=self.share_link,
            role=Membership.Role.VIEWER,
            status=Membership.Status.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        Membership.objects.create(
            space=self.space,
            user=self.removed_user,
            joined_via=None,
            role=Membership.Role.COLLABORATOR,
            status=Membership.Status.REMOVED,
            created_at=now,
            updated_at=now,
        )

    def test_current_space_recipients_include_only_active_members(self):
        recipients = _current_space_recipients(self.space.space_id)

        self.assertEqual(
            recipients,
            sorted([self.owner.user_id, self.collaborator.user_id, self.viewer.user_id]),
        )

    def test_current_space_recipients_exclude_viewer_after_share_link_revoke(self):
        self.share_link.is_active = False
        self.share_link.save(update_fields=["is_active"])

        recipients = _current_space_recipients(self.space.space_id)

        self.assertEqual(
            recipients,
            sorted([self.owner.user_id, self.collaborator.user_id]),
        )

