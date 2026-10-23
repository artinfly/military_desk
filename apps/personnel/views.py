"""Страницы учётных карточек."""

from django.views.generic import ListView

from .filters import PersonFilterForm
from .services import search_people, sort_people

# Колонки списка: (ключ сортировки или None, заголовок)
COLUMNS = [
    ("tab_number", "Таб. номер"),
    ("name", "ФИО"),
    ("rank", "Звание"),
    (None, "Пол"),
    ("birth_date", "Дата рождения"),
    ("dismissal_date", "Дата увольнения"),
    ("duty", "Военная обязанность"),
    ("department", "Место работы"),
    (None, "Учёт"),
    (None, "Бронь"),
    (None, "СВО"),
]


class PersonListView(ListView):
    """Список учётных карточек с фильтрами (как главное окно старой программы)."""

    template_name = "personnel/person_list.html"
    paginate_by = 50
    extra_context = {"page_title": "Учётные карточки"}

    def get_queryset(self):
        self.form = PersonFilterForm(self.request.GET or None)
        filters = self.form.cleaned_data if self.form.is_valid() else {}
        people, self.sort = sort_people(
            search_people(filters), self.request.GET.get("sort", "")
        )
        return people

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        params.pop("sort", None)
        context.update(
            form=self.form,
            sort=self.sort,
            columns=[
                {
                    "title": title,
                    "key": key,
                    "active": key and self.sort.lstrip("-") == key,
                    "descending": self.sort.startswith("-"),
                    # Повторный клик по той же колонке меняет направление
                    "next": f"-{key}" if key and self.sort == key else key,
                }
                for key, title in COLUMNS
            ],
            filter_params=params.urlencode(),
            has_filters=any(
                v for k, v in self.request.GET.items() if k not in ("page", "sort")
            ),
        )
        return context
