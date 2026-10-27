"""Общее для отчётов: кто считается кем, выборки людей и текст ячеек.

Условия взяты из представлений старой программы (countsview, reservesview…),
но без их ошибок: уволенные не попадают в подсчёты, внешние совместители
действительно исключаются.
"""

from datetime import date

from django.db.models import OuterRef, Prefetch, Q, Subquery

from apps.military.models import CommissariatRegistration
from apps.personnel.models import (
    Address,
    Assignment,
    Education,
    IdentityDocument,
    Person,
)

# Военная обязанность (справочник «Военная обязанность»)
LIABLE = "Военнообязанный"
CONSCRIPT = "Призывник"

# Коды видов учёта (справочник «Виды специального учёта»)
RESERVED = "X4"  # спецучёт — забронирован
TEAM = "R7"  # команда
GENERAL = "H9"  # общий учёт

# Вид приказа последнего назначения у внешних совместителей — их не бронируют
EXTERNAL_PART_TIME = "по совм. внеш."
# Источник приёма, который не попадает в форму бронирования
EXCLUDED_HIRE_SOURCE = "ИК"
# Должности водителей (начало названия, без учёта регистра)
DRIVER_POSITIONS = ("Водитель автомобиля", "Тракторист")
# Школьное образование: в отчёте по призывникам берётся образование выше школьного
SCHOOL_EDUCATION = (
    "среднее общее",
    "среднее полное",
    "среднееполное",
    "основное общее",
    "неполное среднее",
    "неполноесреднее",
)

OFFICER = Q(military__rank__is_officer=True)
IS_LIABLE = Q(military__duty__name=LIABLE)
IS_CONSCRIPT = Q(military__duty__name=CONSCRIPT)


def account(code):
    """Условие «вид учёта с кодом code» (X4, R7, H9)."""
    return Q(military__special_account_type__code=code)


def is_driver():
    condition = Q()
    for position in DRIVER_POSITIONS:
        condition |= Q(position__istartswith=position)
    return condition


def working_people():
    """Работающие (без даты увольнения)."""
    return Person.objects.filter(dismissal_date__isnull=True)


def without_external_part_timers(people):
    """Без внешних совместителей: вид приказа последнего назначения — «по совм. внеш.»."""
    last_order = Assignment.objects.filter(person=OuterRef("pk")).order_by(
        "-order_date", "-date_from"
    )
    # Без назначений (NULL) — не совместитель; NULL надо оставить явно, иначе
    # сравнение с NULL в SQL отбросит строку
    return people.annotate(
        last_order_kind=Subquery(last_order.values("order_kind")[:1])
    ).filter(
        Q(last_order_kind__isnull=True)
        | ~Q(last_order_kind__istartswith=EXTERNAL_PART_TIME)
    )


def with_card_data(people):
    """Всё для строк отчётов одной выборкой — без запроса на каждого человека."""
    return people.select_related(
        "department",
        "military__duty",
        "military__rank",
        "military__speciality",
        "military__reserve_composition",
        "military__commissariat",
        "military__special_account_type",
        "military__document_type",
    ).prefetch_related(
        Prefetch(
            "documents",
            IdentityDocument.objects.select_related("document_type"),
        ),
        Prefetch(
            "commissariat_history",
            CommissariatRegistration.objects.select_related("commissariat"),
        ),
        Prefetch(
            "addresses",
            Address.objects.select_related(
                "address_type", "region", "city", "street"
            ).order_by("-registration_date", "-date_from"),
        ),
        Prefetch(
            "education",
            Education.objects.order_by("-graduation_date"),
        ),
        Prefetch(
            "assignments",
            Assignment.objects.order_by("-order_date", "-date_from"),
        ),
    )


# --- Текст ячеек ---


def text(value):
    return str(value) if value else ""


def day(value):
    return value.strftime("%d.%m.%Y") if value else ""


def passport(person):
    """Паспорт: «серия номер, дата выдачи» (паспорт гражданина РФ, иначе первый документ)."""
    documents = list(person.documents.all())
    found = next(
        (d for d in documents if "паспорт гражданина" in d.document_type.name.lower()),
        documents[0] if documents else None,
    )
    if found is None:
        return ""
    number = f"{found.series} {found.number}".strip()
    return f"{number}, {day(found.issue_date)}" if found.issue_date else number


def passport_and_snils(person):
    parts = [passport(person)]
    if person.snils:
        parts.append(f"СНИЛС {person.snils}")
    return ", ".join(part for part in parts if part)


def current_registration(person):
    """Текущая приписка к военкомату: последняя без даты окончания."""
    current = [r for r in person.commissariat_history.all() if r.date_to is None]
    return max(current, key=lambda r: r.date_from or date.min, default=None)


def commissariat(person):
    """Военкомат: по текущей приписке, иначе — из воинского учёта."""
    registration = current_registration(person)
    if registration:
        return str(registration.commissariat)
    military = getattr(person, "military", None)
    return text(military and military.commissariat)


def military_document(military):
    """Документ воинского учёта: «Военный билет АВ №1234567 (01.02.2010)»."""
    if military is None or not (military.document_series or military.document_number):
        return ""
    number = f"{military.document_series} №{military.document_number}".strip()
    dated = (
        f"{number} ({day(military.document_date)})"
        if military.document_date
        else number
    )
    return f"{text(military.document_type)} {dated}".strip()


def living_address(person):
    """Адрес проживания (иначе — последний по дате регистрации)."""
    addresses = list(person.addresses.all())
    living = next(
        (
            a
            for a in addresses
            if a.address_type and a.address_type.name == "Проживания"
        ),
        addresses[0] if addresses else None,
    )
    return text(living)


def workshop(person):
    """Цех: номер (как в старых отчётах), иначе название."""
    department = person.department
    return text(department and (department.number or department.name))


def higher_education(person):
    """Последнее образование выше школьного (для призывников)."""
    return next(
        (
            e
            for e in person.education.all()
            if not any(s in e.education_type.lower() for s in SCHOOL_EDUCATION)
        ),
        None,
    )


def age(person, today):
    born = person.birth_date
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
