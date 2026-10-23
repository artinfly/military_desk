from django.apps import AppConfig


class PersonnelConfig(AppConfig):
    """Учётные карточки работников и их разделы (документы, адреса, родственники…)."""

    name = "apps.personnel"
    label = "personnel"
    verbose_name = "Учётные карточки"
