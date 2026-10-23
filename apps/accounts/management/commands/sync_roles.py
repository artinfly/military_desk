from django.core.management.base import BaseCommand

from apps.accounts.roles import sync_roles


class Command(BaseCommand):
    help = "Создаёт группы ролей и выставляет им права по описанию в apps/accounts/roles.py."

    def handle(self, *args, **options):
        for role, count in sync_roles().items():
            self.stdout.write(f"{role}: прав {count}")
