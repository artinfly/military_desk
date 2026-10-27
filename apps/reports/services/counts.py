"""Численность работающих по воинскому учёту (главная страница и отчёт).

Как countsview старой программы, но «Всего» считается по базе (там оно вводилось
вручную), а офицеры — только среди работающих.
"""

from dataclasses import dataclass, field

from django.db.models import Count, Q

from .common import (
    IS_CONSCRIPT,
    IS_LIABLE,
    OFFICER,
    RESERVED,
    TEAM,
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
    "reserved": account(RESERVED),
    "reserved_officers": account(RESERVED) & IS_LIABLE & OFFICER,
    "team": account(TEAM) & IS_LIABLE,
    "team_officers": account(TEAM) & IS_LIABLE & OFFICER,
    "drivers": IS_LIABLE & is_driver(),
    "conscripts": IS_CONSCRIPT & Q(military__special_account_type__isnull=True),
}


@dataclass
class Figure:
    """Плашка: главное число и уточнения под ним («из них офицеры»)."""

    title: str
    value: int
    details: list = field(default_factory=list)


def headcount():
    """Все показатели одним запросом: {показатель: число}."""
    return working_people().aggregate(
        **{key: Count("pk", filter=cond or None) for key, cond in CONDITIONS.items()}
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
            "Забронировано (X4)", c["reserved"], [("офицеров", c["reserved_officers"])]
        ),
        Figure("Команда (R7)", c["team"], [("офицеров", c["team_officers"])]),
        Figure("Офицеров всего", c["officers"]),
        Figure("Призывников без вида учёта", c["conscripts"]),
    ]


def report_sheets(params):
    """Отчёт «Численность»: показатель — количество."""
    rows = []
    for figure in figures():
        rows.append([figure.title, figure.value])
        rows.extend([f"   из них {name}", value] for name, value in figure.details)
    return [("Численность", ["Показатель", "Количество"], rows)]
