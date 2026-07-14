# Autor: Luka Jankovic, 704/19
"""Kontroleri i pomoćne funkcije za prikaz, autentikaciju i API sloj aplikacije SideKick."""

import json
import re
import secrets
from html import unescape
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
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
    get_or_create_universal_space,
    get_collaboration_requests,
    get_current_user,
    get_membership,
    get_profile_user,
    get_request_auth_token_value,
    get_recent_items_for_user,
    get_space_collaborators,
    get_space_items,
    get_space,
    get_user_profile_summary,
    is_extension_request,
    is_universal_space,
    item_user_filters,
    serialize_item,
    serialize_space,
)
from .models import AuthToken, CollaborationRequest, Item, Membership, ResearchSpace, ShareLink, User
from .realtime import emit_space_item_created, emit_space_item_moved, emit_space_item_removed


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
    """Vraća JSON odgovor sa standardizovanom strukturom greške."""
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


def parse_request_data(request):
    """Vraća podatke iz zahteva kao rečnik ili QueryDict, odnosno `None` za neispravan JSON."""
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return None
    if request.method in {"POST", "PATCH", "DELETE"}:
        return request.POST
    return request.GET


def password_validation_error(password):
    """Vraća poruku o grešci za lozinku ili `None` kada lozinka prolazi sve provere."""
    for validator, message in PASSWORD_VALIDATORS:
        if not validator(password):
            return message
    return None


def fetch_html_document(url):
    """Vraća HTML sadržaj prosleđene adrese ili prazan string ako čitanje ne uspe."""
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
            return response.read(200000).decode("utf-8", errors="ignore")
    except (ValueError, URLError, TimeoutError):
        return ""


def clean_metadata_title(value):
    """Vraća očišćen i skraćen naslov izdvojen iz metapodataka stranice."""
    title = unescape(re.sub(r"\s+", " ", value or "")).strip()
    if not title:
        return ""
    return title[:255]


def title_looks_like_url(title):
    """Vraća informaciju da li naslov zapravo liči na sirovi URL umesto na pravi naziv."""
    if not title:
        return True
    normalized = title.strip().lower()
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return True
    if "/" in normalized and "." in normalized and " " not in normalized:
        return True
    return False


def extract_title_from_html(html):
    """Vraća najrelevantniji naslov izdvojen iz HTML dokumenta."""
    if not html:
        return ""

    metadata_patterns = [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:title["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']twitter:title["\']',
        r'<meta[^>]+itemprop=["\']headline["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+itemprop=["\']headline["\']',
        r'<meta[^>]+name=["\']title["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']title["\']',
        r"<title[^>]*>(.*?)</title>",
    ]
    for pattern in metadata_patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        title = clean_metadata_title(match.group(1))
        if title and not title_looks_like_url(title):
            return title

    json_ld_matches = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    for block in json_ld_matches:
        try:
            payload = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        title = extract_title_from_json_ld(payload)
        if title:
            return title

    return ""


def extract_title_from_json_ld(payload):
    """Vraća naslov pronađen u JSON-LD strukturi ili prazan string ako ga nema."""
    if isinstance(payload, list):
        for item in payload:
            title = extract_title_from_json_ld(item)
            if title:
                return title
        return ""

    if not isinstance(payload, dict):
        return ""

    for key in ("headline", "name", "title"):
        value = payload.get(key)
        if isinstance(value, str):
            title = clean_metadata_title(value)
            if title and not title_looks_like_url(title):
                return title

    for key in ("@graph", "mainEntity", "itemListElement"):
        nested = payload.get(key)
        title = extract_title_from_json_ld(nested)
        if title:
            return title

    return ""


def read_url_title(url):
    """Vraća naslov stranice dobijen iz HTML sadržaja zadatog URL-a."""
    html = fetch_html_document(url)
    return extract_title_from_html(html)


GENERIC_LINK_PATH_SEGMENTS = {
    "article",
    "articles",
    "blog",
    "category",
    "clanak",
    "clanci",
    "news",
    "objava",
    "post",
    "posts",
    "region",
    "story",
    "stories",
    "tekst",
    "vest",
    "vesti",
    "video",
    "videos",
    "world",
}


def normalize_path_segment_title(segment):
    """Vraća čitljiv tekst dobijen iz jednog segmenta putanje URL-a."""
    candidate = re.sub(r"\.[A-Za-z0-9]+$", "", segment or "")
    candidate = re.sub(r"[-_]+", " ", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip()
    return candidate


def title_from_url_path(url):
    """Vraća heuristički naslov izveden iz putanje URL-a."""
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        return ""

    ranked_candidates = []
    for index, segment in enumerate(path_parts):
        candidate = normalize_path_segment_title(segment)
        if not candidate or len(candidate) < 4:
            continue
        if re.fullmatch(r"[0-9]+", candidate):
            continue
        if candidate.lower() in GENERIC_LINK_PATH_SEGMENTS:
            continue
        score = (
            len(candidate.split()),
            len(candidate),
            index,
        )
        ranked_candidates.append((score, candidate))

    if ranked_candidates:
        best_candidate = max(ranked_candidates, key=lambda item: item[0])[1]
        return best_candidate.title()[:255]

    fallback_candidates = []
    for index, segment in enumerate(path_parts):
        candidate = normalize_path_segment_title(segment)
        if not candidate or len(candidate) < 4:
            continue
        if re.fullmatch(r"[0-9]+", candidate):
            continue
        fallback_candidates.append(((len(candidate), index), candidate))

    if not fallback_candidates:
        return ""

    best_candidate = max(fallback_candidates, key=lambda item: item[0])[1]
    return best_candidate.title()[:255]


def title_from_domain(url):
    """Vraća naslov izveden iz domena kada bolji naslov nije dostupan."""
    hostname = (urlparse(url).hostname or "").lower().replace("www.", "")
    if not hostname:
        return ""
    return hostname[:255]


def fallback_link_title(url):
    """Vraća rezervni naslov linka izveden iz putanje ili domena."""
    return title_from_url_path(url) or title_from_domain(url)


def oembed_endpoint_for_url(url):
    """Vraća oEmbed endpoint za podržane servise ili prazan string kada ne postoji."""
    hostname = (urlparse(url).hostname or "").lower()
    if hostname in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        return f"https://www.youtube.com/oembed?{urlencode({'url': url, 'format': 'json'})}"
    if hostname in {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}:
        return f"https://vimeo.com/api/oembed.json?{urlencode({'url': url})}"
    return ""


def read_url_metadata(url):
    """Vraća metapodatke o linku, prvenstveno naslov, koristeći oEmbed ili HTML parsiranje."""
    endpoint = oembed_endpoint_for_url(url)
    if endpoint:
        try:
            request = Request(
                endpoint,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; SideKick/1.0)",
                    "Accept": "application/json",
                },
            )
            with urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            title = (payload.get("title") or "").strip()
            if title:
                return {"title": title[:255]}
        except (ValueError, URLError, TimeoutError, json.JSONDecodeError):
            pass

    title = read_url_title(url)
    if title:
        return {"title": title[:255]}

    fallback_title = fallback_link_title(url)
    return {"title": fallback_title} if fallback_title else {}


