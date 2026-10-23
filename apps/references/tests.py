from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.roles import VIEWER
from apps.accounts.testing import make_user

from . import models
from .registry import REFERENCES, get_reference

User = get_user_model()


class RegistryTests(TestCase):
    def test_every_reference_model_is_registered(self):
        reference_models = {
            m
            for m in vars(models).values()
            if isinstance(m, type)
            and issubclass(m, models.Reference)
            and not m._meta.abstract
        }
        self.assertEqual(reference_models, {ref.model for ref in REFERENCES})
        self.assertEqual(len({ref.slug for ref in REFERENCES}), len(REFERENCES))

    def test_extra_fields(self):
        self.assertEqual(get_reference("departments").extra_fields, ["number"])
        self.assertEqual(get_reference("military-ranks").extra_fields, ["is_officer"])
        self.assertEqual(get_reference("regions").extra_fields, [])
        self.assertEqual(
            get_reference("branches").form_fields,
            ["name", "address", "code", "sort_order", "is_active"],
        )


class ReferenceModelTests(TestCase):
    def test_active_and_ordering(self):
        models.MilitaryRank.objects.create(name="Сержант", sort_order=3)
        models.MilitaryRank.objects.create(name="Рядовой", sort_order=1)
        models.MilitaryRank.objects.create(
            name="Ефрейтор", sort_order=2, is_active=False
        )
        self.assertEqual(
            [str(r) for r in models.MilitaryRank.objects.all()],
            ["Рядовой", "Ефрейтор", "Сержант"],
        )
        self.assertEqual(
            [str(r) for r in models.MilitaryRank.objects.active()],
            ["Рядовой", "Сержант"],
        )

    def test_code_unique_only_when_filled(self):
        models.Region.objects.create(name="Регион А")
        models.Region.objects.create(name="Регион Б")  # пустые коды не мешают
        models.Region.objects.create(name="Регион В", code="66")
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.Region.objects.create(name="Регион Г", code="66")

    def test_department_same_name_different_numbers(self):
        models.Department.objects.create(name="Механический цех", number="10")
        models.Department.objects.create(name="Механический цех", number="20")
        self.assertEqual(str(models.Department.objects.first()), "10 Механический цех")
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.Department.objects.create(name="Механический цех", number="10")


class ReferenceViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = make_user("viewer", VIEWER)
        cls.admin = User.objects.create_superuser("admin", password="x")
        models.MilitaryRank.objects.create(name="Рядовой", code="1")
        models.MilitaryRank.objects.create(name="Майор", code="15", is_active=False)

    def list_names(self, response):
        return [values[0] for _obj, values in response.context["rows"]]

    def test_catalog(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("references:catalog"))
        self.assertEqual(response.status_code, 200)
        refs = [
            ref for _title, items in response.context["sections"] for ref, _n in items
        ]
        self.assertEqual(len(refs), len(REFERENCES))
        self.assertContains(response, "Воинские звания")

    def test_list_search_and_status(self):
        self.client.force_login(self.operator)
        url = reverse("references:list", args=["military-ranks"])
        self.assertEqual(self.list_names(self.client.get(url)), ["Рядовой"])
        self.assertEqual(
            self.list_names(self.client.get(url, {"status": "inactive"})), ["Майор"]
        )
        self.assertEqual(
            self.list_names(self.client.get(url, {"status": "all", "q": "15"})),
            ["Майор"],
        )
        response = self.client.get(url)
        self.assertFalse(response.context["can_add"])
        self.assertNotContains(
            response, reverse("references:add", args=["military-ranks"])
        )

    def test_unknown_reference(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("references:list", args=["nothing"]))
        self.assertEqual(response.status_code, 404)

    def test_editing_needs_permission(self):
        self.client.force_login(self.operator)
        add_url = reverse("references:add", args=["military-ranks"])
        self.assertEqual(self.client.get(add_url).status_code, 403)
        self.operator.user_permissions.add(
            Permission.objects.get(codename="add_militaryrank")
        )
        self.assertEqual(self.client.get(add_url).status_code, 200)

    def test_add_edit_and_duplicate(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("references:add", args=["military-ranks"]),
            {"name": "Сержант", "code": "5", "sort_order": 3, "is_active": "on"},
            follow=True,
        )
        self.assertContains(response, "Запись «Сержант» добавлена")

        duplicate = self.client.post(
            reverse("references:add", args=["military-ranks"]),
            {"name": "Сержант", "code": "1", "sort_order": 0, "is_active": "on"},
        )
        self.assertEqual(duplicate.status_code, 200)
        errors = duplicate.context["form"].errors
        self.assertEqual(errors["name"], ["Запись с таким названием уже есть."])
        self.assertEqual(errors["__all__"], ["Запись с таким кодом уже есть."])

        rank = models.MilitaryRank.objects.get(name="Сержант")
        self.client.post(
            reverse("references:edit", args=["military-ranks", rank.pk]),
            {"name": "Сержант", "code": "5", "sort_order": 3},  # «Действует» снят
        )
        rank.refresh_from_db()
        self.assertFalse(rank.is_active)
