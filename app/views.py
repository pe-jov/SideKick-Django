# Author Petar Jovanovic
import json
import re
import secrets
from html import unescape
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.core.files.storage import default_storage

from .context import (
    ITEM_FILTERS,
    PASSWORD_RULES,
    SETTINGS,
    SPACE_FILTERS,
    accessible_spaces,
    filter_items,
    filter_spaces,
    get_collaboration_requests,
    get_current_user,
    get_membership,
    get_profile_user,
    get_recent_items_for_user,
    get_space_collaborators,
    get_space_items,
    get_space,
    get_user_profile_summary,
    item_user_filters,
    serialize_item,
    serialize_space,
)
from .models import AuthToken, CollaborationRequest, Item, Membership, ResearchSpace, ShareLink, User


PASSWORD_VALIDATORS = [
    (lambda value: len(value) >= 8, "Password must have at least 8 characters."),
    (lambda value: re.search(r"[a-z]", value), "Password must contain a lowercase letter."),
    (lambda value: re.search(r"[A-Z]", value), "Password must contain an uppercase letter."),
    (lambda value: re.search(r"\d", value), "Password must contain a number."),
    (
        lambda value: re.search(r"[^A-Za-z0-9]", value),
        "Password must contain a special character.",
    ),
]


def json_error(message, *, status, code):
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


def parse_request_data(request):
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return None
    if request.method in {"POST", "PATCH", "DELETE"}:
        return request.POST
    return request.GET


def password_validation_error(password):
    for validator, message in PASSWORD_VALIDATORS:
        if not validator(password):
            return message
    return None


def read_url_title(url):
    try:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; SideKick/1.0)",
            },
        )
        with urlopen(request, timeout=3) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return ""
            html = response.read(200000).decode("utf-8", errors="ignore")
    except (ValueError, URLError, TimeoutError):
        return ""

    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    title = unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return title[:255]


def normalized_url(value):
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return value
    if not parsed.scheme and parsed.path and "." in parsed.path:
        return f"https://{value}"
    return value


def looks_like_absolute_url(value):
    parsed = urlparse(value or "")
    return bool(parsed.scheme and parsed.netloc)


def issue_auth_token(user, *, client_type=AuthToken.ClientType.WEB):
    now = timezone.now()
    return AuthToken.objects.create(
        user=user,
        token_value=secrets.token_urlsafe(32),
        client_type=client_type,
        issued_at=now,
        expires_at=None,
        is_revoked=False,
    )


def serialize_user_payload(user):
    return {
        "id": user.user_id,
        "email": user.email,
        "fullName": user.full_name,
        "createdAt": user.created_at.isoformat(),
        "updatedAt": user.updated_at.isoformat(),
    }


def serialize_space_payload(space, current_user):
    role = "owner" if is_owner(space, current_user) else membership_role(space, current_user) or "viewer"
    return {
        "id": space.space_id,
        "name": space.name,
        "description": space.description,
        "role": role,
        "ownerId": space.owner_id,
        "isArchived": space.is_archived,
        "createdAt": space.created_at.isoformat(),
        "updatedAt": space.updated_at.isoformat(),
    }


def serialize_item_payload(item):
    payload = {
        "id": item.item_id,
        "spaceId": item.space_id,
        "addedById": item.added_by_id,
        "addedByName": item.added_by.full_name,
        "type": item.item_type,
        "content": item.content_text,
        "sourceUrl": item.source_url,
        "imagePath": item.image_path,
        "title": item.title,
        "note": item.note,
        "sourcePlatform": item.source_platform,
        "capturedUrl": item.captured_url,
        "pageTitle": item.page_title,
        "createdAt": item.created_at.isoformat(),
        "updatedAt": item.updated_at.isoformat(),
    }
    if item.item_type == Item.ItemType.LINK:
        payload["domain"] = item.domain
    return payload


def get_token_from_request(request):
    header = request.headers.get("Authorization", "").strip()
    if not header:
        return None
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() not in {"token", "bearer"}:
        return None
    return parts[1]


def require_api_token(request):
    token_value = get_token_from_request(request)
    if not token_value:
        return None, None, json_error(
            "Authorization token is required.",
            status=401,
            code="missing_token",
        )

    auth_token = (
        AuthToken.objects.select_related("user")
        .filter(token_value=token_value)
        .first()
    )
    if auth_token is None or auth_token.is_revoked:
        return None, None, json_error(
            "Authentication token is invalid.",
            status=401,
            code="invalid_token",
        )

    if auth_token.expires_at and auth_token.expires_at <= timezone.now():
        return None, None, json_error(
            "Authentication token has expired.",
            status=401,
            code="expired_token",
        )

    return auth_token.user, auth_token, None


def save_uploaded_image(uploaded_image, current_user):
    safe_name = slugify(uploaded_image.name.rsplit(".", 1)[0]) or "image"
    extension = uploaded_image.name.rsplit(".", 1)[-1].lower() if "." in uploaded_image.name else "bin"
    stored_path = default_storage.save(
        f"uploads/user_{current_user.user_id}/{timezone.now().strftime('%Y%m%d%H%M%S')}_{safe_name}.{extension}",
        uploaded_image,
    )
    return default_storage.url(stored_path)


def create_item_record(*, current_user, space, item_type, content_text="", source_url="", note="", title="", uploaded_image=None):
    item_type = (item_type or Item.ItemType.TEXT).lower()
    valid_item_types = {choice for choice, _ in Item.ItemType.choices}
    if item_type not in valid_item_types:
        return None, "Unsupported item type.", "invalid_type"

    content_text = (content_text or "").strip()
    source_url = normalized_url(source_url)
    note = (note or "").strip()
    title = (title or "").strip()
    captured_url = source_url
    image_path = ""
    page_title = title

    if item_type == Item.ItemType.TEXT:
        if not content_text:
            return None, "Text items require content.", "missing_content"
    elif item_type == Item.ItemType.LINK:
        if not source_url or not looks_like_absolute_url(source_url):
            return None, "Link items require a valid source URL.", "missing_source_url"
        if not title:
            title = read_url_title(source_url)
        page_title = title or source_url
    elif item_type == Item.ItemType.IMAGE:
        image_url = normalized_url(source_url)
        if uploaded_image is not None:
            image_path = save_uploaded_image(uploaded_image, current_user)
            source_url = image_path
            captured_url = ""
            page_title = title or uploaded_image.name
        elif image_url and looks_like_absolute_url(image_url):
            source_url = image_url
            page_title = title or read_url_title(image_url) or image_url
        else:
            return None, "Image items require an uploaded image or a valid image URL.", "missing_image"

    now = timezone.now()
    item = Item.objects.create(
        space=space,
        added_by=current_user,
        item_type=item_type,
        content_text=content_text,
        source_url=source_url,
        image_path=image_path,
        title=title or page_title or source_url,
        note=note,
        source_platform=Item.SourcePlatform.WEB,
        captured_url=captured_url,
        page_title=page_title,
        created_at=now,
        updated_at=now,
    )
    return Item.objects.select_related("space", "added_by").get(item_id=item.item_id), None, None


