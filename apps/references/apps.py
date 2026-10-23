from django.apps import AppConfig


class ReferencesConfig(AppConfig):
    """Справочники (НСИ): звания, ВУС, военкоматы, цеха, адреса и т.д."""

    name = "apps.references"
    label = "references"
    verbose_name = "Справочники"
