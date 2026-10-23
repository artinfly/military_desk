"""Корневые адреса сайта: админка и адреса каждого приложения."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("references/", include("apps.references.urls")),
    path("", include("apps.core.urls")),
]
