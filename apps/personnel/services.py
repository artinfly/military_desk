"""Поиск учётных карточек по фильтрам (для списка и отчёта по фильтру).

Модели personnel не зависят от military; поиск же показывает и воинские поля,
поэтому обращается к ним по связи person.military (MilitaryRecord).
"""

from django.db.models import Q

from .models import Person

# Колонка списка -> поле для сортировки (ключ приходит из адреса ?sort=…)
SORT_FIELDS = {
    "tab_number": "tab_number",
    "name": "last_name",
    "rank": "military__rank__sort_order",
    "birth_date": "birth_date",
    "dismissal_date": "dismissal_date",
    "duty": "military__duty__sort_order",
    "department": "department__number",
}
DEFAULT_SORT = "name"


def people_queryset():
    """Карточки со всем, что показывает список, одним запросом."""
    return Person.objects.select_related(
        "department",
        "military__rank",
        "military__duty",
        "military__special_account_type",
    )


def search_people(filters, queryset=None):
    """Карточки, подходящие под фильтры (cleaned_data формы PersonFilterForm)."""
    people = people_queryset() if queryset is None else queryset

    query = (filters.get("q") or "").strip()
    if query:
        # Табельный номер целиком или все слова запроса в ФИО («петров ив»)
        words = Q()
        for word in query.split():
            words &= (
                Q(last_name__icontains=word)
                | Q(first_name__icontains=word)
                | Q(patronymic__icontains=word)
            )
        people = people.filter(Q(tab_number=query) | words)

    status = filters.get("status") or "working"
    if status == "working":
        people = people.filter(dismissal_date__isnull=True)
    elif status == "dismissed":
        people = people.filter(dismissal_date__isnull=False)

    exact = {
        "duty": "military__duty",
        "account_type": "military__special_account_type",
        "department": "department",
        "commissariat": "military__commissariat",
    }
    for key, lookup in exact.items():
        if filters.get(key):
            people = people.filter(**{lookup: filters[key]})

    if filters.get("attribute_value"):
        people = people.filter(attributes__value=filters["attribute_value"]).distinct()

    speciality = (filters.get("speciality") or "").strip()
    if speciality:
        people = people.filter(military__speciality__name__icontains=speciality)

    if filters.get("officers"):
        people = people.filter(military__rank__is_officer=True)
    if filters.get("reserved"):
        people = people.filter(military__is_reserved=True)
    if filters.get("svo"):
        people = people.filter(is_svo=True)
    if filters.get("no_military"):
        people = people.filter(military__isnull=True)

    return people


def sort_people(people, sort):
    """Сортировка по колонке: «name» — по возрастанию, «-name» — по убыванию."""
    key = sort.lstrip("-") if sort else DEFAULT_SORT
    if key not in SORT_FIELDS:
        key, sort = DEFAULT_SORT, DEFAULT_SORT
    field = SORT_FIELDS[key]
    if sort.startswith("-"):
        return people.order_by(f"-{field}", "last_name", "first_name"), sort
    return people.order_by(field, "last_name", "first_name"), sort
