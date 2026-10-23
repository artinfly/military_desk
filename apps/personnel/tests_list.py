"""Список учётных карточек: поиск, фильтры, сортировка."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.roles import VIEWER
from apps.accounts.testing import make_user
from apps.military.models import MilitaryRecord
from apps.references import models as ref

from .models import AdditionalAttribute, Person
from .services import search_people, sort_people
from .tests import make_person

User = get_user_model()


class SearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.duty = ref.MilitaryDuty.objects.create(name="Военнообязанный")
        cls.conscript = ref.MilitaryDuty.objects.create(name="Призывник")
        cls.team = ref.SpecialAccountType.objects.create(name="Команда", code="R7")
        cls.dep10 = ref.Department.objects.create(name="Механический цех", number="10")
        cls.dep20 = ref.Department.objects.create(name="Сборочный цех", number="20")
        cls.comm = ref.MilitaryCommissariat.objects.create(name="Военкомат г. Энска")
        major = ref.MilitaryRank.objects.create(name="Майор", is_officer=True)
        private = ref.MilitaryRank.objects.create(name="Рядовой")
        vus = ref.MilitarySpeciality.objects.create(name="100182 — Стрелок")
        svo = ref.AttributeValue.objects.create(name="Специальная военная операция")
        attribute = ref.AttributeType.objects.create(name="Участие в боевых действиях")

        cls.ivanov = make_person(
            "1001",
            last_name="Иванов",
            first_name="Иван",
            department=cls.dep10,
            is_svo=True,
        )
        MilitaryRecord.objects.create(
            person=cls.ivanov,
            duty=cls.duty,
            rank=major,
            speciality=vus,
            special_account_type=cls.team,
            commissariat=cls.comm,
            is_reserved=True,
        )
        AdditionalAttribute.objects.create(
            person=cls.ivanov, attribute=attribute, value=svo
        )

        cls.petrov = make_person(
            "1002", last_name="Петров", first_name="Пётр", department=cls.dep20
        )
        MilitaryRecord.objects.create(
            person=cls.petrov, duty=cls.conscript, rank=private
        )

        cls.sidorova = make_person(
            "1003",
            last_name="Сидорова",
            first_name="Анна",
            gender="Ж",
            department=cls.dep10,
            birth_date=date(1985, 1, 1),
        )
        cls.dismissed = make_person(
            "1004", last_name="Уволенный", dismissal_date=date(2025, 1, 1)
        )

    def found(self, **filters):
        return sorted(p.tab_number for p in search_people(filters))

    def test_working_by_default(self):
        self.assertEqual(self.found(), ["1001", "1002", "1003"])
        self.assertEqual(self.found(status="dismissed"), ["1004"])
        self.assertEqual(len(self.found(status="all")), 4)

    def test_text_search(self):
        self.assertEqual(self.found(q="1002"), ["1002"])
        self.assertEqual(self.found(q="иван"), ["1001"])
        self.assertEqual(self.found(q="сидорова анна"), ["1003"])
        self.assertEqual(self.found(q="сидорова иван"), [])

    def test_each_filter(self):
        cases = {
            "duty": (self.conscript, ["1002"]),
            "account_type": (self.team, ["1001"]),
            "department": (self.dep10, ["1001", "1003"]),
            "commissariat": (self.comm, ["1001"]),
            "attribute_value": (ref.AttributeValue.objects.get(), ["1001"]),
            "speciality": ("стрелок", ["1001"]),
            "officers": (True, ["1001"]),
            "reserved": (True, ["1001"]),
            "svo": (True, ["1001"]),
            "no_military": (True, ["1003"]),
        }
        for key, (value, expected) in cases.items():
            with self.subTest(filter=key):
                self.assertEqual(self.found(**{key: value}), expected)

    def test_filters_combine(self):
        self.assertEqual(self.found(department=self.dep10, reserved=True), ["1001"])
        self.assertEqual(self.found(department=self.dep20, officers=True), [])

    def test_sorting(self):
        people, sort = sort_people(search_people({}), "-birth_date")
        self.assertEqual(sort, "-birth_date")
        self.assertEqual([p.tab_number for p in people][-1], "1003")  # самая старшая
        people, sort = sort_people(search_people({}), "nonsense")
        self.assertEqual(sort, "name")
        self.assertEqual(
            [p.last_name for p in people], ["Иванов", "Петров", "Сидорова"]
        )


class PersonListViewTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("viewer", VIEWER))

    def test_page_and_filters(self):
        for n in range(30):
            person = make_person(f"2{n:03d}", last_name=f"Фамилия{n:02d}")
            MilitaryRecord.objects.create(person=person)
        url = reverse("personnel:list")
        with self.assertNumQueries(11):
            # Сессия, пользователь, 2 — права (кнопка «Добавить»), счётчик, 5 справочников, страница —
            # число запросов не зависит от количества карточек
            response = self.client.get(url, {"sort": "-tab_number"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["paginator"].count, 30)
        self.assertEqual(response.context["object_list"][0].tab_number, "2029")
        self.assertContains(
            response, "sort=tab_number"
        )  # повторный клик — по возрастанию

        response = self.client.get(url, {"q": "Фамилия07"})
        self.assertEqual(
            [p.tab_number for p in response.context["object_list"]], ["2007"]
        )

    def test_anonymous(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("personnel:list")).status_code, 302)

    def test_menu_item_active(self):
        response = self.client.get(reverse("personnel:list"))
        active = [
            i["label"]
            for s in response.context["menu"]
            for i in s["items"]
            if i["active"]
        ]
        self.assertEqual(active, ["Учётные карточки"])
