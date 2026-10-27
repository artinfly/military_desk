from datetime import date
from io import BytesIO

from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.accounts.roles import VIEWER
from apps.accounts.testing import make_user
from apps.military.models import (
    CommissariatRegistration,
    MilitaryRecord,
    ReservationDismissal,
)
from apps.personnel.models import Assignment, Education
from apps.personnel.tests import make_person
from apps.references import models as ref

from .registry import REPORTS
from .services import counts, lists


class ReportDataTests(TestCase):
    """Отбор людей в отчёты — по правилам старой программы, без её ошибок."""

    def setUp(self):
        self.liable = ref.MilitaryDuty.objects.create(name="Военнообязанный")
        self.conscript = ref.MilitaryDuty.objects.create(name="Призывник")
        self.officer = ref.MilitaryRank.objects.create(
            name="Лейтенант", is_officer=True
        )
        self.private = ref.MilitaryRank.objects.create(name="Рядовой")
        self.x4 = ref.SpecialAccountType.objects.create(name="Спец. учёт", code="X4")
        self.r7 = ref.SpecialAccountType.objects.create(name="Команда", code="R7")
        self.listed = ref.MilitarySpeciality.objects.create(
            name="450100 — Оператор", in_reservation_list=True
        )
        self.other = ref.MilitarySpeciality.objects.create(name="100182 — Стрелок")
        self.ticket = ref.RegistrationDocument.objects.create(name="Военный билет")
        self.temporary = ref.RegistrationDocument.objects.create(
            name="Временное удостоверение", in_reservation_appendix=True
        )
        self.numbers = iter(range(1000, 2000))

    def person(self, duty=None, **military):
        person_fields = {
            k: military.pop(k)
            for k in ("dismissal_date", "hire_source", "position", "employment_date")
            if k in military
        }
        person = make_person(str(next(self.numbers)), **person_fields)
        MilitaryRecord.objects.create(
            person=person, duty=duty or self.liable, **military
        )
        return person

    def names(self, sheet):
        return sorted(row[0] for row in sheet[2])

    def test_headcount(self):
        self.person(rank=self.officer, special_account_type=self.x4)
        self.person(
            rank=self.private,
            special_account_type=self.r7,
            position="Водитель автомобиля",
        )
        self.person(rank=self.officer, dismissal_date=date(2025, 1, 1))  # уволен
        self.person(duty=self.conscript)
        c = counts.headcount()
        self.assertEqual(
            (c["total"], c["liable"], c["officers"], c["reserved_officers"]),
            (3, 2, 1, 1),
        )
        self.assertEqual((c["team"], c["drivers"], c["conscripts"]), (1, 1, 1))

    def test_reservation_form_and_appendices(self):
        main = self.person(speciality=self.other, document_type=self.ticket)
        listed = self.person(speciality=self.listed, document_type=self.ticket)
        temporary = self.person(speciality=self.listed, document_type=self.temporary)
        self.person(hire_source="ИК")
        self.person(dismissal_date=date(2025, 1, 1))
        part_timer = self.person()
        Assignment.objects.create(
            person=part_timer, order_kind="Приём на работу", order_date=date(2020, 1, 1)
        )
        Assignment.objects.create(
            person=part_timer, order_kind="по совм. внеш.", order_date=date(2021, 1, 1)
        )
        form, appendix1, appendix2 = lists.reservation_form({})
        tabs = lambda sheet: sorted(row[0] for row in sheet[2])  # noqa: E731
        self.assertEqual(tabs(form), sorted([main.tab_number, listed.tab_number]))
        self.assertEqual(tabs(appendix1), [listed.tab_number])
        self.assertEqual(tabs(appendix2), [temporary.tab_number])

    def test_card_row(self):
        person = self.person(
            speciality=self.other,
            document_type=self.ticket,
            document_series="АВ",
            document_number="1234567",
            document_date=date(2010, 2, 1),
        )
        place = ref.MilitaryCommissariat.objects.create(name="Военкомат Энска")
        CommissariatRegistration.objects.create(
            person=person, commissariat=place, date_from=date(2015, 3, 1)
        )
        row = dict(
            zip(lists.CARD_HEADERS, lists.reservation_form({})[0][2][0], strict=True)
        )
        self.assertEqual(row["Военкомат"], "Военкомат Энска")
        self.assertEqual(row["Дата постановки на учёт"], date(2015, 3, 1))
        self.assertEqual(
            row["Документ воинского учёта"], "Военный билет АВ №1234567 (01.02.2010)"
        )

    def test_hired_period(self):
        self.person(special_account_type=self.x4, employment_date=date(2026, 3, 1))
        self.person(special_account_type=self.r7, employment_date=date(2024, 3, 1))
        self.person(employment_date=date(2026, 3, 1))  # без брони и команды
        sheet = lists.hired({"date_from": date(2026, 1, 1), "date_to": None})[0]
        self.assertEqual(len(sheet[2]), 1)
        self.assertEqual(len(lists.hired({})[0][2]), 2)

    def test_reserved_dismissed(self):
        person = self.person(dismissal_date=date(2026, 2, 1))
        ReservationDismissal.objects.create(
            person=person, order="15/24", dismissal_date=date(2026, 2, 1)
        )
        rows = lists.reserved_dismissed({})[0][2]
        self.assertEqual(rows[0][-2:], ["15/24", date(2026, 2, 1)])
        self.assertEqual(
            lists.reserved_dismissed({"date_to": date(2026, 1, 1)})[0][2], []
        )

    def test_conscripts_skip_school_education(self):
        person = self.person(duty=self.conscript)
        Education.objects.create(
            person=person, education_type="Среднее общее", institution="Школа № 5",
            graduation_date=date(2024, 6, 1),
        )  # fmt: skip
        Education.objects.create(
            person=person, education_type="Среднее профессиональное",
            institution="Энский колледж", graduation_date=date(2023, 6, 1),
        )  # fmt: skip
        row = dict(
            zip(lists.CONSCRIPT_HEADERS, lists.conscripts({})[0][2][0], strict=True)
        )
        self.assertEqual(row["Учебное заведение"], "Энский колледж")

    def test_vus_by_account(self):
        self.person(speciality=self.listed, special_account_type=self.x4)
        self.person(speciality=self.listed, special_account_type=self.r7)
        self.person(speciality=self.listed, special_account_type=self.x4,
                    dismissal_date=date(2025, 1, 1))  # fmt: skip
        rows = lists.vus_by_account({})[0][2]
        self.assertEqual(rows[0], ["450100 — Оператор", 1, 1, 0, 2])
        self.assertEqual(rows[-1][0], "Итого")


