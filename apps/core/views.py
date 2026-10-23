from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Главная страница: приветствие и роли пользователя."""

    template_name = "core/home.html"
    extra_context = {"page_title": "Главная"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["roles"] = list(self.request.user.groups.values_list("name", flat=True))
        return context
