"""Pomocne strukture i funkcije za ponovno popunjavanje demo podataka aplikacije."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from .context import get_or_create_universal_space
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
    """Opis jedne demo stavke koja se ubacuje u odgovarajuci prostor."""

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


@dataclass(frozen=True)
class LinkSeed:
    """Opis link stavke iz zajednicke biblioteke."""

    title: str
    url: str
    page_title: str
    source_platform: str


@dataclass(frozen=True)
class ImageSeed:
    """Opis image stavke iz zajednicke biblioteke."""

    title: str
    image_url: str
    captured_url: str
    page_title: str
    source_platform: str


@dataclass(frozen=True)
class CollectionSeed:
    """Opis jedne kolekcije koja pravi 10 razlicitih stavki za prostor ili inbox."""

    space_key: str
    contributors: Sequence[str]
    texts: Sequence[str]
    link_keys: Sequence[str]
    image_keys: Sequence[str]
    start_hours_ago: int


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
        key="apex_vault",
        owner="petar",
        name="Apex Vault",
        description="Benchmark board for flagship supercars, hybrid hypercars, and standout launch assets.",
        created_days_ago=24,
        updated_hours_ago=9,
    ),
    SpaceSeed(
        key="carbon_atelier",
        owner="milica",
        name="Carbon Atelier",
        description="Material, interior, and surface references focused on carbon tubs, leather, and cockpit details.",
        created_days_ago=21,
        updated_hours_ago=11,
    ),
    SpaceSeed(
        key="v12_symphony",
        owner="stefan",
        name="V12 Symphony",
        description="Engine character studies, sound references, and drivetrain notes for emotional supercar storytelling.",
        created_days_ago=19,
        updated_hours_ago=7,
    ),
    SpaceSeed(
        key="track_legends",
        owner="tamara",
        name="Track Legends Lab",
        description="Track-special machines, lap-time narratives, circuit moodboards, and aero-heavy visuals.",
        created_days_ago=17,
        updated_hours_ago=6,
    ),
]

MEMBERSHIPS = [
    ("apex_vault", "milica", Membership.Role.COLLABORATOR),
    ("apex_vault", "stefan", Membership.Role.VIEWER),
    ("carbon_atelier", "stefan", Membership.Role.COLLABORATOR),
    ("carbon_atelier", "tamara", Membership.Role.VIEWER),
    ("v12_symphony", "tamara", Membership.Role.COLLABORATOR),
    ("v12_symphony", "petar", Membership.Role.VIEWER),
    ("track_legends", "petar", Membership.Role.COLLABORATOR),
    ("track_legends", "milica", Membership.Role.VIEWER),
]

LINK_LIBRARY = {
    "ferrari_sf90": LinkSeed(
        "Ferrari SF90 Stradale",
        "https://www.ferrari.com/en-EN/auto/sf90-stradale",
        "Ferrari SF90 Stradale",
        Item.SourcePlatform.WEB,
    ),
    "lamborghini_revuelto": LinkSeed(
        "Lamborghini Revuelto",
        "https://www.lamborghini.com/en-en/models/revuelto",
        "Lamborghini Revuelto",
        Item.SourcePlatform.EXTENSION,
    ),
    "rimac_nevera": LinkSeed(
        "Rimac Nevera",
        "https://www.rimac-automobili.com/nevera/",
        "Rimac Nevera",
        Item.SourcePlatform.WEB,
    ),
    "mclaren_750s": LinkSeed(
        "McLaren 750S",
        "https://cars.mclaren.com/en/750s",
        "McLaren 750S",
        Item.SourcePlatform.EXTENSION,
    ),
    "pagani_utopia": LinkSeed(
        "Pagani Utopia",
        "https://www.pagani.com/utopia/",
        "Pagani Utopia",
        Item.SourcePlatform.WEB,
    ),
    "koenigsegg_cc850": LinkSeed(
        "Koenigsegg CC850",
        "https://www.koenigsegg.com/model/cc850",
        "Koenigsegg CC850",
        Item.SourcePlatform.WEB,
    ),
    "maserati_mc20": LinkSeed(
        "Maserati MC20",
        "https://www.maserati.com/global/en/models/mc20",
        "Maserati MC20",
        Item.SourcePlatform.EXTENSION,
    ),
    "mclaren_artura": LinkSeed(
        "McLaren Artura",
        "https://cars.mclaren.com/en/artura",
        "McLaren Artura",
        Item.SourcePlatform.WEB,
    ),
    "aston_valkyrie": LinkSeed(
        "Aston Martin Valkyrie",
        "https://www.astonmartin.com/en/models/aston-martin-valkyrie",
        "Aston Martin Valkyrie",
        Item.SourcePlatform.WEB,
    ),
    "pagani_huayra_r": LinkSeed(
        "Pagani Huayra R",
        "https://www.pagani.com/huayra-r/",
        "Pagani Huayra R",
        Item.SourcePlatform.EXTENSION,
    ),
    "mercedes_amg_one": LinkSeed(
        "Mercedes-AMG ONE",
        "https://www.mercedes-amg.com/en/vehicles/amg-one.html",
        "Mercedes-AMG ONE",
        Item.SourcePlatform.WEB,
    ),
    "gma_t50_story": LinkSeed(
        "Road & Track: Gordon Murray T.50 Revealed",
        "https://www.roadandtrack.com/news/a35818364/gordon-murray-t50-revealed/",
        "Road & Track: Gordon Murray T.50 Revealed",
        Item.SourcePlatform.EXTENSION,
    ),
    "porsche_gt3rs": LinkSeed(
        "Porsche 911 GT3 RS",
        "https://www.porsche.com/international/models/911/911-gt3-rs/",
        "Porsche 911 GT3 RS",
        Item.SourcePlatform.WEB,
    ),
    "bugatti_bolide": LinkSeed(
        "Bugatti Bolide",
        "https://www.bugatti.com/the-bugatti-models/bolide/",
        "Bugatti Bolide",
        Item.SourcePlatform.WEB,
    ),
    "evo_mclaren_senna": LinkSeed(
        "Evo: McLaren Senna Review",
        "https://www.evo.co.uk/mclaren/203167/mclaren-senna-review",
        "Evo: McLaren Senna Review",
        Item.SourcePlatform.EXTENSION,
    ),
    "roadtrack_amg_one_drive": LinkSeed(
        "Road & Track: Mercedes-AMG ONE First Drive",
        "https://www.roadandtrack.com/reviews/a60794428/mercedes-amg-one-first-drive/",
        "Road & Track: Mercedes-AMG ONE First Drive",
        Item.SourcePlatform.WEB,
    ),
    "ferrari_daytona_sp3": LinkSeed(
        "Ferrari Daytona SP3",
        "https://www.ferrari.com/en-EN/auto/daytona-sp3",
        "Ferrari Daytona SP3",
        Item.SourcePlatform.EXTENSION,
    ),
    "ferrari_296": LinkSeed(
        "Ferrari 296 GTB",
        "https://www.ferrari.com/en-EN/auto/296-gtb",
        "Ferrari 296 GTB",
        Item.SourcePlatform.WEB,
    ),
    "hagerty_f40": LinkSeed(
        "Hagerty: Ferrari F40 Buyer's Guide",
        "https://www.hagerty.com/media/car-profiles/ferrari-f40-buyers-guide/",
        "Hagerty: Ferrari F40 Buyer's Guide",
        Item.SourcePlatform.WEB,
    ),
    "topgear_enzo_legacy": LinkSeed(
        "Top Gear: Ferrari Enzo 20 Years Later",
        "https://www.topgear.com/car-news/supercars/ferrari-enzo-20-years-later",
        "Top Gear: Ferrari Enzo 20 Years Later",
        Item.SourcePlatform.EXTENSION,
    ),
    "aston_valhalla": LinkSeed(
        "Aston Martin Valhalla",
        "https://www.astonmartin.com/en/models/valhalla",
        "Aston Martin Valhalla",
        Item.SourcePlatform.WEB,
    ),
    "lotus_evija": LinkSeed(
        "Lotus Evija",
        "https://www.lotuscars.com/en-GB/evija",
        "Lotus Evija",
        Item.SourcePlatform.WEB,
    ),
    "caranddriver_gt3rs": LinkSeed(
        "Car and Driver: Porsche 911 GT3 RS",
        "https://www.caranddriver.com/porsche/911-gt3-rs",
        "Car and Driver: Porsche 911 GT3 RS",
        Item.SourcePlatform.EXTENSION,
    ),
    "caranddriver_mc20": LinkSeed(
        "Car and Driver: Maserati MC20",
        "https://www.caranddriver.com/maserati/mc20",
        "Car and Driver: Maserati MC20",
        Item.SourcePlatform.WEB,
    ),
    "koenigsegg_jesko": LinkSeed(
        "Koenigsegg Jesko",
        "https://www.koenigsegg.com/model/jesko",
        "Koenigsegg Jesko",
        Item.SourcePlatform.EXTENSION,
    ),
    "bugatti_tourbillon": LinkSeed(
        "Bugatti Tourbillon",
        "https://www.bugatti.com/the-bugatti-models/tourbillon/",
        "Bugatti Tourbillon",
        Item.SourcePlatform.WEB,
    ),
    "evo_t50": LinkSeed(
        "Evo: Gordon Murray T.50 Review",
        "https://www.evo.co.uk/gordon-murray-automotive/206180/gordon-murray-t50-review",
        "Evo: Gordon Murray T.50 Review",
        Item.SourcePlatform.WEB,
    ),
    "roadtrack_nevera_tech": LinkSeed(
        "Road & Track: Rimac Nevera Performance Story",
        "https://www.roadandtrack.com/news/a44214576/rimac-nevera-time-attack-records/",
        "Road & Track: Rimac Nevera Performance Story",
        Item.SourcePlatform.EXTENSION,
    ),
    "goodwood_daytona_sp3": LinkSeed(
        "Goodwood: Ferrari Daytona SP3 Review",
        "https://www.goodwood.com/grr/road/news/ferrari-daytona-sp3-review/",
        "Goodwood: Ferrari Daytona SP3 Review",
        Item.SourcePlatform.WEB,
    ),
    "goodwood_jesko_absolut": LinkSeed(
        "Goodwood: Koenigsegg Jesko Absolut Review",
        "https://www.goodwood.com/grr/road/news/koenigsegg-jesko-absolut-review/",
        "Goodwood: Koenigsegg Jesko Absolut Review",
        Item.SourcePlatform.EXTENSION,
    ),
    "topgear_revuelto_drive": LinkSeed(
        "Top Gear: Lamborghini Revuelto Review",
        "https://www.topgear.com/car-reviews/lamborghini/revuelto",
        "Top Gear: Lamborghini Revuelto Review",
        Item.SourcePlatform.WEB,
    ),
    "motor1_countach": LinkSeed(
        "Motor1: Lamborghini Countach LPI 800-4 Review",
        "https://www.motor1.com/reviews/600916/lamborghini-countach-lpi-800-4-review/",
        "Motor1: Lamborghini Countach LPI 800-4 Review",
        Item.SourcePlatform.EXTENSION,
    ),
    "autocar_valhalla": LinkSeed(
        "Autocar: Aston Martin Valhalla Review",
        "https://www.autocar.co.uk/car-review/aston-martin/valhalla",
        "Autocar: Aston Martin Valhalla Review",
        Item.SourcePlatform.WEB,
    ),
    "hennessey_venom_f5": LinkSeed(
        "Hennessey Venom F5",
        "https://www.hennesseyspecialvehicles.com/venom-f5/",
        "Hennessey Venom F5",
        Item.SourcePlatform.WEB,
    ),
    "ssc_tuatara": LinkSeed(
        "SSC Tuatara",
        "https://www.sscnorthamerica.com/model/tuatara",
        "SSC Tuatara",
        Item.SourcePlatform.EXTENSION,
    ),
    "czinger_21c": LinkSeed(
        "Czinger 21C",
        "https://www.czinger.com/21c/",
        "Czinger 21C",
        Item.SourcePlatform.WEB,
    ),
    "koenigsegg_gemera": LinkSeed(
        "Koenigsegg Gemera",
        "https://www.koenigsegg.com/model/gemera",
        "Koenigsegg Gemera",
        Item.SourcePlatform.WEB,
    ),
    "bugatti_chiron_ss": LinkSeed(
        "Bugatti Chiron Super Sport",
        "https://www.bugatti.com/the-bugatti-models/chiron-models/chiron-super-sport/",
        "Bugatti Chiron Super Sport",
        Item.SourcePlatform.EXTENSION,
    ),
    "topgear_tourbillon": LinkSeed(
        "Top Gear: Bugatti Tourbillon V16 Hypercar",
        "https://www.topgear.com/car-news/supercars/new-bugatti-tourbillon-1800hp-v16-hypercar",
        "Top Gear: Bugatti Tourbillon V16 Hypercar",
        Item.SourcePlatform.WEB,
    ),
    "evo_utopia_review": LinkSeed(
        "Evo: Pagani Utopia Review",
        "https://www.evo.co.uk/pagani/206172/pagani-utopia-review",
        "Evo: Pagani Utopia Review",
        Item.SourcePlatform.EXTENSION,
    ),
    "lamborghini_temerario": LinkSeed(
        "Lamborghini Temerario",
        "https://www.lamborghini.com/en-en/models/temerario",
        "Lamborghini Temerario",
        Item.SourcePlatform.WEB,
    ),
    "hagerty_carrera_gt": LinkSeed(
        "Hagerty: The Porsche Carrera GT Is Still the Supercar to Beat",
        "https://www.hagerty.com/media/car-profiles/the-porsche-carrera-gt-is-still-the-supercar-to-beat/",
        "Hagerty: The Porsche Carrera GT Is Still the Supercar to Beat",
        Item.SourcePlatform.WEB,
    ),
}

IMAGE_LIBRARY = {
    "sf90_studio": ImageSeed(
        "SF90 studio profile",
        "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=1200&q=80",
        "https://www.ferrari.com/en-EN/auto/sf90-stradale",
        "Ferrari SF90 studio profile",
        Item.SourcePlatform.WEB,
    ),
    "revuelto_night": ImageSeed(
        "Revuelto night run",
        "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=1200&q=80",
        "https://www.lamborghini.com/en-en/models/revuelto",
        "Lamborghini Revuelto at night",
        Item.SourcePlatform.EXTENSION,
    ),
    "utopia_detail": ImageSeed(
        "Utopia body detail",
        "https://images.unsplash.com/photo-1494905998402-395d579af36f?auto=format&fit=crop&w=1200&q=80",
        "https://www.pagani.com/utopia/",
        "Pagani Utopia body detail",
        Item.SourcePlatform.WEB,
    ),
    "nevera_blue": ImageSeed(
        "Nevera electric blue",
        "https://images.unsplash.com/photo-1511919884226-fd3cad34687c?auto=format&fit=crop&w=1200&q=80",
        "https://www.rimac-automobili.com/nevera/",
        "Rimac Nevera electric blue",
        Item.SourcePlatform.WEB,
    ),
    "jesko_orange": ImageSeed(
        "Jesko orange profile",
        "https://images.unsplash.com/photo-1489824904134-891ab64532f1?auto=format&fit=crop&w=1200&q=80",
        "https://www.koenigsegg.com/model/jesko",
        "Koenigsegg Jesko orange profile",
        Item.SourcePlatform.EXTENSION,
    ),
    "valkyrie_track": ImageSeed(
        "Valkyrie pit lane",
        "https://images.unsplash.com/photo-1503736334956-4c8f8e92946d?auto=format&fit=crop&w=1200&q=80",
        "https://www.astonmartin.com/en/models/aston-martin-valkyrie",
        "Aston Martin Valkyrie pit lane",
        Item.SourcePlatform.WEB,
    ),
    "f40_archive": ImageSeed(
        "Ferrari F40 archive shot",
        "https://images.unsplash.com/photo-1502877338535-766e1452684a?auto=format&fit=crop&w=1200&q=80",
        "https://www.hagerty.com/media/car-profiles/ferrari-f40-buyers-guide/",
        "Ferrari F40 archive shot",
        Item.SourcePlatform.WEB,
    ),
    "countach_sunset": ImageSeed(
        "Countach sunset angle",
        "https://images.unsplash.com/photo-1493238792000-8113da705763?auto=format&fit=crop&w=1200&q=80",
        "https://www.motor1.com/reviews/600916/lamborghini-countach-lpi-800-4-review/",
        "Countach sunset angle",
        Item.SourcePlatform.EXTENSION,
    ),
    "mc20_coast": ImageSeed(
        "MC20 coastal drive",
        "https://images.unsplash.com/photo-1502161254066-6c74afbf07aa?auto=format&fit=crop&w=1200&q=80",
        "https://www.maserati.com/global/en/models/mc20",
        "Maserati MC20 coastal drive",
        Item.SourcePlatform.WEB,
    ),
    "amg_one_pit": ImageSeed(
        "AMG ONE pit box",
        "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?auto=format&fit=crop&w=1200&q=80",
        "https://www.mercedes-amg.com/en/vehicles/amg-one.html",
        "Mercedes-AMG ONE pit box",
        Item.SourcePlatform.WEB,
    ),
    "gt3rs_corner": ImageSeed(
        "GT3 RS corner entry",
        "https://images.unsplash.com/photo-1517524008697-84bbe3c3fd98?auto=format&fit=crop&w=1200&q=80",
        "https://www.porsche.com/international/models/911/911-gt3-rs/",
        "Porsche GT3 RS corner entry",
        Item.SourcePlatform.EXTENSION,
    ),
    "tourbillon_profile": ImageSeed(
        "Tourbillon profile render",
        "https://images.unsplash.com/photo-1507136566006-cfc505b114fc?auto=format&fit=crop&w=1200&q=80",
        "https://www.bugatti.com/the-bugatti-models/tourbillon/",
        "Bugatti Tourbillon profile render",
        Item.SourcePlatform.WEB,
    ),
    "gemera_family": ImageSeed(
        "Gemera grand-touring stance",
        "https://images.unsplash.com/photo-1514316454349-750a7fd3da3a?auto=format&fit=crop&w=1200&q=80",
        "https://www.koenigsegg.com/model/gemera",
        "Koenigsegg Gemera grand-touring stance",
        Item.SourcePlatform.WEB,
    ),
    "huayra_road": ImageSeed(
        "Huayra R roadside detail",
        "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=1200&q=80",
        "https://www.pagani.com/huayra-r/",
        "Pagani Huayra R roadside detail",
        Item.SourcePlatform.EXTENSION,
    ),
    "venom_f5_run": ImageSeed(
        "Venom F5 desert run",
        "https://images.unsplash.com/photo-1542282088-72c9c27ed0cd?auto=format&fit=crop&w=1200&q=80",
        "https://www.hennesseyspecialvehicles.com/venom-f5/",
        "Hennessey Venom F5 desert run",
        Item.SourcePlatform.WEB,
    ),
    "evija_neon": ImageSeed(
        "Evija neon studio",
        "https://images.unsplash.com/photo-1515569067071-ec3b51335dd1?auto=format&fit=crop&w=1200&q=80",
        "https://www.lotuscars.com/en-GB/evija",
        "Lotus Evija neon studio",
        Item.SourcePlatform.WEB,
    ),
    "bolide_aero": ImageSeed(
        "Bolide aero study",
        "https://images.unsplash.com/photo-1563720223185-11003d516935?auto=format&fit=crop&w=1200&q=80",
        "https://www.bugatti.com/the-bugatti-models/bolide/",
        "Bugatti Bolide aero study",
        Item.SourcePlatform.EXTENSION,
    ),
    "artura_green": ImageSeed(
        "Artura green tunnel",
        "https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=1200&q=80",
        "https://cars.mclaren.com/en/artura",
        "McLaren Artura green tunnel",
        Item.SourcePlatform.WEB,
    ),
    "czinger_shadow": ImageSeed(
        "Czinger 21C shadow study",
        "https://images.unsplash.com/photo-1553440569-bcc63803a83d?auto=format&fit=crop&w=1200&q=80",
        "https://www.czinger.com/21c/",
        "Czinger 21C shadow study",
        Item.SourcePlatform.WEB,
    ),
    "daytona_sp3_red": ImageSeed(
        "Daytona SP3 red sprint",
        "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=1200&q=80",
        "https://www.ferrari.com/en-EN/auto/daytona-sp3",
        "Ferrari Daytona SP3 red sprint",
        Item.SourcePlatform.EXTENSION,
    ),
}

COLLECTIONS = [
    CollectionSeed(
        space_key="apex_vault",
        contributors=("petar", "milica"),
        texts=(
            "Collect benchmarks where aero devices change attitude without ruining road presence.",
            "Need a comparison of hybrid throttle response between SF90, Nevera, and Revuelto.",
            "Pin references where the cabin still feels analog even with a digital gauge stack.",
            "Prioritize launch assets that show stance, cooling paths, and wheel fitment in one frame.",
        ),
        link_keys=("ferrari_sf90", "lamborghini_revuelto", "rimac_nevera", "mclaren_750s"),
        image_keys=("sf90_studio", "revuelto_night"),
        start_hours_ago=38,
    ),
    CollectionSeed(
        space_key="carbon_atelier",
        contributors=("milica", "stefan"),
        texts=(
            "Look for matte forged carbon that reads technical rather than flashy under soft studio light.",
            "Great cabins mix carbon weave with leather grain so the surfaces do not feel clinical.",
            "Save examples of exposed tub edges, seat shells, and door sills with clean transitions.",
            "Wheel and brake photography should show material contrast, not just horsepower spectacle.",
        ),
        link_keys=("pagani_utopia", "koenigsegg_cc850", "maserati_mc20", "mclaren_artura"),
        image_keys=("utopia_detail", "mc20_coast"),
        start_hours_ago=34,
    ),
    CollectionSeed(
        space_key="v12_symphony",
        contributors=("stefan", "tamara"),
        texts=(
            "Catalog engines by character: sharp top-end scream, layered induction, or deep mechanical idle.",
            "Need clips and notes for naturally aspirated V12s that still sound rich below 4000 rpm.",
            "Track where exhaust placement changes the emotional feel in launch videos.",
            "Collect examples where gearbox calibration keeps the soundtrack alive during upshifts.",
        ),
        link_keys=("aston_valkyrie", "pagani_huayra_r", "mercedes_amg_one", "gma_t50_story"),
        image_keys=("valkyrie_track", "huayra_road"),
        start_hours_ago=30,
    ),
    CollectionSeed(
        space_key="track_legends",
        contributors=("tamara", "petar"),
        texts=(
            "The best track-special references show brake temp, tire pickup, and body control in the same sequence.",
            "Need a folder for aero details that only become obvious at speed: dive planes, louvers, shark fins.",
            "Compare how brands narrate lap times versus driver confidence and approachability.",
            "Add examples of pit-lane photography where motion blur still keeps badge and wheel design readable.",
        ),
        link_keys=("porsche_gt3rs", "bugatti_bolide", "evo_mclaren_senna", "roadtrack_amg_one_drive"),
        image_keys=("gt3rs_corner", "amg_one_pit"),
        start_hours_ago=26,
    ),
    CollectionSeed(
        space_key="inbox::petar",
        contributors=("petar",),
        texts=(
            "Ferrari notes should balance heritage language with modern hybrid credibility.",
            "F40, F50, Enzo, and Daytona SP3 make a strong lineage wall for storytelling.",
            "Look for shots where red paint is secondary to the sculpture of the body.",
            "Need a short write-up on why Ferrari interiors photograph best with warm highlights.",
        ),
        link_keys=("ferrari_daytona_sp3", "ferrari_296", "hagerty_f40", "topgear_enzo_legacy"),
        image_keys=("f40_archive", "daytona_sp3_red"),
        start_hours_ago=24,
    ),
    CollectionSeed(
        space_key="inbox::milica",
        contributors=("milica",),
        texts=(
            "Alcantara, open-pore carbon, and satin metal need different lighting notes for the material board.",
            "Save quilt patterns only when they support a lightweight brief rather than a luxury brief.",
            "Blue stitching on dark leather works best when there is one other cool accent nearby.",
            "Seat bolsters should look precision-cut, not overstuffed.",
        ),
        link_keys=("aston_valhalla", "lotus_evija", "caranddriver_gt3rs", "caranddriver_mc20"),
        image_keys=("artura_green", "evija_neon"),
        start_hours_ago=22,
    ),
    CollectionSeed(
        space_key="inbox::stefan",
        contributors=("stefan",),
        texts=(
            "Lap overlays are most useful when steering trace, brake pressure, and gear choice stay visible together.",
            "Collect dashboards that surface battery deploy, tire temp, and differential behavior without clutter.",
            "Engine bay references should include cooling exits, not only the block itself.",
            "Need examples of clean telemetry graphics that could inspire a SideKick card layout.",
        ),
        link_keys=("koenigsegg_jesko", "bugatti_tourbillon", "evo_t50", "roadtrack_nevera_tech"),
        image_keys=("jesko_orange", "tourbillon_profile"),
        start_hours_ago=20,
    ),
    CollectionSeed(
        space_key="inbox::tamara",
        contributors=("tamara",),
        texts=(
            "Track-day packs should mix pit references, paddock maps, and weather notes for the same circuit.",
            "Save cafe, hotel, or roadside stops only if they add atmosphere to the drive route.",
            "Need one comparison board for Spa, Monza, and the Nordschleife as destination brands.",
            "Capture how people photograph supercars in motion without losing circuit context.",
        ),
        link_keys=("goodwood_daytona_sp3", "goodwood_jesko_absolut", "topgear_revuelto_drive", "motor1_countach"),
        image_keys=("countach_sunset", "gemera_family"),
        start_hours_ago=18,
    ),
    CollectionSeed(
        space_key="inbox::jelena",
        contributors=("jelena",),
        texts=(
            "Launch copy works best when one visceral line is backed by one concrete engineering claim.",
            "Social snippets should distinguish beauty shots from proof points like aero load or power delivery.",
            "Need examples of headlines that sound premium without becoming generic luxury language.",
            "Collect taglines that feel fast, precise, and slightly dangerous.",
        ),
        link_keys=("autocar_valhalla", "hennessey_venom_f5", "ssc_tuatara", "evo_utopia_review"),
        image_keys=("venom_f5_run", "utopia_detail"),
        start_hours_ago=16,
    ),
    CollectionSeed(
        space_key="inbox::nikola",
        contributors=("nikola",),
        texts=(
            "Hybrid hypercars feel credible when packaging diagrams explain where the electric assist matters.",
            "Battery cooling details are as visually interesting as the motors when they are clearly annotated.",
            "Need examples of front-axle e-motor storytelling that stay understandable for non-engineers.",
            "Compare how brands explain torque fill, regen, and launch control in one sequence.",
        ),
        link_keys=("czinger_21c", "koenigsegg_gemera", "bugatti_chiron_ss", "topgear_tourbillon"),
        image_keys=("czinger_shadow", "nevera_blue"),
        start_hours_ago=14,
    ),
]

INBOX_CREATED_DAYS_AGO = {
    "petar": 12,
    "milica": 11,
    "stefan": 10,
    "tamara": 9,
    "jelena": 8,
    "nikola": 7,
}


def reset_uploaded_media(base_dir: Path) -> None:
    """Brise prethodno generisane otpremljene fajlove iz demo okruzenja."""

    uploads_dir = base_dir / "media" / "uploads"
    if uploads_dir.exists():
        shutil.rmtree(uploads_dir)


def build_collection_items(collection: CollectionSeed) -> list[ItemSeed]:
    """Pravi standardni miks od 10 tekst, link i image stavki za kolekciju."""

    if len(collection.texts) != 4 or len(collection.link_keys) != 4 or len(collection.image_keys) != 2:
        raise ValueError(f"Collection '{collection.space_key}' must define 4 texts, 4 links, and 2 images.")

    contributors = list(collection.contributors)
    schedule = [
        ("text", collection.texts[0]),
        ("link", collection.link_keys[0]),
        ("image", collection.image_keys[0]),
        ("text", collection.texts[1]),
        ("link", collection.link_keys[1]),
        ("text", collection.texts[2]),
        ("image", collection.image_keys[1]),
        ("link", collection.link_keys[2]),
        ("text", collection.texts[3]),
        ("link", collection.link_keys[3]),
    ]

    items: list[ItemSeed] = []
    for index, (kind, payload) in enumerate(schedule):
        contributor = contributors[index % len(contributors)]
        hours_ago = collection.start_hours_ago + (len(schedule) - index - 1)
        if kind == "text":
            items.append(
                ItemSeed(
                    space=collection.space_key,
                    added_by=contributor,
                    item_type=Item.ItemType.TEXT,
                    title="",
                    content_text=payload,
                    source_url="",
                    captured_url="",
                    page_title="",
                    source_platform=Item.SourcePlatform.WEB if index % 2 == 0 else Item.SourcePlatform.EXTENSION,
                    hours_ago=hours_ago,
                )
            )
            continue

        if kind == "link":
            link = LINK_LIBRARY[payload]
            items.append(
                ItemSeed(
                    space=collection.space_key,
                    added_by=contributor,
                    item_type=Item.ItemType.LINK,
                    title=link.title,
                    content_text="",
                    source_url=link.url,
                    captured_url=link.url,
                    page_title=link.page_title,
                    source_platform=link.source_platform,
                    hours_ago=hours_ago,
                )
            )
            continue

        image = IMAGE_LIBRARY[payload]
        items.append(
            ItemSeed(
                space=collection.space_key,
                added_by=contributor,
                item_type=Item.ItemType.IMAGE,
                title=image.title,
                content_text="",
                source_url=image.image_url,
                captured_url=image.captured_url,
                page_title=image.page_title,
                source_platform=image.source_platform,
                hours_ago=hours_ago,
            )
        )

    return items


def build_all_items() -> list[ItemSeed]:
    """Priprema sve demo stavke za glavne prostore i inboxe korisnika."""

    items: list[ItemSeed] = []
    for collection in COLLECTIONS:
        items.extend(build_collection_items(collection))
    return items


def rebuild_demo_data(*, base_dir: Path) -> dict[str, list[str]]:
    """Ponovo kreira demo korisnike, prostore i stavke i vraca sazetak unetih podataka."""

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

    for user_key, user in user_map.items():
        inbox_space = get_or_create_universal_space(user)
        inbox_created_at = now - timedelta(days=INBOX_CREATED_DAYS_AGO[user_key])
        inbox_space.created_at = inbox_created_at
        inbox_space.updated_at = inbox_created_at
        inbox_space.save(update_fields=["created_at", "updated_at"])
        space_map[f"inbox::{user_key}"] = inbox_space

    share_link_map = {
        "apex_vault": ShareLink.objects.create(
            space=space_map["apex_vault"],
            created_by=user_map["petar"],
            token="apex-vault-share",
            created_at=now - timedelta(days=3),
            expires_at=None,
            is_active=True,
        ),
        "carbon_atelier": ShareLink.objects.create(
            space=space_map["carbon_atelier"],
            created_by=user_map["milica"],
            token="carbon-atelier-share",
            created_at=now - timedelta(days=2),
            expires_at=now + timedelta(days=30),
            is_active=True,
        ),
        "v12_symphony": ShareLink.objects.create(
            space=space_map["v12_symphony"],
            created_by=user_map["stefan"],
            token="v12-symphony-share",
            created_at=now - timedelta(days=4),
            expires_at=None,
            is_active=True,
        ),
        "track_legends": ShareLink.objects.create(
            space=space_map["track_legends"],
            created_by=user_map["tamara"],
            token="track-legends-share",
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
        space=space_map["apex_vault"],
        requester=user_map["jelena"],
        resolved_by=None,
        status=CollaborationRequest.Status.PENDING,
        message="Would love collaborator access for launch messaging and hero-copy passes.",
        requested_at=now - timedelta(hours=13),
        resolved_at=None,
    )
    CollaborationRequest.objects.create(
        space=space_map["track_legends"],
        requester=user_map["nikola"],
        resolved_by=None,
        status=CollaborationRequest.Status.PENDING,
        message="Need access to add hybrid track-tech references and braking notes.",
        requested_at=now - timedelta(hours=9),
        resolved_at=None,
    )

    latest_space_updates: dict[int, datetime] = {}
    for item_seed in build_all_items():
        timestamp = now - timedelta(hours=item_seed.hours_ago)
        item = Item.objects.create(
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
        previous_timestamp = latest_space_updates.get(item.space_id)
        if previous_timestamp is None or timestamp > previous_timestamp:
            latest_space_updates[item.space_id] = timestamp

    for space in space_map.values():
        latest_timestamp = latest_space_updates.get(space.space_id)
        if latest_timestamp is None or latest_timestamp <= space.updated_at:
            continue
        space.updated_at = latest_timestamp
        space.save(update_fields=["updated_at"])

    credentials = [f"{seed.email} / {DEFAULT_PASSWORD}" for seed in USERS[:4]]
    return {"credentials": credentials}
