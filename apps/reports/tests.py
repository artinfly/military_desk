from datetime import date
from io import BytesIO

from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.accounts.roles import VIEWER
from apps.accounts.testing import make_user
from apps.personnel.models import Address, IdentityDocument, Relative
from apps.personnel.tests import make_person
from apps.references import models as ref

from .services import FILTER_REPORT_HEADERS


class FilterReportTests(TestCase):
    url = reverse("reports:filter")

    def setUp(self):
        self.client.force_login(make_user("viewer", VIEWER))

    def sheet(self, response):
        self.assertEqual(response.status_code, 200)
        return load_workbook(BytesIO(response.content)).active

    def test_requires_view_permission(self):
        self.client.force_login(make_user("nobody"))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_columns_and_filters(self):
        person = make_person("1001", snils="123-456-789 01")
        make_person("1002", last_name="Сидоров", dismissal_date=date(2026, 1, 1))
        passport = ref.RegistrationDocument.objects.create(name="Паспорт гражданина РФ")
        IdentityDocument.objects.create(
            person=person, document_type=passport, series="4600", number="123456"
        )
        Address.objects.create(
            person=person,
            address_type=ref.AddressType.objects.create(name="Проживания"),
            house="5",
        )
        son = ref.RelationType.objects.create(name="Сын")
        wife = ref.RelationType.objects.create(name="Жена")
        Relative.objects.create(
            person=person,
            relation=son,
            last_name="Петров",
            first_name="Иван",
            birth_date=date(2015, 1, 1),
        )
        Relative.objects.create(person=person, relation=wife, last_name="Петрова")

        response = self.client.get(self.url, {"status": "working"})
        self.assertIn("attachment", response["Content-Disposition"])
        sheet = self.sheet(response)
        rows = list(sheet.values)
        self.assertEqual(list(rows[0]), FILTER_REPORT_HEADERS)
        self.assertEqual(len(rows), 2)  # уволенный Сидоров отфильтрован
        row = dict(zip(FILTER_REPORT_HEADERS, rows[1]))
        self.assertEqual(row["Фамилия имя отчество"], "Петров Пётр Петрович")
        self.assertEqual(row["Паспорт, СНИЛС"], "4600 123456, СНИЛС 123-456-789 01")
        self.assertIn("д. 5", row["Место жительства"])
        self.assertEqual(row["Дети"], "Иван 2015")

    def test_list_has_export_link(self):
        response = self.client.get(reverse("personnel:list"), {"q": "Петров"})
        self.assertContains(response, f"{self.url}?q=")
