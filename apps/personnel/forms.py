"""Форма основных данных учётной карточки (вкладка «Общее»)."""

from apps.core.forms import BaseModelForm

from .models import Person

# Группы полей: (заголовок, поля) — для просмотра и формы
GENERAL_FIELDSETS = (
    (
        "Основное",
        (
            "tab_number",
            "last_name",
            "first_name",
            "patronymic",
            "gender",
            "birth_date",
            "birth_place",
            "previous_last_name",
            "last_name_changed_on",
        ),
    ),
    (
        "Личные данные",
        (
            "citizenship",
            "nationality",
            "inn",
            "snils",
            "card_number",
            "phone",
            "email",
        ),
    ),
    (
        "Работа",
        (
            "employment_date",
            "dismissal_date",
            "department",
            "position",
            "hire_type",
            "hire_source",
            "is_svo",
        ),
    ),
)


class PersonForm(BaseModelForm):
    class Meta:
        model = Person
        fields = [name for _title, names in GENERAL_FIELDSETS for name in names]

    def clean(self):
        cleaned = super().clean()
        hired, dismissed = cleaned.get("employment_date"), cleaned.get("dismissal_date")
        if hired and dismissed and dismissed < hired:
            self.add_error("dismissal_date", "Дата увольнения раньше даты приёма.")
        return cleaned
