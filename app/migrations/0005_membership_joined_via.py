# Autor: Milan Neskovic, 545/19
# Generated manually for share-link-backed viewer access.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0004_refresh_sample_media"),
    ]

    operations = [
        migrations.AddField(
            model_name="membership",
            name="joined_via",
            field=models.ForeignKey(
                blank=True,
                db_column="joinedVia",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="granted_memberships",
                to="app.sharelink",
            ),
        ),
    ]

