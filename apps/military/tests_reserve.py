from datetime import date
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings, TestCase
from django.urls import reverse
from openpyxl import Workbook

from apps.accounts.roles import OPERATOR
from apps.accounts.testing import make_user
from apps.personnel.tests import make_person
from apps.references.models import AccountingGroup, SpecialAccountType

from .models import MilitaryRecord
from .services import reserve_by_snils


@override_settings(
    MILITARY_ACCOUNT_CODES={
        "reserved": "DEMO-BOOK",
        "team": "DEMO-TEAM",
        "general": "DEMO-GENERAL",
    }
)
class ReserveTests(TestCase):
    def setUp(self):
        self.actor = make_user("operator", OPERATOR)
        self.kind = SpecialAccountType.objects.create(code="DEMO-BOOK", name="Бронь")
        self.person = make_person(snils="123-456-789 00")
        MilitaryRecord.objects.create(person=self.person, unreservation_order="old")

    def test_reserve_marks_actor_and_does_not_touch_dismissed(self):
        other = make_person(
            "2", snils="111-111-111 11", dismissal_date=date(2026, 1, 1)
        )
        MilitaryRecord.objects.create(person=other)
        result = reserve_by_snils(
            ["12345678900", "11111111111"], "12/26", self.kind, actor=self.actor
        )
        self.assertEqual((result.reserved, result.not_found), (1, ["11111111111"]))
        self.person.refresh_from_db()
        record = self.person.military
        self.assertTrue(record.is_reserved)
        self.assertEqual(record.reservation_document, "12/26")
        self.assertEqual(record.unreservation_order, "")
        self.assertEqual(self.person.updated_by_id, self.actor.pk)

    def test_ambiguous_snils_and_missing_military_roll_back_everything(self):
        duplicate = make_person("2", snils=self.person.snils)
        with self.assertRaises(ValidationError):
            reserve_by_snils(["12345678900"], "12/26", self.kind)
        self.assertFalse(self.person.military.is_reserved)
        duplicate.snils = "111-111-111 11"
        duplicate.save()
        with self.assertRaises(ValidationError):
            reserve_by_snils(["12345678900", "11111111111"], "12/26", self.kind)
        self.person.military.refresh_from_db()
        self.assertFalse(self.person.military.is_reserved)

    def test_view_uses_distinct_field_ids_and_handles_invalid_file(self):
        SpecialAccountType.objects.create(code="DEMO-GENERAL", name="Общий")
        self.client.force_login(self.actor)
        url = reverse("military:operations")
        response = self.client.get(url)
        self.assertContains(response, 'name="reserve-file"')
        self.assertTrue(response.context["can_reserve"])
        self.assertTrue(response.context["can_unreserve"])
        response = self.client.post(
            url,
            {
                "action": "reserve",
                "reserve-order": "12/26",
                "reserve-account_type": self.kind.pk,
                "reserve-file": SimpleUploadedFile("bad.xlsx", b"bad"),
            },
        )
        self.assertContains(response, "Не удалось прочитать файл Excel")
        group = AccountingGroup.objects.create(name="Демонстрационная группа")
        book = Workbook()
        sheet = book.active
        sheet.append(["ФИО", "СНИЛС"])
        sheet.append([self.person.full_name, self.person.snils])
        buffer = BytesIO()
        book.save(buffer)
        response = self.client.post(
            url,
            {
                "action": "reserve",
                "reserve-order": "12/26",
                "reserve-account_type": self.kind.pk,
                "reserve-accounting_group": group.pk,
                "reserve-file": SimpleUploadedFile("list.xlsx", buffer.getvalue()),
            },
        )
        self.assertRedirects(response, url)
        self.person.military.refresh_from_db()
        self.assertTrue(self.person.military.is_reserved)
        self.assertEqual(self.person.military.accounting_group, group)

    @override_settings(MILITARY_ACCOUNT_CODES={})
    def test_buttons_are_visible_when_unconfigured(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse("military:operations"))
        self.assertContains(response, "disabled>Забронировать</button>")
        self.assertContains(response, "disabled>Разбронировать</button>")
        self.assertContains(response, 'name="reserve-accounting_group"')
