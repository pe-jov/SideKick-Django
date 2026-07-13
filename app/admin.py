# Author Petar Jovanovic
from django.contrib import admin

from .models import AuthToken, CollaborationRequest, Item, Membership, ResearchSpace, ShareLink, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("user_id", "full_name", "email", "created_at")
    search_fields = ("full_name", "email")


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ("token_id", "user", "client_type", "issued_at", "is_revoked")
    list_filter = ("client_type", "is_revoked")


@admin.register(ResearchSpace)
class ResearchSpaceAdmin(admin.ModelAdmin):
    list_display = ("space_id", "name", "owner", "is_archived", "created_at")
    list_filter = ("is_archived",)
    search_fields = ("name", "owner__full_name")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("membership_id", "space", "user", "role", "status")
    list_filter = ("role", "status")


@admin.register(CollaborationRequest)
class CollaborationRequestAdmin(admin.ModelAdmin):
    list_display = ("request_id", "space", "requester", "status", "requested_at", "resolved_by")
    list_filter = ("status",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("item_id", "space", "added_by", "item_type", "source_platform", "created_at")
    list_filter = ("item_type", "source_platform")
    search_fields = ("title", "content_text", "space__name", "added_by__full_name")


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ("share_link_id", "space", "created_by", "token", "is_active")
    list_filter = ("is_active",)
