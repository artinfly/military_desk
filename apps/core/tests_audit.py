"""Регрессии, найденные при аудите: доступ, отбор, даты и безопасный Excel."""

from datetime import date
from io import BytesIO

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.accounts.roles import VIEWER
from apps.accounts.testing import make_user
from apps.military.models import CommissariatRegistration, MilitaryRecord
from apps.personnel.models import AdditionalAttribute, Address, Assignment
from apps.personnel.services import sort_people
from apps.personnel.tests import make_person
from apps.references import models as ref
from apps.reports.excel import build_workbook
from apps.reports.services.common import without_external_part_timers


class AuditRegressionTests(TestCase):
    def test_formula_text_and_excel_types(self):
        rows = iter(
            [['=HYPERLINK("https://example.org")', "00123", date(2026, 1, 2), 15]]
        )
        sheet = load_workbook(
            BytesIO(
                build_workbook("Проверка", ["Текст", "Номер", "Дата", "Число"], rows)
            )
        ).active
        self.assertEqual(sheet["A2"].data_type, "s")
        self.assertTrue(sheet["A2"].value.startswith("=HYPERLINK"))
        self.assertEqual(sheet["B2"].value, "00123")
        self.assertEqual(sheet["C2"].number_format, "DD.MM.YYYY")
        self.assertEqual(sheet["D2"].value, 15)

    def test_invalid_filters_do_not_export_everybody(self):
        self.client.force_login(make_user("viewer", VIEWER))
        make_person()
        for params in (
            {"department": "not-an-id"},
            {"status": "bad"},
            {"department": "999999999"},
        ):
            response = self.client.get(reverse("personnel:list"), params)
            self.assertEqual(response.context["paginator"].count, 0)
            self.assertContains(response, "Исправьте условия поиска")
            self.assertEqual(
                self.client.get(reverse("reports:filter"), params).status_code, 400
            )
        self.assertEqual(
            self.client.get(reverse("personnel:list")).context["paginator"].count, 1
        )
        self.assertEqual(self.client.get(reverse("reports:filter")).status_code, 200)

    def test_person_only_permission_cannot_infer_military_or_export(self):
        user = make_user("person-only")
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="personnel", codename="view_person"
            )
        )
        person = make_person()
        MilitaryRecord.objects.create(
            person=person, reservation_document="SECRET-ORDER-9", is_reserved=True
        )
        self.client.force_login(user)
        response = self.client.get(reverse("personnel:list"))
        self.assertContains(response, person.full_name)
        self.assertNotContains(response, "SECRET-ORDER-9")
        self.assertNotContains(response, "Выгрузить в Excel")
        self.assertNotContains(response, 'name="reserved"')
        response = self.client.get(reverse("personnel:list"), {"reserved": "on"})
        self.assertEqual(response.context["paginator"].count, 0)
        self.assertEqual(self.client.get(reverse("reports:filter")).status_code, 403)

    def test_military_permission_alone_cannot_export_personal_data(self):
        user = make_user("military-only")
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="military", codename="view_militaryrecord"
            )
        )
        self.client.force_login(user)
        for slug in (
            "reservation",
            "hired",
            "reserved-dismissed",
            "conscripts",
            "headcount",
            "vus",
        ):
            self.assertEqual(
                self.client.get(reverse("reports:download", args=[slug])).status_code,
                403,
                slug,
            )
        self.assertNotContains(self.client.get("/"), "Военнообязанных")

    def test_period_validation(self):
        for model in (
            Assignment,
            Address,
            AdditionalAttribute,
            CommissariatRegistration,
        ):
            with self.subTest(model=model.__name__):
                obj = model(date_from=date(2026, 2, 1), date_to=date(2026, 1, 1))
                with self.assertRaises(ValidationError) as raised:
                    obj.clean()
                self.assertIn("date_to", raised.exception.message_dict)
                obj.date_to = obj.date_from
                obj.clean()
                obj.date_to = None
                obj.clean()

    def test_latest_order_null_dates_and_ties(self):
        person = make_person()
        Assignment.objects.create(person=person, order_kind="Не датирован")
        Assignment.objects.create(
            person=person, order_kind="по совм. внеш.", order_date=date(2026, 1, 1)
        )
        self.assertFalse(
            without_external_part_timers(type(person).objects.all()).exists()
        )
        Assignment.objects.create(
            person=person, order_kind="Приём", order_date=date(2026, 1, 1)
        )
        self.assertTrue(
            without_external_part_timers(type(person).objects.all()).exists()
        )

    def test_sort_normalized_and_stable(self):
        first = make_person("2")
        second = make_person("1")
        for sort in ("", "--name", "unknown", "name"):
            people, active = sort_people(type(first).objects.all(), sort)
            self.assertEqual(active, "name")
            self.assertEqual(
                list(people.values_list("pk", flat=True)), [first.pk, second.pk]
            )

    def test_legacy_document_code_and_real_name_marked(self):
        from apps.references.reservation import mark_reservation_flags

        by_code = ref.RegistrationDocument.objects.create(
            name="Перенесённый документ", code="3767"
        )
        by_name = ref.RegistrationDocument.objects.create(
            name="Справка взамен военного билета"
        )
        ticket = ref.RegistrationDocument.objects.create(name="Военный билет")
        mark_reservation_flags(ref.MilitarySpeciality, ref.RegistrationDocument)
        for document in (by_code, by_name):
            document.refresh_from_db()
            self.assertTrue(document.in_reservation_appendix)
        ticket.refresh_from_db()
        self.assertFalse(ticket.in_reservation_appendix)

    def test_authenticated_pages_and_exports_are_not_cached(self):
        self.client.force_login(make_user("cache-viewer", VIEWER))
        for url in (reverse("personnel:list"), reverse("reports:filter")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn("private", response["Cache-Control"])
            self.assertIn("no-store", response["Cache-Control"])

    def test_data_audit_is_read_only_and_has_no_personal_output(self):
        from django.core.management import call_command

        person = make_person(snils="00123456789", last_name="СекретнаяФамилия")
        original = person.updated_at
        out = __import__("io").StringIO()
        call_command("audit_data", stdout=out)
        self.assertIn("Карточек всего: 1", out.getvalue())
        self.assertNotIn(person.snils, out.getvalue())
        self.assertNotIn(person.last_name, out.getvalue())
        person.refresh_from_db()
        self.assertEqual(person.updated_at, original)

    def test_military_change_permission_cannot_delete_dismissal_history(self):
        user = make_user("limited-operator")
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="military", codename="change_militaryrecord"
            )
        )
        self.client.force_login(user)
        self.assertNotContains(
            self.client.get(reverse("military:operations")),
            "Обновление спец. уволенных",
        )
        self.assertEqual(
            self.client.post(
                reverse("military:operations"), {"action": "dismissed"}
            ).status_code,
            403,
        )
