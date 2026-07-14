# Autor: Milan Neskovic, 545/19
# Generated manually to refresh seeded sample media with more realistic imagery.
from django.db import migrations


def refresh_sample_media(apps, schema_editor):
    Item = apps.get_model("app", "Item")

    updates = {
        "Design Board": {
            "source_url": "https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=1200&q=80",
            "captured_url": "https://dribbble.com/shots/sidekick-design",
        },
        "Alpha moodboard": {
            "source_url": "https://images.unsplash.com/photo-1497366412874-3415097a27e7?auto=format&fit=crop&w=1200&q=80",
            "captured_url": "https://www.behance.net/gallery/alpha-moodboard",
        },
        "Travel visual": {
            "source_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
            "captured_url": "https://unsplash.com/photos/travel",
        },
    }

    for page_title, values in updates.items():
        Item.objects.filter(page_title=page_title).update(**values)


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0003_seed_real_passwords"),
    ]

    operations = [
        migrations.RunPython(refresh_sample_media, migrations.RunPython.noop),
    ]

