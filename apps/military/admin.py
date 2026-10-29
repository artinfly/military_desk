"""Воинский учёт в админке: разделы на странице учётной карточки.

Расширяет PersonAdmin из personnel, добавляя разделы воинского учёта.
"""

from django.contrib import admin

from apps.personnel.admin import PersonAdmin as BasePersonAdmin
from apps.personnel.models import Person

from . import models


class MilitaryRecordInline(admin.StackedInline):
    model = models.MilitaryRecord
    can_delete = False
    fieldsets = (
        (
            "Документ",
            {
                "fields": (
                    ("document_type", "document_series", "document_number"),
                    "document_date",
                )
            },
        ),
        (
            "Учёт",
            {
                "fields": (
                    ("duty", "rank", "speciality"),
                    ("accounting_group", "reserve_category", "reserve_composition"),
                    ("fitness_category", "commissariat", "special_account_type"),
                    ("mobilization_order", "mobilization_letter", "gpz"),
                    "note",
                )
            },
        ),
        (
            "Бронирование",
            {
                "fields": (
                    ("is_reserved", "reservation_document", "unreservation_order"),
                )
            },
        ),
    )


def _inline(model_class):
    return type(
        f"{model_class.__name__}Inline",
        (admin.TabularInline,),
        {"model": model_class, "extra": 0},
    )


MILITARY_INLINES = [
    MilitaryRecordInline,
    *(
        _inline(m)
        for m in (
            models.CommissariatRegistration,
            models.ReservationDismissal,
        )
    ),
]


admin.site.unregister(Person)


@admin.register(Person)
class PersonAdmin(BasePersonAdmin):
    inlines = [MILITARY_INLINES[0], *BasePersonAdmin.inlines, *MILITARY_INLINES[1:]]
    list_filter = (*BasePersonAdmin.list_filter, "military__is_reserved")
