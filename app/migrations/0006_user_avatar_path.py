# Autor: Milan Neskovic, 545/19
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0005_membership_joined_via"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="avatar_path",
            field=models.CharField(blank=True, db_column="avatarPath", max_length=500),
        ),
    ]

