import io
import struct
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import override_settings, SimpleTestCase, TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.accounts.roles import ADMIN, OPERATOR, VIEWER
from apps.accounts.testing import make_user
from apps.military.models import MilitaryRecord
from apps.personnel.models import Education, Person
from apps.personnel.tests import make_person
from apps.references.models import MilitaryDuty, SpecialAccountType

from .dbf import DbfTable, convert_dbf, csv_bytes, spr_dbf
from .dump import read_dump, unescape
from .exchange import import_extended, parse_extended
from .hr_archive import import_archive
from .hr_importer import import_hr
from .hr_source import BK_COUNT_LABEL, parse_hr
from .importer import LegacyImporter
from .models import ImportBatch, PersonnelCode, ProfessionCode, SourceRow
from .tests import card as legacy_card
from .tests import tables as legacy_tables


def hr_file(**changes):
    values = [""] * 286
    defaults = {
        1: "101",
        2: "000001",
        3: "Тестов",
        4: "Иван",
        8: "М",
        10: "01.01.1990",
        11: "01.01.2020",
        12: "31.12.2099",
        13: "1",
        14: "Военнообязанный",
        63: "503",
        64: "DEMO-GENERAL",
        17: "201",
        47: "123-456-789 00",
        222: "301",
        223: "Высшее",
        227: "Университет",
    }
    defaults.update({int(k): v for k, v in changes.items()})
    for index, value in defaults.items():
        values[index] = value
    return SimpleUploadedFile(
        "vus.csv", ("header\n" + "\t".join(values) + "\n").encode("cp1251")
    )


def hr_zip(*entries):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return SimpleUploadedFile("cadres.zip", buffer.getvalue())


def main_csv(bk=None):
    data = hr_file(**{"285": "77"}).read().rstrip(b"\n")
    return data + (f"\t{bk}\t\t".encode() if bk is not None else b"") + b"\n"


def extended_csv():
    return "Табельный\tОКПДТР\tКатегория\n000001\t123456\tРабочий\n".encode("cp1251")


def dbf_file(fields, rows):
    header_length = 33 + 32 * len(fields)
    record_length = 1 + sum(size for name, kind, size in fields)
    header = bytearray(header_length)
    header[0] = 3
    struct.pack_into("<IHH", header, 4, 0, header_length, record_length)
    for index, (name, kind, size) in enumerate(fields):
        position = 32 + index * 32
        header[position : position + len(name)] = name.encode("ascii")
        header[position + 11] = ord(kind)
        header[position + 16] = size
    header[-1] = 13
    table = DbfTable(bytes(header))
    records = []
    for row in rows:
        record = bytearray(b" " * record_length)
        for name, value in row.items():
            table.set(record, name, value)
        records.append(record)
    return table.build(records)


