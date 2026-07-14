# Autor: Milan Neskovic, 545/19
"""Testovi za izvlačenje naslova linkova i kreiranje link stavki."""

from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.utils import timezone

from app.models import Item, ResearchSpace, User
from app.views import create_item_record, extract_title_from_html, title_from_domain, title_from_url_path


class LinkMetadataTests(TestCase):
    """Proverava parsiranje naslova i rezervne heuristike za link preview podatke."""

    def setUp(self):
        """Priprema korisnika i prostor za testiranje metapodataka linkova."""
        now = timezone.now()
        self.user = User.objects.create(
            email="metadata@example.com",
            password_hash=make_password("Sidekick123!"),
            full_name="Metadata Tester",
            created_at=now,
            updated_at=now,
        )
        self.space = ResearchSpace.objects.create(
            owner=self.user,
            name="Metadata Space",
            description="",
            is_archived=False,
            created_at=now,
            updated_at=now,
        )

    def test_extract_title_from_html_prefers_open_graph_and_json_ld(self):
        html = """
        <html>
          <head>
            <meta property="og:title" content="OG Story Title">
            <script type="application/ld+json">
              {"headline": "JSON LD Headline"}
            </script>
            <title>Fallback Title</title>
          </head>
        </html>
        """

        self.assertEqual(extract_title_from_html(html), "OG Story Title")

    @patch("app.views.read_url_metadata")
    def test_create_item_record_ignores_hostname_placeholder_and_fetches_metadata(self, read_url_metadata):
        read_url_metadata.return_value = {"title": "Real Article Title"}

        item, error_message, error_code = create_item_record(
            current_user=self.user,
            space=self.space,
            item_type=Item.ItemType.LINK,
            source_url="https://www.newsmaxbalkans.com/region/vesti/12345/sample-article",
            title=title_from_domain("https://www.newsmaxbalkans.com/region/vesti/12345/sample-article"),
        )

        self.assertIsNone(error_message)
        self.assertIsNone(error_code)
        self.assertEqual(item.title, "Real Article Title")
        self.assertEqual(item.page_title, "Real Article Title")
        read_url_metadata.assert_called_once()

    @patch("app.views.read_url_metadata")
    def test_create_item_record_falls_back_to_clean_slug_when_metadata_missing(self, read_url_metadata):
        read_url_metadata.return_value = {}

        item, error_message, error_code = create_item_record(
            current_user=self.user,
            space=self.space,
            item_type=Item.ItemType.LINK,
            source_url="https://www.newsmaxbalkans.com/region/vesti/58391/institucije-ukljucene-u-istragu-incidenta",
            title="",
        )

        self.assertIsNone(error_message)
        self.assertIsNone(error_code)
        self.assertEqual(item.title, "Institucije Ukljucene U Istragu Incidenta")
        self.assertEqual(item.page_title, "Institucije Ukljucene U Istragu Incidenta")
        read_url_metadata.assert_called_once()

    def test_title_from_url_path_ignores_generic_news_segments(self):
        title = title_from_url_path(
            "https://www.newsmaxbalkans.com/region/vest/incident-u-avionu-rajanera-u-kom-je-povreden-drzavljanin-srbije"
        )

        self.assertEqual(
            title,
            "Incident U Avionu Rajanera U Kom Je Povreden Drzavljanin Srbije",
        )

