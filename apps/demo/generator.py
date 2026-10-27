"""Генератор вымышленных данных: справочники, учётные карточки, воинский учёт.

Результат повторяем: одинаковый seed — одинаковые данные. Записи создаются
пачками (bulk_create), поэтому тысячи карточек генерируются за секунды.
"""

import random
from collections import Counter
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from apps.military import models as mil
from apps.personnel import models as per
from apps.references import models as ref

from . import data

# Звания по группам — для подбора состава запаса
RANK_COMPOSITION = {
    "Солдаты и матросы": ["Рядовой", "Ефрейтор"],
    "Сержанты и старшины": [
        "Младший сержант",
        "Сержант",
        "Старший сержант",
        "Старшина",
    ],
    "Прапорщики и мичманы": ["Прапорщик", "Старший прапорщик"],
    "Младшие офицеры": [
        "Младший лейтенант",
        "Лейтенант",
        "Старший лейтенант",
        "Капитан",
    ],
    "Старшие офицеры": ["Майор", "Подполковник", "Полковник"],
}
COMPOSITION_WEIGHTS = [55, 25, 6, 11, 3]


def seed_references():
    """Справочники: создаёт недостающие записи, существующие не трогает."""
    for model_name, names in data.REFERENCES.items():
        model = getattr(ref, model_name)
        codes = data.REFERENCE_CODES.get(model_name, {})
        for order, name in enumerate(names, 1):
            model.objects.get_or_create(
                name=name,
                defaults={"sort_order": order, "code": codes.get(name, str(order))},
            )
    ranks = data.REFERENCES["MilitaryRank"]
    officers = ranks[ranks.index(data.OFFICER_RANKS_FROM) :]
    ref.MilitaryRank.objects.filter(name__in=officers).update(is_officer=True)
    for order, name in enumerate(data.CITIES, 1):
        ref.City.objects.get_or_create(
            name=name, defaults={"code": f"6600000{order:04d}", "sort_order": order}
        )
    for order, name in enumerate(data.STREETS, 1):
        ref.Street.objects.get_or_create(
            name=name, defaults={"code": f"66000001{order:04d}", "sort_order": order}
        )
    for order, (number, name) in enumerate(data.DEPARTMENTS, 1):
        ref.Department.objects.get_or_create(
            number=number, name=name, defaults={"sort_order": order}
        )


