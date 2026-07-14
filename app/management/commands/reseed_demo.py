# Autor: Milan Neskovic, 545/19
"""Komanda za ponovno generisanje demo podataka za lokalni razvoj."""

from pathlib import Path

from django.core.management.base import BaseCommand

from app.demo_seed import rebuild_demo_data


class Command(BaseCommand):
    """Resetuje demo bazu i popunjava je unapred pripremljenim podacima."""

    help = "Reset the local SideKick demo database to a curated realistic state."

    def handle(self, *args, **options):
        """Pokreće ponovno kreiranje demo podataka.

        Vraća tekstualni ispis rezultata kroz standardni Django output.
        """
        result = rebuild_demo_data(base_dir=Path(__file__).resolve().parents[4])
        self.stdout.write(self.style.SUCCESS("SideKick demo data reseeded."))
        self.stdout.write("Test accounts:")
        for credential in result["credentials"]:
            self.stdout.write(f"  - {credential}")

