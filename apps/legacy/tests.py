from datetime import date
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.military.models import CommissariatRegistration, MilitaryRecord
from apps.personnel.models import Address, Person
from apps.references import models as ref

from .importer import LegacyImporter
from .source import NO_END

# Колонки разделов, которые не важны для тестов, — пустые
SECTION_BLANKS = {
    "education": [
        "education_type",
        "institution_name",
        "edu_form",
        "speciality",
        "qualification",
        "educational_program",
        "training_direction",
        "admission_date",
        "graduation_date",
        "document",
        "series",
        "doc_num",
        "issue_date",
        "main_specialization",
        "note",
    ],
    "addresses": [
        "country",
        "index",
        "district",
        "apartment",
        "registration_date",
        "phone_code",
        "phone_number",
        "kladr_code",
        "okato",
        "oktmo",
        "ifns",
        "note",
        "from_date",
        "by_date",
    ],
}


def nsi(id_column, name_column, *names, start=1):
    return [
        {id_column: n, name_column: name, "delete_bit": "0"}
        for n, name in enumerate(names, start)
    ]


def card(account_id, tab, **fields):
    row = {
        "account_id": account_id,
        "tab_number": tab,
        "surname": "Петров",
        "name": "Пётр",
        "patronymic": "Петрович",
        "gender": "М",
        "birth_date": date(1990, 1, 1),
        "birth_place": "г. Энск",
        "family_status_id": None,
        "dismissal_date": NO_END,
        "employment_date": date(2015, 1, 1),
        "curr_dep": None,
        "curr_position": None,
        "hire_type": "",
        "hire_source": "",
        "is_svo": False,
        "mil_duty_id": 1,
        "mil_rank_id": None,
        "delete_bit": "0",
    }
    row.update(fields)
    return row


def tables(**extra):
    result = {
        "nsi_military_duties": nsi("mil_duty_id", "military_duty", "Военнообязанный"),
        "nsi_military_ranks": nsi("mil_rank_id", "military_rank", "Рядовой", "Капитан"),
        "nsi_specials": nsi("special_id", "special", "X4", "R7", "H9"),
        "nsi_mil_registration_docs": nsi(
            "mil_reg_doc_id",
            "mil_reg_document",
            "Паспорт гражданина РФ",
            "Временное удостоверение взамен военного билета",
        ),
        "nsi_vuses": nsi("vus_id", "vus", "100182", "450100"),
        "nsi_military_commissariarts": nsi(
            "military_commissariart_id", "military_commissariart", "Военкомат Энска"
        ),
        "nsi_departments": [
            {
                "id_department": 1,
                "name_department": "Цех 7",
                "dep_number": "007",
                "delete_bit": "0",
            },
            {
                "id_department": 2,
                "name_department": "Цех 7",
                "dep_number": "007",
                "delete_bit": "0",
            },
        ],
        "nsi_cities": [
            {"city_id": "660001", "city": "г. Энск", "delete_bit": "0"},
            {"city_id": "660002", "city": "г. Энск", "delete_bit": "1"},
        ],
        "nsi_houses": [{"id_house": "H1", "house_num": "12а"}],
    }
    result.update(extra)
    return result


class ReferencesTests(TestCase):
    def test_reference_mapping(self):
        LegacyImporter(tables()).run()
        self.assertEqual(
            set(ref.SpecialAccountType.objects.values_list("code", "name")),
            {("X4", "Спец. учёт"), ("R7", "Команда"), ("H9", "Общий учёт")},
        )
        self.assertEqual(ref.Department.objects.count(), 1)  # повтор цеха — одна запись
        self.assertEqual(ref.City.objects.count(), 2)  # одноимённые города — разные
        self.assertFalse(ref.City.objects.get(code="660002").is_active)
        self.assertTrue(ref.MilitaryRank.objects.get(name="Капитан").is_officer)
        self.assertTrue(
            ref.MilitarySpeciality.objects.get(name="450100").in_reservation_list
        )
        self.assertTrue(
            ref.RegistrationDocument.objects.get(
                name="Временное удостоверение взамен военного билета"
            ).in_reservation_appendix
        )
        # Повторный перенос не дублирует справочники
        LegacyImporter(tables()).run()
        self.assertEqual(ref.MilitarySpeciality.objects.count(), 2)


