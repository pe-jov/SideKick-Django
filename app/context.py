# Author Petar Jovanovic
from urllib.parse import urlparse

from django.utils import timezone

from .models import AuthToken, CollaborationRequest, Item, Membership, ResearchSpace, ShareLink, User


SETTINGS = ["Notifications", "Privacy & Security", "Appearance", "Help & Support"]
SPACE_FILTERS = ["All", "Owned", "Shared"]
ITEM_FILTERS = ["All", "Images", "Links", "Text"]
UNIVERSAL_SPACE_PREFIX = "[[SIDEKICK_UNIVERSAL]]"
PASSWORD_RULES = [
    "Najmanje 8 karaktera",
    "Najmanje jedno malo slovo",
    "Najmanje jedno veliko slovo",
    "Najmanje jedna cifra",
    "Najmanje jedan specijalni karakter",
]


def get_demo_user():
    user = User.objects.filter(email="petar@example.com").first()
    if user:
        return user
    return User.objects.order_by("user_id").first()


def get_request_auth_token_value(request):
    cached = getattr(request, "_sidekick_extension_auth_token", None)
    if cached:
        return cached

    token_value = (
        request.GET.get("authToken")
        or request.POST.get("authToken")
        or request.GET.get("auth_token")
        or request.POST.get("auth_token")
    )
    if token_value:
        return token_value

    header = request.headers.get("Authorization", "").strip()
    if not header:
        return ""
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() not in {"token", "bearer"}:
        return ""
    return parts[1]


def get_request_auth_token(request):
    cached = getattr(request, "_sidekick_extension_auth_token_object", None)
    if cached is not None:
        return cached

    token_value = get_request_auth_token_value(request)
    if not token_value:
        request._sidekick_extension_auth_token_object = None
        return None

    auth_token = (
        AuthToken.objects.select_related("user")
        .filter(token_value=token_value, is_revoked=False)
        .first()
    )
    if auth_token is None:
        request._sidekick_extension_auth_token_object = None
        return None
    if auth_token.expires_at and auth_token.expires_at <= timezone.now():
        request._sidekick_extension_auth_token_object = None
        return None

    request._sidekick_extension_auth_token = token_value
    request._sidekick_extension_auth_token_object = auth_token
    return auth_token


def get_current_auth_token_value(request):
    auth_token = get_request_auth_token(request)
    if auth_token is None:
        return ""
    return auth_token.token_value


def get_current_user(request):
    cached_user = getattr(request, "_sidekick_current_user", None)
    if cached_user is not None:
        return cached_user

    user_id = request.session.get("sidekick_user_id")
    if user_id:
        user = User.objects.filter(user_id=user_id).first()
        if user is not None:
            request._sidekick_current_user = user
            return user

    auth_token = get_request_auth_token(request)
    if auth_token is None:
        request._sidekick_current_user = None
        return None

    request._sidekick_current_user = auth_token.user
    return auth_token.user


def share_link_is_available(share_link):
    return share_link is not None and share_link.is_active and (
        share_link.expires_at is None or share_link.expires_at > timezone.now()
    ) 


def universal_space_marker(user):
    return f"{UNIVERSAL_SPACE_PREFIX}:{user.user_id}"


def is_universal_space(space):
    if space is None:
        return False
    return (space.description or "").startswith(UNIVERSAL_SPACE_PREFIX)


def get_or_create_universal_space(user):
    marker = universal_space_marker(user)
    space = ResearchSpace.objects.filter(owner=user, description=marker).first()
    if space is not None:
        return space

    now = timezone.now()
    return ResearchSpace.objects.create(
        owner=user,
        name="Inbox",
        description=marker,
        is_archived=False,
        created_at=now,
        updated_at=now,
    )


def membership_grants_access(membership):
    if membership.status != Membership.Status.ACTIVE:
        return False
    if membership.role == Membership.Role.VIEWER and membership.joined_via_id:
        return share_link_is_available(membership.joined_via)
    return True


def filter_spaces(active_filter, current_user):
    spaces = ResearchSpace.objects.select_related("owner").prefetch_related("memberships__user", "memberships__joined_via")
    if current_user is None:
        return []
    visible_spaces = sorted(
        [space for space in spaces if not is_universal_space(space)],
        key=lambda space: (space.updated_at, space.space_id),
        reverse=True,
    )

    if active_filter == "Owned":
        return [space for space in visible_spaces if space.owner_id == current_user.user_id]
    if active_filter == "Shared":
        return [
            space for space in visible_spaces
            if space.owner_id != current_user.user_id and current_space_role(space, current_user) in {"Collaborator", "Viewer"}
        ]

    return [
        space for space in visible_spaces
        if space.owner_id == current_user.user_id or current_space_role(space, current_user) in {"Collaborator", "Viewer"}
    ]


def current_space_role(space, current_user):
    if current_user is None:
        return "Preview"
    if space.owner_id == current_user.user_id:
        return "Owner"
    membership = next(
        (
            membership
            for membership in space.memberships.all()
            if membership.user_id == current_user.user_id
            and membership_grants_access(membership)
        ),
        None,
    )
    if membership:
        return membership.role.capitalize()
    return None


def serialize_space(space, current_user):
    return {
        "id": space.space_id,
        "name": space.name,
        "description": space.description,
        "role": current_space_role(space, current_user),
        "is_archived": space.is_archived,
    }


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


