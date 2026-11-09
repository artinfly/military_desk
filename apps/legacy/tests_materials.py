"""Необязательная проверка локальных материалов: только во временной тестовой БД.

MILITARY_LEGACY_MATERIALS — каталог «Военный стол — материалы».
MILITARY_LEGACY_DUMP — путь к stol.sql. Файлы не входят в репозиторий.
"""

import os
from pathlib import Path
from unittest import skipUnless

from django.test import TestCase

from apps.accounts.roles import OPERATOR
from apps.accounts.testing import make_user
from apps.personnel import models as personnel
from apps.personnel.models import Person

from .dbf import DbfTable, convert_dbf
from .dump import read_dump
from .exchange import import_extended, parse_extended
from .hr_importer import import_hr
from .hr_source import parse_hr
from .importer import LegacyImporter
from .models import PersonnelCode, ProfessionCode


@skipUnless(os.getenv("MILITARY_LEGACY_DUMP"), "Локальная SQL-выгрузка не указана")
class RealDumpTests(TestCase):
    def test_all_active_cards_and_sections(self):
        tables = read_dump(os.environ["MILITARY_LEGACY_DUMP"])
        report = LegacyImporter(tables).run()
        expected = {
            r["tab_number"].strip()
            for r in tables["account_cards"]
            if str(r.get("delete_bit")) != "1"
        }
        self.assertEqual(Person.objects.count(), len(expected))
        self.assertEqual(
            Person.objects.filter(military__isnull=False).count(), len(expected)
        )
        self.assertGreater(report.counts["Образование"], 10000)
        self.assertGreater(ProfessionCode.objects.count(), 1000)


@skipUnless(
    os.getenv("MILITARY_LEGACY_MATERIALS"), "Локальные исходные файлы не указаны"
)
class RealExchangeTests(TestCase):
    def test_hr_and_dbf_materials(self):
        root = Path(os.environ["MILITARY_LEGACY_MATERIALS"]) / "as_stol" / "out"
        archive = root / "Выгрузка_old" / "03.11.2026"
        actor = make_user("operator", OPERATOR)
        if os.getenv("MILITARY_LEGACY_DUMP"):
            LegacyImporter(read_dump(os.environ["MILITARY_LEGACY_DUMP"])).run()
        with (archive / "vus.csv").open("rb") as file:
            tables = parse_hr(file)
        import_hr(tables, actor, "integration")
        self.assertGreaterEqual(Person.objects.count(), len(tables["account_cards"]))
        models = (
            Person,
            personnel.IdentityDocument,
            personnel.Address,
            personnel.Relative,
            personnel.Education,
            personnel.Assignment,
            personnel.AdditionalAttribute,
        )
        counts = {model: model.objects.count() for model in models}
        import_hr(tables, actor, "integration-repeat")
        for model in models:
            self.assertEqual(model.objects.count(), counts[model], model._meta.label)
        with (archive / "vus_ext.csv").open("rb") as file:
            extended = parse_extended(file)
        import_extended(extended, actor, "integration-ext")
        self.assertGreater(PersonnelCode.objects.count(), 10000)
        for name, kind in (("proff.dbf", "proff"), ("KADR_EDAY.dbf", "kadr")):
            converted = convert_dbf((root / "dbf" / name).read_bytes(), kind)
            self.assertGreater(converted.accepted, 0)
            self.assertEqual(DbfTable(converted.content).count, converted.accepted)
