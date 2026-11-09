"""Загрузка дополнительных кадровых кодов (vus_ext.csv)."""

import csv
import io
import re

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.personnel.models import Person

from .hr_source import decode_upload
from .models import ImportBatch, PersonnelCode, ProfessionCode
from .report import Report


def parse_extended(file):
    rows = csv.DictReader(
        io.StringIO(decode_upload(file)), delimiter="\t", quoting=csv.QUOTE_NONE
    )
    if not {"Табельный", "ОКПДТР", "Категория"} <= set(rows.fieldnames or ()):
        raise ValidationError(
            "Нужны колонки «Табельный», «ОКПДТР» и «Категория» (TSV)."
        )
    result = {}
    for number, row in enumerate(rows, 2):
        tab = (row.get("Табельный") or "").strip()
        code = (row.get("ОКПДТР") or "").strip()
        category = (row.get("Категория") or "").strip()
        if not tab and not code:
            continue
        if (
            not tab
            or (code and not re.fullmatch(r"[0-9]{6}", code))
            or len(category) > 100
        ):
            raise ValidationError(
                f"Строка {number}: проверьте табельный номер, шестизначный ОКПДТР и категорию."
            )
        result[tab] = (code, category)
    if not result:
        raise ValidationError("В дополнительной выгрузке нет данных.")
    return result


def import_extended(rows, actor, checksum, *, dry_run=False):
    report = Report()
    with transaction.atomic():
        people = {
            p.tab_number: p
            for p in Person.objects.filter(tab_number__in=rows)
            .order_by("pk")
            .select_for_update()
        }
        codes = {code for code, category in rows.values() if code}
        ProfessionCode.objects.bulk_create(
            [ProfessionCode(code=c) for c in codes], ignore_conflicts=True
        )
        professions = {p.code: p for p in ProfessionCode.objects.filter(code__in=codes)}
        records = [
            PersonnelCode(
                person=p,
                profession=professions.get(rows[tab][0]),
                category=rows[tab][1],
            )
            for tab, p in people.items()
        ]
        PersonnelCode.objects.bulk_create(
            records,
            update_conflicts=True,
            update_fields=("profession", "category"),
            unique_fields=("person",),
        )
        report.count("Кадровые коды сопоставлены", len(records))
        report.count("Табельные номера не найдены", len(rows) - len(records))
        report.count(
            "Коды без строки NS",
            sum(p.row_number is None for p in professions.values()),
        )
        report.count(
            "Записи без ОКПДТР", sum(not code for code, category in rows.values())
        )
        if not dry_run:
            ImportBatch.objects.create(
                created_by=actor,
                kind="extended",
                checksum=checksum,
                counts=report.counts,
            )
        else:
            transaction.set_rollback(True)
    return report
