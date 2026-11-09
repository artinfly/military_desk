from django import forms

from .hr_source import MAX_FILE_SIZE
from .models import ProfessionCode


class UploadForm(forms.Form):
    kind = forms.ChoiceField(
        label="Формат данных",
        choices=(
            ("hr", "Кадровая выгрузка vus.csv"),
            ("extended", "Дополнительные коды vus_ext.csv"),
        ),
    )
    file = forms.FileField(
        label="Файл TSV", widget=forms.ClearableFileInput(attrs={"accept": ".csv,.tsv"})
    )
    confirm = forms.BooleanField(label="Применить изменения в базе", required=False)

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > MAX_FILE_SIZE:
            raise forms.ValidationError("Размер файла превышает 200 МБ.")
        if not file.name.lower().endswith((".csv", ".tsv")):
            raise forms.ValidationError(
                "Нужен файл .csv или .tsv с разделителем табуляции."
            )
        return file


class DbfForm(forms.Form):
    kind = forms.ChoiceField(
        label="Исходный файл",
        choices=(
            ("proff", "proff.dbf → proff.dbf"),
            ("kadr", "KADR_EDAY.dbf → kadr940.dbf"),
        ),
    )
    file = forms.FileField(
        label="Файл DBF", widget=forms.ClearableFileInput(attrs={"accept": ".dbf"})
    )

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > MAX_FILE_SIZE or not file.name.lower().endswith(".dbf"):
            raise forms.ValidationError("Нужен файл .dbf размером не более 200 МБ.")
        return file


class ProfessionCodeForm(forms.ModelForm):
    class Meta:
        model = ProfessionCode
        fields = ("row_number",)
