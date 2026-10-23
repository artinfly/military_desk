from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.military.models import MilitaryRecord
from apps.personnel.models import Person
from apps.references import models as ref

from .generator import seed


class SeedDemoTests(TestCase):
    def test_references_not_duplicated(self):
        seed(count=0)
        ranks = ref.MilitaryRank.objects.count()
        seed(count=0)
        self.assertEqual(ref.MilitaryRank.objects.count(), ranks)
        self.assertEqual(
            list(ref.MilitaryRank.objects.values_list("name", flat=True)[:3]),
            ["Рядовой", "Ефрейтор", "Младший сержант"],
        )

    def test_people(self):
        seed(count=120)
        people = Person.objects.all()
        self.assertEqual(people.count(), 120)
        self.assertEqual(people.values("tab_number").distinct().count(), 120)
        for person in people.prefetch_related("documents", "addresses"):
            self.assertTrue(person.documents.exists())
            self.assertTrue(
                person.addresses.filter(address_type__name="Регистрации").exists()
            )

        men = people.filter(gender=Person.Gender.MALE)
        self.assertGreater(men.count(), 50)
        self.assertEqual(
            MilitaryRecord.objects.filter(person__in=men).count(), men.count()
        )

        records = MilitaryRecord.objects.select_related("duty")
        for record in records.filter(is_reserved=True):
            self.assertTrue(record.reservation_document)
        for record in records.filter(duty__name="Призывник"):
            self.assertIsNone(record.rank)

    def test_same_seed_same_people(self):
        seed(count=20, seed_value=7)
        first = list(
            Person.objects.order_by("tab_number").values_list("tab_number", "last_name")
        )
        seed(count=20, seed_value=7, clear=True)
        second = list(
            Person.objects.order_by("tab_number").values_list("tab_number", "last_name")
        )
        self.assertEqual(first, second)

    def test_command(self):
        out = StringIO()
        call_command("seed_demo", count=5, stdout=out)
        self.assertIn("учётные карточки: 5", out.getvalue())
