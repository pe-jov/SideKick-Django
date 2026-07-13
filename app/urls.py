# Author Petar Jovanovic
from django.urls import path

from . import views


app_name = "app"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/register/", views.api_register, name="api_register"),
    path("api/login/", views.api_login, name="api_login"),
    path("api/logout/", views.api_logout, name="api_logout"),
    path("api/me/", views.api_me, name="api_me"),
    path("api/change-password/", views.api_change_password, name="api_change_password"),
    path("api/spaces/", views.api_spaces, name="api_spaces"),
    path("api/spaces/<int:space_id>/", views.api_space_detail, name="api_space_detail"),
    path("api/spaces/<int:space_id>/share-link/", views.api_space_share_link, name="api_space_share_link"),
    path("api/spaces/<int:space_id>/items/", views.api_space_items, name="api_space_items"),
    path("api/items/", views.api_create_item, name="api_create_item"),
    path("api/items/<int:item_id>/", views.api_delete_item, name="api_delete_item"),
    path("auth/login/", views.login_action, name="login_action"),
    path("auth/register/", views.register_action, name="register_action"),
    path("auth/logout/", views.logout_action, name="logout_action"),
    path("auth/connect-extension/", views.connect_extension, name="connect_extension"),
    path("account/profile/", views.update_profile, name="update_profile"),
    path("account/password/", views.change_password, name="change_password"),
    path("spaces/create/", views.create_space, name="create_space"),
    path("spaces/update/", views.update_space, name="update_space"),
    path("items/create/", views.create_item, name="create_item"),
    path("items/delete/", views.delete_item, name="delete_item"),
    path("items/move/", views.move_item, name="move_item"),
    path("members/invite/", views.invite_member, name="invite_member"),
    path("members/remove/", views.remove_member, name="remove_member"),
    path("requests/review/", views.review_request, name="review_request"),
    path("spaces/delete/", views.delete_space, name="delete_space"),
    path("share/create/", views.create_share_link, name="create_share_link"),
    path("share/revoke/", views.revoke_share_link, name="revoke_share_link"),
    path("share/<str:token>/", views.share_link_access, name="share_link_access"),
    path("share/<str:token>/join/", views.join_shared_space, name="join_shared_space"),
    path("share/<str:token>/request/", views.request_shared_space_access, name="request_shared_space_access"),
    path("spaces/<int:space_id>/request-collaboration/", views.request_space_collaboration, name="request_space_collaboration"),
    path("profile/", views.profile, name="profile"),
    path("spaces/<int:space_id>/", views.space_detail, name="space_detail"),
]
