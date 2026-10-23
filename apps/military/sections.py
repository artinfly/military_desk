"""Разделы воинского учёта на вкладках учётной карточки.

Регистрируются в реестре personnel при запуске (MilitaryConfig.ready()).
"""

from apps.personnel.sections import MILITARY, Section, register

from . import models

SECTIONS = [
    Section(
        "military",
        "Воинский учёт",
        models.MilitaryRecord,
        group=MILITARY,
        order=1,
        single=True,
        template="military/tab_record.html",
        fieldsets=(
            (
                "Документ воинского учёта",
                (
                    "document_type",
                    "document_series",
                    "document_number",
                    "document_date",
                    "issued_by",
                ),
            ),
            (
                "Учёт",
                (
                    "duty",
                    "rank",
                    "speciality",
                    "accounting_group",
                    "reserve_category",
                    "reserve_composition",
                    "fitness_category",
                    "commissariat",
                    "special_account_type",
                    "mobilization_order",
                    "mobilization_letter",
                    "gpz",
                    "note",
                ),
            ),
            (
                "Бронирование",
                ("is_reserved", "reservation_document", "unreservation_order"),
            ),
        ),
    ),
    Section(
        "commissariats",
        "Приписка",
        models.CommissariatRegistration,
        ("commissariat", "date_from", "date_to"),
        group=MILITARY,
        order=110,
    ),
    Section(
        "ranks",
        "Звания",
        models.RankAssignment,
        ("rank", "date_from", "date_to", "order"),
        group=MILITARY,
        order=120,
    ),
    Section(
        "service",
        "Служба",
        models.MilitaryService,
        ("unit", "speciality", "date_from", "date_to", "order_in", "order_out"),
        group=MILITARY,
        order=130,
    ),
    Section(
        "trainings",
        "Сборы",
        models.Training,
        ("year", "days", "organization", "speciality"),
        group=MILITARY,
        order=140,
    ),
    Section(
        "oaths",
        "Присяга",
        models.Oath,
        ("date", "place", "height", "head_size", "clothing_size", "shoe_size"),
        group=MILITARY,
        order=150,
    ),
    Section(
        "removals",
        "Снятие с учёта",
        models.Removal,
        ("date", "reason", "note"),
        group=MILITARY,
        order=160,
    ),
    Section(
        "awards",
        "Награды",
        models.PersonAward,
        ("award", "date", "category", "document_number", "issued_by"),
        group=MILITARY,
        order=170,
    ),
    Section(
        "special-accounts",
        "Спецучёт",
        models.SpecialAccount,
        ("series", "number", "activity", "paragraph", "registered_on", "withdrawn_on"),
        group=MILITARY,
        order=180,
    ),
    Section(
        "reservation-dismissals",
        "Увольнения брони",
        models.ReservationDismissal,
        ("order", "dismissal_date"),
        group=MILITARY,
        order=190,
    ),
]


def register_sections():
    for section in SECTIONS:
        register(section)
