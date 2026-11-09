from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from apps.accounts.testing import make_user
from apps.personnel.models import Person
from apps.personnel.tests import make_person
from apps.references import models as ref

from . import services
from .models import MilitaryRecord, ReservationDismissal
from .tests_operations import xlsx_file


class MassOperationAuditTests(TestCase):
    def setUp(self):
        self.actor = make_user("operator-audit")
        self.general = ref.SpecialAccountType.objects.create(
            name="Общий учёт", code="H9"
        )
        self.team = ref.SpecialAccountType.objects.create(name="Команда", code="R7")
        self.person = make_person(snils="001-234-567 89")
        self.record = MilitaryRecord.objects.create(
            person=self.person,
            is_reserved=True,
            special_account_type=self.team,
            reservation_document="77",
        )
        self.before = timezone.now() - timedelta(days=1)
        Person.objects.filter(pk=self.person.pk).update(updated_at=self.before)
        MilitaryRecord.objects.filter(pk=self.record.pk).update(updated_at=self.before)

    def assert_marked(self):
        self.person.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(self.person.updated_by, self.actor)
        self.assertGreater(self.person.updated_at, self.before)
        self.assertGreater(self.record.updated_at, self.before)

    def test_missing_or_inactive_h9_rolls_back(self):
        self.general.is_active = False
        self.general.save()
        with self.assertRaises(ValidationError):
            services.unreserve_by_snils(["00123456789"], "99", actor=self.actor)
        self.record.refresh_from_db()
        self.person.refresh_from_db()
        self.assertTrue(self.record.is_reserved)
        self.assertEqual(self.record.reservation_document, "77")
        self.assertEqual(self.person.updated_at, self.before)

    def test_unreserve_marks_author(self):
        services.unreserve_by_snils(["00123456789"], "99", actor=self.actor)
        self.assert_marked()

    def test_change_type_marks_author(self):
        self.record.is_reserved = False
        self.record.save()
        services.change_account_type(self.team, self.general, actor=self.actor)
        self.assert_marked()

    def test_dismissed_marks_author_and_repeat_is_safe(self):
        self.person.dismissal_date = date(2026, 1, 1)
        self.person.save()
        result = services.update_reserved_dismissed(actor=self.actor)
        self.assertEqual(result.added, 1)
        self.assert_marked()
        self.assertEqual(services.update_reserved_dismissed(actor=self.actor).added, 0)
        self.assertEqual(ReservationDismissal.objects.count(), 1)

    def test_duplicate_snils_aborts_all_changes(self):
        other = make_person("2", snils="00123456789")
        MilitaryRecord.objects.create(person=other, is_reserved=True)
        with self.assertRaises(ValidationError):
            services.unreserve_by_snils(["00123456789"], "99", actor=self.actor)
        self.record.refresh_from_db()
        self.assertTrue(self.record.is_reserved)
        self.assertIsNone(Person.objects.get(pk=self.person.pk).updated_by)

    def test_file_numeric_leading_zeros_and_invalid_rows(self):
        self.assertEqual(
            services.read_snils_file(xlsx_file([123456789, "001-234-567 89"])),
            ["00123456789"],
        )
        for values in ([], ["1"], ["123456789ab"], ["=1+1"], [-123], [1.5]):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                services.read_snils_file(xlsx_file(values))


class ConcurrentOperationAuditTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_parallel_dismissed_updates_do_not_duplicate_history(self):
        person = make_person(dismissal_date=date(2026, 1, 1))
        MilitaryRecord.objects.create(
            person=person, is_reserved=True, reservation_document="77"
        )
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return services.update_reserved_dismissed()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(sum(r.added for r in results), 1)
        self.assertEqual(sum(r.unreserved for r in results), 1)
        self.assertEqual(ReservationDismissal.objects.count(), 1)
