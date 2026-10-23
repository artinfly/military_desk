"""Данные, которые нужны каждой странице: меню с отметкой текущего пункта."""

from django.urls import reverse

from .navigation import MENU


def navigation(request):
    """Меню для текущего пользователя: без недоступных пунктов и пустых разделов."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"menu": []}

    match = request.resolver_match
    current = match.view_name if match else ""
    namespace = match.namespace if match else ""

    def is_active(item):
        if item.get("namespace"):
            return item["namespace"] == namespace
        return item["url_name"] == current

    menu = []
    for section in MENU:
        items = [
            {
                "label": item["label"],
                "url": reverse(item["url_name"]),
                "active": is_active(item),
            }
            for item in section["items"]
            if not item.get("staff_only") or user.is_staff
        ]
        if items:
            menu.append({"title": section["title"], "items": items})
    return {"menu": menu}