def normalized_url(value):
    """Vraća normalizovan URL sa šemom kada je to moguće."""
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
    """Vraća informaciju da li prosleđena vrednost predstavlja pun apsolutni URL."""
    parsed = urlparse(value or "")
    return bool(parsed.scheme and parsed.netloc)


def issue_auth_token(user, *, client_type=AuthToken.ClientType.WEB):
    """Kreira i vraća novi autentikacioni token za korisnika."""
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
    """Vraća korisnika serijalizovanog u oblik pogodан za API odgovor."""
    return {
        "id": user.user_id,
        "email": user.email,
        "fullName": user.full_name,
        "createdAt": user.created_at.isoformat(),
        "updatedAt": user.updated_at.isoformat(),
    }


def serialize_space_payload(space, current_user):
    """Vraća prostor serijalizovan za API, zajedno sa ulogom tekućeg korisnika."""
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
    """Vraća stavku serijalizovanu za API odgovor."""
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
    """Vraća vrednost tokena iz Authorization zaglavlja ili `None` ako ne postoji."""
    header = request.headers.get("Authorization", "").strip()
    if not header:
        return None
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() not in {"token", "bearer"}:
        return None
    return parts[1]


def require_api_token(request):
    """Vraća korisnika, token i eventualni JSON odgovor o grešci za API autentikaciju."""
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
    """Smešta otpremljenu sliku i vraća njenu javnu putanju."""
    safe_name = slugify(uploaded_image.name.rsplit(".", 1)[0]) or "image"
    extension = uploaded_image.name.rsplit(".", 1)[-1].lower() if "." in uploaded_image.name else "bin"
    stored_path = default_storage.save(
        f"uploads/user_{current_user.user_id}/{timezone.now().strftime('%Y%m%d%H%M%S')}_{safe_name}.{extension}",
        uploaded_image,
    )
    return default_storage.url(stored_path)


def save_uploaded_avatar(uploaded_image, current_user):
    """Smešta otpremljeni avatar i vraća njegovu javnu putanju."""
    safe_name = slugify(uploaded_image.name.rsplit(".", 1)[0]) or "avatar"
    extension = uploaded_image.name.rsplit(".", 1)[-1].lower() if "." in uploaded_image.name else "bin"
    stored_path = default_storage.save(
        f"uploads/user_{current_user.user_id}/avatars/{timezone.now().strftime('%Y%m%d%H%M%S')}_{safe_name}.{extension}",
        uploaded_image,
    )
    return default_storage.url(stored_path)