class DumpTests(SimpleTestCase):
    def test_copy_null_escapes_types_and_no_sql_execution(self):
        source = """CREATE TABLE public.account_cards (
    account_id integer,
    birth_date date,
    is_svo boolean,
    surname text
);
COPY public.account_cards (account_id, birth_date, is_svo, surname) FROM stdin;
1\t1990-01-01\tf\tTest\\tName
\\.
COPY public.personal_data (id) FROM stdin;
\\.
COPY public.mil_ids_info (id) FROM stdin;
\\.
DROP TABLE public.account_cards;
"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "stol.sql"
            path.write_text(source, encoding="utf-8")
            row = read_dump(path)["account_cards"][0]
        self.assertEqual(row["account_id"], 1)
        self.assertFalse(row["is_svo"])
        self.assertEqual(row["birth_date"], date(1990, 1, 1))
        self.assertEqual(row["surname"], "Test\tName")
        self.assertEqual(unescape(r"one\\two\nthree"), "one\\two\nthree")


@override_settings(
    MILITARY_ACCOUNT_CODES={
        "reserved": "DEMO-BOOK",
        "team": "DEMO-TEAM",
        "general": "DEMO-GENERAL",
    }
)
class HRTests(TestCase):
    def setUp(self):
        self.actor = make_user("operator", OPERATOR)

    def test_dry_run_rolls_back_all_sections_and_references(self):
        report = import_hr(parse_hr(hr_file()), self.actor, "hash", dry_run=True)
        self.assertTrue(report.counts)
        self.assertFalse(Person.objects.exists())
        self.assertFalse(Education.objects.exists())
        self.assertFalse(SourceRow.objects.exists())
        self.assertFalse(ImportBatch.objects.exists())
        self.assertFalse(MilitaryDuty.objects.exists())

    def test_repeat_updates_sections_without_duplicates_and_preserves_reservation(self):
        import_hr(parse_hr(hr_file()), self.actor, "first")
        person = Person.objects.get()
        person.phone = "manual"
        person.save()
        record = person.military
        record.is_reserved = True
        record.reservation_document = "12/26"
        record.document_number = "manual-number"
        record.special_account_type = SpecialAccountType.objects.create(
            code="DEMO-BOOK", name="Бронь"
        )
        record.save()
        import_hr(parse_hr(hr_file(**{"227": "Новое название"})), self.actor, "second")
        person.refresh_from_db()
        record.refresh_from_db()
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(Education.objects.count(), 1)
        self.assertEqual(person.education.get().institution, "Новое название")
        self.assertEqual(person.phone, "manual")
        self.assertTrue(record.is_reserved)
        self.assertEqual(record.reservation_document, "12/26")
        self.assertEqual(record.document_number, "manual-number")
        self.assertEqual(record.special_account_type.code, "DEMO-BOOK")
        self.assertEqual(person.updated_by_id, self.actor.pk)

    def test_bad_file_does_not_change_database(self):
        with self.assertRaises(ValidationError):
            parse_hr(hr_file(**{"10": "31.02.2026"}))
        self.assertFalse(Person.objects.exists())

    def test_extended_dry_run_and_repeat(self):
        person = make_person("000001")
        file = SimpleUploadedFile(
            "vus_ext.csv",
            "Табельный\tОКПДТР\tКатегория\n000001\t123456\tРабочий\n".encode("cp1251"),
        )
        rows = parse_extended(file)
        import_extended(rows, self.actor, "hash", dry_run=True)
        self.assertFalse(PersonnelCode.objects.exists())
        import_extended(rows, self.actor, "hash")
        import_extended(rows, self.actor, "hash")
        self.assertEqual(PersonnelCode.objects.get().person, person)
        self.assertEqual(PersonnelCode.objects.count(), 1)

    def test_viewer_cannot_upload_and_unconfirmed_import_is_rejected(self):
        url = reverse("legacy:exchange")
        self.client.force_login(make_user("viewer", VIEWER))
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(
            url, {"file": hr_zip(("vus.csv", main_csv())), "action": "import"}
        )
        self.assertContains(response, "Отметьте применение изменений")
        self.assertFalse(Person.objects.exists())
        self.assertEqual(self.client.get(reverse("legacy:codes")).status_code, 403)

    def test_web_preview_and_apply(self):
        self.client.force_login(self.actor)
        url = reverse("legacy:exchange")
        response = self.client.post(
            url, {"file": hr_zip(("vus.csv", main_csv())), "action": "preview"}
        )
        self.assertContains(response, "изменения не сохранены")
        self.assertFalse(Person.objects.exists())
        response = self.client.post(
            url,
            {
                "file": hr_zip(("vus.csv", main_csv())),
                "action": "import",
                "confirm": "on",
            },
        )
        self.assertContains(response, "Данные загружены")
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(len(ImportBatch.objects.get().checksum), 64)

    def test_archive_and_report_use_last_applied_bk(self):
        self.client.force_login(self.actor)
        url = reverse("legacy:exchange")
        for action, value in (("import", "125"), ("preview", "999"), ("import", None)):
            response = self.client.post(
                url,
                {
                    "action": action,
                    "confirm": "on",
                    "file": hr_zip(
                        ("Данные/VUS.CSV", main_csv(value)),
                        ("Данные/vus_ext.csv", extended_csv()),
                    ),
                },
            )
            self.assertContains(
                response,
                "изменения не сохранены" if action == "preview" else "Данные загружены",
            )
        self.assertEqual(ImportBatch.objects.count(), 2)
        self.assertEqual(
            ImportBatch.objects.filter(counts__has_key=BK_COUNT_LABEL)
            .get()
            .counts[BK_COUNT_LABEL],
            125,
        )
        self.assertEqual(PersonnelCode.objects.get().profession.code, "123456")
        response = self.client.get(reverse("reports:download", args=["headcount"]))
        rows = dict(load_workbook(io.BytesIO(response.content)).active.values)
        self.assertEqual(rows[BK_COUNT_LABEL], 125)
        import_archive(hr_zip(("vus.csv", main_csv("0"))), self.actor)
        response = self.client.get(reverse("reports:download", args=["headcount"]))
        rows = dict(load_workbook(io.BytesIO(response.content)).active.values)
        self.assertEqual(rows[BK_COUNT_LABEL], 0)
        self.assertEqual(PersonnelCode.objects.count(), 1)

    def test_invalid_archive_rejects_whole_import(self):
        self.client.force_login(self.actor)
        url = reverse("legacy:exchange")
        cases = [
            (hr_zip(("vus_ext.csv", extended_csv())), "нет обязательного"),
            (
                hr_zip(("vus.csv", main_csv()), ("x/VUS.csv", main_csv())),
                "несколько файлов",
            ),
            (hr_zip(("vus.csv", main_csv("invalid"))), "целое число БК"),
            (
                hr_zip(("vus.csv", main_csv("42")), ("vus_ext.csv", b"bad")),
                "vus_ext.csv:",
            ),
            (SimpleUploadedFile("broken.zip", b"broken"), "Не удалось прочитать ZIP"),
        ]
        for file, message in cases:
            with self.subTest(message=message):
                response = self.client.post(
                    url, {"action": "import", "confirm": "on", "file": file}
                )
                self.assertContains(response, message)
                self.assertFalse(Person.objects.exists())
                self.assertFalse(ImportBatch.objects.exists())

    def test_error_during_second_import_rolls_back_first(self):
        file = hr_zip(("vus.csv", main_csv("42")), ("vus_ext.csv", extended_csv()))
        with patch(
            "apps.legacy.hr_archive.import_extended",
            side_effect=ValidationError("ошибка"),
        ):
            with self.assertRaises(ValidationError):
                import_archive(file, self.actor)
        self.assertFalse(Person.objects.exists())
        self.assertFalse(ImportBatch.objects.exists())

    def test_bk_may_be_in_a_separate_trailing_row(self):
        content = main_csv() + b"\t" * 286 + b"1234\t\n"
        parsed = parse_hr(io.BytesIO(content))
        self.assertEqual(parsed["__bk_count__"], 1234)
        self.assertEqual(len(parsed["account_cards"]), 1)

    def test_command_dry_run_and_invalid_second_file_are_atomic(self):
        with TemporaryDirectory() as directory:
            main = Path(directory) / "vus.csv"
            extended = Path(directory) / "vus_ext.csv"
            main.write_bytes(hr_file().read())
            extended.write_bytes(b"bad header\n")
            call_command(
                "sync_hr",
                "--file",
                str(main),
                "--user",
                self.actor.username,
                "--dry-run",
                stdout=io.StringIO(),
            )
            self.assertFalse(Person.objects.exists())
            with self.assertRaises(CommandError):
                call_command(
                    "sync_hr",
                    "--file",
                    str(main),
                    "--extended",
                    str(extended),
                    "--user",
                    self.actor.username,
                    stdout=io.StringIO(),
                )
            self.assertFalse(Person.objects.exists())

    def test_initial_import_includes_first_department_codes(self):
        data = legacy_tables(
            account_cards=[legacy_card(1, "1001")],
            spr=[{"da1": "123456", "ns": "12"}],
            emps_spr=[{"account_card_id": 1, "code": "123456", "cat": "Рабочий"}],
        )
        LegacyImporter(data).run()
        code = PersonnelCode.objects.select_related("profession").get()
        self.assertEqual(code.profession.row_number, 12)
        self.assertEqual(code.category, "Рабочий")


@override_settings(
    MILITARY_ACCOUNT_CODES={"reserved": "DB", "team": "DT", "general": "DG"}
)
class DbfTests(TestCase):
    def setUp(self):
        self.person = make_person("000001")
        duty = MilitaryDuty.objects.create(name="Военнообязанный")
        account = SpecialAccountType.objects.create(code="DB", name="Бронь")
        MilitaryRecord.objects.create(
            person=self.person, duty=duty, special_account_type=account
        )

    def test_proff_rules_and_raw_fields_are_preserved(self):
        fields = [
            ("TAB_N", "C", 7),
            ("OKPD", "N", 13),
            ("PRIZNAK", "N", 8),
            ("CATEG_ID", "N", 8),
            ("MIL", "C", 1),
            ("UCHET", "C", 2),
        ]
        base = dict(
            TAB_N="000001",
            OKPD="123456",
            PRIZNAK="2.000000",
            CATEG_ID="1.000000",
            MIL="V",
            UCHET="DG",
        )
        raw = dbf_file(fields, [base, {**base, "MIL": "N"}, {**base, "OKPD": "bad"}])
        result = convert_dbf(raw, "proff")
        self.assertEqual((result.accepted, len(result.rejected)), (1, 2))
        output = DbfTable(result.content)
        record = next(output.records())[1]
        self.assertEqual(output.value(record, "UCHET"), "DB")
        self.assertEqual(output.value(record, "TAB_N"), "000001")
        self.assertEqual(output.value(record, "PRIZNAK"), "2")

    def test_kadr_duplicates_specuh_and_output_validation(self):
        fields = [
            ("TABNOM", "C", 7),
            ("ZK", "C", 1),
            ("MER", "C", 2),
            ("PROF", "C", 6),
            ("SPECUH", "C", 1),
            ("SOSTAV", "C", 2),
        ]
        row = dict(
            TABNOM="000001", ZK="", MER="01", PROF="123456", SPECUH="", SOSTAV="1"
        )
        result = convert_dbf(dbf_file(fields, [row, row]), "kadr")
        self.assertEqual((result.accepted, result.duplicates), (1, 1))
        output = DbfTable(result.content)
        self.assertEqual(output.value(next(output.records())[1], "SPECUH"), "2")
        self.assertEqual(result.missing_codes, {"123456"})
        result = convert_dbf(dbf_file(fields, [{**row, "SOSTAV": ""}]), "kadr")
        self.assertEqual(result.accepted, 0)

    def test_spr_roundtrip_and_truncated_dbf_rejected(self):
        table = DbfTable(spr_dbf([(12, "123456")]))
        record = next(table.records())[1]
        self.assertEqual(table.value(record, "NS"), "12")
        self.assertEqual(table.value(record, "DA1"), "123456")
        with self.assertRaises(ValidationError):
            DbfTable(spr_dbf([(12, "123456")])[:-5])

    def test_csv_error_report_does_not_create_spreadsheet_formulas(self):
        result = csv_bytes(["Табельный номер"], [["=1+1"]]).decode("utf-8-sig")
        self.assertIn("'=1+1", result)


class WorkerCategoryTests(TestCase):
    def test_edit_category_keeps_search_and_validates_choices(self):
        self.client.force_login(make_user("category-admin", ADMIN))
        code = ProfessionCode.objects.create(code="20629", row_number=1)
        url = reverse("legacy:codes") + "?q=20629"
        page = self.client.get(url)
        self.assertContains(page, "Руководители")
        self.assertRedirects(
            self.client.post(url, {"code": code.pk, "row_number": "12"}), url
        )
        code.refresh_from_db()
        self.assertEqual(code.row_number, 12)
        response = self.client.post(url, {"code": code.pk, "row_number": "11"})
        self.assertEqual(response.status_code, 200)
        code.refresh_from_db()
        self.assertEqual(code.row_number, 12)