class ReportPagesTests(TestCase):
    def test_list_and_downloads(self):
        self.client.force_login(make_user("viewer", VIEWER))
        response = self.client.get(reverse("reports:list"))
        for report in REPORTS:
            self.assertContains(response, report.title)
            response_file = self.client.get(
                reverse("reports:download", args=[report.slug])
            )
            self.assertEqual(response_file.status_code, 200, report.slug)
            load_workbook(BytesIO(response_file.content))

    def test_bad_period(self):
        self.client.force_login(make_user("viewer", VIEWER))
        url = reverse("reports:download", args=["hired"])
        response = self.client.get(
            url, {"date_from": "2026-05-01", "date_to": "2026-01-01"}
        )
        self.assertRedirects(response, reverse("reports:list"))

    def test_access(self):
        self.client.force_login(make_user("nobody"))
        self.assertEqual(self.client.get(reverse("reports:list")).status_code, 403)
        url = reverse("reports:download", args=["headcount"])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get("/reports/unknown/").status_code, 404)

    def test_home_figures(self):
        self.client.force_login(make_user("viewer", VIEWER))
        self.assertContains(self.client.get("/"), "Военнообязанных")
        self.client.force_login(make_user("nobody"))
        self.assertNotContains(self.client.get("/"), "Военнообязанных")
