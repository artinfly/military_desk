"""Учётные карточки в админке: карточка и её разделы на одной странице.

Разделы воинского учёта добавляет apps/military/admin.py (оно расширяет PersonAdmin),
чтобы personnel не зависел от military.
"""

from django.contrib import admin

from . import models


class SectionInline(admin.TabularInline):
    extra = 0
    show_change_link = False


class DocumentInline(SectionInline):
    model = models.IdentityDocument


class AddressInline(admin.StackedInline):
    model = models.Address
    extra = 0
    classes = ("collapse",)


class RelativeInline(SectionInline):
    model = models.Relative


class EducationInline(admin.StackedInline):
    model = models.Education
    extra = 0
    classes = ("collapse",)


class AssignmentInline(SectionInline):
    model = models.Assignment


class AttributeInline(SectionInline):
    model = models.AdditionalAttribute


@admin.register(models.Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = (
        "tab_number",
        "full_name",
        "birth_date",
        "department",
        "position",
        "is_working",
    )
    list_filter = ("gender", "is_svo", "department")
    search_fields = ("tab_number", "last_name", "first_name", "patronymic", "snils")
    readonly_fields = ("created_at", "updated_at", "updated_by")
    list_select_related = ("department",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "tab_number",
                    ("last_name", "first_name", "patronymic"),
                    ("gender", "birth_date"),
                    "birth_place",
                    ("previous_last_name", "last_name_changed_on"),
                )
            },
        ),
        (
            "Личные данные",
            {
                "fields": (
                    ("citizenship", "nationality"),
                    ("inn", "snils", "card_number"),
                    ("phone", "email"),
                )
            },
        ),
        (
            "Работа",
            {
                "fields": (
                    ("employment_date", "dismissal_date"),
                    ("department", "position"),
                    ("hire_type", "hire_source"),
                    "is_svo",
                )
            },
        ),
        ("Изменения", {"fields": (("created_at", "updated_at", "updated_by"),)}),
    )
    inlines = [
        DocumentInline,
        AddressInline,
        RelativeInline,
        EducationInline,
        AssignmentInline,
        AttributeInline,
    ]

    @admin.display(description="ФИО", ordering="last_name")
    def full_name(self, person):
        return person.full_name

    @admin.display(description="Работает", boolean=True)
    def is_working(self, person):
        return person.is_working

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
