# Author Petar Jovanovic
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from .context import (
    ALL_ITEMS,
    COLLABORATORS,
    ITEM_FILTERS,
    RECENT_ITEMS,
    SETTINGS,
    SPACE_FILTERS,
    filter_items,
    filter_spaces,
    get_space,
)


def url_with_query(request, **updates):
    query = request.GET.copy()
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


def base_context(request, *, title, active_tab="home", selected_space=None):
    return {
        "title": title,
        "active_tab": active_tab,
        "selected_space": selected_space,
        "collaborators": COLLABORATORS,
        "is_modal_open": request.GET.get("modal") == "team",
        "team_url": url_with_query(request, modal="team"),
        "close_modal_url": url_with_query(request, modal=None),
        "home_url": reverse("app:home"),
        "profile_url": reverse("app:profile"),
        "back_url": reverse("app:home"),
    }


def home(request):
    active_space_filter = request.GET.get("space_filter", "All")
    active_item_filter = request.GET.get("item_filter", "All")
    context = base_context(request, title="SideKick")
    context.update(
        {
            "spaces": filter_spaces(active_space_filter),
            "items": filter_items(RECENT_ITEMS, active_item_filter),
            "space_filter_links": filter_links(
                request, SPACE_FILTERS, "space_filter", active_space_filter
            ),
            "item_filter_links": filter_links(request, ITEM_FILTERS, "item_filter", active_item_filter),
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
    space_items = [item for item in ALL_ITEMS if item["space"] == space["name"]]
    context = base_context(request, title=space["name"], selected_space=space)
    context.update(
        {
            "space": space,
            "item_count": len(space_items),
            "items": filter_items(space_items, active_item_filter),
            "item_filter_links": filter_links(request, ITEM_FILTERS, "item_filter", active_item_filter),
        }
    )
    return render(request, "app/space_detail.html", context)
