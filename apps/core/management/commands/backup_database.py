"""Резервная копия PostgreSQL средствами pg_dump; существующий файл не заменяется."""

import gzip
import io
import os
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, transaction


class Command(BaseCommand):
    help = "Создать резервную копию текущей базы (.dump), не заменяя существующие файлы"

    def add_arguments(self, parser):
        parser.add_argument("output", help="путь к новому файлу .dump")
        parser.add_argument(
            "--format",
            choices=("postgres", "json"),
            default="postgres",
            help="postgres — pg_dump; json — данные приложения в .json.gz",
        )

    def handle(self, *args, **options):
        executable = shutil.which("pg_dump")
        if not executable and options["format"] == "postgres":
            raise CommandError(
                "pg_dump не найден. Добавьте PostgreSQL/bin в PATH или используйте --format json с файлом .json.gz."
            )
        output = Path(options["output"]).resolve()
        database = settings.DATABASES["default"]
        environment = os.environ.copy()
        for key, name in (
            ("PGHOST", "HOST"),
            ("PGPORT", "PORT"),
            ("PGUSER", "USER"),
            ("PGPASSWORD", "PASSWORD"),
            ("PGDATABASE", "NAME"),
        ):
            environment[key] = str(database.get(name, ""))
        try:
            # xb исключает случайную перезапись копии, даже при одновременных запусках.
            file = output.open("xb")
        except OSError as error:
            raise CommandError(
                "Не удалось создать новый файл копии. Проверьте папку и имя файла."
            ) from error
        succeeded = False
        try:
            with file:
                if options["format"] == "json":
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                            )
                        with gzip.GzipFile(
                            fileobj=file, mode="wb", mtime=0
                        ) as compressed:
                            with io.TextIOWrapper(
                                compressed, encoding="utf-8"
                            ) as stream:
                                call_command(
                                    "dumpdata",
                                    exclude=("sessions.session", "admin.logentry"),
                                    use_natural_foreign_keys=True,
                                    use_natural_primary_keys=True,
                                    stdout=stream,
                                )
                else:
                    subprocess.run(
                        [executable, "--format=custom", "--no-password"],
                        stdout=file,
                        stderr=subprocess.PIPE,
                        env=environment,
                        check=True,
                    )
            succeeded = True
        except (
            OSError,
            subprocess.CalledProcessError,
            DatabaseError,
            CommandError,
        ) as error:
            raise CommandError(
                "Не удалось создать копию. Проверьте доступ к базе и выбранный формат."
            ) from error
        finally:
            if not succeeded:
                output.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS(f"Резервная копия создана: {output}"))