def sanitize_next_url(request, fallback):
    next_url = request.POST.get("next_url") or request.GET.get("next") or fallback
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return fallback


def require_current_user(request):
    current_user = get_current_user(request)
    if current_user is None:
        return None, redirect(reverse("app:home"))
    return current_user, None


def is_owner(space, current_user):
    return current_user is not None and space.owner_id == current_user.user_id


def active_membership(space, current_user):
    return get_membership(space, current_user)


def membership_role(space, current_user):
    membership = active_membership(space, current_user)
    return membership.role if membership else None


def can_add_items(space, current_user):
    if is_owner(space, current_user):
        return True
    return membership_role(space, current_user) == Membership.Role.COLLABORATOR


def can_delete_item_record(item, current_user):
    if is_owner(item.space, current_user):
        return True
    role = membership_role(item.space, current_user)
    if role != Membership.Role.COLLABORATOR:
        return False
    return item.added_by_id == current_user.user_id


def can_manage_members(space, current_user):
    return is_owner(space, current_user)


def active_share_link(space):
    now = timezone.now()
    return (
        ShareLink.objects.filter(space=space, is_active=True)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .order_by("-created_at", "-share_link_id")
        .first()
    )


def latest_collaboration_request(space, user):
    if space is None or user is None:
        return None
    return (
        CollaborationRequest.objects.filter(space=space, requester=user)
        .order_by("-requested_at", "-request_id")
        .first()
    )


def create_collaboration_request(*, space, requester, message):
    existing = latest_collaboration_request(space, requester)
    if existing is not None:
        if existing.status == CollaborationRequest.Status.PENDING:
            return None, "info", "Your collaborator request is already pending."
        if existing.status == CollaborationRequest.Status.REJECTED:
            return None, "error", "This collaborator request was already rejected and cannot be sent again."
        if existing.status == CollaborationRequest.Status.APPROVED:
            return None, "info", "Your access request was already approved."

    request_record = CollaborationRequest.objects.create(
        space=space,
        requester=requester,
        resolved_by=None,
        status=CollaborationRequest.Status.PENDING,
        message=message,
        requested_at=timezone.now(),
        resolved_at=None,
    )
    return request_record, "success", "Collaborator request sent."


def serialize_request_state(request_record):
    if request_record is None:
        return None
    status_classes = {
        CollaborationRequest.Status.PENDING: "status-pending",
        CollaborationRequest.Status.APPROVED: "status-approved",
        CollaborationRequest.Status.REJECTED: "status-rejected",
    }
    return {
        "status": request_record.status.capitalize(),
        "status_class": status_classes[request_record.status],
        "note": request_record.message or "Your request is recorded in SideKick.",
    }


def revoke_space_share_links(space):
    now = timezone.now()
    active_links = list(ShareLink.objects.filter(space=space, is_active=True))
    if not active_links:
        return 0

    link_ids = [link.share_link_id for link in active_links]
    ShareLink.objects.filter(share_link_id__in=link_ids).update(is_active=False)
    Membership.objects.filter(
        space=space,
        role=Membership.Role.VIEWER,
        status=Membership.Status.ACTIVE,
        joined_via_id__in=link_ids,
    ).update(status=Membership.Status.REMOVED, updated_at=now)
    return len(link_ids)


def set_flash_and_redirect(request, level, message, target):
    getattr(messages, level)(request, message)
    return redirect(target)


def url_with_query(request, **updates):
    query = request.GET.copy()
    if query.get("mock") not in {"login", "register"}:
        query.pop("mock", None)
    for key, value in updates.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    encoded = query.urlencode()
    return f"{request.path}?{encoded}" if encoded else request.path


def filter_links(request, filters, query_key, active_filter):
    return [
        {
            "label": label,
            "is_active": label == active_filter,
            "url": url_with_query(request, **{query_key: None if label == "All" else label}),
        }
        for label in filters
    ]


def decorate_items(request, items):
    decorated = []
    for item in items:
        decorated.append(
            {
                **item,
                "preview_url": url_with_query(request, preview=item["id"]),
            }
        )
    return decorated


def build_item_preview(request, items):
    preview_id = request.GET.get("preview")
    if not preview_id or not items:
        return None

    selected_item = next((item for item in items if str(item["id"]) == preview_id), None)
    if selected_item is None:
        return None

    external_url = selected_item.get("captured_url") or selected_item.get("source_url")
    domain = selected_item.get("domain") or ""
    favicon_url = ""
    if external_url:
        favicon_url = f"https://www.google.com/s2/favicons?sz=128&domain_url={external_url}"

    return {
        **selected_item,
        "external_url": external_url,
        "favicon_url": favicon_url,
        "close_url": url_with_query(request, preview=None),
    }


