"""Загрузка крупных кадровых файлов без ограничения времени HTTP-запроса."""

import hashlib
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.legacy.exchange import import_extended, parse_extended
from apps.legacy.hr_importer import import_hr
from apps.legacy.hr_source import parse_hr
from apps.legacy.permissions import IMPORT_PERMISSIONS


class Command(BaseCommand):
    help = "Загрузить vus.csv и/или vus_ext.csv с журналом и пробным режимом"

    def add_arguments(self, parser):
        parser.add_argument("--file", help="кадровая выгрузка vus.csv")
        parser.add_argument("--extended", help="дополнительная выгрузка vus_ext.csv")
        parser.add_argument(
            "--user",
            required=True,
            help="логин оператора, от которого выполняется загрузка",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="проверить с откатом изменений"
        )

    def handle(self, *args, **options):
        if not options["file"] and not options["extended"]:
            raise CommandError("Укажите --file и/или --extended")
        actor = (
            get_user_model()
            .objects.filter(username=options["user"], is_active=True)
            .first()
        )
        if actor is None or not actor.has_perms(IMPORT_PERMISSIONS):
            raise CommandError(
                "Не найден активный пользователь с правами кадровой загрузки"
            )
        inputs = []
        try:
            for option, parse, apply in (
                ("file", parse_hr, import_hr),
                ("extended", parse_extended, import_extended),
            ):
                if options[option]:
                    with Path(options[option]).open("rb") as file:
                        checksum = hashlib.file_digest(file, "sha256").hexdigest()
                        file.seek(0)
                        inputs.append((parse(file), apply, checksum))
            with transaction.atomic():
                for rows, apply, checksum in inputs:
                    report = apply(rows, actor, checksum)
                    for line in report.lines():
                        self.stdout.write(line)
                if options["dry_run"]:
                    transaction.set_rollback(True)
        except (OSError, ValidationError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS(
                "Проверка завершена, изменения отменены."
                if options["dry_run"]
                else "Кадровые данные загружены."
            )
        )
