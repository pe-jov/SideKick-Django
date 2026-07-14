# Autor: Milan Neskovic, 545/19
"""Socket.IO helpers for real-time item updates."""

from http.cookies import SimpleCookie
from importlib import import_module
import logging
from urllib.parse import urlparse

from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.utils import timezone

import socketio

from .context import get_space, membership_grants_access
from .models import AuthToken, Item, ResearchSpace, User


sio = socketio.AsyncServer(async_mode="asgi")
logger = logging.getLogger(__name__)


def _session_store_class():
    return import_module(settings.SESSION_ENGINE).SessionStore


def _normalize_auth_token(auth):
    if not isinstance(auth, dict):
        return ""
    return (
        auth.get("authToken")
        or auth.get("auth_token")
        or auth.get("token")
        or ""
    ).strip()


def _user_from_auth_token(token_value):
    if not token_value:
        return None

    token = (
        AuthToken.objects.select_related("user")
        .filter(token_value=token_value, is_revoked=False)
        .first()
    )
    if token is None:
        return None
    if token.expires_at and token.expires_at <= timezone.now():
        return None
    return token.user


def _user_from_session_cookie(environ):
    scope = environ.get("asgi.scope", {})
    headers = {
        key.decode("latin-1"): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }
    raw_cookie = headers.get("cookie", "")
    if not raw_cookie:
        return None

    cookie = SimpleCookie()
    cookie.load(raw_cookie)
    session_cookie = cookie.get(settings.SESSION_COOKIE_NAME)
    if session_cookie is None or not session_cookie.value:
        return None

    session_store = _session_store_class()(session_key=session_cookie.value)
    user_id = session_store.get("sidekick_user_id")
    session_token_value = session_store.get("sidekick_auth_token")
    if not user_id or not session_token_value:
        return None

    session_token = (
        AuthToken.objects.select_related("user")
        .filter(
            token_value=session_token_value,
            user_id=user_id,
            is_revoked=False,
        )
        .first()
    )
    if session_token is None:
        return None
    if session_token.expires_at and session_token.expires_at <= timezone.now():
        return None

    return session_token.user


def _resolve_socket_user(auth, environ):
    token_user = _user_from_auth_token(_normalize_auth_token(auth))
    if token_user is not None:
        return token_user
    return _user_from_session_cookie(environ)


def _resolve_joinable_space_id(user_id, space_id):
    user = User.objects.filter(user_id=user_id).first()
    if user is None:
        return None

    space = get_space(space_id, user)
    if space is None:
        return None

    return space.space_id


def _space_user_room(space_id, user_id):
    return f"space:{space_id}:user:{user_id}"


def _current_space_recipients(space_id):
    space = (
        ResearchSpace.objects.select_related("owner")
        .prefetch_related("memberships__joined_via")
        .filter(space_id=space_id)
        .first()
    )
    if space is None:
        return []

    recipients = {space.owner_id}
    for membership in space.memberships.all():
        if membership_grants_access(membership):
            recipients.add(membership.user_id)
    return sorted(recipients)


def serialize_realtime_item(item):
    url = item.source_url or item.captured_url
    return {
        "id": item.item_id,
        "spaceId": item.space_id,
        "type": item.item_type,
        "src": item.image_url if item.item_type == Item.ItemType.IMAGE else "",
        "content": item.content_text if item.item_type == Item.ItemType.TEXT else "",
        "title": item.title if item.item_type == Item.ItemType.LINK else "",
        "domain": urlparse(url).netloc if item.item_type == Item.ItemType.LINK and url else "",
        "sourceUrl": item.source_url,
        "capturedUrl": item.captured_url,
        "externalUrl": item.captured_url or item.source_url,
        "pageTitle": item.page_title,
        "addedBy": item.added_by.full_name,
        "addedById": item.added_by_id,
        "createdAt": item.created_at.isoformat(),
        "updatedAt": item.updated_at.isoformat(),
    }


def _emit_to_space_recipients(event_name, payload, space_id):
    recipients = _current_space_recipients(space_id)
    for user_id in recipients:
        try:
            async_to_sync(sio.emit)(
                event_name,
                payload,
                room=_space_user_room(space_id, user_id),
            )
        except Exception:
            logger.exception(
                "Failed to emit %s for space %s to user %s.",
                event_name,
                space_id,
                user_id,
            )


def emit_space_item_created(item):
    _emit_to_space_recipients(
        "space:item_created",
        {"spaceId": item.space_id, "item": serialize_realtime_item(item)},
        item.space_id,
    )


def emit_space_item_removed(space_id, item_id):
    _emit_to_space_recipients(
        "space:item_removed",
        {"spaceId": space_id, "itemId": item_id},
        space_id,
    )


def emit_space_item_moved(item, source_space_id):
    emit_space_item_removed(source_space_id, item.item_id)
    emit_space_item_created(item)


@sio.event
async def connect(sid, environ, auth):
    user = await sync_to_async(_resolve_socket_user)(auth, environ)
    if user is None:
        return False

    await sio.save_session(sid, {"user_id": user.user_id})
    return True


@sio.on("space:join")
async def join_space(sid, data):
    session = await sio.get_session(sid)
    user_id = session.get("user_id")
    if not user_id:
        return {"ok": False, "error": "unauthorized"}

    try:
        requested_space_id = int((data or {}).get("spaceId"))
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_space"}

    space_id = await sync_to_async(_resolve_joinable_space_id)(user_id, requested_space_id)
    if space_id is None:
        return {"ok": False, "error": "forbidden"}

    previous_space_id = session.get("space_id")
    previous_room = (
        _space_user_room(previous_space_id, user_id)
        if previous_space_id is not None
        else None
    )
    next_room = _space_user_room(space_id, user_id)
    if previous_room and previous_room != next_room:
        await sio.leave_room(sid, previous_room)

    await sio.enter_room(sid, next_room)
    session["space_id"] = space_id
    await sio.save_session(sid, session)
    return {"ok": True, "spaceId": space_id}