def create_item_record(*, current_user, space, item_type, content_text="", source_url="", title="", uploaded_image=None):
    """Kreira novu stavku i vraća torku `(stavka, poruka_greške, kod_greške)`."""
    item_type = (item_type or Item.ItemType.TEXT).lower()
    valid_item_types = {choice for choice, _ in Item.ItemType.choices}
    if item_type not in valid_item_types:
        return None, "Unsupported item type.", "invalid_type"

    content_text = (content_text or "").strip()
    source_url = normalized_url(source_url)
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
        if not title or title_looks_like_url(title) or title.lower() == title_from_domain(source_url).lower():
            metadata = read_url_metadata(source_url)
            title = metadata.get("title", "")
        page_title = title or fallback_link_title(source_url)
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
        note="",
        source_platform=Item.SourcePlatform.WEB,
        captured_url=captured_url,
        page_title=page_title,
        created_at=now,
        updated_at=now,
    )
    space.updated_at = now
    space.save(update_fields=["updated_at"])
    return Item.objects.select_related("space", "added_by").get(item_id=item.item_id), None, None


def sanitize_next_url(request, fallback):
    """Vraća bezbednu internu povratnu adresu ili zadati podrazumevani URL."""
    next_url = request.POST.get("next_url") or request.GET.get("next") or fallback
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return fallback


def require_current_user(request):
    """Vraća prijavljenog korisnika i eventualni redirect odgovor kada korisnik nije prijavljen."""
    current_user = get_current_user(request)
    if current_user is None:
        return None, redirect(reverse("app:home"))
    return current_user, None


def is_owner(space, current_user):
    """Vraća informaciju da li je prosleđeni korisnik vlasnik prostora."""
    return current_user is not None and space.owner_id == current_user.user_id


def active_membership(space, current_user):
    """Vraća aktivno članstvo korisnika u prostoru ili `None` ako ne postoji."""
    return get_membership(space, current_user)


def membership_role(space, current_user):
    """Vraća ulogu korisnika u prostoru ili `None` ako korisnik nema članstvo."""
    membership = active_membership(space, current_user)
    return membership.role if membership else None


def can_add_items(space, current_user):
    """Vraća informaciju da li korisnik sme da dodaje stavke u dati prostor."""
    if is_owner(space, current_user):
        return True
    return membership_role(space, current_user) == Membership.Role.COLLABORATOR


def can_move_item_record(item, current_user, target_space):
    """Vraća informaciju da li korisnik sme da premesti stavku u ciljni prostor."""
    if item is None or target_space is None:
        return False
    if is_universal_space(item.space):
        return (
            item.space.owner_id == current_user.user_id
            and item.added_by_id == current_user.user_id
            and can_add_items(target_space, current_user)
        )
    if not can_add_items(target_space, current_user):
        return False
    return can_delete_item_record(item, current_user)


def can_delete_item_record(item, current_user):
    """Vraća informaciju da li korisnik sme da obriše prosleđenu stavku."""
    if is_owner(item.space, current_user):
        return True
    role = membership_role(item.space, current_user)
    if role != Membership.Role.COLLABORATOR:
        return False
    return item.added_by_id == current_user.user_id


def can_manage_members(space, current_user):
    """Vraća informaciju da li korisnik sme da upravlja članovima prostora."""
    return is_owner(space, current_user)


def active_share_link(space):
    """Vraća trenutno aktivan deljeni link prostora ili `None` ako ne postoji."""
    now = timezone.now()
    return (
        ShareLink.objects.filter(space=space, is_active=True)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .order_by("-created_at", "-share_link_id")
        .first()
    )


def latest_collaboration_request(space, user):
    """Vraća poslednji zahtev za saradnju korisnika u prostoru ili `None`."""
    if space is None or user is None:
        return None
    return (
        CollaborationRequest.objects.filter(space=space, requester=user)
        .order_by("-requested_at", "-request_id")
        .first()
    )


def create_collaboration_request(*, space, requester, message):
    """Kreira zahtev za saradnju i vraća torku `(zahtev, nivo_poruke, poruka)`."""
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
    """Vraća stanje zahteva za saradnju serijalizovano za prikaz u interfejsu."""
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
    """Deaktivira sve aktivne deljene linkove prostora i vraća njihov broj."""
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
    """Postavlja flash poruku i vraća redirect odgovor ka ciljnoj adresi."""
    getattr(messages, level)(request, message)
    return redirect(append_request_auth(target, request))


