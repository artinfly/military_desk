from django import forms

from apps.core.forms import DateInput


class PeriodForm(forms.Form):
    """Период отчёта; пустые границы не ограничивают."""

    date_from = forms.DateField(label="С", required=False, widget=DateInput)
    date_to = forms.DateField(label="По", required=False, widget=DateInput)

    def clean(self):
        data = super().clean()
        start, end = data.get("date_from"), data.get("date_to")
        if start and end and start > end:
            raise forms.ValidationError("Начало периода позже конца.")
        return data
