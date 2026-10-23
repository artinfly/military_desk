from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Общий каркас сайта: меню, главная страница, общие шаблоны."""

    name = "apps.core"
    label = "core"
    verbose_name = "Основное"
