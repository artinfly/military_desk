"""Численность работающих по воинскому учёту (главная страница и отчёт).

Как countsview старой программы, но «Всего» считается по базе (там оно вводилось
вручную), а офицеры — только среди работающих.
"""

from dataclasses import dataclass, field

from django.db.models import Count, Q

from apps.legacy.hr_source import BK_COUNT_LABEL
from apps.legacy.models import ImportBatch
from apps.military.account_codes import account_code

from .common import (
    IS_CONSCRIPT,
    IS_LIABLE,
    OFFICER,
    account,
    is_driver,
    working_people,
)

# Показатель -> условие отбора среди работающих
CONDITIONS = {
    "total": Q(),
    "liable": IS_LIABLE,
    "liable_officers": IS_LIABLE & OFFICER,
    "officers": OFFICER,
    "drivers": IS_LIABLE & is_driver(),
    "conscripts": IS_CONSCRIPT & Q(military__special_account_type__isnull=True),
}


@dataclass
class Figure:
    """Плашка: главное число и уточнения под ним («из них офицеры»)."""

    title: str
    value: int | None
    details: list = field(default_factory=list)


def headcount():
    """Все показатели одним запросом: {показатель: число}."""
    conditions = {
        **CONDITIONS,
        "reserved": account("reserved"),
        "reserved_officers": account("reserved") & IS_LIABLE & OFFICER,
        "team": account("team") & IS_LIABLE,
        "team_officers": account("team") & IS_LIABLE & OFFICER,
    }
    return working_people().aggregate(
        **{key: Count("pk", filter=cond or None) for key, cond in conditions.items()}
    )


def figures(counts=None):
    """Плашки для главной страницы."""
    c = counts or headcount()
    return [
        Figure("Работающих", c["total"]),
        Figure(
            "Военнообязанных",
            c["liable"],
            [("офицеров", c["liable_officers"]), ("водителей", c["drivers"])],
        ),
        Figure(
            "Забронировано",
            c["reserved"] if account_code("reserved") else None,
            [("офицеров", c["reserved_officers"])] if account_code("reserved") else [],
        ),
        Figure(
            "Команда",
            c["team"] if account_code("team") else None,
            [("офицеров", c["team_officers"])] if account_code("team") else [],
        ),
        Figure("Офицеров всего", c["officers"]),
        Figure("Призывников без вида учёта", c["conscripts"]),
    ]


def report_sheets(params):
    """Отчёт «Численность»: показатель — количество."""
    rows = []
    for figure in figures():
        rows.append([figure.title, figure.value])
        rows.extend([f"   из них {name}", value] for name, value in figure.details)
    last = (
        ImportBatch.objects.filter(
            kind__in=("hr", "hr_zip", "hr_zip_extended"), counts__has_key=BK_COUNT_LABEL
        )
        .values_list("counts", flat=True)
        .first()
    )
    rows.insert(1, [BK_COUNT_LABEL, last[BK_COUNT_LABEL] if last is not None else None])
    return [("Численность", ["Показатель", "Количество"], rows)]