def append_request_auth(target, request):
    """Vraća URL dopunjen tokenom iz zahteva kada je aplikacija u extension režimu."""
    if not is_extension_request(request) or not isinstance(target, str) or not target.startswith("/"):
        return target

    auth_token_value = get_request_auth_token_value(request)
    if not auth_token_value:
        return target

    parsed = urlparse(target)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.pop("auth_token", None)
    query["authToken"] = auth_token_value
    updated_query = urlencode(query)
    return urlunparse(parsed._replace(query=updated_query))


def redirect_with_request_auth(request, target):
    """Vraća redirect odgovor ka URL-u dopunjenom autentikacionim tokenom po potrebi."""
    return redirect(append_request_auth(target, request))


def url_with_query(request, **updates):
    """Vraća trenutni URL sa ažuriranim query parametrima."""
    query = request.GET.copy()
    if not is_extension_request(request):
        query.pop("authToken", None)
        query.pop("auth_token", None)
    else:
        auth_token_value = get_request_auth_token_value(request)
        if auth_token_value:
            query["authToken"] = auth_token_value
        query.pop("auth_token", None)
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
    """Vraća listu linkova za filtere sa informacijom koji filter je aktivan."""
    return [
        {
            "label": label,
            "is_active": label == active_filter,
            "url": url_with_query(request, **{query_key: None if label == "All" else label}),
        }
        for label in filters
    ]


def decorate_items(request, items):
    """Vraća listu stavki obogaćenu URL-ovima za pregled pojedinačne stavke."""
    decorated = []
    for item in items:
        decorated.append(
            {
                **item,
                "preview_url": url_with_query(request, preview=item["id"]),
            }
        )
    return decorated


def decorate_item_for_request(request, item, *, can_delete=False, can_drag=False):
    """Vraća serijalizovanu stavku obogaćenu URL-ovima i dozvolama za prikaz."""
    serialized = serialize_item(item)
    serialized["preview_url"] = url_with_query(request, preview=item.item_id)
    serialized["external_url"] = serialized.get("captured_url") or serialized.get("source_url")
    if can_delete:
        serialized["delete_url"] = url_with_query(request, dialog="delete-item", item=item.item_id)
    if can_drag:
        serialized["can_drag"] = True
    return serialized


def build_item_preview(request, items):
    """Vraća podatke za modalni pregled izabrane stavke ili `None` kada pregled nije otvoren."""
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
    """Vraća konfiguraciju aktivnog modala akcije ili `None` kada modal nije otvoren."""
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
            "avatar_url": current_user.avatar_url,
        }
    if dialog == "create-space":
        return {
            "type": "create-space",
            "title": "Create Space",
        }
    if dialog == "space-settings" and selected_space:
        return {
            "type": "space-settings",
            "title": "Space Settings",
            "space_name": selected_space["name"],
            "space_description": selected_space.get("description", ""),
        }
    if dialog == "add-item" and selected_space:
        return {
            "type": "add-item",
            "title": "Add Item",
            "space_name": selected_space["name"],
            "space_id": selected_space["id"],
        }
    if dialog == "add-item" and current_user and request.GET.get("target") == "inbox":
        inbox_space = get_or_create_universal_space(current_user)
        return {
            "type": "add-item",
            "title": "Add Item",
            "space_name": "Inbox",
            "space_id": inbox_space.space_id,
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
                "title": "Delete item",
                "copy": "Delete this item?",
                "confirm_label": "Delete item",
                "action_url": reverse("app:delete_item"),
                "item_id": selected_item["id"],
            }
    return None


