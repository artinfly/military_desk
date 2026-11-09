"""Права, отбор и объём данных при выборе записи большого справочника."""

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.accounts.roles import VIEWER
from apps.accounts.testing import make_user
from apps.personnel.forms import PersonForm
from apps.personnel.tests import make_person
from apps.references.models import City, Department


class ReferencePickerTests(TestCase):
    def setUp(self):
        self.url = reverse("references:choices", args=["cities"])
        self.user = make_user("viewer", VIEWER)
        self.client.force_login(self.user)

    def test_search_is_paginated_and_excludes_inactive(self):
        City.objects.bulk_create(
            [City(name=f"Town {i:03}", code=str(i)) for i in range(60)]
        )
        City.objects.create(name="Hidden town", code="hidden", is_active=False)
        first = self.client.get(self.url).json()
        second = self.client.get(self.url, {"page": 2}).json()
        self.assertEqual(first["count"], 60)
        self.assertEqual(len(first["results"]), 25)
        self.assertTrue(first["has_next"])
        self.assertFalse(first["has_previous"])
        self.assertTrue(second["has_previous"])
        self.assertFalse(
            {r["id"] for r in first["results"]} & {r["id"] for r in second["results"]}
        )
        self.assertEqual(
            self.client.get(self.url, {"q": "Town 007"}).json()["count"], 1
        )
        self.assertEqual(self.client.get(self.url, {"q": "hidden"}).json()["count"], 0)
        self.assertEqual(self.client.get(self.url, {"q": "59"}).json()["count"], 1)

    def test_search_department_number_and_bad_page(self):
        Department.objects.create(name="Production", number="042", code="dept")
        url = reverse("references:choices", args=["departments"])
        response = self.client.get(url, {"q": "042", "page": "invalid"}).json()
        self.assertEqual(response["count"], 1)
        self.assertIn("042", response["results"][0]["label"])
        self.assertEqual(response["page"], 1)

    def test_requires_view_permission_and_login(self):
        self.client.force_login(make_user("no-role"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(
                reverse("references:choices", args=["missing"])
            ).status_code,
            404,
        )

    def test_form_keeps_inactive_value_without_loading_full_directory(self):
        Department.objects.bulk_create(
            [Department(name=f"Department {i}", code=str(i)) for i in range(60)]
        )
        old = Department.objects.create(
            name="Archived department", code="old", is_active=False
        )
        person = make_person(department=old, card_number="keep-old-data")
        form = PersonForm(instance=person)
        with self.assertNumQueries(1):
            html = str(form["department"])
        self.assertIn("Archived department", html)
        self.assertNotIn("<select", html)
        self.assertIn('type="hidden" name="department"', html)
        self.assertIn('id="id_department_display"', html)
        self.assertNotIn("Department 59", html)
        self.assertNotIn("card_number", form.fields)
        self.assertIn(str(old.pk), html)
        new_form = PersonForm()
        self.assertNotIn(old, new_form.fields["department"].queryset)
        data = {
            "tab_number": person.tab_number,
            "last_name": "Changed",
            "first_name": person.first_name,
            "gender": person.gender,
            "birth_date": person.birth_date,
            "department": old.pk,
        }
        bound = PersonForm(data, instance=person)
        self.assertTrue(bound.is_valid(), bound.errors)
        bound.save()
        person.refresh_from_db()
        self.assertEqual(person.card_number, "keep-old-data")
        self.assertEqual(person.department_id, old.pk)
        data["department"] = "not-a-pk"
        invalid = PersonForm(data, instance=person)
        self.assertFalse(invalid.is_valid())
        self.assertIn("Выбрать", str(invalid["department"]))
