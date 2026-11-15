from django import forms

from .categories import category_choices
from .hr_source import MAX_FILE_SIZE
from .models import ProfessionCode


class UploadForm(forms.Form):
    file = forms.FileField(
        label="Кадровый архив ZIP",
        widget=forms.ClearableFileInput(attrs={"accept": ".zip"}),
    )
    confirm = forms.BooleanField(label="Применить изменения в базе", required=False)

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > MAX_FILE_SIZE:
            raise forms.ValidationError("Размер файла превышает 200 МБ.")
        if not file.name.lower().endswith(".zip"):
            raise forms.ValidationError("Нужен архив в формате .zip.")
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
    row_number = forms.TypedChoiceField(
        label="Категория работника", coerce=int, empty_value=None, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["row_number"].choices = category_choices(self.instance.row_number)

    class Meta:
        model = ProfessionCode
        fields = ("row_number",)