def base_context(request, *, title, active_tab="home", selected_space=None):
    """Vraća osnovni template kontekst zajednički za više stranica aplikacije."""
    mock_panel = request.GET.get("mock")
    current_user = get_current_user(request)
    auth_next_url = url_with_query(request, mock=None)
    auth_error = request.GET.get("auth_error")
    collaboration_requests = get_collaboration_requests(selected_space["_object"], current_user) if selected_space else []
    context = {
        "title": title,
        "active_tab": active_tab,
        "selected_space": selected_space,
        "current_user": current_user,
        "collaborators": get_space_collaborators(selected_space["_object"]) if selected_space else [],
        "collaboration_requests": collaboration_requests,
        "pending_collaboration_requests": [request_item for request_item in collaboration_requests if request_item["is_pending"]],
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
        "connect_extension_url": reverse("app:connect_extension"),
        "next_url": auth_next_url,
        "password_rules": PASSWORD_RULES,
        "auth_token_value": get_request_auth_token_value(request) if is_extension_request(request) else "",
        "is_extension_mode": is_extension_request(request),
        "home_url": append_request_auth(reverse("app:home"), request),
        "profile_url": append_request_auth(reverse("app:profile"), request),
        "back_url": append_request_auth(reverse("app:home"), request),
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
    """Prikazuje početnu stranicu sa prostorima korisnika i njegovim Inbox sadržajem."""
    current_user = get_current_user(request)
    active_space_filter = request.GET.get("space_filter", "All")
    active_item_filter = request.GET.get("item_filter", "All")
    context = base_context(request, title="SideKick")
    space_dicts = []
    universal_space = None
    universal_items = []
    if current_user:
        universal_space = get_or_create_universal_space(current_user)
        for space in filter_spaces(active_space_filter, current_user):
            serialized_space = serialize_space(space, current_user)
            serialized_space["detail_url"] = append_request_auth(
                reverse("app:space_detail", args=[space.space_id]),
                request,
            )
            serialized_space["can_accept_drop"] = can_add_items(space, current_user)
            space_dicts.append(serialized_space)
        universal_items = [
            decorate_item_for_request(
                request,
                item,
                can_delete=can_delete_item_record(item, current_user),
                can_drag=True,
            )
            for item in get_space_items(universal_space)
        ]
    filtered_universal_items = filter_items(universal_items, active_item_filter)
    context.update(
        {
            "spaces": space_dicts,
            "items": filtered_universal_items,
            "space_filter_links": filter_links(
                request, SPACE_FILTERS, "space_filter", active_space_filter
            ),
            "item_filter_links": filter_links(request, ITEM_FILTERS, "item_filter", active_item_filter),
            "show_item_actions": True,
            "home_capture_space_id": universal_space.space_id if universal_space else None,
            "move_item_url": reverse("app:move_item"),
            "inbox_add_item_url": url_with_query(request, dialog="add-item", target="inbox"),
            "item_preview": build_item_preview(request, filtered_universal_items),
        }
    )
    context["action_modal"] = build_action_modal(request, items=universal_items)
    return render(request, "app/home.html", context)


def profile(request):
    """Prikazuje profil prijavljenog korisnika i dostupne nalog akcije."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    context = base_context(request, title="Profile", active_tab="profile")
    context["profile_user"] = get_profile_user(request)
    context["profile_summary"] = get_user_profile_summary(current_user)
    return render(request, "app/profile.html", context)


def space_detail(request, space_id):
    """Prikazuje detalje jednog prostora zajedno sa njegovim stavkama i članovima."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    space_obj = get_space(space_id, current_user)
    if space_obj is None:
        raise Http404("Space not found")
    if is_universal_space(space_obj):
        return redirect_with_request_auth(request, reverse("app:home"))

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
        serialized_item["external_url"] = serialized_item.get("captured_url") or serialized_item.get("source_url")
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
            "show_item_actions": True,
            "can_add_item": can_add_items(space_obj, current_user),
            "can_manage_members": can_manage_members(space_obj, current_user),
            "can_request_collaboration": (
                current_membership is not None
                and current_membership.role == Membership.Role.VIEWER
            ),
            "request_collaboration_url": reverse("app:request_space_collaboration", args=[space_obj.space_id]),
            "latest_collaboration_request": latest_request,
            "team_modal_return_url": append_request_auth(
                f'{reverse("app:space_detail", args=[space_obj.space_id])}?modal=team',
                request,
            ),
            "invite_people_url": url_with_query(request, modal="team", dialog="invite-member"),
            "share_space_url": url_with_query(request, modal="team", dialog="share-link"),
            "space_settings_url": url_with_query(request, dialog="space-settings"),
            "team_url": url_with_query(request, modal="team"),
            "item_preview": build_item_preview(request, filtered_items),
        }
    )
    return render(request, "app/space_detail.html", context)


def login_action(request):
    """Obrađuje prijavu preko web forme i vraća redirect na odgovarajuću stranicu."""
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

    fallback = reverse("app:home")
    next_url = sanitize_next_url(request, fallback)
    email = (request.POST.get("email") or "").strip().lower()
    password = request.POST.get("password") or ""

    user = User.objects.filter(email=email).first()
    if user is None or not check_password(password, user.password_hash):
        login_url = f'{reverse("app:home")}?mock=login&auth_error=invalid_login'
        if next_url and next_url != "/":
            login_url = f"{login_url}&next={next_url}"
        return redirect_with_request_auth(request, login_url)

    session_token = issue_auth_token(user)
    request.session["sidekick_user_id"] = user.user_id
    request.session["sidekick_auth_token"] = session_token.token_value
    return redirect_with_request_auth(request, next_url)


def register_action(request):
    """Obrađuje registraciju preko web forme i vraća redirect nakon uspeha ili greške."""
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

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
        return redirect_with_request_auth(request, next_url)

    register_url = f'{reverse("app:home")}?mock=register&auth_error={error_code}'
    if next_url and next_url != "/":
        register_url = f"{register_url}&next={next_url}"
    return redirect_with_request_auth(request, register_url)


