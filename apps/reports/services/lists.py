"""Списочные отчёты воинского учёта (по представлениям старой программы).

Каждый отчёт — функция params -> [(название листа, шапка, строки)]; params —
проверенные параметры формы (период). Строки собираются из выборки с
with_card_data, поэтому запросов к базе — несколько на весь отчёт.
"""

from django.db.models import Count, Q
from django.utils import timezone

from apps.military.models import ReservationDismissal
from apps.personnel.models import Person

from .common import (
    EXCLUDED_HIRE_SOURCE,
    GENERAL,
    IS_CONSCRIPT,
    IS_LIABLE,
    RESERVED,
    TEAM,
    account,
    age,
    commissariat,
    current_registration,
    higher_education,
    living_address,
    military_document,
    passport,
    passport_and_snils,
    text,
    with_card_data,
    without_external_part_timers,
    working_people,
    workshop,
)


def _period(queryset, field, params):
    """Отбор по периоду «с — по» из параметров (пустые границы не ограничивают)."""
    if params.get("date_from"):
        queryset = queryset.filter(**{f"{field}__gte": params["date_from"]})
    if params.get("date_to"):
        queryset = queryset.filter(**{f"{field}__lte": params["date_to"]})
    return queryset


# --- Форма бронирования и принятые (reservesview, hiring_view) ---

CARD_HEADERS = [
    "Таб. номер",
    "ФИО",
    "Пол",
    "Дата рождения",
    "Паспорт",
    "СНИЛС",
    "ВУС",
    "Военкомат",
    "Дата постановки на учёт",
    "Состав",
    "Звание",
    "Военная обязанность",
    "Цех",
    "Должность",
    "Вид учёта",
    "Дата приёма",
    "Участник СВО",
    "Документ воинского учёта",
]


def card_row(person):
    military = getattr(person, "military", None)
    registration = current_registration(person)
    return [
        person.tab_number,
        person.full_name,
        person.get_gender_display(),
        person.birth_date,
        passport(person),
        person.snils,
        text(military and military.speciality),
        commissariat(person),
        registration.date_from if registration else None,
        text(military and military.reserve_composition),
        text(military and military.rank),
        text(military and military.duty),
        workshop(person),
        person.position,
        text(military and military.special_account_type),
        person.employment_date,
        "Да" if person.is_svo else "Нет",
        military_document(military),
    ]


def _rows(people):
    return [
        card_row(p) for p in with_card_data(people.order_by("last_name", "first_name"))
    ]


def reservation_people():
    """Работающие военнообязанные для формы бронирования (без внешних совместителей)."""
    people = (
        working_people().filter(IS_LIABLE).exclude(hire_source=EXCLUDED_HIRE_SOURCE)
    )
    return without_external_part_timers(people)


def reservation_form(params):
    """Форма бронирования и два приложения — листами одной книги.

    Приложение 1 — ВУС из перечня (флажок у ВУС), приложение 2 — люди с документом,
    отмеченным «Отдельно в приложении 2» (их нет в форме и приложении 1).
    """
    people = reservation_people()
    separate = Q(military__document_type__in_reservation_appendix=True)
    main = people.exclude(separate)
    return [
        ("Форма", CARD_HEADERS, _rows(main)),
        (
            "Приложение 1",
            CARD_HEADERS,
            _rows(main.filter(military__speciality__in_reservation_list=True)),
        ),
        ("Приложение 2", CARD_HEADERS, _rows(people.filter(separate))),
    ]


def hired(params):
    """Работающие с бронью (X4) или в команде (R7), принятые за период."""
    people = working_people().filter(account(RESERVED) | account(TEAM))
    people = _period(people, "employment_date", params)
    return [("Принятые", CARD_HEADERS, _rows(people))]


# --- Спец. уволенные (dis_spec_view) ---

DISMISSED_HEADERS = [
    "ФИО",
    "Дата рождения",
    "Паспорт",
    "СНИЛС",
    "ВУС",
    "Военкомат",
    "Удостоверение / приказ",
    "Дата увольнения",
]


def reserved_dismissed(params):
    """Уволенные забронированные (раздел «Увольнения забронированных»)."""
    items = _period(ReservationDismissal.objects.all(), "dismissal_date", params)
    items = items.select_related("person").order_by("-dismissal_date")
    people = with_card_data(Person.objects.filter(pk__in=items.values("person_id")))
    people = {p.pk: p for p in people}
    rows = []
    for item in items:
        person = people[item.person_id]
        military = getattr(person, "military", None)
        rows.append(
            [
                person.full_name,
                person.birth_date,
                passport(person),
                person.snils,
                text(military and military.speciality),
                commissariat(person),
                item.order,
                item.dismissal_date,
            ]
        )
    return [("Спец. уволенные", DISMISSED_HEADERS, rows)]


# --- Призывники (recruitsview) ---

CONSCRIPT_HEADERS = [
    "ФИО",
    "Место рождения",
    "Дата рождения",
    "Возраст",
    "Учебное заведение",
    "Специальность",
    "Документ об образовании",
    "Дата окончания",
    "Уровень образования",
    "Адрес проживания",
    "Военкомат",
    "Отметка военкомата",
    "Должность",
    "Дата назначения",
    "Цех",
    "Паспорт и СНИЛС",
]


def conscripts(params):
    today = timezone.localdate()
    people = with_card_data(working_people().filter(IS_CONSCRIPT).order_by("last_name"))
    rows = []
    for person in people:
        education = higher_education(person)
        assignment = next(iter(person.assignments.all()), None)
        rows.append(
            [
                person.full_name,
                person.birth_place,
                person.birth_date,
                age(person, today),
                education.institution if education else "",
                education.speciality if education else "",
                (
                    f"{education.document_series} {education.document_number}".strip()
                    if education
                    else ""
                ),
                education.graduation_date if education else None,
                education.education_type if education else "",
                living_address(person),
                commissariat(person),
                text(person.military.duty),
                person.position,
                assignment.date_from if assignment else None,
                workshop(person),
                passport_and_snils(person),
            ]
        )
    return [("Призывники", CONSCRIPT_HEADERS, rows)]


# --- ВУС по видам учёта (specialscountsview) ---


def vus_by_account(params):
    """Работающие военнообязанные: по каждой ВУС — X4, R7, H9 и всего."""
    rows = (
        working_people()
        .filter(IS_LIABLE, military__speciality__isnull=False)
        .values("military__speciality__name")
        .annotate(
            reserved=Count("pk", filter=account(RESERVED)),
            team=Count("pk", filter=account(TEAM)),
            general=Count("pk", filter=account(GENERAL)),
            total=Count("pk"),
        )
        .order_by("military__speciality__name")
    )
    headers = ["ВУС", "Бронь (X4)", "Команда (R7)", "Общий учёт (H9)", "Всего"]
    data = [
        [
            r["military__speciality__name"],
            r["reserved"],
            r["team"],
            r["general"],
            r["total"],
        ]
        for r in rows
    ]
    if data:
        data.append(["Итого", *(sum(r[i] for r in data) for i in range(1, 5))])
    return [("ВУС по видам учёта", headers, data)]
