# Generated manually for prototype seed data.
from datetime import datetime, timedelta, timezone

from django.db import migrations


def seed_data(apps, schema_editor):
    User = apps.get_model("app", "User")
    ResearchSpace = apps.get_model("app", "ResearchSpace")
    Membership = apps.get_model("app", "Membership")
    CollaborationRequest = apps.get_model("app", "CollaborationRequest")
    AuthToken = apps.get_model("app", "AuthToken")
    Item = apps.get_model("app", "Item")
    ShareLink = apps.get_model("app", "ShareLink")

    if User.objects.exists():
        return

    now = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)

    petar = User.objects.create(
        email="petar@example.com",
        password_hash="sidekick-demo-hash",
        full_name="Petar",
        created_at=now,
        updated_at=now,
    )
    milan = User.objects.create(
        email="milan@example.com",
        password_hash="sidekick-demo-hash",
        full_name="Milan",
        created_at=now,
        updated_at=now,
    )
    luka = User.objects.create(
        email="luka@example.com",
        password_hash="sidekick-demo-hash",
        full_name="Luka",
        created_at=now,
        updated_at=now,
    )
    ana = User.objects.create(
        email="ana@example.com",
        password_hash="sidekick-demo-hash",
        full_name="Ana Markovic",
        created_at=now,
        updated_at=now,
    )
    nikola = User.objects.create(
        email="nikola@example.com",
        password_hash="sidekick-demo-hash",
        full_name="Nikola Ilic",
        created_at=now,
        updated_at=now,
    )
    jelena = User.objects.create(
        email="jelena@example.com",
        password_hash="sidekick-demo-hash",
        full_name="Jelena Popovic",
        created_at=now,
        updated_at=now,
    )

    design = ResearchSpace.objects.create(
        owner=petar,
        name="Design Inspiration",
        description="Visual references, brand ideas, and product moodboards.",
        is_archived=False,
        created_at=now - timedelta(days=20),
        updated_at=now - timedelta(days=1),
    )
    alpha = ResearchSpace.objects.create(
        owner=milan,
        name="Project Alpha",
        description="Shared product research for the core release.",
        is_archived=False,
        created_at=now - timedelta(days=18),
        updated_at=now - timedelta(hours=12),
    )
    recipes = ResearchSpace.objects.create(
        owner=petar,
        name="Recipes",
        description="Collected cooking notes and ingredient references.",
        is_archived=True,
        created_at=now - timedelta(days=16),
        updated_at=now - timedelta(days=3),
    )
    travel = ResearchSpace.objects.create(
        owner=luka,
        name="Travel Ideas",
        description="Trip planning, saved routes, and destination links.",
        is_archived=False,
        created_at=now - timedelta(days=14),
        updated_at=now - timedelta(hours=6),
    )

    Membership.objects.bulk_create(
        [
            Membership(
                space=alpha,
                user=petar,
                role="collaborator",
                status="active",
                created_at=now - timedelta(days=12),
                updated_at=now - timedelta(days=2),
            ),
            Membership(
                space=travel,
                user=petar,
                role="collaborator",
                status="active",
                created_at=now - timedelta(days=10),
                updated_at=now - timedelta(days=1),
            ),
            Membership(
                space=design,
                user=luka,
                role="viewer",
                status="active",
                created_at=now - timedelta(days=8),
                updated_at=now - timedelta(days=1),
            ),
            Membership(
                space=alpha,
                user=luka,
                role="viewer",
                status="active",
                created_at=now - timedelta(days=7),
                updated_at=now - timedelta(days=1),
            ),
            Membership(
                space=travel,
                user=milan,
                role="viewer",
                status="active",
                created_at=now - timedelta(days=6),
                updated_at=now - timedelta(days=1),
            ),
        ]
    )

    CollaborationRequest.objects.bulk_create(
        [
            CollaborationRequest(
                space=alpha,
                requester=ana,
                resolved_by=None,
                status="pending",
                message="Owner treba da pregleda zahtev za pristup.",
                requested_at=now - timedelta(days=2, hours=5),
                resolved_at=None,
            ),
            CollaborationRequest(
                space=travel,
                requester=nikola,
                resolved_by=luka,
                status="approved",
                message="Pristup je odobren i korisnik je obavesten.",
                requested_at=now - timedelta(days=5),
                resolved_at=now - timedelta(days=4, hours=20),
            ),
            CollaborationRequest(
                space=design,
                requester=jelena,
                resolved_by=petar,
                status="rejected",
                message="Zahtev je zatvoren i ne moze se slati beskonacno iznova.",
                requested_at=now - timedelta(days=7),
                resolved_at=now - timedelta(days=6, hours=18),
            ),
        ]
    )

    AuthToken.objects.bulk_create(
        [
            AuthToken(
                user=petar,
                token_value="token-petar-web",
                client_type="web",
                issued_at=now - timedelta(days=1),
                expires_at=now + timedelta(days=29),
                is_revoked=False,
            ),
            AuthToken(
                user=petar,
                token_value="token-petar-extension",
                client_type="extension",
                issued_at=now - timedelta(hours=10),
                expires_at=now + timedelta(days=29),
                is_revoked=False,
            ),
            AuthToken(
                user=milan,
                token_value="token-milan-web",
                client_type="web",
                issued_at=now - timedelta(days=2),
                expires_at=now + timedelta(days=28),
                is_revoked=False,
            ),
        ]
    )

    items = []
    item_specs = [
        (
            design,
            petar,
            "image",
            "",
            "https://picsum.photos/seed/designboard/600/700",
            "",
            "",
            "",
            "web",
            "https://dribbble.com/shots/sidekick-design",
            "Design Board",
            30,
        ),
        (
            design,
            luka,
            "text",
            "Minimalistička misao za novi onboarding tok.",
            "",
            "",
            "",
            "Keep it simple and fast.",
            "extension",
            "https://medium.com/design/onboarding-patterns",
            "Onboarding patterns",
            28,
        ),
        (
            alpha,
            milan,
            "link",
            "",
            "https://developer.apple.com/design/human-interface-guidelines/",
            "",
            "Apple HIG",
            "Useful interaction reference.",
            "web",
            "https://developer.apple.com/design/human-interface-guidelines/",
            "Human Interface Guidelines",
            26,
        ),
        (
            alpha,
            petar,
            "image",
            "",
            "https://picsum.photos/seed/alphaimage/600/600",
            "",
            "",
            "",
            "extension",
            "https://www.behance.net/gallery/alpha-moodboard",
            "Alpha moodboard",
            24,
        ),
        (
            recipes,
            petar,
            "text",
            "Minimalistička misao #5 za Recipes. Neka bude jednostavno i čisto.",
            "",
            "",
            "",
            "Seasonal note.",
            "web",
            "",
            "",
            22,
        ),
        (
            travel,
            luka,
            "link",
            "",
            "https://developer.apple.com/maps/",
            "",
            "Travel route reference",
            "Saved for itinerary planning.",
            "web",
            "https://developer.apple.com/maps/",
            "Maps resources",
            20,
        ),
        (
            travel,
            petar,
            "image",
            "",
            "https://picsum.photos/seed/travelnotes/600/650",
            "",
            "",
            "",
            "extension",
            "https://unsplash.com/photos/travel",
            "Travel visual",
            18,
        ),
        (
            alpha,
            petar,
            "text",
            "Sprint summary for Project Alpha with focus on permissions flow.",
            "",
            "",
            "",
            "Need to validate owner-only actions.",
            "web",
            "",
            "",
            16,
        ),
    ]

    for index, spec in enumerate(item_specs, start=1):
        (
            space,
            user,
            item_type,
            content_text,
            source_url,
            image_path,
            title,
            note,
            source_platform,
            captured_url,
            page_title,
            hours_ago,
        ) = spec
        timestamp = now - timedelta(hours=hours_ago)
        items.append(
            Item(
                space=space,
                added_by=user,
                item_type=item_type,
                content_text=content_text,
                source_url=source_url,
                image_path=image_path,
                title=title,
                note=note,
                source_platform=source_platform,
                captured_url=captured_url,
                page_title=page_title,
                created_at=timestamp,
                updated_at=timestamp + timedelta(minutes=index),
            )
        )

    Item.objects.bulk_create(items)

    ShareLink.objects.bulk_create(
        [
            ShareLink(
                space=design,
                created_by=petar,
                token="design-space-share",
                created_at=now - timedelta(days=3),
                expires_at=now + timedelta(days=30),
                is_active=True,
            ),
            ShareLink(
                space=travel,
                created_by=luka,
                token="travel-space-share",
                created_at=now - timedelta(days=2),
                expires_at=None,
                is_active=True,
            ),
        ]
    )


def unseed_data(apps, schema_editor):
    User = apps.get_model("app", "User")
    User.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_data, unseed_data),
    ]
