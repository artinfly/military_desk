from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    """Пользователи системы, вход и роли."""

    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Пользователи"

    def ready(self):
        # Группы ролей с правами создаются и обновляются после каждого migrate
        from .roles import sync_roles_after_migrate

        post_migrate.connect(
            sync_roles_after_migrate, dispatch_uid="accounts_sync_roles"
        )
