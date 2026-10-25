"""Данные отчётов.

«Отчёт по фильтру» — те же люди, что в списке карточек с выбранными фильтрами
(apps.personnel.services.search_people), с колонками старой программы.
"""

from django.db.models import Prefetch

from apps.personnel.models import Address, Education, IdentityDocument, Relative

# Родственники, которые считаются детьми (по названию степени родства)
CHILD_RELATIONS = ("Сын", "Дочь")

FILTER_REPORT_HEADERS = [
    "Таб. номер",
    "Фамилия имя отчество",
    "Дата рождения",
    "Воинское звание",
    "Категория запаса",
    "Состав",
    "ВУС",
    "Категория годности",
    "Место рождения",
    "Паспорт, СНИЛС",
    "Учебное заведение",
    "Место жительства",
    "Дети",
    "Должность",
    "Место работы",
    "Место приписки",
    "Примечание",
]


def with_report_data(people):
    """Добавляет к выборке всё, что нужно отчёту, — без запроса на каждого человека."""
    return people.select_related(
        "military__reserve_category",
        "military__reserve_composition",
        "military__speciality",
        "military__fitness_category",
        "military__commissariat",
    ).prefetch_related(
        Prefetch("documents", IdentityDocument.objects.select_related("document_type")),
        Prefetch(
            "addresses",
            Address.objects.select_related("address_type", "region", "city", "street"),
        ),
        Prefetch(
            "relatives",
            Relative.objects.select_related("relation").filter(
                relation__name__in=CHILD_RELATIONS
            ),
            to_attr="children",
        ),
        Prefetch(
            "education", Education.objects.order_by("-is_main", "-graduation_date")
        ),
    )


def _text(value):
    return str(value) if value else ""


def _passport_and_snils(person):
    documents = list(person.documents.all())
    passport = next(
        (d for d in documents if "паспорт гражданина" in d.document_type.name.lower()),
        documents[0] if documents else None,
    )
    parts = []
    if passport:
        parts.append(f"{passport.series} {passport.number}".strip())
    if person.snils:
        parts.append(f"СНИЛС {person.snils}")
    return ", ".join(parts)


def _living_address(person):
    addresses = list(person.addresses.all())
    living = next(
        (
            a
            for a in addresses
            if a.address_type and a.address_type.name == "Проживания"
        ),
        addresses[0] if addresses else None,
    )
    return _text(living)


def _children(person):
    return ", ".join(
        (
            f"{child.first_name} {child.birth_date.year}"
            if child.birth_date
            else child.first_name
        )
        for child in person.children
    )


def filter_report_rows(people):
    """Строки «Отчёта по фильтру» для выборки карточек."""
    rows = []
    for person in with_report_data(people):
        military = getattr(person, "military", None)
        education = next(iter(person.education.all()), None)
        rows.append(
            [
                person.tab_number,
                person.full_name,
                person.birth_date,
                _text(military and military.rank),
                _text(military and military.reserve_category),
                _text(military and military.reserve_composition),
                _text(military and military.speciality),
                _text(military and military.fitness_category),
                person.birth_place,
                _passport_and_snils(person),
                _text(education and education.institution),
                _living_address(person),
                _children(person),
                person.position,
                _text(person.department),
                _text(military and military.commissariat),
                _text(military and military.note),
            ]
        )
    return rows
