from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Пользователи: стандартная админка Django + ФИО полностью, подразделение, должность."""

    list_display = ("username", "full_name", "department", "is_active", "is_staff")
    search_fields = ("username", "last_name", "first_name", "patronymic", "department")
    ordering = ("last_name", "first_name", "username")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Сотрудник",
            {
                "fields": (
                    "last_name",
                    "first_name",
                    "patronymic",
                    "department",
                    "position",
                )
            },
        ),
        (
            "Права",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "last_name",
                    "first_name",
                    "patronymic",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    @admin.display(description="ФИО")
    def full_name(self, user):
        return user.full_name