def item_user_filters(items):
    return ["All", *sorted({item["added_by"] for item in items})]


def serialize_item(item):
    domain = ""
    if item.source_url or item.captured_url:
        domain = urlparse(item.source_url or item.captured_url).netloc
    return {
        "id": item.item_id,
        "type": item.item_type,
        "src": item.image_url if item.item_type == Item.ItemType.IMAGE else None,
        "content": item.content_text if item.item_type == Item.ItemType.TEXT else None,
        "title": item.title if item.item_type == Item.ItemType.LINK else None,
        "domain": domain if item.item_type == Item.ItemType.LINK else None,
        "space": item.space.name,
        "added_by": item.added_by.full_name,
        "source_url": item.source_url,
        "captured_url": item.captured_url,
        "page_title": item.page_title,
    }


def get_recent_items():
    return Item.objects.none()


def accessible_spaces(current_user):
    if current_user is None:
        return ResearchSpace.objects.none()
    all_spaces = (
        ResearchSpace.objects.select_related("owner")
        .prefetch_related("memberships__user", "memberships__joined_via")
    )
    allowed_ids = [
        space.space_id
        for space in all_spaces
        if not is_universal_space(space)
        and (space.owner_id == current_user.user_id or current_space_role(space, current_user) in {"Collaborator", "Viewer"})
    ]
    return ResearchSpace.objects.filter(space_id__in=allowed_ids)


def get_recent_items_for_user(current_user):
    if current_user is None:
        return Item.objects.none()
    return (
        Item.objects.select_related("space", "added_by")
        .filter(space__in=accessible_spaces(current_user))
        .order_by("-created_at", "-item_id")[:6]
    )


def get_space(space_id, current_user=None):
    space = (
        ResearchSpace.objects.select_related("owner")
        .prefetch_related("memberships__user", "memberships__joined_via")
        .filter(space_id=space_id)
        .first()
    )
    if current_user is None or space is None:
        return None
    if space.owner_id == current_user.user_id:
        return space
    if get_membership(space, current_user):
        return space
    return None


def get_space_items(space):
    return (
        Item.objects.select_related("space", "added_by")
        .filter(space=space)
        .order_by("-created_at", "-item_id")
    )


def get_membership(space, user):
    if user is None:
        return None
    return next(
        (
            membership
            for membership in space.memberships.all()
            if membership.user_id == user.user_id
            and membership_grants_access(membership)
        ),
        None,
    )


def get_space_collaborators(space):
    collaborators = [
        {
            "id": space.owner.user_id,
            "member_id": None,
            "name": space.owner.full_name,
            "email": space.owner.email,
            "role": "Owner",
            "avatar": space.owner.avatar_url,
            "badge_class": "role-owner",
        }
    ]
    badge_map = {
        Membership.Role.COLLABORATOR: "role-collaborator",
        Membership.Role.VIEWER: "role-viewer",
    }
    collaborators.extend(
        {
            "id": membership.user.user_id,
            "member_id": membership.membership_id,
            "name": membership.user.full_name,
            "email": membership.user.email,
            "role": membership.role.capitalize(),
            "avatar": membership.user.avatar_url,
            "badge_class": badge_map[membership.role],
        }
        for membership in space.memberships.all()
        if membership_grants_access(membership)
    )
    return collaborators


def get_collaboration_requests(space=None, current_user=None):
    requests = CollaborationRequest.objects.select_related("requester", "space")
    if space is not None:
        requests = requests.filter(space=space)
    if current_user is not None and space is not None and space.owner_id != current_user.user_id:
        requests = requests.filter(requester=current_user)
    status_classes = {
        CollaborationRequest.Status.PENDING: "status-pending",
        CollaborationRequest.Status.APPROVED: "status-approved",
        CollaborationRequest.Status.REJECTED: "status-rejected",
    }
    return [
        {
            "id": request.request_id,
            "name": request.requester.full_name,
            "space": request.space.name,
            "status": request.status.capitalize(),
            "status_class": status_classes[request.status],
            "note": request.message or "Zahtev je evidentiran u sistemu.",
            "is_pending": request.status == CollaborationRequest.Status.PENDING,
        }
        for request in requests.order_by("request_id")
    ]


def get_profile_user(request):
    return get_current_user(request) or get_demo_user()


def get_user_profile_summary(current_user):
    if current_user is None:
        return {
            "owned_spaces": 0,
            "shared_spaces": 0,
            "saved_items": 0,
            "recent_items": [],
        }

    owned_spaces = ResearchSpace.objects.filter(owner=current_user).exclude(description__startswith=UNIVERSAL_SPACE_PREFIX).count()
    shared_memberships = Membership.objects.select_related("joined_via").filter(
        user=current_user,
        status=Membership.Status.ACTIVE,
    )
    shared_spaces = sum(1 for membership in shared_memberships if membership_grants_access(membership))
    saved_items = Item.objects.filter(added_by=current_user).count()
    recent_items = (
        Item.objects.select_related("space")
        .filter(added_by=current_user)
        .order_by("-created_at", "-item_id")[:5]
    )

    return {
        "owned_spaces": owned_spaces,
        "shared_spaces": shared_spaces,
        "saved_items": saved_items,
        "recent_items": recent_items,
    }
