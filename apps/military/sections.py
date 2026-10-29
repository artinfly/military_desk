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
