from django.views.generic import TemplateView

from apps.reports.registry import MILITARY_VIEW
from apps.reports.services.counts import figures


class HomeView(TemplateView):
    """Главная страница: приветствие, роли и численность по воинскому учёту."""

    template_name = "core/home.html"
    extra_context = {"page_title": "Главная"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["roles"] = list(user.groups.values_list("name", flat=True))
        if user.has_perm(MILITARY_VIEW):
            context["figures"] = figures()
        return context