class PeopleTests(TestCase):
    def run_import(self, **extra):
        return LegacyImporter(tables(**extra)).run()

    def test_cards(self):
        report = self.run_import(
            account_cards=[
                card(1, "1001", dismissal_date=NO_END, curr_dep="007 Цех"),
                card(2, "1002", dismissal_date=date(2025, 3, 1), gender="Ж"),
                card(3, "1002"),  # повтор табельного номера
                card(4, "1004", delete_bit="1"),  # удалённая карточка
                card(5, "1005", gender="?"),
            ],
            personal_data=[
                {
                    "personal_data_id": 11,
                    "account_card_id": 1,
                    "snils": "123-456-789 01",
                    "inn": "",
                    "sitizenship": "РФ",
                    "phone": None,
                    "email": None,
                    "card_num": "77",
                    "delete_bit": "0",
                },
            ],
            personal_properties=[
                {
                    "personal_property_id": 1,
                    "personal_id": 11,
                    "document_type": 1,
                    "series": "6500",
                    "doc_number": "123456",
                    "issue_date": date(2010, 1, 1),
                    "place_doc": "ОВД",
                    "subdivision_code": "",
                    "valid_until": None,
                    "note": None,
                    "before_lastname": "Сидоров",
                    "date_change_lastname": date(2012, 1, 1),
                    "int_passport_series": "75",
                    "int_passport_number": "7654321",
                    "int_issue_by": None,
                    "int_from_date": None,
                    "int_by_date": None,
                    "delete_bit": "0",
                },
            ],
        )
        self.assertEqual(
            sorted(Person.objects.values_list("tab_number", flat=True)),
            ["1001", "1002", "1005"],
        )
        first = Person.objects.get(tab_number="1001")
        self.assertIsNone(first.dismissal_date)
        self.assertEqual(first.department.number, "007")
        self.assertEqual((first.snils, first.card_number), ("123-456-789 01", "77"))
        self.assertEqual(first.previous_last_name, "Сидоров")
        self.assertEqual(
            sorted(str(d.document_type) for d in first.documents.all()),
            ["Заграничный паспорт", "Паспорт гражданина РФ"],
        )
        self.assertEqual(Person.objects.get(tab_number="1002").gender, "Ж")
        self.assertEqual(len(report.problems), 2)  # повтор номера и неизвестный пол

    def test_military_and_sections(self):
        self.run_import(
            account_cards=[card(1, "1001", mil_rank_id=2)],
            mil_ids_info=[
                {
                    "account_card_id": 1,
                    "mil_reg_doc_id": 2,
                    "vus_id": 2,
                    "special_id": 1,
                    "mil_commissariat_id": 1,
                    "is_spec": True,
                    "spec_order": "15/24",
                    "mil_doc_series": "АВ",
                    "mil_doc_number": "1234567",
                    "nationality": "русский",
                    "delete_bit": "0",
                },
            ],
            com_history=[
                {
                    "account_card_id": 1,
                    "comm": 1,
                    "from_date": date(2010, 1, 1),
                    "by_date": NO_END,
                    "is_deleted": False,
                },
                {
                    "account_card_id": 1,
                    "comm": 1,
                    "from_date": date(2000, 1, 1),
                    "by_date": date(2009, 1, 1),
                    "is_deleted": True,
                },
            ],
            addresses=[
                {
                    "account_card_id": 1,
                    "type_address": None,
                    "region": None,
                    "city": "660001",
                    "street": None,
                    "house": "H1",
                    "delete_bit": "0",
                    **dict.fromkeys(SECTION_BLANKS["addresses"]),
                },
            ],
            assigments=[
                {
                    "account_card_id": 1,
                    "division": 1,
                    "job_title": "Токарь",
                    "kind_order": "Приём",
                    "order_date": date(2015, 1, 1),
                    "from_date": date(2015, 1, 1),
                    "by_date": NO_END,
                    "start_date": None,
                    "finish_date": NO_END,
                    "rank": "",
                    "employee_cat": "",
                    "employee_status": None,
                    "order_num": "1",
                    "delete_bit": "0",
                },
            ],
        )
        record = MilitaryRecord.objects.get()
        self.assertEqual(str(record.rank), "Капитан")
        self.assertEqual(record.special_account_type.code, "X4")
        self.assertTrue(record.is_reserved)
        self.assertEqual(record.person.nationality, "русский")
        registration = CommissariatRegistration.objects.get()
        self.assertIsNone(registration.date_to)
        self.assertEqual(Address.objects.get().house, "12а")
        self.assertEqual(record.person.position, "Токарь")


class CommandTests(TestCase):
    def test_dry_run_and_refusal(self):
        data = tables(account_cards=[card(1, "1001")])
        out = StringIO()
        with (
            mock.patch("apps.legacy.source.read", return_value=data),
            mock.patch.dict("os.environ", {"LEGACY_DB_PASSWORD": "x"}),
        ):
            call_command(
                "import_legacy", "--host", "h", "--user", "u", "--dry-run", stdout=out
            )
            self.assertIn("Учётные карточки: 1", out.getvalue())
            self.assertFalse(Person.objects.exists())

            call_command(
                "import_legacy", "--host", "h", "--user", "u", stdout=StringIO()
            )
            self.assertEqual(Person.objects.count(), 1)
            with self.assertRaises(CommandError):
                call_command("import_legacy", "--host", "h", "--user", "u")
            call_command(
                "import_legacy",
                "--host",
                "h",
                "--user",
                "u",
                "--replace",
                stdout=StringIO(),
            )
            self.assertEqual(Person.objects.count(), 1)
