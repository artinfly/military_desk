from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "core"

urlpatterns = [
    path(
        "help/",
        TemplateView.as_view(
            template_name="core/help.html", extra_context={"page_title": "Инструкция"}
        ),
        name="help",
    ),
    path("", views.HomeView.as_view(), name="home"),
]