def build_action_modal(request, *, selected_space=None, items=None):
    dialog = request.GET.get("dialog")
    current_user = get_current_user(request)
    if dialog == "change-password" and current_user:
        return {
            "type": "change-password",
            "title": "Change Password",
        }
    if dialog == "edit-profile" and current_user:
        return {
            "type": "edit-profile",
            "title": "Edit Profile",
            "full_name": current_user.full_name,
            "email": current_user.email,
        }
    if dialog == "create-space":
        return {
            "type": "create-space",
            "title": "Create Space",
        }
    if dialog == "edit-space" and selected_space:
        return {
            "type": "edit-space",
            "title": "Edit Space",
            "space_name": selected_space["name"],
            "space_description": selected_space.get("description", ""),
        }
    if dialog == "add-item" and selected_space:
        return {
            "type": "add-item",
            "title": "Add Item",
            "space_name": selected_space["name"],
        }
    if dialog == "invite-member" and selected_space:
        return {
            "type": "invite-member",
            "title": "Invite People",
            "space_name": selected_space["name"],
        }
    if dialog == "share-link" and selected_space:
        return {
            "type": "share-link",
            "title": "Share Link",
            "share_url": request.GET.get("share_url", ""),
        }
    if dialog == "delete-space" and selected_space and selected_space["role"] == "Owner":
        return {
            "type": "delete-space",
            "title": "Delete Space",
            "copy": (
                f'"{selected_space["name"]}" bi bio trajno obrisan zajedno sa svim stavkama i collaborator-ima.'
            ),
            "confirm_label": "Delete space",
            "action_url": reverse("app:delete_space"),
            "space_id": selected_space["id"],
        }
    if dialog == "remove-member" and request.GET.get("member_id"):
        member_name = request.GET.get("member_name", "this member")
        return {
            "type": "remove-member",
            "title": "Remove Collaborator",
            "copy": f"{member_name} bi odmah izgubio pristup ovom prostoru.",
            "confirm_label": "Remove collaborator",
            "action_url": reverse("app:remove_member"),
            "member_id": request.GET["member_id"],
            "space_id": selected_space["id"] if selected_space else None,
        }
    if dialog == "review-request" and request.GET.get("request_id") and request.GET.get("decision"):
        decision = request.GET["decision"]
        return {
            "type": "review-request",
            "title": "Review Request",
            "copy": "This collaboration request will be updated immediately.",
            "confirm_label": "Approve request" if decision == "approve" else "Reject request",
            "action_url": reverse("app:review_request"),
            "request_id": request.GET["request_id"],
            "decision": decision,
        }
    if dialog == "delete-item" and items:
        item_id = request.GET.get("item")
        selected_item = next((item for item in items if str(item["id"]) == item_id), None)
        if selected_item:
            return {
                "type": "delete-item",
                "title": "Delete Item",
                "copy": f'Stavka koju je dodao {selected_item["added_by"]} bi bila trajno uklonjena iz prikaza.',
                "confirm_label": "Delete item",
                "action_url": reverse("app:delete_item"),
                "item_id": selected_item["id"],
            }
    return None


def base_context(request, *, title, active_tab="home", selected_space=None):
    mock_panel = request.GET.get("mock")
    current_user = get_current_user(request)
    auth_next_url = url_with_query(request, mock=None)
    auth_error = request.GET.get("auth_error")
    context = {
        "title": title,
        "active_tab": active_tab,
        "selected_space": selected_space,
        "current_user": current_user,
        "collaborators": get_space_collaborators(selected_space["_object"]) if selected_space else [],
        "collaboration_requests": get_collaboration_requests(selected_space["_object"], current_user) if selected_space else [],
        "is_modal_open": request.GET.get("modal") == "team",
        "mock_panel": mock_panel if mock_panel in {"login", "register"} else None,
        "auth_error": auth_error,
        "team_url": url_with_query(request, modal="team"),
        "close_modal_url": url_with_query(request, modal=None),
        "login_url": url_with_query(request, mock="login"),
        "register_url": url_with_query(request, mock="register"),
        "close_mock_url": url_with_query(request, mock=None),
        "login_action_url": reverse("app:login_action"),
        "register_action_url": reverse("app:register_action"),
        "logout_action_url": reverse("app:logout_action"),
        "next_url": auth_next_url,
        "password_rules": PASSWORD_RULES,
        "home_url": reverse("app:home"),
        "profile_url": reverse("app:profile"),
        "back_url": reverse("app:home"),
        "password_url": url_with_query(request, dialog="change-password"),
        "edit_profile_url": url_with_query(request, dialog="edit-profile"),
        "create_space_url": url_with_query(request, dialog="create-space"),
        "update_profile_url": reverse("app:update_profile"),
        "change_password_url": reverse("app:change_password"),
        "save_space_url": reverse("app:create_space"),
        "update_space_url": reverse("app:update_space"),
        "save_item_url": reverse("app:create_item"),
        "invite_member_url": reverse("app:invite_member"),
        "action_modal": build_action_modal(request, selected_space=selected_space),
        "close_dialog_url": url_with_query(
            request,
            dialog=None,
            item=None,
            member=None,
            member_id=None,
            member_name=None,
            request_id=None,
            decision=None,
            share_url=None,
        ),
    }
    return context


def home(request):
    current_user = get_current_user(request)
    active_space_filter = request.GET.get("space_filter", "All")
    context = base_context(request, title="SideKick")
    space_dicts = [serialize_space(space, current_user) for space in filter_spaces(active_space_filter, current_user)]
    recent_items = decorate_items(request, [serialize_item(item) for item in get_recent_items_for_user(current_user)])
    context.update(
        {
            "spaces": space_dicts,
            "items": recent_items,
            "space_filter_links": filter_links(
                request, SPACE_FILTERS, "space_filter", active_space_filter
            ),
            "item_preview": build_item_preview(request, recent_items),
        }
    )
    return render(request, "app/home.html", context)


