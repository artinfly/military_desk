"""Карточка: вкладки, права, правка карточки и её разделов."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.roles import VIEWER
from apps.accounts.testing import make_user
from apps.military.models import MilitaryRecord
from apps.references import models as ref

from .models import IdentityDocument, Person, Relative
from .sections import all_sections
from .tests import make_person

User = get_user_model()


class CardTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", password="x")
        cls.operator = make_user("viewer", VIEWER)
        cls.passport = ref.RegistrationDocument.objects.create(name="Паспорт")
        cls.son = ref.RelationType.objects.create(name="Сын")
        cls.private = ref.MilitaryRank.objects.create(name="Рядовой")
        cls.person = make_person()
        IdentityDocument.objects.create(
            person=cls.person, document_type=cls.passport, number="123456"
        )
        Relative.objects.create(person=cls.person, relation=cls.son, last_name="Петров")
        MilitaryRecord.objects.create(person=cls.person, rank=cls.private)

    def url(self, name, *args):
        return reverse(f"personnel:{name}", args=[self.person.pk, *args])


class CardViewTests(CardTestCase):
    def test_every_tab(self):
        self.client.force_login(self.admin)
        for section in [None, *all_sections()]:
            tab = section.slug if section else "general"
            # Сессия, пользователь, карточка, воинский учёт для шапки (+ записи раздела)
            with self.subTest(tab=tab), self.assertNumQueries(
                4 if tab == "general" else 5
            ):
                response = self.client.get(self.url("detail"), {"tab": tab})
                self.assertEqual(response.status_code, 200)
        response = self.client.get(self.url("detail"), {"tab": "documents"})
        self.assertContains(response, "123456")
        self.assertContains(response, self.url("section_add", "documents"))
        response = self.client.get(self.url("detail"), {"tab": "military"})
        self.assertContains(response, "Рядовой")

    def test_unknown_tab(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url("detail"), {"tab": "nothing"})
        self.assertEqual(response.status_code, 404)

    def test_viewer_cannot_edit(self):
        self.client.force_login(self.operator)
        response = self.client.get(self.url("detail"), {"tab": "documents"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.url("edit"))
        self.assertNotContains(response, self.url("section_add", "documents"))
        document = IdentityDocument.objects.get()
        for url in [
            reverse("personnel:add"),
            self.url("edit"),
            self.url("delete"),
            self.url("section_add", "documents"),
            self.url("section_edit", "documents", document.pk),
            self.url("section_delete", "documents", document.pk),
            self.url("section_single", "military"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)


class CardEditTests(CardTestCase):
    def setUp(self):
        self.client.force_login(self.admin)

    def person_data(self, **changes):
        data = {
            "tab_number": "2002",
            "last_name": "Сидоров",
            "first_name": "Семён",
            "gender": "М",
            "birth_date": "1991-02-03",
        }
        data.update(changes)
        return data

    def test_create_person(self):
        response = self.client.post(reverse("personnel:add"), self.person_data())
        person = Person.objects.get(tab_number="2002")
        self.assertRedirects(response, reverse("personnel:detail", args=[person.pk]))
        self.assertEqual(person.updated_by, self.admin)
        self.assertEqual(person.birth_date, date(1991, 2, 3))

    def test_dismissal_before_hire(self):
        response = self.client.post(
            self.url("edit"),
            self.person_data(
                tab_number="1001",
                employment_date="2020-01-01",
                dismissal_date="2019-01-01",
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("dismissal_date", response.context["form"].errors)

    def test_section_add_edit_delete(self):
        add = self.client.post(
            self.url("section_add", "documents"),
            {"document_type": self.passport.pk, "series": "4500", "number": "654321"},
        )
        self.assertRedirects(add, f"{self.url('detail')}?tab=documents")
        document = IdentityDocument.objects.get(number="654321")
        self.person.refresh_from_db()
        self.assertEqual(self.person.updated_by, self.admin)

        self.client.post(
            self.url("section_edit", "documents", document.pk),
            {"document_type": self.passport.pk, "series": "4501", "number": "654321"},
        )
        document.refresh_from_db()
        self.assertEqual(document.series, "4501")

        self.assertContains(
            self.client.get(self.url("section_delete", "documents", document.pk)),
            "Удалить запись",
        )
        self.client.post(self.url("section_delete", "documents", document.pk))
        self.assertFalse(IdentityDocument.objects.filter(pk=document.pk).exists())

    def test_military_single_record(self):
        other = make_person("3003")
        url = reverse("personnel:section_single", args=[other.pk, "military"])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(
            url,
            {
                "rank": self.private.pk,
                "is_reserved": "on",
                "reservation_document": "АБ 1",
            },
        )
        self.client.post(url, {"rank": self.private.pk, "reservation_document": "АБ 2"})
        record = MilitaryRecord.objects.get(person=other)
        self.assertEqual(
            (record.reservation_document, record.is_reserved), ("АБ 2", False)
        )

    def test_inactive_reference_in_forms(self):
        relative = Relative.objects.get()
        self.son.is_active = False
        self.son.save()
        new_form = self.client.get(self.url("section_add", "relatives")).context["form"]
        self.assertNotIn(self.son, new_form.fields["relation"].queryset)
        edit_form = self.client.get(
            self.url("section_edit", "relatives", relative.pk)
        ).context["form"]
        self.assertIn(self.son, edit_form.fields["relation"].queryset)

    def test_delete_person(self):
        self.assertContains(self.client.get(self.url("delete")), "со всеми разделами")
        response = self.client.post(self.url("delete"))
        self.assertRedirects(response, reverse("personnel:list"))
        self.assertFalse(Person.objects.exists())
