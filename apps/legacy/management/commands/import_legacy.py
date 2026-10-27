"""manage.py import_legacy — перенос данных из старой базы «stol».

Старая база только читается. Перенос идёт одной транзакцией: при ошибке
в новой базе не остаётся ничего. Пароль к старой базе спрашивается при запуске
(или берётся из переменной окружения LEGACY_DB_PASSWORD).

    manage.py import_legacy --host <адрес> --dbname stol --user <пользователь> --dry-run
    manage.py import_legacy --host <адрес> --dbname stol --user <пользователь>
"""

import getpass
import os

import psycopg
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.legacy import source
from apps.legacy.importer import LegacyImporter
from apps.personnel.models import Person


class DryRun(Exception):
    """Отмена транзакции после пробного переноса."""


class Command(BaseCommand):
    help = "Перенос карточек, воинского учёта и справочников из старой базы «stol»"

    def add_arguments(self, parser):
        parser.add_argument("--host", required=True)
        parser.add_argument("--port", default="5432")
        parser.add_argument("--dbname", default="stol")
        parser.add_argument("--user", required=True)
        parser.add_argument(
            "--dry-run", action="store_true", help="перенести и откатить: только итог"
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="удалить уже перенесённые карточки (справочники остаются)",
        )

    def handle(self, *args, **options):
        if Person.objects.exists() and not options["replace"]:
            raise CommandError(
                "В базе уже есть учётные карточки. Перенос — только в пустую базу "
                "(или с --replace: карточки будут удалены и перенесены заново)."
            )
        # Пароль — из переменной окружения (для запуска без вопросов) или вводом
        password = os.getenv("LEGACY_DB_PASSWORD") or getpass.getpass(
            "Пароль к старой базе: "
        )
        try:
            tables = source.read(
                options["host"],
                options["port"],
                options["dbname"],
                options["user"],
                password,
            )
        except psycopg.Error as error:
            raise CommandError(f"Не удалось прочитать старую базу: {error}") from error

        try:
            with transaction.atomic():
                if options["replace"]:
                    Person.objects.all().delete()
                report = LegacyImporter(tables).run()
                if options["dry_run"]:
                    raise DryRun
        except DryRun:
            self.stdout.write(
                self.style.WARNING("Пробный перенос: изменения отменены.")
            )
        for line in report.lines():
            self.stdout.write(line)
        if not options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Перенос завершён."))
