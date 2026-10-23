from django.apps import AppConfig


class DemoConfig(AppConfig):
    """Вымышленные данные для разработки (команда seed_demo). Подключено только в dev."""

    name = "apps.demo"
    label = "demo"
    verbose_name = "Демо-данные"
