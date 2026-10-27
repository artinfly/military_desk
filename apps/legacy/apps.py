from django.apps import AppConfig


class LegacyConfig(AppConfig):
    """Перенос данных из старой программы (Lazarus, база «stol»). Нужен один раз."""

    name = "apps.legacy"
    label = "legacy"
    verbose_name = "Перенос из старой программы"
