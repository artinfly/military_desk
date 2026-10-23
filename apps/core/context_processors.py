"""Данные, которые нужны каждой странице: меню с отметкой текущего пункта."""

from django.urls import reverse

from .navigation import MENU


def navigation(request):
    """Меню для текущего пользователя: без недоступных пунктов и пустых разделов."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"menu": []}

    current = request.resolver_match.view_name if request.resolver_match else ""
    menu = []
    for section in MENU:
        items = [
            {
                "label": item["label"],
                "url": reverse(item["url_name"]),
                "active": item["url_name"] == current,
            }
            for item in section["items"]
            if not item.get("staff_only") or user.is_staff
        ]
        if items:
            menu.append({"title": section["title"], "items": items})
    return {"menu": menu}