def profile(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    context = base_context(request, title="Profile", active_tab="profile")
    context["settings"] = SETTINGS
    context["profile_user"] = get_profile_user(request)
    context["profile_summary"] = get_user_profile_summary(current_user)
    context["owned_spaces"] = accessible_spaces(current_user).filter(owner=current_user)
    return render(request, "app/profile.html", context)


def space_detail(request, space_id):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    space_obj = get_space(space_id, current_user)
    if space_obj is None:
        raise Http404("Space not found")

    active_item_filter = request.GET.get("item_filter", "All")
    active_user_filter = request.GET.get("user_filter", "All")
    selected_space = serialize_space(space_obj, current_user)
    selected_space["_object"] = space_obj
    raw_space_items = list(get_space_items(space_obj))
    space_items = []
    for item in raw_space_items:
        serialized_item = serialize_item(item)
        if can_delete_item_record(item, current_user):
            serialized_item["delete_url"] = url_with_query(request, dialog="delete-item", item=item.item_id)
        serialized_item["preview_url"] = url_with_query(request, preview=item.item_id)
        space_items.append(serialized_item)
    context = base_context(request, title=space_obj.name, selected_space=selected_space)
    context["action_modal"] = build_action_modal(request, selected_space=selected_space, items=space_items)
    user_filters = item_user_filters(space_items)
    filtered_items = filter_items(space_items, active_item_filter, active_user_filter)
    current_membership = get_membership(space_obj, current_user)
    latest_request = serialize_request_state(latest_collaboration_request(space_obj, current_user))
    context.update(
        {
            "space": selected_space,
            "item_count": len(space_items),
            "items": filtered_items,
            "item_filter_links": filter_links(request, ITEM_FILTERS, "item_filter", active_item_filter),
            "user_filter_links": filter_links(request, user_filters, "user_filter", active_user_filter),
            "delete_space_url": url_with_query(request, dialog="delete-space"),
            "show_item_actions": True,
            "can_add_item": can_add_items(space_obj, current_user),
            "can_manage_members": can_manage_members(space_obj, current_user),
            "can_request_collaboration": (
                current_membership is not None
                and current_membership.role == Membership.Role.VIEWER
            ),
            "request_collaboration_url": reverse("app:request_space_collaboration", args=[space_obj.space_id]),
            "latest_collaboration_request": latest_request,
            "team_modal_return_url": f'{reverse("app:space_detail", args=[space_obj.space_id])}?modal=team',
            "invite_people_url": url_with_query(request, modal="team", dialog="invite-member"),
            "share_space_url": url_with_query(request, dialog="share-link"),
            "item_preview": build_item_preview(request, filtered_items),
        }
    )
    return render(request, "app/space_detail.html", context)


def login_action(request):
    if request.method != "POST":
        return redirect("app:home")

    fallback = reverse("app:home")
    next_url = sanitize_next_url(request, fallback)
    email = (request.POST.get("email") or "").strip().lower()
    password = request.POST.get("password") or ""

    user = User.objects.filter(email=email).first()
    if user is None or not check_password(password, user.password_hash):
        login_url = f'{reverse("app:home")}?mock=login&auth_error=invalid_login'
        if next_url and next_url != "/":
            login_url = f"{login_url}&next={next_url}"
        return redirect(login_url)

    session_token = issue_auth_token(user)
    request.session["sidekick_user_id"] = user.user_id
    request.session["sidekick_auth_token"] = session_token.token_value
    return redirect(next_url)


def register_action(request):
    if request.method != "POST":
        return redirect("app:home")

    fallback = reverse("app:home")
    next_url = sanitize_next_url(request, fallback)
    full_name = (request.POST.get("name") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    password = request.POST.get("password") or ""
    confirm_password = request.POST.get("confirm_password") or ""

    if not full_name or not email or not password:
        error_code = "missing_fields"
    elif User.objects.filter(email=email).exists():
        error_code = "email_exists"
    elif password != confirm_password:
        error_code = "password_mismatch"
    elif password_validation_error(password):
        error_code = "weak_password"
    else:
        now = timezone.now()
        user = User.objects.create(
            email=email,
            password_hash=make_password(password),
            full_name=full_name,
            created_at=now,
            updated_at=now,
        )
        session_token = issue_auth_token(user)
        request.session["sidekick_user_id"] = user.user_id
        request.session["sidekick_auth_token"] = session_token.token_value
        return redirect(next_url)

    register_url = f'{reverse("app:home")}?mock=register&auth_error={error_code}'
    if next_url and next_url != "/":
        register_url = f"{register_url}&next={next_url}"
    return redirect(register_url)


def logout_action(request):
    if request.method != "POST":
        return redirect("app:home")

    session_token_value = request.session.pop("sidekick_auth_token", None)
    if session_token_value:
        AuthToken.objects.filter(token_value=session_token_value).update(is_revoked=True)
    request.session.pop("sidekick_user_id", None)
    return redirect(sanitize_next_url(request, reverse("app:home")))


def update_profile(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:profile")

    full_name = (request.POST.get("full_name") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    if not full_name or not email:
        messages.error(request, "Full name and email are required.")
        return redirect(f'{reverse("app:profile")}?dialog=edit-profile')
    if User.objects.filter(email=email).exclude(user_id=current_user.user_id).exists():
        messages.error(request, "That email is already registered.")
        return redirect(f'{reverse("app:profile")}?dialog=edit-profile')

    current_user.full_name = full_name
    current_user.email = email
    current_user.updated_at = timezone.now()
    current_user.save(update_fields=["full_name", "email", "updated_at"])
    messages.success(request, "Profile updated.")
    return redirect(reverse("app:profile"))


def change_password(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:profile")

    current_password = request.POST.get("current_password") or ""
    new_password = request.POST.get("new_password") or ""
    confirm_password = request.POST.get("confirm_password") or ""

    if not current_password or not new_password or not confirm_password:
        messages.error(request, "All password fields are required.")
        return redirect(f'{reverse("app:profile")}?dialog=change-password')
    if not check_password(current_password, current_user.password_hash):
        messages.error(request, "Current password is incorrect.")
        return redirect(f'{reverse("app:profile")}?dialog=change-password')
    if new_password != confirm_password:
        messages.error(request, "New password confirmation does not match.")
        return redirect(f'{reverse("app:profile")}?dialog=change-password')

    password_error = password_validation_error(new_password)
    if password_error:
        messages.error(request, password_error)
        return redirect(f'{reverse("app:profile")}?dialog=change-password')

    current_user.password_hash = make_password(new_password)
    current_user.updated_at = timezone.now()
    current_user.save(update_fields=["password_hash", "updated_at"])
    messages.success(request, "Password updated.")
    return redirect(reverse("app:profile"))


def api_register(request):
    if request.method != "POST":
        return json_error("Method not allowed.", status=405, code="method_not_allowed")

    payload = parse_request_data(request)
    if payload is None:
        return json_error("Request body must be valid JSON.", status=400, code="invalid_json")

    full_name = (payload.get("fullName") or payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not full_name or not email or not password:
        return json_error("Full name, email, and password are required.", status=400, code="missing_fields")
    if User.objects.filter(email=email).exists():
        return json_error("That email is already registered.", status=400, code="email_exists")

    password_error = password_validation_error(password)
    if password_error:
        return json_error(password_error, status=400, code="weak_password")

    now = timezone.now()
    user = User.objects.create(
        email=email,
        password_hash=make_password(password),
        full_name=full_name,
        created_at=now,
        updated_at=now,
    )
    auth_token = issue_auth_token(user, client_type=AuthToken.ClientType.WEB)
    return JsonResponse(
        {
            "user": serialize_user_payload(user),
            "token": auth_token.token_value,
            "clientType": auth_token.client_type,
            "issuedAt": auth_token.issued_at.isoformat(),
        },
        status=201,
    )


def api_login(request):
    if request.method != "POST":
        return json_error("Method not allowed.", status=405, code="method_not_allowed")

    payload = parse_request_data(request)
    if payload is None:
        return json_error("Request body must be valid JSON.", status=400, code="invalid_json")

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    client_type = payload.get("clientType") or AuthToken.ClientType.WEB
    valid_client_types = {choice for choice, _ in AuthToken.ClientType.choices}
    if client_type not in valid_client_types:
        client_type = AuthToken.ClientType.WEB

    user = User.objects.filter(email=email).first()
    if user is None or not check_password(password, user.password_hash):
        return json_error("Wrong email or password.", status=401, code="invalid_credentials")

    auth_token = issue_auth_token(user, client_type=client_type)
    return JsonResponse(
        {
            "user": serialize_user_payload(user),
            "token": auth_token.token_value,
            "clientType": auth_token.client_type,
            "issuedAt": auth_token.issued_at.isoformat(),
        }
    )


def api_logout(request):
    if request.method != "POST":
        return json_error("Method not allowed.", status=405, code="method_not_allowed")

    current_user, auth_token, error_response = require_api_token(request)
    if error_response:
        return error_response

    auth_token.is_revoked = True
    auth_token.save(update_fields=["is_revoked"])
    if request.session.get("sidekick_user_id") == current_user.user_id:
        request.session.pop("sidekick_user_id", None)
        request.session.pop("sidekick_auth_token", None)
    return JsonResponse({}, status=204)


def api_me(request):
    current_user, auth_token, error_response = require_api_token(request)
    if error_response:
        return error_response

    if request.method == "PATCH":
        payload = parse_request_data(request)
        if payload is None:
            return json_error("Request body must be valid JSON.", status=400, code="invalid_json")

        full_name = (payload.get("fullName") or payload.get("name") or "").strip()
        email = (payload.get("email") or "").strip().lower()
        if not full_name or not email:
            return json_error("Full name and email are required.", status=400, code="missing_fields")
        if User.objects.filter(email=email).exclude(user_id=current_user.user_id).exists():
            return json_error("That email is already registered.", status=400, code="email_exists")

        current_user.full_name = full_name
        current_user.email = email
        current_user.updated_at = timezone.now()
        current_user.save(update_fields=["full_name", "email", "updated_at"])
        return JsonResponse({"user": serialize_user_payload(current_user)})

    if request.method != "GET":
        return json_error("Method not allowed.", status=405, code="method_not_allowed")

    return JsonResponse(
        {
            "user": serialize_user_payload(current_user),
            "token": {
                "value": auth_token.token_value,
                "clientType": auth_token.client_type,
                "issuedAt": auth_token.issued_at.isoformat(),
                "expiresAt": auth_token.expires_at.isoformat() if auth_token.expires_at else None,
            },
        }
    )


def api_change_password(request):
    if request.method != "POST":
        return json_error("Method not allowed.", status=405, code="method_not_allowed")

    current_user, _auth_token, error_response = require_api_token(request)
    if error_response:
        return error_response

    payload = parse_request_data(request)
    if payload is None:
        return json_error("Request body must be valid JSON.", status=400, code="invalid_json")

    current_password = payload.get("currentPassword") or payload.get("current_password") or ""
    new_password = payload.get("newPassword") or payload.get("new_password") or ""
    confirm_password = payload.get("confirmPassword") or payload.get("confirm_password") or ""

    if not current_password or not new_password or not confirm_password:
        return json_error("All password fields are required.", status=400, code="missing_fields")
    if not check_password(current_password, current_user.password_hash):
        return json_error("Current password is incorrect.", status=400, code="current_password_incorrect")
    if new_password != confirm_password:
        return json_error("New password confirmation does not match.", status=400, code="password_mismatch")
    password_error = password_validation_error(new_password)
    if password_error:
        return json_error(password_error, status=400, code="weak_password")

    current_user.password_hash = make_password(new_password)
    current_user.updated_at = timezone.now()
    current_user.save(update_fields=["password_hash", "updated_at"])
    return JsonResponse({"status": "ok"})


def api_spaces(request):
    current_user, _auth_token, error_response = require_api_token(request)
    if error_response:
        return error_response

    if request.method == "GET":
        active_filter = request.GET.get("filter", "All")
        spaces = [
            serialize_space_payload(space, current_user)
            for space in filter_spaces(active_filter, current_user)
        ]
        return JsonResponse({"spaces": spaces})

    if request.method == "POST":
        payload = parse_request_data(request)
        if payload is None:
            return json_error("Request body must be valid JSON.", status=400, code="invalid_json")
        name = (payload.get("name") or "").strip()
        description = (payload.get("description") or "").strip()
        if not name:
            return json_error("Space name is required.", status=400, code="missing_name")

        now = timezone.now()
        space = ResearchSpace.objects.create(
            owner=current_user,
            name=name,
            description=description,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        return JsonResponse({"space": serialize_space_payload(space, current_user)}, status=201)

    return json_error("Method not allowed.", status=405, code="method_not_allowed")


def api_space_detail(request, space_id):
    current_user, _auth_token, error_response = require_api_token(request)
    if error_response:
        return error_response

    space = get_space(space_id, current_user)
    if space is None:
        return json_error("Space not found.", status=404, code="space_not_found")

    if request.method == "GET":
        return JsonResponse({"space": serialize_space_payload(space, current_user)})

    if request.method == "PATCH":
        if not is_owner(space, current_user):
            return json_error("Only the owner can update this space.", status=403, code="forbidden")
        payload = parse_request_data(request)
        if payload is None:
            return json_error("Request body must be valid JSON.", status=400, code="invalid_json")
        name = payload.get("name")
        description = payload.get("description")
        update_fields = ["updated_at"]
        if name is not None:
            name = name.strip()
            if not name:
                return json_error("Space name is required.", status=400, code="missing_name")
            space.name = name
            update_fields.append("name")
        if description is not None:
            space.description = description.strip()
            update_fields.append("description")
        space.updated_at = timezone.now()
        space.save(update_fields=update_fields)
        return JsonResponse({"space": serialize_space_payload(space, current_user)})

    if request.method == "DELETE":
        if not is_owner(space, current_user):
            return json_error("Only the owner can delete this space.", status=403, code="forbidden")
        space.delete()
        return JsonResponse({}, status=204)

    return json_error("Method not allowed.", status=405, code="method_not_allowed")


def api_space_items(request, space_id):
    current_user, _auth_token, error_response = require_api_token(request)
    if error_response:
        return error_response

    space = get_space(space_id, current_user)
    if space is None:
        return json_error("Space not found.", status=404, code="space_not_found")

    if request.method != "GET":
        return json_error("Method not allowed.", status=405, code="method_not_allowed")

    items = get_space_items(space)
    item_type = request.GET.get("type")
    added_by = request.GET.get("added_by")
    since = request.GET.get("since")
    if item_type:
        items = items.filter(item_type=item_type.lower())
    if added_by:
        items = items.filter(added_by_id=added_by)
    if since:
        try:
            since_dt = timezone.datetime.fromisoformat(since.replace("Z", "+00:00"))
            if timezone.is_naive(since_dt):
                since_dt = timezone.make_aware(since_dt, timezone.utc)
            items = items.filter(created_at__gt=since_dt)
        except ValueError:
            return json_error("The since parameter must be a valid ISO timestamp.", status=400, code="invalid_since")

    return JsonResponse({"items": [serialize_item_payload(item) for item in items]})


def api_space_share_link(request, space_id):
    current_user, _auth_token, error_response = require_api_token(request)
    if error_response:
        return error_response

    space = get_space(space_id, current_user)
    if space is None:
        return json_error("Space not found.", status=404, code="space_not_found")
    if not is_owner(space, current_user):
        return json_error("Only the owner can manage share links.", status=403, code="forbidden")

    if request.method == "POST":
        share_link = active_share_link(space)
        now = timezone.now()
        if share_link is None:
            share_link = ShareLink.objects.create(
                space=space,
                created_by=current_user,
                token=secrets.token_urlsafe(18),
                created_at=now,
                expires_at=None,
                is_active=True,
            )
        return JsonResponse(
            {
                "shareLink": {
                    "id": share_link.share_link_id,
                    "token": share_link.token,
                    "url": request.build_absolute_uri(
                        reverse("app:share_link_access", args=[share_link.token])
                    ),
                    "isActive": share_link.is_active,
                    "createdAt": share_link.created_at.isoformat(),
                    "expiresAt": share_link.expires_at.isoformat() if share_link.expires_at else None,
                }
            },
            status=201,
        )

    if request.method == "DELETE":
        revoked_count = revoke_space_share_links(space)
        return JsonResponse({"revokedLinks": revoked_count}, status=200)

    return json_error("Method not allowed.", status=405, code="method_not_allowed")


def api_create_item(request):
    if request.method != "POST":
        return json_error("Method not allowed.", status=405, code="method_not_allowed")

    current_user, _auth_token, error_response = require_api_token(request)
    if error_response:
        return error_response

    payload = parse_request_data(request)
    if payload is None:
        return json_error("Request body must be valid JSON.", status=400, code="invalid_json")

    space_id = payload.get("spaceId") or payload.get("space_id")
    space = get_space(space_id, current_user)
    if space is None:
        return json_error("Space not found.", status=404, code="space_not_found")
    if not can_add_items(space, current_user):
        return json_error("You do not have permission to add items here.", status=403, code="forbidden")

    item, error_message, error_code = create_item_record(
        current_user=current_user,
        space=space,
        item_type=payload.get("type") or payload.get("item_type") or Item.ItemType.TEXT,
        content_text=payload.get("content") or payload.get("content_text") or "",
        source_url=payload.get("sourceUrl")
        or payload.get("source_url")
        or payload.get("imageSourceUrl")
        or payload.get("image_source_url")
        or "",
        note=payload.get("note") or "",
        title=payload.get("title") or "",
        uploaded_image=request.FILES.get("image_file"),
    )
    if error_message:
        return json_error(error_message, status=400, code=error_code)

    return JsonResponse({"item": serialize_item_payload(item)}, status=201)


def api_delete_item(request, item_id):
    if request.method != "DELETE":
        return json_error("Method not allowed.", status=405, code="method_not_allowed")

    current_user, _auth_token, error_response = require_api_token(request)
    if error_response:
        return error_response

    item = Item.objects.select_related("space", "added_by").filter(item_id=item_id).first()
    if item is None:
        return json_error("Item not found.", status=404, code="item_not_found")
    if not can_delete_item_record(item, current_user):
        return json_error("You do not have permission to delete this item.", status=403, code="forbidden")

    item.delete()
    return JsonResponse({}, status=204)


def create_space(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    name = (request.POST.get("name") or "").strip()
    description = (request.POST.get("description") or "").strip()
    if not name:
        return redirect(f'{reverse("app:home")}?dialog=create-space')

    now = timezone.now()
    space = ResearchSpace.objects.create(
        owner=current_user,
        name=name,
        description=description,
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    return redirect(reverse("app:space_detail", args=[space.space_id]))


def update_space(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    space = get_space(request.POST.get("space_id"), current_user)
    if space is None or not is_owner(space, current_user):
        return redirect("app:home")

    name = (request.POST.get("name") or "").strip()
    description = (request.POST.get("description") or "").strip()
    if not name:
        messages.error(request, "Space name is required.")
        return redirect(f'{reverse("app:space_detail", args=[space.space_id])}?dialog=edit-space')

    space.name = name
    space.description = description
    space.updated_at = timezone.now()
    space.save(update_fields=["name", "description", "updated_at"])
    messages.success(request, "Space updated.")
    return redirect(reverse("app:space_detail", args=[space.space_id]))


def create_item(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")
    is_ajax_request = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    space_id = request.POST.get("space_id")
    space = get_space(space_id, current_user)
    if space is None or not can_add_items(space, current_user):
        if is_ajax_request:
            return json_error("You do not have permission to add items here.", status=403, code="forbidden")
        return redirect("app:home")

    item_type = request.POST.get("item_type") or Item.ItemType.TEXT
    link_title = (request.POST.get("link_title") or "").strip()
    image_title = (request.POST.get("image_title") or "").strip()
    note = (request.POST.get("note") or "").strip()
    content_text = (request.POST.get("content_text") or "").strip()
    source_url = (request.POST.get("source_url") or "").strip()
    image_source_url = (request.POST.get("image_source_url") or "").strip()
    title = link_title if item_type == Item.ItemType.LINK else image_title

    _item, error_message, _error_code = create_item_record(
        current_user=current_user,
        space=space,
        item_type=item_type,
        content_text=content_text,
        source_url=image_source_url if item_type == Item.ItemType.IMAGE else source_url,
        note=note,
        title=title,
        uploaded_image=request.FILES.get("image_file"),
    )
    if error_message:
        if is_ajax_request:
            return json_error(error_message, status=400, code="invalid_item")
        messages.error(request, error_message)
        return redirect(f'{reverse("app:space_detail", args=[space.space_id])}?dialog=add-item')

    if is_ajax_request:
        return JsonResponse({"status": "ok"}, status=201)
    messages.success(request, "Item saved.")
    return redirect(reverse("app:space_detail", args=[space.space_id]))


def delete_item(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    item_id = request.POST.get("item_id")
    item = (
        Item.objects.select_related("space")
        .filter(item_id=item_id)
        .first()
    )
    if item is None:
        return redirect("app:home")
    if not can_delete_item_record(item, current_user):
        return redirect("app:home")

    space_id = item.space.space_id
    item.delete()
    return redirect(reverse("app:space_detail", args=[space_id]))


def invite_member(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    space = get_space(request.POST.get("space_id"), current_user)
    if space is None or not can_manage_members(space, current_user):
        return set_flash_and_redirect(request, "error", "Only the owner can invite people to this space.", reverse("app:home"))

    email = (request.POST.get("email") or "").strip().lower()
    role = request.POST.get("role") or Membership.Role.COLLABORATOR
    valid_roles = {Membership.Role.COLLABORATOR, Membership.Role.VIEWER}
    if role not in valid_roles:
        return set_flash_and_redirect(
            request,
            "error",
            "Choose a valid role for the invited member.",
            f'{reverse("app:space_detail", args=[space.space_id])}?modal=team&dialog=invite-member',
        )
    user = User.objects.filter(email=email).first()
    if user is None:
        return set_flash_and_redirect(
            request,
            "error",
            "That user does not exist yet. Ask them to register first.",
            f'{reverse("app:space_detail", args=[space.space_id])}?modal=team&dialog=invite-member',
        )
    if user.user_id == space.owner_id:
        return set_flash_and_redirect(
            request,
            "info",
            "The owner is already part of this space.",
            f'{reverse("app:space_detail", args=[space.space_id])}?modal=team',
        )

    now = timezone.now()
    membership, created = Membership.objects.get_or_create(
        space=space,
        user=user,
        defaults={
            "joined_via": None,
            "role": role,
            "status": Membership.Status.ACTIVE,
            "created_at": now,
            "updated_at": now,
        },
    )
    if not created:
        membership.joined_via = None
        membership.role = role
        membership.status = Membership.Status.ACTIVE
        membership.updated_at = now
        membership.save(update_fields=["joined_via", "role", "status", "updated_at"])

    CollaborationRequest.objects.filter(
        space=space,
        requester=user,
        status=CollaborationRequest.Status.PENDING,
    ).update(
        status=CollaborationRequest.Status.APPROVED,
        resolved_by=current_user,
        resolved_at=now,
    )

    return set_flash_and_redirect(
        request,
        "success",
        f"{user.full_name} now has {role} access to this space.",
        f'{reverse("app:space_detail", args=[space.space_id])}?modal=team',
    )


def remove_member(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    space = get_space(request.POST.get("space_id"), current_user)
    if space is None or not can_manage_members(space, current_user):
        return set_flash_and_redirect(request, "error", "Only the owner can remove members from this space.", reverse("app:home"))

    membership = Membership.objects.filter(
        space=space,
        membership_id=request.POST.get("member_id"),
        status=Membership.Status.ACTIVE,
    ).first()
    if membership is not None:
        membership.status = Membership.Status.REMOVED
        membership.updated_at = timezone.now()
        membership.save(update_fields=["status", "updated_at"])
        return set_flash_and_redirect(
            request,
            "success",
            f"{membership.user.full_name} was removed from the space.",
            f'{reverse("app:space_detail", args=[space.space_id])}?modal=team',
        )

    return set_flash_and_redirect(
        request,
        "info",
        "That member no longer has active access.",
        f'{reverse("app:space_detail", args=[space.space_id])}?modal=team',
    )


def review_request(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    collab_request = CollaborationRequest.objects.select_related("space", "requester").filter(
        request_id=request.POST.get("request_id")
    ).first()
    if collab_request is None or not can_manage_members(collab_request.space, current_user):
        return set_flash_and_redirect(request, "error", "Only the owner can review collaboration requests.", reverse("app:home"))

    if collab_request.status != CollaborationRequest.Status.PENDING:
        return set_flash_and_redirect(
            request,
            "info",
            "That request has already been reviewed.",
            f'{reverse("app:space_detail", args=[collab_request.space.space_id])}?modal=team',
        )

    now = timezone.now()
    decision = request.POST.get("decision")
    if decision == "approve":
        membership, created = Membership.objects.get_or_create(
            space=collab_request.space,
            user=collab_request.requester,
            defaults={
                "joined_via": None,
                "role": Membership.Role.COLLABORATOR,
                "status": Membership.Status.ACTIVE,
                "created_at": now,
                "updated_at": now,
            },
        )
        if not created:
            membership.joined_via = None
            membership.role = Membership.Role.COLLABORATOR
            membership.status = Membership.Status.ACTIVE
            membership.updated_at = now
            membership.save(update_fields=["joined_via", "role", "status", "updated_at"])
        collab_request.status = CollaborationRequest.Status.APPROVED
        flash_message = f"{collab_request.requester.full_name} is now a collaborator."
    elif decision == "reject":
        collab_request.status = CollaborationRequest.Status.REJECTED
        flash_message = f"{collab_request.requester.full_name}'s request was rejected."
    else:
        return set_flash_and_redirect(
            request,
            "error",
            "Choose a valid review action.",
            f'{reverse("app:space_detail", args=[collab_request.space.space_id])}?modal=team',
        )

    collab_request.resolved_by = current_user
    collab_request.resolved_at = now
    collab_request.save(update_fields=["status", "resolved_by", "resolved_at"])
    return set_flash_and_redirect(
        request,
        "success",
        flash_message,
        f'{reverse("app:space_detail", args=[collab_request.space.space_id])}?modal=team',
    )


def create_share_link(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    space = get_space(request.POST.get("space_id"), current_user)
    if space is None or not can_manage_members(space, current_user):
        return set_flash_and_redirect(request, "error", "Only the owner can create share links.", reverse("app:home"))

    share_link = active_share_link(space)
    now = timezone.now()
    if share_link is None:
        share_link = ShareLink.objects.create(
            space=space,
            created_by=current_user,
            token=secrets.token_urlsafe(18),
            created_at=now,
            expires_at=None,
            is_active=True,
        )

    share_url = request.build_absolute_uri(reverse("app:share_link_access", args=[share_link.token]))
    return redirect(
        f"{reverse('app:space_detail', args=[space.space_id])}?{urlencode({'dialog': 'share-link', 'share_url': share_url})}"
    )


def revoke_share_link(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    space = get_space(request.POST.get("space_id"), current_user)
    if space is None or not can_manage_members(space, current_user):
        return set_flash_and_redirect(request, "error", "Only the owner can revoke share links.", reverse("app:home"))

    revoked_count = revoke_space_share_links(space)
    if revoked_count == 0:
        return set_flash_and_redirect(
            request,
            "info",
            "There is no active share link to revoke.",
            reverse("app:space_detail", args=[space.space_id]),
        )
    return set_flash_and_redirect(
        request,
        "success",
        "Share link revoked and viewer access removed.",
        reverse("app:space_detail", args=[space.space_id]),
    )


def share_link_access(request, token):
    share_link = ShareLink.objects.select_related("space", "created_by").filter(
        token=token,
        is_active=True,
    ).first()
    if share_link is None:
        raise Http404("Share link not found")
    if share_link.expires_at and share_link.expires_at <= timezone.now():
        raise Http404("Share link expired")

    current_user = get_current_user(request)
    if current_user is None:
        login_url = f"{reverse('app:home')}?mock=login&next={reverse('app:share_link_access', args=[token])}"
        return redirect(login_url)

    space = get_space(share_link.space.space_id, current_user)
    if space is not None:
        return redirect(reverse("app:space_detail", args=[share_link.space.space_id]))

    existing_request = (
        CollaborationRequest.objects.filter(
            space=share_link.space,
            requester=current_user,
        )
        .order_by("-requested_at", "-request_id")
        .first()
    )
    serialized_existing_request = None
    if existing_request is not None:
        serialized_existing_request = {
            "status": existing_request.status.capitalize(),
            "note": existing_request.message or "Your request is recorded in SideKick.",
        }
    context = base_context(request, title=share_link.space.name)
    context.update(
        {
            "space": share_link.space,
            "join_url": reverse("app:join_shared_space", args=[token]),
            "request_url": reverse("app:request_shared_space_access", args=[token]),
            "existing_request": serialized_existing_request,
        }
    )
    return render(request, "app/share_link_access.html", context)


def join_shared_space(request, token):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    share_link = ShareLink.objects.select_related("space").filter(token=token, is_active=True).first()
    if share_link is None:
        raise Http404("Share link not found")

    if share_link.space.owner_id == current_user.user_id:
        return set_flash_and_redirect(
            request,
            "info",
            "You already own this space.",
            reverse("app:space_detail", args=[share_link.space.space_id]),
        )

    current_membership = get_membership(share_link.space, current_user)
    if current_membership is not None:
        return set_flash_and_redirect(
            request,
            "info",
            "You already have access to this space.",
            reverse("app:space_detail", args=[share_link.space.space_id]),
        )

    now = timezone.now()
    membership, created = Membership.objects.get_or_create(
        space=share_link.space,
        user=current_user,
        defaults={
            "joined_via": share_link,
            "role": Membership.Role.VIEWER,
            "status": Membership.Status.ACTIVE,
            "created_at": now,
            "updated_at": now,
        },
    )
    if not created:
        membership.joined_via = share_link
        membership.role = Membership.Role.VIEWER
        membership.status = Membership.Status.ACTIVE
        membership.updated_at = now
        membership.save(update_fields=["joined_via", "role", "status", "updated_at"])

    return set_flash_and_redirect(
        request,
        "success",
        "You joined the space as a viewer.",
        reverse("app:space_detail", args=[share_link.space.space_id]),
    )


def request_shared_space_access(request, token):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    share_link = ShareLink.objects.select_related("space").filter(token=token, is_active=True).first()
    if share_link is None:
        raise Http404("Share link not found")

    if share_link.space.owner_id == current_user.user_id or get_membership(share_link.space, current_user):
        messages.info(request, "You already have access to this space.")
        return redirect(reverse("app:share_link_access", args=[token]))

    _, level, message = create_collaboration_request(
        space=share_link.space,
        requester=current_user,
        message="Requested collaborator access from shared link.",
    )
    getattr(messages, level)(request, message)

    return redirect(reverse("app:share_link_access", args=[token]))


def request_space_collaboration(request, space_id):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    space = get_space(space_id, current_user)
    if space is None:
        raise Http404("Space not found")

    fallback = f'{reverse("app:space_detail", args=[space.space_id])}?modal=team'
    next_url = sanitize_next_url(request, fallback)

    if is_owner(space, current_user):
        return set_flash_and_redirect(request, "info", "You already own this space.", next_url)

    membership = get_membership(space, current_user)
    if membership is None:
        return set_flash_and_redirect(
            request,
            "error",
            "You need viewer access before requesting collaborator access.",
            next_url,
        )
    if membership.role != Membership.Role.VIEWER:
        return set_flash_and_redirect(
            request,
            "info",
            "You already have collaborator access to this space.",
            next_url,
        )

    _, level, message = create_collaboration_request(
        space=space,
        requester=current_user,
        message="Requested collaborator access from the Team panel.",
    )
    return set_flash_and_redirect(request, level, message, next_url)


def delete_space(request):
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect("app:home")

    space = get_space(request.POST.get("space_id"), current_user)
    if space is None or not is_owner(space, current_user):
        return redirect("app:home")

    space.delete()
    return redirect(reverse("app:home"))
