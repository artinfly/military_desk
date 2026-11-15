"""Проверка ZIP и атомарная загрузка кадровой выгрузки."""

import hashlib
import zlib
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError
from django.db import transaction

from .exchange import import_extended, parse_extended
from .hr_importer import import_hr
from .hr_source import BK_COUNT_LABEL, MAX_FILE_SIZE, parse_hr
from .models import ImportBatch

MAIN_NAME = "vus.csv"
EXTENDED_NAME = "vus_ext.csv"


def parse_archive(file):
    file.seek(0, 2)
    if file.tell() > MAX_FILE_SIZE:
        raise ValidationError("Размер архива превышает 200 МБ.")
    try:
        with ZipFile(file) as archive:
            selected = {}
            for member in archive.infolist():
                name = PurePosixPath(member.filename.replace("\\", "/")).name.lower()
                if member.is_dir() or name not in (MAIN_NAME, EXTENDED_NAME):
                    continue
                if name in selected:
                    raise ValidationError(
                        f"В архиве несколько файлов {name}. Оставьте один."
                    )
                selected[name] = member
            if MAIN_NAME not in selected:
                raise ValidationError("В архиве нет обязательного файла vus.csv.")
            if sum(member.file_size for member in selected.values()) > MAX_FILE_SIZE:
                raise ValidationError("Размер CSV внутри архива превышает 200 МБ.")
            if any(member.flag_bits & 1 for member in selected.values()):
                raise ValidationError("Загрузите архив без пароля.")

            def read(name, parser):
                try:
                    with archive.open(selected[name]) as source:
                        return parser(source)
                except ValidationError as error:
                    raise ValidationError(
                        [f"{name}: {msg}" for msg in error.messages]
                    ) from error

            main = read(MAIN_NAME, parse_hr)
            extended = (
                read(EXTENDED_NAME, parse_extended)
                if EXTENDED_NAME in selected
                else None
            )
            return main, extended
    except (
        BadZipFile,
        EOFError,
        OSError,
        NotImplementedError,
        RuntimeError,
        zlib.error,
    ) as error:
        raise ValidationError("Не удалось прочитать ZIP. Проверьте архив.") from error


def import_archive(file, actor, *, dry_run=False):
    main, extended = parse_archive(file)
    file.seek(0)
    checksum = hashlib.file_digest(file, "sha256").hexdigest()
    with transaction.atomic():
        report = import_hr(main, actor, checksum, record_batch=False)
        if extended is not None:
            extra = import_extended(extended, actor, checksum, record_batch=False)
            for name, count in extra.counts.items():
                report.count(name, count)
            report.problems.extend(extra.problems)
        if BK_COUNT_LABEL not in report.counts:
            report.problem(
                "В vus.csv нет числа БК. Последнее сохранённое значение не изменится."
            )
        if dry_run:
            transaction.set_rollback(True)
        else:
            ImportBatch.objects.create(
                created_by=actor,
                kind="hr_zip" if extended is None else "hr_zip_extended",
                checksum=checksum,
                counts=report.counts,
            )
    return report
