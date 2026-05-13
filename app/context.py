# Author Petar Jovanovic
SPACES = [
    {
        "id": 1,
        "name": "Design Inspiration",
        "role": "Owner",
        "image": "https://picsum.photos/seed/design/400/400",
        "is_favorite": True,
        "is_archived": False,
    },
    {
        "id": 2,
        "name": "Project Alpha",
        "role": "Collaborator",
        "image": "https://picsum.photos/seed/alpha/400/400",
        "is_favorite": False,
        "is_archived": False,
    },
    {
        "id": 3,
        "name": "Recipes",
        "role": "Owner",
        "image": "https://picsum.photos/seed/recipes/400/400",
        "is_favorite": False,
        "is_archived": True,
    },
    {
        "id": 4,
        "name": "Travel Ideas",
        "role": "Collaborator",
        "image": "https://picsum.photos/seed/travel/400/400",
        "is_favorite": True,
        "is_archived": False,
    },
]

COLLABORATORS = [
    {
        "id": 1,
        "name": "Petar",
        "email": "petar@example.com",
        "role": "Owner",
        "avatar": "https://picsum.photos/seed/petar/100/100",
        "badge_class": "role-owner",
    },
    {
        "id": 2,
        "name": "Milan",
        "email": "milan@example.com",
        "role": "Collaborator",
        "avatar": "https://picsum.photos/seed/milan/100/100",
        "badge_class": "role-collaborator",
    },
    {
        "id": 3,
        "name": "Luka",
        "email": "luka@example.com",
        "role": "Viewer",
        "avatar": "https://picsum.photos/seed/luka/100/100",
        "badge_class": "role-viewer",
    },
]

COLLABORATION_REQUESTS = [
    {
        "id": 1,
        "name": "Ana Markovic",
        "space": "Project Alpha",
        "status": "Pending approval",
        "status_class": "status-pending",
        "note": "Owner treba da pregleda zahtev za pristup.",
    },
    {
        "id": 2,
        "name": "Nikola Ilic",
        "space": "Travel Ideas",
        "status": "Approved",
        "status_class": "status-approved",
        "note": "Pristup je odobren i korisnik je obavesten.",
    },
    {
        "id": 3,
        "name": "Jelena Popovic",
        "space": "Design Inspiration",
        "status": "Rejected",
        "status_class": "status-rejected",
        "note": "Zahtev je zatvoren i ne moze se slati beskonacno iznova.",
    },
]

SETTINGS = ["Notifications", "Privacy & Security", "Appearance", "Help & Support"]
SPACE_FILTERS = ["All", "Owned", "Shared"]
ITEM_FILTERS = ["All", "Images", "Links", "Text"]
PASSWORD_RULES = [
    "Najmanje 8 karaktera",
    "Najmanje jedno malo slovo",
    "Najmanje jedno veliko slovo",
    "Najmanje jedna cifra",
    "Najmanje jedan specijalni karakter",
]


def generate_items():
    items = []
    item_id = 1
    authors = [user["name"] for user in COLLABORATORS]
    for space in SPACES:
        seed_name = space["name"].replace(" ", "")
        for index in range(10):
            item_type = "image" if index % 3 == 0 else "text" if index % 3 == 1 else "link"
            items.append(
                {
                    "id": item_id,
                    "type": item_type,
                    "src": (
                        f"https://picsum.photos/seed/{seed_name}{index}/600/{600 + (index % 3) * 100}"
                        if item_type == "image"
                        else None
                    ),
                    "content": (
                        f"Minimalistička misao #{index + 1} za {space['name']}. "
                        "Neka bude jednostavno i čisto."
                        if item_type == "text"
                        else None
                    ),
                    "title": f"Korisni resurs #{index + 1}" if item_type == "link" else None,
                    "domain": "developer.apple.com" if item_type == "link" else None,
                    "space": space["name"],
                    "added_by": authors[(index + space["id"]) % len(authors)],
                }
            )
            item_id += 1
    return items


ALL_ITEMS = generate_items()
RECENT_ITEMS = ALL_ITEMS[:6]


def get_space(space_id):
    return next((space for space in SPACES if space["id"] == space_id), None)


def filter_spaces(active_filter):
    if active_filter == "Owned":
        return [space for space in SPACES if space["role"] == "Owner"]
    if active_filter == "Shared":
        return [space for space in SPACES if space["role"] == "Collaborator"]
    if active_filter == "Archived":
        return [space for space in SPACES if space["is_archived"]]
    if active_filter == "Favorites":
        return [space for space in SPACES if space["is_favorite"]]
    return SPACES


def item_user_filters(items):
    return ["All", *sorted({item["added_by"] for item in items})]


def filter_items(items, active_filter, active_user_filter="All"):
    filtered_items = items
    if active_filter == "Images":
        filtered_items = [item for item in filtered_items if item["type"] == "image"]
    elif active_filter == "Links":
        filtered_items = [item for item in filtered_items if item["type"] == "link"]
    elif active_filter == "Text":
        filtered_items = [item for item in filtered_items if item["type"] == "text"]

    if active_user_filter != "All":
        filtered_items = [item for item in filtered_items if item["added_by"] == active_user_filter]

    return filtered_items
