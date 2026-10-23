from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from apps.references import models as ref

from .models import Address, IdentityDocument, Person, Relative

User = get_user_model()


def make_person(tab_number="1001", **kwargs):
    data = {
        "tab_number": tab_number,
        "last_name": "Петров",
        "first_name": "Пётр",
        "patronymic": "Петрович",
        "gender": Person.Gender.MALE,
        "birth_date": date(1990, 5, 17),
    }
    data.update(kwargs)
    return Person.objects.create(**data)


class PersonTests(TestCase):
    def test_names_and_status(self):
        person = make_person()
        self.assertEqual(person.full_name, "Петров Пётр Петрович")
        self.assertEqual(str(person), "Петров Пётр Петрович (1001)")
        self.assertTrue(person.is_working)
        person.dismissal_date = date(2026, 1, 31)
        self.assertFalse(person.is_working)

    def test_tab_number_unique(self):
        make_person()
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_person()

    def test_address_text(self):
        region = ref.Region.objects.create(name="Свердловская обл.")
        city = ref.City.objects.create(name="г. Энск")
        street = ref.Street.objects.create(name="ул. Ленина")
        address = Address(
            person=make_person(),
            postal_code="620000",
            region=region,
            city=city,
            street=street,
            house="5",
            apartment="12",
        )
        self.assertEqual(
            str(address), "620000, Свердловская обл., г. Энск, ул. Ленина, д. 5, кв. 12"
        )

    def test_used_reference_cannot_be_deleted(self):
        relation = ref.RelationType.objects.create(name="Сын")
        Relative.objects.create(
            person=make_person(), relation=relation, last_name="Петров"
        )
        with self.assertRaises(ProtectedError):
            relation.delete()

    def test_sections_deleted_with_person(self):
        person = make_person()
        passport = ref.RegistrationDocument.objects.create(name="Паспорт")
        IdentityDocument.objects.create(
            person=person, document_type=passport, number="1"
        )
        person.delete()
        self.assertFalse(IdentityDocument.objects.exists())


class PersonAdminTests(TestCase):
    def test_admin_pages(self):
        admin = User.objects.create_superuser("admin", password="x")
        self.client.force_login(admin)
        person = make_person()
        self.assertEqual(
            self.client.get(reverse("admin:personnel_person_changelist")).status_code,
            200,
        )
        change_url = reverse("admin:personnel_person_change", args=[person.pk])
        page = self.client.get(change_url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Воинский учёт")  # раздел из apps.military
        self.assertContains(page, "Родственники")
