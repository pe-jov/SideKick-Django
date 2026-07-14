"""Pomoćne strukture i funkcije za ponovno popunjavanje demo podataka aplikacije."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from .models import AuthToken, CollaborationRequest, Item, Membership, ResearchSpace, ShareLink, User


DEFAULT_PASSWORD = "Sidekick123!"


@dataclass(frozen=True)
class UserSeed:
    """Opis jednog demo korisnika koji se koristi prilikom seed-ovanja baze."""
    key: str
    full_name: str
    email: str


@dataclass(frozen=True)
class SpaceSeed:
    """Opis jednog demo prostora sa osnovnim metapodacima i vremenima."""
    key: str
    owner: str
    name: str
    description: str
    created_days_ago: int
    updated_hours_ago: int


@dataclass(frozen=True)
class ItemSeed:
    """Opis jedne demo stavke koja se ubacuje u odgovarajući prostor."""
    space: str
    added_by: str
    item_type: str
    title: str
    content_text: str
    source_url: str
    captured_url: str
    page_title: str
    source_platform: str
    hours_ago: int


USERS = [
    UserSeed("petar", "Petar Jovanovic", "petar@example.com"),
    UserSeed("milica", "Milica Nikolic", "milica@example.com"),
    UserSeed("stefan", "Stefan Markovic", "stefan@example.com"),
    UserSeed("tamara", "Tamara Ilic", "tamara@example.com"),
    UserSeed("jelena", "Jelena Vasic", "jelena@example.com"),
    UserSeed("nikola", "Nikola Ristic", "nikola@example.com"),
]

SPACES = [
    SpaceSeed(
        key="narrative_lab",
        owner="petar",
        name="Product Narrative Lab",
        description="Positioning ideas, onboarding language, and product framing for SideKick.",
        created_days_ago=21,
        updated_hours_ago=5,
    ),
    SpaceSeed(
        key="material_futures",
        owner="milica",
        name="Material Futures",
        description="Surface references, tactile direction, and packaging research.",
        created_days_ago=18,
        updated_hours_ago=8,
    ),
    SpaceSeed(
        key="cabin_study",
        owner="stefan",
        name="Urban Cabin Study",
        description="Compact living references, layouts, and hospitality details.",
        created_days_ago=16,
        updated_hours_ago=10,
    ),
    SpaceSeed(
        key="food_atlas",
        owner="tamara",
        name="Balkan Food Atlas",
        description="Regional dish notes, market finds, and plating references.",
        created_days_ago=14,
        updated_hours_ago=4,
    ),
]

MEMBERSHIPS = [
    ("narrative_lab", "milica", Membership.Role.COLLABORATOR),
    ("narrative_lab", "stefan", Membership.Role.VIEWER),
    ("material_futures", "stefan", Membership.Role.COLLABORATOR),
    ("material_futures", "tamara", Membership.Role.VIEWER),
    ("cabin_study", "tamara", Membership.Role.COLLABORATOR),
    ("cabin_study", "petar", Membership.Role.VIEWER),
    ("food_atlas", "petar", Membership.Role.COLLABORATOR),
    ("food_atlas", "milica", Membership.Role.VIEWER),
]

ITEMS = [
    ItemSeed(
        space="narrative_lab",
        added_by="petar",
        item_type=Item.ItemType.TEXT,
        title="",
        content_text="SideKick should feel like a private research desk, not a dumping ground for bookmarks.",
        source_url="",
        captured_url="",
        page_title="",
        source_platform=Item.SourcePlatform.WEB,
        hours_ago=30,
    ),
    ItemSeed(
        space="narrative_lab",
        added_by="milica",
        item_type=Item.ItemType.LINK,
        title="Intercom on Jobs To Be Done",
        content_text="",
        source_url="https://www.intercom.com/blog/jobs-to-be-done/",
        captured_url="https://www.intercom.com/blog/jobs-to-be-done/",
        page_title="Intercom on Jobs To Be Done",
        source_platform=Item.SourcePlatform.EXTENSION,
        hours_ago=28,
    ),
    ItemSeed(
        space="narrative_lab",
        added_by="petar",
        item_type=Item.ItemType.IMAGE,
        title="Review wall references",
        content_text="",
        source_url="https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=1200&q=80",
        captured_url="https://www.behance.net/",
        page_title="Review wall references",
        source_platform=Item.SourcePlatform.WEB,
        hours_ago=26,
    ),
    ItemSeed(
        space="material_futures",
        added_by="milica",
        item_type=Item.ItemType.IMAGE,
        title="Material swatch table",
        content_text="",
        source_url="https://images.unsplash.com/photo-1512436991641-6745cdb1723f?auto=format&fit=crop&w=1200&q=80",
        captured_url="https://www.pinterest.com/",
        page_title="Material swatch table",
        source_platform=Item.SourcePlatform.WEB,
        hours_ago=24,
    ),
    ItemSeed(
        space="material_futures",
        added_by="stefan",
        item_type=Item.ItemType.TEXT,
        title="",
        content_text="Look for low-gloss finishes that still keep enough warmth under daylight photography.",
        source_url="",
        captured_url="",
        page_title="",
        source_platform=Item.SourcePlatform.EXTENSION,
        hours_ago=22,
    ),
    ItemSeed(
        space="material_futures",
        added_by="milica",
        item_type=Item.ItemType.LINK,
        title="Dezeen material archive",
        content_text="",
        source_url="https://www.dezeen.com/tag/materials/",
        captured_url="https://www.dezeen.com/tag/materials/",
        page_title="Dezeen material archive",
        source_platform=Item.SourcePlatform.WEB,
        hours_ago=20,
    ),
    ItemSeed(
        space="cabin_study",
        added_by="stefan",
        item_type=Item.ItemType.IMAGE,
        title="Cabin interior study",
        content_text="",
        source_url="https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=80",
        captured_url="https://www.archdaily.com/",
        page_title="Cabin interior study",
        source_platform=Item.SourcePlatform.WEB,
        hours_ago=18,
    ),
    ItemSeed(
        space="cabin_study",
        added_by="tamara",
        item_type=Item.ItemType.LINK,
        title="ArchDaily small cabin roundup",
        content_text="",
        source_url="https://www.archdaily.com/search/projects/categories/cabins",
        captured_url="https://www.archdaily.com/search/projects/categories/cabins",
        page_title="ArchDaily small cabin roundup",
        source_platform=Item.SourcePlatform.EXTENSION,
        hours_ago=16,
    ),
    ItemSeed(
        space="cabin_study",
        added_by="stefan",
        item_type=Item.ItemType.TEXT,
        title="",
        content_text="Keep the sleeping niche visually calm and let the storage wall carry the stronger material contrast.",
        source_url="",
        captured_url="",
        page_title="",
        source_platform=Item.SourcePlatform.WEB,
        hours_ago=14,
    ),
    ItemSeed(
        space="food_atlas",
        added_by="tamara",
        item_type=Item.ItemType.IMAGE,
        title="Market notebook spread",
        content_text="",
        source_url="https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=1200&q=80",
        captured_url="https://www.instagram.com/",
        page_title="Market notebook spread",
        source_platform=Item.SourcePlatform.WEB,
        hours_ago=12,
    ),
    ItemSeed(
        space="food_atlas",
        added_by="petar",
        item_type=Item.ItemType.TEXT,
        title="",
        content_text="The best entries pair a dish photo with one sentence about context: where it is eaten and by whom.",
        source_url="",
        captured_url="",
        page_title="",
        source_platform=Item.SourcePlatform.EXTENSION,
        hours_ago=10,
    ),
    ItemSeed(
        space="food_atlas",
        added_by="tamara",
        item_type=Item.ItemType.LINK,
        title="Serious Eats Balkan recipes",
        content_text="",
        source_url="https://www.seriouseats.com/",
        captured_url="https://www.seriouseats.com/",
        page_title="Serious Eats Balkan recipes",
        source_platform=Item.SourcePlatform.WEB,
        hours_ago=8,
    ),
]


def reset_uploaded_media(base_dir: Path) -> None:
    """Briše prethodno generisane otpremljene fajlove iz demo okruženja."""
    uploads_dir = base_dir / "media" / "uploads"
    if uploads_dir.exists():
        shutil.rmtree(uploads_dir)


def rebuild_demo_data(*, base_dir: Path) -> dict[str, list[str]]:
    """Ponovo kreira demo korisnike, prostore i stavke i vraća sažetak unetih podataka."""
    reset_uploaded_media(base_dir)

    Item.objects.all().delete()
    CollaborationRequest.objects.all().delete()
    Membership.objects.all().delete()
    ShareLink.objects.all().delete()
    AuthToken.objects.all().delete()
    ResearchSpace.objects.all().delete()
    User.objects.all().delete()

    now = timezone.now()
    user_map: dict[str, User] = {}
    for index, user_seed in enumerate(USERS):
        timestamp = now - timedelta(days=32 - index)
        user_map[user_seed.key] = User.objects.create(
            email=user_seed.email,
            password_hash=make_password(DEFAULT_PASSWORD),
            full_name=user_seed.full_name,
            created_at=timestamp,
            updated_at=timestamp,
        )

    space_map: dict[str, ResearchSpace] = {}
    for space_seed in SPACES:
        created_at = now - timedelta(days=space_seed.created_days_ago)
        updated_at = now - timedelta(hours=space_seed.updated_hours_ago)
        space_map[space_seed.key] = ResearchSpace.objects.create(
            owner=user_map[space_seed.owner],
            name=space_seed.name,
            description=space_seed.description,
            is_archived=False,
            created_at=created_at,
            updated_at=updated_at,
        )

    share_link_map = {
        "narrative_lab": ShareLink.objects.create(
            space=space_map["narrative_lab"],
            created_by=user_map["petar"],
            token="narrative-lab-share",
            created_at=now - timedelta(days=3),
            expires_at=None,
            is_active=True,
        ),
        "material_futures": ShareLink.objects.create(
            space=space_map["material_futures"],
            created_by=user_map["milica"],
            token="material-futures-share",
            created_at=now - timedelta(days=2),
            expires_at=now + timedelta(days=30),
            is_active=True,
        ),
        "cabin_study": ShareLink.objects.create(
            space=space_map["cabin_study"],
            created_by=user_map["stefan"],
            token="cabin-study-share",
            created_at=now - timedelta(days=5),
            expires_at=None,
            is_active=True,
        ),
        "food_atlas": ShareLink.objects.create(
            space=space_map["food_atlas"],
            created_by=user_map["tamara"],
            token="food-atlas-share",
            created_at=now - timedelta(days=1),
            expires_at=None,
            is_active=True,
        ),
    }

    for index, (space_key, user_key, role) in enumerate(MEMBERSHIPS, start=1):
        joined_via = share_link_map[space_key] if role == Membership.Role.VIEWER else None
        timestamp = now - timedelta(days=10 - min(index, 9))
        Membership.objects.create(
            space=space_map[space_key],
            user=user_map[user_key],
            joined_via=joined_via,
            role=role,
            status=Membership.Status.ACTIVE,
            created_at=timestamp,
            updated_at=timestamp,
        )

    CollaborationRequest.objects.create(
        space=space_map["narrative_lab"],
        requester=user_map["jelena"],
        resolved_by=None,
        status=CollaborationRequest.Status.PENDING,
        message="Would like collaborator access for onboarding copy review.",
        requested_at=now - timedelta(hours=18),
        resolved_at=None,
    )
    CollaborationRequest.objects.create(
        space=space_map["material_futures"],
        requester=user_map["nikola"],
        resolved_by=None,
        status=CollaborationRequest.Status.PENDING,
        message="Needs access to continue packaging references.",
        requested_at=now - timedelta(hours=11),
        resolved_at=None,
    )

    for item_seed in ITEMS:
        timestamp = now - timedelta(hours=item_seed.hours_ago)
        Item.objects.create(
            space=space_map[item_seed.space],
            added_by=user_map[item_seed.added_by],
            item_type=item_seed.item_type,
            content_text=item_seed.content_text,
            source_url=item_seed.source_url,
            image_path="",
            title=item_seed.title,
            note="",
            source_platform=item_seed.source_platform,
            captured_url=item_seed.captured_url,
            page_title=item_seed.page_title,
            created_at=timestamp,
            updated_at=timestamp,
        )

    credentials = [f"{seed.email} / {DEFAULT_PASSWORD}" for seed in USERS[:4]]
    return {"credentials": credentials}
