from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.utils import timezone

from app.models import DEFAULT_AVATAR_URL, Item, ResearchSpace, User


class ModelPropertyTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.user = User.objects.create(
            email="model-properties@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Model Properties",
            created_at=now,
            updated_at=now,
        )
        self.space = ResearchSpace.objects.create(
            owner=self.user,
            name="Apex Vault",
            description="Model property space",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )

    def test_user_avatar_url_falls_back_to_default(self):
        self.assertEqual(self.user.avatar_url, DEFAULT_AVATAR_URL)

        self.user.avatar_path = "/media/custom-avatar.png"
        self.assertEqual(self.user.avatar_url, "/media/custom-avatar.png")

    def test_research_space_image_url_uses_known_slug_and_fallback(self):
        self.assertIn("1492144534655", self.space.image_url)

        self.space.name = "Unknown Space Theme"
        self.assertIn("1517248135467", self.space.image_url)

    def test_item_domain_prefers_source_url_then_captured_url(self):
        now = timezone.now()
        item = Item.objects.create(
            space=self.space,
            added_by=self.user,
            item_type=Item.ItemType.LINK,
            content_text="",
            source_url="https://example.com/path",
            image_path="",
            title="Example",
            note="",
            source_platform=Item.SourcePlatform.WEB,
            captured_url="https://fallback.example.org/captured",
            page_title="Example",
            created_at=now,
            updated_at=now,
        )
        self.assertEqual(item.domain, "example.com")

        item.source_url = ""
        self.assertEqual(item.domain, "fallback.example.org")

    def test_item_image_url_prefers_uploaded_path_then_source_url(self):
        now = timezone.now()
        item = Item.objects.create(
            space=self.space,
            added_by=self.user,
            item_type=Item.ItemType.IMAGE,
            content_text="",
            source_url="https://example.com/source-image.jpg",
            image_path="/media/uploads/saved-image.jpg",
            title="Image",
            note="",
            source_platform=Item.SourcePlatform.WEB,
            captured_url="",
            page_title="Image",
            created_at=now,
            updated_at=now,
        )
        self.assertEqual(item.image_url, "/media/uploads/saved-image.jpg")

        item.image_path = ""
        self.assertEqual(item.image_url, "https://example.com/source-image.jpg")
