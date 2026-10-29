"""Данные, которые нужны каждой странице: меню с отметкой текущего пункта."""

from django.urls import reverse

from .navigation import MENU


def is_allowed(user, item):
    """Пункт меню доступен пользователю (право или любое право приложения)."""
    if item.get("perm") and not user.has_perm(item["perm"]):
        return False
    return not item.get("module") or user.has_module_perms(item["module"])


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
            if is_allowed(user, item)
        ]
        if items:
            menu.append({"title": section["title"], "items": items})
    return {"menu": menu}