class PeopleGenerator:
    """Учётные карточки со всеми разделами и воинским учётом."""

    def __init__(self, seed=1):
        self.rnd = random.Random(seed)
        self.today = timezone.localdate()
        self.refs = {
            name: list(getattr(ref, name).objects.active())
            for name in [*data.REFERENCES, "City", "Street", "Department"]
        }
        self.by_name = {
            name: {r.name: r for r in items} for name, items in self.refs.items()
        }
        self.rows = {}  # модель -> список объектов для bulk_create

    # --- Вспомогательное ---

    def pick(self, model_name):
        return self.rnd.choice(self.refs[model_name])

    def get(self, model_name, name):
        return self.by_name[model_name][name]

    def chance(self, percent):
        return self.rnd.random() * 100 < percent

    def date_between(self, start, end):
        if end <= start:
            return start
        return start + timedelta(days=self.rnd.randrange((end - start).days + 1))

    def years_ago(self, years):
        return self.today - timedelta(days=round(years * 365.25))

    def digits(self, count):
        return "".join(str(self.rnd.randrange(10)) for _ in range(count))

    def add(self, obj):
        self.rows.setdefault(type(obj), []).append(obj)

    # --- Карточка ---

    def make_person(self, tab_number):
        male = self.chance(70)
        first = self.rnd.choice(data.MALE_FIRST if male else data.FEMALE_FIRST)
        surname = self.rnd.choice(data.SURNAMES)
        father = self.rnd.choice(list(data.PATRONYMICS))
        birth = self.date_between(self.years_ago(60), self.years_ago(18))
        employed = self.date_between(
            max(birth + timedelta(days=18 * 366), date(2000, 1, 1)), self.today
        )
        dismissed = self.date_between(employed, self.today) if self.chance(10) else None
        department = self.pick("Department")
        category = self.rnd.choices(list(data.POSITIONS), weights=[70, 22, 8])[0]
        return per.Person(
            tab_number=tab_number,
            last_name=surname if male else surname + "а",
            first_name=first,
            patronymic=data.PATRONYMICS[father][0 if male else 1],
            gender=per.Person.Gender.MALE if male else per.Person.Gender.FEMALE,
            birth_date=birth,
            birth_place=self.rnd.choice(data.CITIES),
            citizenship="Российская Федерация",
            family_status=self.pick("FamilyStatus"),
            inn=self.digits(12),
            snils=f"{self.digits(3)}-{self.digits(3)}-{self.digits(3)} {self.digits(2)}",
            phone=f"+7 9{self.digits(2)} {self.digits(3)}-{self.digits(2)}-{self.digits(2)}",
            card_number=tab_number[-5:],
            employment_date=employed,
            dismissal_date=dismissed,
            department=department,
            position=self.rnd.choice(data.POSITIONS[category]),
            hire_type="Основное место работы",
            is_svo=male and not dismissed and self.chance(3),
        )

    def add_sections(self, person):
        age = (self.today - person.birth_date).days // 365
        passport = self.get("RegistrationDocument", "Паспорт гражданина РФ")
        self.add(
            per.IdentityDocument(
                person=person,
                document_type=passport,
                series=self.digits(4),
                number=self.digits(6),
                issue_date=(
                    self.date_between(
                        person.birth_date + timedelta(days=20 * 366), self.today
                    )
                    if age >= 20
                    else person.birth_date + timedelta(days=14 * 366)
                ),
                issued_by="Отделом МВД по г. Энску",
                subdivision_code=f"660-{self.digits(3)}",
            )
        )
        for address_type in ["Регистрации"] + (
            ["Проживания"] if self.chance(30) else []
        ):
            self.add(
                per.Address(
                    person=person,
                    address_type=self.get("AddressType", address_type),
                    country="Россия",
                    postal_code=f"62{self.digits(4)}",
                    region=self.get("Region", "Энская область"),
                    city=self.pick("City"),
                    street=self.pick("Street"),
                    house=str(self.rnd.randint(1, 120)),
                    apartment=str(self.rnd.randint(1, 200)) if self.chance(80) else "",
                    date_from=self.date_between(person.birth_date, self.today),
                )
            )
        self.add_relatives(person, age)
        self.add(
            per.Education(
                person=person,
                education_type=self.rnd.choice(data.EDUCATION_TYPES),
                institution=self.rnd.choice(data.INSTITUTIONS),
                speciality=self.rnd.choice(data.SPECIALITIES),
                study_form="Очная",
                graduation_date=person.birth_date
                + timedelta(days=self.rnd.randint(18, 24) * 365),
                document="Диплом",
                document_number=self.digits(7),
                is_main=True,
            )
        )
        working = self.get("WorkStatus", "Работает")
        self.add(
            per.Assignment(
                person=person,
                department=person.department,
                position=person.position,
                status=working,
                order_kind="Приём на работу",
                order_number=f"{self.rnd.randint(1, 900)}-к",
                order_date=person.employment_date,
                date_from=person.employment_date,
                date_to=person.dismissal_date,
            )
        )
        if person.dismissal_date:
            self.add(
                per.Assignment(
                    person=person,
                    department=person.department,
                    position=person.position,
                    status=self.get("WorkStatus", "Уволен"),
                    order_kind="Увольнение",
                    order_number=f"{self.rnd.randint(1, 900)}-у",
                    order_date=person.dismissal_date,
                    date_from=person.dismissal_date,
                )
            )
        if person.gender == per.Person.Gender.MALE and (
            person.is_svo or self.chance(5)
        ):
            self.add(
                per.AdditionalAttribute(
                    person=person,
                    attribute=self.pick("AttributeType"),
                    value=self.get("AttributeValue", "Специальная военная операция"),
                    date_from=self.date_between(date(2022, 2, 24), self.today),
                )
            )

    def add_relatives(self, person, age):
        male = person.gender == per.Person.Gender.MALE
        relatives = []
        if age < 50:
            relatives += [("Мать", "а"), ("Отец", "")]
        if self.chance(60) and age >= 22:
            relatives.append(("Жена", "а") if male else ("Муж", ""))
        if age >= 25:
            relatives += [
                self.rnd.choice([("Сын", ""), ("Дочь", "а")])
                for _ in range(self.rnd.randint(0, 2))
            ]
        surname = person.last_name[:-1] if not male else person.last_name
        used = {person.first_name}  # имена в одной семье не повторяются
        for relation, ending in relatives:
            names = data.MALE_FIRST if ending == "" else data.FEMALE_FIRST
            first = self.rnd.choice([n for n in names if n not in used])
            used.add(first)
            if relation in ("Мать", "Отец"):
                born = person.birth_date - timedelta(
                    days=self.rnd.randint(20, 35) * 365
                )
            elif relation in ("Сын", "Дочь"):
                born = person.birth_date + timedelta(
                    days=self.rnd.randint(20, 35) * 365
                )
                if born > self.today:
                    continue
            else:
                born = person.birth_date + timedelta(days=self.rnd.randint(-5, 5) * 365)
            self.add(
                per.Relative(
                    person=person,
                    relation=self.get("RelationType", relation),
                    last_name=surname + ending,
                    first_name=first,
                    birth_date=born,
                    is_dependent=relation in ("Сын", "Дочь")
                    and born > self.years_ago(18),
                )
            )

    # --- Воинский учёт ---

    def add_military(self, person):
        age = (self.today - person.birth_date).days // 365
        male = person.gender == per.Person.Gender.MALE
        if not male and not self.chance(10):
            return  # не военнообязанная
        conscript = male and age <= 27 and self.chance(40)
        commissariat = self.pick("MilitaryCommissariat")
        record = mil.MilitaryRecord(
            person=person,
            commissariat=commissariat,
            accounting_group=self.rnd.choices(
                self.refs["AccountingGroup"], weights=[80, 8, 6, 3, 3]
            )[0],
            fitness_category=self.rnd.choices(
                self.refs["FitnessCategory"], weights=[60, 25, 12, 2, 1]
            )[0],
            issued_by=(
                self.get("IssuingAuthority", commissariat.name)
                if commissariat.name in self.by_name["IssuingAuthority"]
                else self.pick("IssuingAuthority")
            ),
        )
        if conscript:
            record.duty = self.get("MilitaryDuty", "Призывник")
            record.document_type = self.get(
                "RegistrationDocument", "Удостоверение гражданина, подлежащего призыву"
            )
            record.document_number = self.digits(7)
            record.document_date = person.birth_date + timedelta(days=17 * 366)
        else:
            # Звание по возрасту: прапорщики — с 21 года, младшие офицеры — с 23, старшие — с 30
            min_age = [0, 0, 21, 23, 30]
            weights = [
                w if age >= limit else 0
                for w, limit in zip(COMPOSITION_WEIGHTS, min_age, strict=True)
            ]
            composition = self.rnd.choices(list(RANK_COMPOSITION), weights=weights)[0]
            record.duty = self.get("MilitaryDuty", "Военнообязанный")
            record.document_type = self.get("RegistrationDocument", "Военный билет")
            record.document_series = self.rnd.choice(["АВ", "АЕ", "АК", "АС"])
            record.document_number = self.digits(7)
            record.document_date = self.date_between(
                person.birth_date + timedelta(days=18 * 366), self.today
            )
            record.rank = self.get(
                "MilitaryRank", self.rnd.choice(RANK_COMPOSITION[composition])
            )
            record.reserve_composition = self.get("ReserveComposition", composition)
            record.reserve_category = self.pick("ReserveCategory")
            record.speciality = self.pick("MilitarySpeciality")
            reserved = self.chance(20)
            team = not reserved and not person.dismissal_date and self.chance(10)
            account_type = (
                "Спец. учёт" if reserved else "Команда" if team else "Общий учёт"
            )
            record.special_account_type = self.get("SpecialAccountType", account_type)
            if reserved and person.dismissal_date:
                record.unreservation_order = f"{self.rnd.randint(1, 300)}-р"
                self.add(
                    mil.ReservationDismissal(
                        person=person,
                        order=f"{self.rnd.randint(1000, 9999)}/{self.digits(2)}",
                        dismissal_date=person.dismissal_date,
                    )
                )
            elif reserved:
                record.is_reserved = True
                record.reservation_document = (
                    f"{self.rnd.choice(['АБ', 'ВГ'])} {self.digits(7)}"
                )
            elif self.chance(30):
                record.mobilization_order = self.digits(6)
                record.mobilization_letter = self.rnd.choice(["А", "Б", "В"])
            self.add_military_history(person, record, age)
        self.add(record)
        self.add(
            mil.CommissariatRegistration(
                person=person,
                commissariat=commissariat,
                date_from=record.document_date,
            )
        )

    def add_military_history(self, person, record, age):
        served_from = person.birth_date + timedelta(days=self.rnd.randint(18, 20) * 366)
        if self.chance(60):
            self.add(
                mil.MilitaryService(
                    person=person,
                    unit=f"Войсковая часть {self.digits(5)}",
                    speciality=record.speciality,
                    date_from=served_from,
                    date_to=served_from + timedelta(days=365),
                )
            )
            self.add(
                mil.Oath(
                    person=person,
                    date=served_from + timedelta(days=30),
                    place="Войсковая часть",
                )
            )
        if record.rank and record.rank.sort_order > 4:
            self.add(
                mil.RankAssignment(
                    person=person,
                    rank=record.rank,
                    date_from=self.date_between(served_from, self.today),
                    order=f"Приказ № {self.rnd.randint(1, 500)}",
                )
            )
        if self.chance(8):
            self.add(
                mil.Training(
                    person=person,
                    year=self.rnd.randint(2010, self.today.year),
                    days=self.rnd.choice([10, 20, 30]),
                    organization="Учебный центр",
                    speciality=record.speciality,
                )
            )
        if person.is_svo or self.chance(1):
            self.add(
                mil.PersonAward(
                    person=person,
                    award=self.pick("Award"),
                    date=self.date_between(date(2022, 6, 1), self.today),
                )
            )
        if age >= 55 and self.chance(30):
            self.add(
                mil.Removal(
                    person=person,
                    date=self.date_between(self.years_ago(age - 55), self.today),
                    reason=self.get("RemovalReason", "По возрасту"),
                )
            )

    # --- Запуск ---

    def run(self, count):
        """Создаёт count карточек со всеми разделами. Возвращает {модель: сколько создано}."""
        taken = set(per.Person.objects.values_list("tab_number", flat=True))
        numbers = [
            n
            for n in (
                str(x)
                for x in self.rnd.sample(range(1000000, 9999999), count + len(taken))
            )
            if n not in taken
        ][:count]
        people = per.Person.objects.bulk_create([self.make_person(n) for n in numbers])
        for person in people:
            self.add_sections(person)
            self.add_military(person)
        created = Counter({per.Person: len(people)})
        for model, objects in self.rows.items():
            created[model] += len(model.objects.bulk_create(objects))
        return {model._meta.verbose_name_plural: n for model, n in created.items()}


@transaction.atomic
def seed(count=300, seed_value=1, clear=False):
    """Справочники + count карточек. clear — удалить все карточки перед генерацией."""
    if clear:
        per.Person.objects.all().delete()
    seed_references()
    return PeopleGenerator(seed_value).run(count)
