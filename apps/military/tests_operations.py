from datetime import date
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from apps.accounts.roles import OPERATOR, VIEWER
from apps.accounts.testing import make_user
from apps.personnel.tests import make_person
from apps.references import models as ref

from . import services
from .models import MilitaryRecord, ReservationDismissal


def xlsx_file(values, name="snils.xlsx"):
    book = Workbook()
    sheet = book.active
    sheet.append(["СНИЛС"])
    for value in values:
        sheet.append([value])
    content = BytesIO()
    book.save(content)
    return SimpleUploadedFile(name, content.getvalue())


class OperationServicesTests(TestCase):
    def setUp(self):
        self.team = ref.SpecialAccountType.objects.create(name="Команда", code="R7")
        self.general = ref.SpecialAccountType.objects.create(
            name="Общий учёт", code="H9"
        )

    def record(self, tab, **kwargs):
        person_fields = {
            key: kwargs.pop(key) for key in ("snils", "dismissal_date") if key in kwargs
        }
        person = make_person(tab, **person_fields)
        return MilitaryRecord.objects.create(person=person, **kwargs)

    def test_change_account_type_skips_reserved(self):
        free = self.record("1", special_account_type=self.team)
        reserved = self.record("2", special_account_type=self.team, is_reserved=True)
        self.assertEqual(services.change_account_type(self.team, self.general), 1)
        free.refresh_from_db()
        reserved.refresh_from_db()
        self.assertEqual(free.special_account_type, self.general)
        self.assertEqual(reserved.special_account_type, self.team)

    def test_change_account_type_to_empty(self):
        free = self.record("1", special_account_type=self.team)
        services.change_account_type(self.team, None)
        free.refresh_from_db()
        self.assertIsNone(free.special_account_type)

    def test_update_reserved_dismissed(self):
        dismissed = self.record(
            "1",
            is_reserved=True,
            reservation_document="15/24",
            dismissal_date=date(2026, 3, 1),
        )
        working = self.record("2")
        ReservationDismissal.objects.create(
            person=working.person, order="1/20", dismissal_date=date(2020, 1, 1)
        )
        result = services.update_reserved_dismissed()
        self.assertEqual((result.added, result.removed, result.unreserved), (1, 1, 1))
        item = ReservationDismissal.objects.get()
        self.assertEqual(item.person, dismissed.person)
        self.assertEqual((item.order, item.dismissal_date), ("15/24", date(2026, 3, 1)))
        dismissed.refresh_from_db()
        self.assertFalse(dismissed.is_reserved)
        # Повторный запуск ничего не дублирует
        result = services.update_reserved_dismissed()
        self.assertEqual((result.added, result.removed, result.unreserved), (0, 0, 0))

    def test_read_snils_file(self):
        file = xlsx_file(["123-456-789 01", 12345678902, None, " "])
        self.assertEqual(services.read_snils_file(file), ["12345678901", "12345678902"])

    def test_unreserve_by_snils(self):
        working = self.record(
            "1",
            snils="123-456-789 01",
            is_reserved=True,
            special_account_type=self.team,
            reservation_document="15/24",
        )
        dismissed = self.record(
            "2",
            snils="123-456-789 02",
            is_reserved=True,
            dismissal_date=date(2026, 1, 1),
        )
        result = services.unreserve_by_snils(
            ["12345678901", "12345678901", "12345678902", "99999999999"], "77-р"
        )
        self.assertEqual(result.unreserved, 1)
        self.assertEqual(result.not_found, ["12345678902", "99999999999"])
        working.refresh_from_db()
        self.assertFalse(working.is_reserved)
        self.assertEqual(working.special_account_type, self.general)
        self.assertEqual(working.unreservation_order, "77-р")
        self.assertEqual(working.reservation_document, "")
        dismissed.refresh_from_db()
        self.assertTrue(dismissed.is_reserved)


class OperationsViewTests(TestCase):
    url = reverse("military:operations")

    def test_requires_change_permission(self):
        self.client.force_login(make_user("viewer", VIEWER))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_operator_runs_operations(self):
        self.client.force_login(make_user("operator", OPERATOR))
        response = self.client.get(self.url)
        self.assertContains(response, "Разбронирование по файлу")
        self.assertContains(response, reverse("military:operations"))  # пункт меню

        response = self.client.post(self.url, {"action": "dismissed"}, follow=True)
        self.assertContains(response, "Спец. уволенные обновлены")

        ref.SpecialAccountType.objects.create(name="Общий учёт", code="H9")
        person = make_person("1", snils="123-456-789 01")
        MilitaryRecord.objects.create(person=person, is_reserved=True)
        response = self.client.post(
            self.url,
            {
                "action": "unreserve",
                "order": "77-р",
                "file": xlsx_file(["12345678901", "1"]),
            },
            follow=True,
        )
        self.assertContains(response, "Разбронировано: 1.")
        self.assertContains(response, "Не найдены среди работающих (1): 1.")

    def test_bad_file(self):
        self.client.force_login(make_user("operator", OPERATOR))
        bad = SimpleUploadedFile("list.xlsx", b"not excel")
        response = self.client.post(
            self.url, {"action": "unreserve", "order": "1", "file": bad}
        )
        self.assertContains(response, "Не удалось прочитать файл Excel.")
