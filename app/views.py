# Author Petar Jovanovic
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from .context import (
    ALL_ITEMS,
    COLLABORATORS,
    COLLABORATION_REQUESTS,
    ITEM_FILTERS,
    PASSWORD_RULES,
    RECENT_ITEMS,
    SETTINGS,
    SPACE_FILTERS,
    filter_items,
    filter_spaces,
    get_space,
    item_user_filters,
)


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
                "delete_url": url_with_query(request, dialog="delete-item", item=item["id"]),
            }
        )
    return decorated


def build_action_modal(request, *, selected_space=None, items=None):
    dialog = request.GET.get("dialog")
    if dialog == "delete-space" and selected_space and selected_space["role"] == "Owner":
        return {
            "title": "Delete Space",
            "copy": (
                f'"{selected_space["name"]}" bi bio trajno obrisan zajedno sa svim stavkama i collaborator-ima.'
            ),
            "confirm_label": "Delete space",
        }
    if dialog == "remove-member" and request.GET.get("member"):
        member_name = request.GET["member"]
        return {
            "title": "Remove Collaborator",
            "copy": f"{member_name} bi odmah izgubio pristup ovom prostoru.",
            "confirm_label": "Remove collaborator",
        }
    if dialog == "delete-item" and items:
        item_id = request.GET.get("item")
        selected_item = next((item for item in items if str(item["id"]) == item_id), None)
        if selected_item:
            return {
                "title": "Delete Item",
                "copy": f'Stavka koju je dodao {selected_item["added_by"]} bi bila trajno uklonjena iz prikaza.',
                "confirm_label": "Delete item",
            }
    return None


def base_context(request, *, title, active_tab="home", selected_space=None):
    mock_panel = request.GET.get("mock")
    context = {
        "title": title,
        "active_tab": active_tab,
        "selected_space": selected_space,
        "collaborators": COLLABORATORS,
        "collaboration_requests": COLLABORATION_REQUESTS,
        "is_modal_open": request.GET.get("modal") == "team",
        "mock_panel": mock_panel if mock_panel in {"login", "register"} else None,
        "team_url": url_with_query(request, modal="team"),
        "close_modal_url": url_with_query(request, modal=None),
        "login_url": url_with_query(request, mock="login"),
        "register_url": url_with_query(request, mock="register"),
        "close_mock_url": url_with_query(request, mock=None),
        "password_rules": PASSWORD_RULES,
        "home_url": reverse("app:home"),
        "profile_url": reverse("app:profile"),
        "back_url": reverse("app:home"),
        "password_url": url_with_query(request, dialog="change-password"),
        "action_modal": None,
        "close_dialog_url": url_with_query(request, dialog=None, item=None, member=None),
    }
    if request.GET.get("dialog") == "change-password":
        context["action_modal"] = {"type": "change-password"}
    return context


def home(request):
    active_space_filter = request.GET.get("space_filter", "All")
    active_item_filter = request.GET.get("item_filter", "All")
    active_user_filter = request.GET.get("user_filter", "All")
    context = base_context(request, title="SideKick")
    recent_items = decorate_items(request, RECENT_ITEMS)
    user_filters = item_user_filters(recent_items)
    context.update(
        {
            "spaces": filter_spaces(active_space_filter),
            "items": filter_items(recent_items, active_item_filter, active_user_filter),
            "space_filter_links": filter_links(
                request, SPACE_FILTERS, "space_filter", active_space_filter
            ),
            "item_filter_links": filter_links(request, ITEM_FILTERS, "item_filter", active_item_filter),
            "user_filter_links": filter_links(request, user_filters, "user_filter", active_user_filter),
        }
    )
    return render(request, "app/home.html", context)


def profile(request):
    context = base_context(request, title="Profile", active_tab="profile")
    context["settings"] = SETTINGS
    return render(request, "app/profile.html", context)


def space_detail(request, space_id):
    space = get_space(space_id)
    if space is None:
        raise Http404("Space not found")

    active_item_filter = request.GET.get("item_filter", "All")
    active_user_filter = request.GET.get("user_filter", "All")
    space_items = decorate_items(
        request, [item for item in ALL_ITEMS if item["space"] == space["name"]]
    )
    context = base_context(request, title=space["name"], selected_space=space)
    context["action_modal"] = build_action_modal(request, selected_space=space, items=space_items)
    user_filters = item_user_filters(space_items)
    context.update(
        {
            "space": space,
            "item_count": len(space_items),
            "items": filter_items(space_items, active_item_filter, active_user_filter),
            "item_filter_links": filter_links(request, ITEM_FILTERS, "item_filter", active_item_filter),
            "user_filter_links": filter_links(request, user_filters, "user_filter", active_user_filter),
            "delete_space_url": url_with_query(request, dialog="delete-space"),
            "show_item_actions": True,
        }
    )
    return render(request, "app/space_detail.html", context)
