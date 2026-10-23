"""Форма фильтров списка учётных карточек (все поля необязательные, сочетаются)."""

from django import forms

from apps.references import models as ref


def _choice(model, label):
    return forms.ModelChoiceField(
        queryset=model.objects.active(), required=False, label=label, empty_label="Все"
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

    def selects(self):
        """Поля второй строки фильтров (выпадающие списки и ВУС)."""
        return [self[name] for name in self.SELECTS]

    def flags(self):
        """Флажки третьей строки."""
        return [self[name] for name in self.FLAGS]