def logout_action(request):
    """Odjavljuje korisnika, opoziva aktivne tokene i vraća redirect na početnu stranu."""
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

    session_token_value = request.session.pop("sidekick_auth_token", None)
    if session_token_value:
        AuthToken.objects.filter(token_value=session_token_value).update(is_revoked=True)
    request_token_value = get_request_auth_token_value(request)
    if request_token_value:
        AuthToken.objects.filter(token_value=request_token_value).update(is_revoked=True)
    request.session.pop("sidekick_user_id", None)
    return redirect(sanitize_next_url(request, reverse("app:home")))


def connect_extension(request):
    """Generiše i vraća token za Chrome ekstenziju, kao JSON ili redirect odgovor."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

    AuthToken.objects.filter(
        user=current_user,
        client_type=AuthToken.ClientType.EXTENSION,
        is_revoked=False,
    ).update(is_revoked=True)
    auth_token = issue_auth_token(current_user, client_type=AuthToken.ClientType.EXTENSION)
    payload = {
        "status": "ok",
        "token": auth_token.token_value,
        "baseUrl": request.build_absolute_uri(reverse("app:home")).rstrip("/"),
        "user": serialize_user_payload(current_user),
    }
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(payload)

    messages.success(request, "Extension token refreshed.")
    return redirect_with_request_auth(request, reverse("app:home"))


def update_profile(request):
    """Ažurira osnovne podatke profila i vraća redirect ka profilu korisnika."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:profile"))

    full_name = (request.POST.get("full_name") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    if not full_name or not email:
        messages.error(request, "Full name and email are required.")
        return redirect_with_request_auth(request, f'{reverse("app:profile")}?dialog=edit-profile')
    if User.objects.filter(email=email).exclude(user_id=current_user.user_id).exists():
        messages.error(request, "That email is already registered.")
        return redirect_with_request_auth(request, f'{reverse("app:profile")}?dialog=edit-profile')

    current_user.full_name = full_name
    current_user.email = email
    uploaded_avatar = request.FILES.get("avatar_file")
    update_fields = ["full_name", "email", "updated_at"]
    if uploaded_avatar is not None:
        current_user.avatar_path = save_uploaded_avatar(uploaded_avatar, current_user)
        update_fields.append("avatar_path")
    current_user.updated_at = timezone.now()
    current_user.save(update_fields=update_fields)
    messages.success(request, "Profile updated.")
    return redirect_with_request_auth(request, reverse("app:profile"))


def change_password(request):
    """Menja lozinku prijavljenog korisnika i vraća redirect sa status porukom."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:profile"))

    current_password = request.POST.get("current_password") or ""
    new_password = request.POST.get("new_password") or ""
    confirm_password = request.POST.get("confirm_password") or ""

    if not current_password or not new_password or not confirm_password:
        messages.error(request, "All password fields are required.")
        return redirect_with_request_auth(request, f'{reverse("app:profile")}?dialog=change-password')
    if not check_password(current_password, current_user.password_hash):
        messages.error(request, "Current password is incorrect.")
        return redirect_with_request_auth(request, f'{reverse("app:profile")}?dialog=change-password')
    if new_password != confirm_password:
        messages.error(request, "New password confirmation does not match.")
        return redirect_with_request_auth(request, f'{reverse("app:profile")}?dialog=change-password')

    password_error = password_validation_error(new_password)
    if password_error:
        messages.error(request, password_error)
        return redirect_with_request_auth(request, f'{reverse("app:profile")}?dialog=change-password')

    current_user.password_hash = make_password(new_password)
    current_user.updated_at = timezone.now()
    current_user.save(update_fields=["password_hash", "updated_at"])
    messages.success(request, "Password updated.")
    return redirect_with_request_auth(request, reverse("app:profile"))


def api_register(request):
    """Kreira korisnika preko API-ja i vraća JSON sa korisnikom i novim tokenom."""
    if request.method != "POST":
        return json_error("Method not allowed.", status=405, code="method_not_allowed")

    payload = parse_request_data(request)
    if payload is None:
        return json_error("Request body must be valid JSON.", status=400, code="invalid_json")

    full_name = (payload.get("fullName") or payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    client_type = payload.get("clientType") or AuthToken.ClientType.WEB
    valid_client_types = {choice for choice, _ in AuthToken.ClientType.choices}
    if client_type not in valid_client_types:
        client_type = AuthToken.ClientType.WEB

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
    auth_token = issue_auth_token(user, client_type=client_type)
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
    """Prijavljuje korisnika preko API-ja i vraća JSON sa korisnikom i tokenom."""
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
    """Odjavljuje korisnika preko API-ja i vraća prazan JSON odgovor sa statusom 204."""
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
    """Vraća ili ažurira podatke tekućeg API korisnika i uzvraća JSON odgovor."""
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
    """Menja lozinku tekućeg API korisnika i vraća JSON status operacije."""
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
    """Vraća listu prostora ili kreira novi prostor preko API-ja."""
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
    """Vraća, menja ili briše jedan prostor preko API-ja i uzvraća JSON odgovor."""
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
    """Vraća filtriranu listu stavki jednog prostora u JSON obliku."""
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
    """Kreira ili opoziva deljeni link prostora preko API-ja i vraća JSON odgovor."""
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
    """Kreira novu stavku preko API-ja i vraća serijalizovanu stavku u JSON formatu."""
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
        title=payload.get("title") or "",
        uploaded_image=request.FILES.get("image_file"),
    )
    if error_message:
        return json_error(error_message, status=400, code=error_code)

    emit_space_item_created(item)
    return JsonResponse({"item": serialize_item_payload(item)}, status=201)


def api_delete_item(request, item_id):
    """Briše stavku preko API-ja i vraća prazan JSON odgovor sa statusom 204."""
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

    source_space_id = item.space_id
    item.delete()
    emit_space_item_removed(source_space_id, item_id)
    return JsonResponse({}, status=204)


def create_space(request):
    """Kreira novi prostor preko web forme i vraća redirect ka njegovom prikazu."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

    name = (request.POST.get("name") or "").strip()
    description = (request.POST.get("description") or "").strip()
    if not name:
        return redirect_with_request_auth(request, f'{reverse("app:home")}?dialog=create-space')

    now = timezone.now()
    space = ResearchSpace.objects.create(
        owner=current_user,
        name=name,
        description=description,
        is_archived=False,
        created_at=now,
        updated_at=now,
    )
    return redirect_with_request_auth(request, reverse("app:space_detail", args=[space.space_id]))


def update_space(request):
    """Ažurira osnovne podatke prostora i vraća redirect na stranicu prostora."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

    space = get_space(request.POST.get("space_id"), current_user)
    if space is None or not is_owner(space, current_user):
        return redirect_with_request_auth(request, reverse("app:home"))

    name = (request.POST.get("name") or "").strip()
    description = (request.POST.get("description") or "").strip()
    if not name:
        messages.error(request, "Space name is required.")
        return redirect_with_request_auth(request, f'{reverse("app:space_detail", args=[space.space_id])}?dialog=space-settings')

    space.name = name
    space.description = description
    space.updated_at = timezone.now()
    space.save(update_fields=["name", "description", "updated_at"])
    messages.success(request, "Space updated.")
    return redirect_with_request_auth(request, reverse("app:space_detail", args=[space.space_id]))


def create_item(request):
    """Kreira novu stavku preko web forme i vraća JSON ili redirect odgovor."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))
    is_ajax_request = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    space_id = request.POST.get("space_id")
    space = get_space(space_id, current_user)
    if space is None or not can_add_items(space, current_user):
        if is_ajax_request:
            return json_error("You do not have permission to add items here.", status=403, code="forbidden")
        return redirect_with_request_auth(request, reverse("app:home"))

    item_type = request.POST.get("item_type") or Item.ItemType.TEXT
    link_title = (request.POST.get("link_title") or "").strip()
    image_title = (request.POST.get("image_title") or "").strip()
    content_text = (request.POST.get("content_text") or "").strip()
    source_url = (request.POST.get("source_url") or "").strip()
    image_source_url = (request.POST.get("image_source_url") or "").strip()
    title = link_title if item_type == Item.ItemType.LINK else image_title

    item, error_message, _error_code = create_item_record(
        current_user=current_user,
        space=space,
        item_type=item_type,
        content_text=content_text,
        source_url=image_source_url if item_type == Item.ItemType.IMAGE else source_url,
        title=title,
        uploaded_image=request.FILES.get("image_file"),
    )
    if error_message:
        if is_ajax_request:
            return json_error(error_message, status=400, code="invalid_item")
        messages.error(request, error_message)
        fallback_url = reverse("app:home") if is_universal_space(space) else reverse("app:space_detail", args=[space.space_id])
        if is_universal_space(space):
            return redirect_with_request_auth(request, fallback_url)
        return redirect_with_request_auth(request, f'{fallback_url}?dialog=add-item')

    emit_space_item_created(item)
    if is_ajax_request:
        return JsonResponse({"status": "ok", "item": serialize_item_payload(item)}, status=201)
    messages.success(request, "Item saved.")
    if is_universal_space(space):
        return redirect_with_request_auth(request, reverse("app:home"))
    return redirect_with_request_auth(request, reverse("app:space_detail", args=[space.space_id]))


def delete_item(request):
    """Briše stavku preko web forme i vraća JSON ili redirect odgovor."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

    is_ajax_request = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    item_id = request.POST.get("item_id")
    item = (
        Item.objects.select_related("space")
        .filter(item_id=item_id)
        .first()
    )
    if item is None:
        if is_ajax_request:
            return json_error("Item not found.", status=404, code="item_not_found")
        return redirect_with_request_auth(request, reverse("app:home"))
    if not can_delete_item_record(item, current_user):
        if is_ajax_request:
            return json_error("You do not have permission to delete this item.", status=403, code="forbidden")
        return redirect_with_request_auth(request, reverse("app:home"))

    source_space = item.space
    source_space_id = source_space.space_id if source_space else None
    now = timezone.now()
    item.delete()
    if source_space is not None:
        source_space.updated_at = now
        source_space.save(update_fields=["updated_at"])
    if source_space_id is not None:
        emit_space_item_removed(source_space_id, int(item_id))

    if is_ajax_request:
        return JsonResponse(
            {
                "status": "ok",
                "itemId": int(item_id),
                "spaceId": source_space.space_id if source_space else None,
                "isUniversalSpace": is_universal_space(source_space),
            }
        )

    if is_universal_space(source_space):
        return redirect_with_request_auth(request, reverse("app:home"))
    return redirect_with_request_auth(request, reverse("app:space_detail", args=[source_space.space_id]))


def move_item(request):
    """Premešta stavku između prostora i vraća JSON ili redirect odgovor."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

    is_ajax_request = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    item = Item.objects.select_related("space", "added_by").filter(item_id=request.POST.get("item_id")).first()
    target_space = get_space(request.POST.get("target_space_id"), current_user)
    if item is None or target_space is None or not can_move_item_record(item, current_user, target_space):
        if is_ajax_request:
            return json_error("You do not have permission to move this item there.", status=403, code="forbidden")
        return redirect_with_request_auth(request, reverse("app:home"))

    if item.space_id == target_space.space_id:
        if is_ajax_request:
            return JsonResponse({"status": "ok", "item": serialize_item_payload(item)}, status=200)
        return redirect_with_request_auth(request, reverse("app:home"))

    source_space_id = item.space_id
    now = timezone.now()
    item.space = target_space
    item.updated_at = now
    item.save(update_fields=["space", "updated_at"])
    target_space.updated_at = now
    target_space.save(update_fields=["updated_at"])
    emit_space_item_moved(item, source_space_id)

    if is_ajax_request:
        return JsonResponse({"status": "ok", "item": serialize_item_payload(item)}, status=200)
    return redirect_with_request_auth(request, reverse("app:home"))


def invite_member(request):
    """Dodaje ili ažurira člana prostora i vraća redirect sa flash porukom."""
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
    """Uklanja aktivnog člana iz prostora i vraća redirect sa status porukom."""
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
    """Odobrava ili odbija zahtev za saradnju i vraća redirect sa rezultatom obrade."""
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
    """Kreira ili ponovo koristi deljeni link prostora i vraća redirect ka Team modalu."""
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
    return redirect_with_request_auth(
        request,
        f"{reverse('app:space_detail', args=[space.space_id])}?{urlencode({'modal': 'team', 'dialog': 'share-link', 'share_url': share_url})}",
    )


def revoke_share_link(request):
    """Opoziva aktivne deljene linkove prostora i vraća redirect sa porukom."""
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
    """Prikazuje stranicu za pristup prostoru preko deljenog linka ili vraća redirect."""
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
        return redirect_with_request_auth(request, login_url)

    space = get_space(share_link.space.space_id, current_user)
    if space is not None:
        return redirect_with_request_auth(request, reverse("app:space_detail", args=[share_link.space.space_id]))

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
    """Dodaje prijavljenog korisnika kao viewer-a u deljeni prostor i vraća redirect."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

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
    """Kreira zahtev za collaborator pristup iz prikaza deljenog linka i vraća redirect."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

    share_link = ShareLink.objects.select_related("space").filter(token=token, is_active=True).first()
    if share_link is None:
        raise Http404("Share link not found")

    if share_link.space.owner_id == current_user.user_id or get_membership(share_link.space, current_user):
        messages.info(request, "You already have access to this space.")
        return redirect_with_request_auth(request, reverse("app:share_link_access", args=[token]))

    _, level, message = create_collaboration_request(
        space=share_link.space,
        requester=current_user,
        message="Requested collaborator access from shared link.",
    )
    getattr(messages, level)(request, message)

    return redirect_with_request_auth(request, reverse("app:share_link_access", args=[token]))


def request_space_collaboration(request, space_id):
    """Kreira zahtev za collaborator ulogu iz samog prostora i vraća redirect odgovor."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

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
    """Briše prostor vlasnika i vraća redirect na početnu stranicu."""
    current_user, redirect_response = require_current_user(request)
    if redirect_response:
        return redirect_response
    if request.method != "POST":
        return redirect_with_request_auth(request, reverse("app:home"))

    space = get_space(request.POST.get("space_id"), current_user)
    if space is None or not is_owner(space, current_user):
        return redirect_with_request_auth(request, reverse("app:home"))

    space.delete()
    return redirect_with_request_auth(request, reverse("app:home"))

