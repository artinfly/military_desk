from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.personnel.tests import make_person
from apps.references import models as ref

from .models import CommissariatRegistration, MilitaryRecord, ReservationDismissal


class MilitaryRecordTests(TestCase):
    def setUp(self):
        self.person = make_person()

    def test_one_record_per_person(self):
        rank = ref.MilitaryRank.objects.create(name="Рядовой")
        MilitaryRecord.objects.create(person=self.person, rank=rank, is_reserved=True)
        self.assertEqual(self.person.military.rank, rank)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MilitaryRecord.objects.create(person=self.person)

    def test_deleted_with_person(self):
        MilitaryRecord.objects.create(person=self.person)
        self.person.delete()
        self.assertFalse(MilitaryRecord.objects.exists())

    def test_commissariat_history_unique(self):
        commissariat = ref.MilitaryCommissariat.objects.create(
            name="Военкомат города Энска"
        )
        period = {"date_from": date(2020, 1, 1), "date_to": date(2022, 1, 1)}
        CommissariatRegistration.objects.create(
            person=self.person, commissariat=commissariat, **period
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CommissariatRegistration.objects.create(
                person=self.person, commissariat=commissariat, **period
            )
        self.assertEqual(
            list(self.person.commissariat_history.all())[0].commissariat, commissariat
        )

    def test_reservation_dismissal_unique_order(self):
        ReservationDismissal.objects.create(
            person=self.person, order="12/34", dismissal_date=date(2026, 3, 1)
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReservationDismissal.objects.create(
                person=self.person, order="12/34", dismissal_date=date(2026, 4, 1)
            )
