from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.roles import ADMIN, OPERATOR, VIEWER
from apps.accounts.testing import make_user
from apps.military.models import MilitaryRecord
from apps.personnel.models import Education, Relative
from apps.personnel.tests import make_person
from apps.references.models import Department, MilitaryDuty, RelationType

from .certificates import CertificateTemplateForm, certificate_text
from .models import CertificateTemplate
from .services.lists import RECONCILIATION_HEADERS, reconciliation


class CertificatesTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Цех", number="42")
        self.person = make_person(department=self.department)
        MilitaryRecord.objects.create(
            person=self.person, is_reserved=True, reservation_document="12/26"
        )

    def test_substitution_is_plain_text_and_does_not_execute_template_code(self):
        text = certificate_text(
            self.person,
            "{{ФИО}} {{ПриказНомер}} {{Дата}} {% include 'x' %}",
            date(2026, 11, 9),
        )
        self.assertIn(self.person.full_name, text)
        self.assertIn("12/26", text)
        self.assertIn("09.11.2026", text)
        self.assertIn("{% include 'x' %}", text)

    def test_individual_and_department_printing_escape_personal_values(self):
        self.client.force_login(make_user("reader", VIEWER))
        self.person.last_name = "<script>alert(1)</script>"
        self.person.save()
        response = self.client.get(
            reverse("reports:certificate", args=[self.person.pk])
        )
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        response = self.client.get(
            reverse("reports:certificates"), {"department": self.department.pk}
        )
        self.assertContains(response, "12/26")
        self.person.dismissal_date = date(2026, 1, 1)
        self.person.save()
        self.assertEqual(
            self.client.get(
                reverse("reports:certificate", args=[self.person.pk])
            ).status_code,
            404,
        )

    def test_edit_requires_admin_and_rejects_unknown_fields(self):
        url = reverse("reports:certificate_template")
        self.client.force_login(make_user("operator", OPERATOR))
        self.assertEqual(self.client.post(url, {"body": "changed"}).status_code, 403)
        self.client.force_login(make_user("admin", ADMIN))
        self.assertEqual(self.client.get(url).status_code, 200)
        data = {
            "name": "Справка",
            "organization": "Организация",
            "body": "{{ФИО}} {{unknown}}",
        }
        self.assertFalse(CertificateTemplateForm(data).is_valid())
        data["body"] = "{{ФИО}} {{ПриказНомер}}"
        data["revision"] = ""
        self.assertRedirects(
            self.client.post(url, data), reverse("reports:certificates")
        )
        template = CertificateTemplate.objects.get()
        data["revision"] = "outdated"
        response = self.client.post(url, data)
        self.assertContains(response, "Шаблон уже изменён")
        self.assertEqual(CertificateTemplate.objects.get().body, template.body)

    def test_no_permission_does_not_expose_certificate(self):
        self.client.force_login(make_user("nobody"))
        self.assertEqual(
            self.client.get(
                reverse("reports:certificate", args=[self.person.pk])
            ).status_code,
            403,
        )


class ReconciliationTests(TestCase):
    def test_one_row_per_person_with_all_relatives_and_educations(self):
        duty = MilitaryDuty.objects.create(name="Военнообязанный")
        person = make_person(inn="123456789012", snils="123-456-789 00")
        MilitaryRecord.objects.create(
            person=person, duty=duty, is_reserved=True, reservation_document="33/26"
        )
        relation = RelationType.objects.create(name="Сын")
        Relative.objects.create(
            person=person,
            relation=relation,
            last_name="Сынов",
            birth_date=date(2010, 1, 1),
        )
        Education.objects.create(person=person, institution="Колледж")
        Education.objects.create(person=person, institution="Университет")
        dismissed = make_person("2", dismissal_date=date(2026, 1, 1))
        MilitaryRecord.objects.create(person=dismissed, duty=duty)
        rows = reconciliation({})[0][2]
        self.assertEqual(len(rows), 1)
        row = dict(zip(RECONCILIATION_HEADERS, rows[0], strict=True))
        self.assertIn("Колледж", row["Образование"])
        self.assertIn("Университет", row["Образование"])
        self.assertIn("Сынов", row["Родственники"])
        self.assertEqual(row["ИНН"], person.inn)
        self.assertIn("33/26", row["Категория учёта"])
