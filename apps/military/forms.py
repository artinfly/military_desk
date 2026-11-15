"""Формы массовых операций воинского учёта."""

from django import forms

from apps.references.models import AccountingGroup, SpecialAccountType

from .account_codes import booking_codes


class ChangeAccountTypeForm(forms.Form):
    old_type = forms.ModelChoiceField(
        SpecialAccountType.objects.all(),
        label="Текущий вид учёта",
        empty_label="— выберите —",
    )
    new_type = forms.ModelChoiceField(
        SpecialAccountType.objects.all(),
        label="Новый вид учёта",
        required=False,
        empty_label="— убрать вид учёта —",
    )

    def clean(self):
        data = super().clean()
        if data.get("old_type") and data.get("old_type") == data.get("new_type"):
            raise forms.ValidationError("Новый вид учёта совпадает с текущим.")
        return data


class UnreserveForm(forms.Form):
    file = forms.FileField(
        label="Файл Excel со СНИЛС",
        help_text="Первая колонка — ФИО, вторая — СНИЛС. Данные со второй строки.",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )
    order = forms.CharField(label="Номер приказа о разбронировании", max_length=50)

    def clean_file(self):
        file = self.cleaned_data["file"]
        if not file.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Нужен файл Excel в формате .xlsx.")
        return file


class ReserveForm(UnreserveForm):
    accounting_group = forms.ModelChoiceField(
        AccountingGroup.objects.active(),
        label="Группа учёта",
        required=False,
        empty_label="— сохранить текущую —",
    )

    order = forms.CharField(label="Номер приказа о бронировании", max_length=50)
    account_type = forms.ModelChoiceField(
        SpecialAccountType.objects.none(),
        label="Вид учёта",
        empty_label="— выберите —",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[
            "account_type"
        ].queryset = SpecialAccountType.objects.active().filter(
            code__in=booking_codes()
        )
