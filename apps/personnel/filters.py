"""Форма фильтров списка учётных карточек (все поля необязательные, сочетаются)."""

from django import forms

from apps.core.widgets import use_reference_picker
from apps.references import models as ref


def _choice(model, label):
    return use_reference_picker(
        forms.ModelChoiceField(
            queryset=model.objects.active(),
            required=False,
            label=label,
            empty_label="Все",
        )
    )


class PersonFilterForm(forms.Form):
    STATUS_CHOICES = [
        ("working", "Работающие"),
        ("dismissed", "Уволенные"),
        ("all", "Все"),
    ]

    q = forms.CharField(
        label="ФИО или табельный номер",
        required=False,
        widget=forms.TextInput(
            attrs={"type": "search", "placeholder": "ФИО или табельный номер"}
        ),
    )
    status = forms.ChoiceField(
        label="Работа", choices=STATUS_CHOICES, required=False, initial="working"
    )
    duty = _choice(ref.MilitaryDuty, "Военная обязанность")
    account_type = _choice(ref.SpecialAccountType, "Вид учёта")
    department = _choice(ref.Department, "Цех")
    commissariat = _choice(ref.MilitaryCommissariat, "Военкомат")
    attribute_value = _choice(ref.AttributeValue, "Доп. атрибут")
    speciality = forms.CharField(
        label="ВУС",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "код или название"}),
    )
    officers = forms.BooleanField(label="Офицеры", required=False)
    reserved = forms.BooleanField(label="Забронированные", required=False)
    svo = forms.BooleanField(label="Участники СВО", required=False)
    no_military = forms.BooleanField(label="Без воинского учёта", required=False)

    SELECTS = [
        "duty",
        "account_type",
        "department",
        "commissariat",
        "attribute_value",
        "speciality",
    ]
    FLAGS = ["officers", "reserved", "svo", "no_military"]

    MILITARY_FIELDS = {
        "duty",
        "account_type",
        "commissariat",
        "speciality",
        "officers",
        "reserved",
        "no_military",
    }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.forbidden_filters = set()
        if user is not None:
            if not user.has_perm("military.view_militaryrecord"):
                self.forbidden_filters |= self.MILITARY_FIELDS
            if not user.has_perm("personnel.view_additionalattribute"):
                self.forbidden_filters.add("attribute_value")
        for name in self.forbidden_filters:
            self.fields.pop(name, None)

    def clean(self):
        cleaned = super().clean()
        if any(self.data.get(name) for name in self.forbidden_filters):
            raise forms.ValidationError("Недостаточно прав для выбранных фильтров.")
        return cleaned

    def selects(self):
        """Поля второй строки фильтров (выпадающие списки и ВУС)."""
        return [self[name] for name in self.SELECTS if name in self.fields]

    def flags(self):
        """Флажки третьей строки."""
        return [self[name] for name in self.FLAGS if name in self.fields]
