"""Корневые адреса сайта: админка и адреса каждого приложения."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("references/", include("apps.references.urls")),
    path("people/", include("apps.personnel.urls")),
    path("military/", include("apps.military.urls")),
    path("reports/", include("apps.reports.urls")),
    path("", include("apps.core.urls")),
]
