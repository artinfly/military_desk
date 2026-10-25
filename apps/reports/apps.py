from django.apps import AppConfig


class ReportsConfig(AppConfig):
    """Отчёты в Excel (только чтение данных)."""

    name = "apps.reports"
    label = "reports"
    verbose_name = "Отчёты"
