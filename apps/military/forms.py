"""Формы массовых операций воинского учёта."""

from django import forms

from apps.references.models import SpecialAccountType


class ChangeAccountTypeForm(forms.Form):
    old_type = forms.ModelChoiceField(
        SpecialAccountType.objects.all(),
        label="Текущая группа учёта",
        empty_label="— выберите —",
    )
    new_type = forms.ModelChoiceField(
        SpecialAccountType.objects.all(),
        label="Новая группа учёта",
        required=False,
        empty_label="— убрать группу —",
    )

    def clean(self):
        data = super().clean()
        if data.get("old_type") and data.get("old_type") == data.get("new_type"):
            raise forms.ValidationError("Новая группа совпадает с текущей.")
        return data


class UnreserveForm(forms.Form):
    file = forms.FileField(
        label="Файл Excel со СНИЛС",
        help_text="СНИЛС — в первой колонке, со второй строки (первая — заголовок).",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )
    order = forms.CharField(label="Номер приказа о разбронировании", max_length=50)

    def clean_file(self):
        file = self.cleaned_data["file"]
        if not file.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Нужен файл Excel в формате .xlsx.")
        return file
