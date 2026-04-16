# Author Petar Jovanovic
from django.urls import path

from . import views


app_name = "app"

urlpatterns = [
    path("", views.home, name="home"),
    path("profile/", views.profile, name="profile"),
    path("spaces/<int:space_id>/", views.space_detail, name="space_detail"),
]
