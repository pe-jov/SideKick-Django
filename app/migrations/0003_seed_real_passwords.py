# Generated manually to make seeded prototype users usable for login.
from django.contrib.auth.hashers import make_password
from django.db import migrations


def set_seed_passwords(apps, schema_editor):
    User = apps.get_model("app", "User")
    password_hash = make_password("Sidekick123!")
    User.objects.filter(
        email__in=[
            "petar@example.com",
            "milan@example.com",
            "luka@example.com",
            "ana@example.com",
            "nikola@example.com",
            "jelena@example.com",
        ]
    ).update(password_hash=password_hash)


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0002_seed_prototype_data"),
    ]

    operations = [
        migrations.RunPython(set_seed_passwords, migrations.RunPython.noop),
    ]
