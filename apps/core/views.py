from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Главная страница."""

    template_name = "core/home.html"
    extra_context = {"page_title": "Главная"}
