"""Общая основа форм проекта."""

from django import forms
from django.db import models
from django.db.models import Q


class DateInput(forms.DateInput):
    """Поле даты с календарём браузера (значение в формате ГГГГ-ММ-ДД)."""

    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs, format="%Y-%m-%d")


def formfield_callback(field, **kwargs):
    """Поля дат — с календарём; остальные — как обычно."""
    if isinstance(field, models.DateField) and not isinstance(
        field, models.DateTimeField
    ):
        kwargs.setdefault("widget", DateInput)
    return field.formfield(**kwargs)


class BaseModelForm(forms.ModelForm):
    """Форма модели: даты с календарём; в списках справочников — только действующие
    записи плюс уже выбранная (даже если её пометили недействующей)."""

    formfield_callback = formfield_callback

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            queryset = getattr(field, "queryset", None)
            if queryset is None or not hasattr(queryset, "active"):
                continue
            current = getattr(self.instance, f"{name}_id", None)
            field.queryset = queryset.filter(Q(is_active=True) | Q(pk=current))
