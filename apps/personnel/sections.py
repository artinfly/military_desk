"""Реестр разделов учётной карточки (вкладки карточки).

Раздел — модель со ссылкой на карточку (поле person). По реестру строятся вкладки,
таблицы, формы добавления/правки и удаление — общими страницами.

Приложения, которые расширяют карточку (military), регистрируют свои разделы сами
в AppConfig.ready() — personnel о них не знает.
"""

from dataclasses import dataclass, field

from django.forms import modelform_factory
from django.http import Http404

from apps.core.forms import BaseModelForm

from . import models

PERSONAL = "Личное"
MILITARY = "Воинский учёт"


@dataclass(frozen=True)
class Section:
    slug: str  # вкладка: ?tab=<slug>
    title: str
    model: type
    columns: tuple = ()  # колонки таблицы списка
    group: str = PERSONAL
    order: int = 100
    single: bool = False  # один на карточку (OneToOne): просмотр + одна форма
    template: str = ""  # свой шаблон вкладки (для single)
    fieldsets: tuple = field(default=())  # ((заголовок, (поля, …)), …) — для single

    def form_class(self):
        """Форма раздела: все поля модели, кроме ссылки на карточку."""
        return modelform_factory(self.model, form=BaseModelForm, exclude=("person",))

    def perm(self, action):
        """Право Django на действие (add/change/delete) с моделью раздела."""
        meta = self.model._meta
        return f"{meta.app_label}.{action}_{meta.model_name}"

    def items(self, person):
        """Записи раздела у карточки (со справочными значениями одним запросом)."""
        related = [
            f.name
            for f in self.model._meta.fields
            if f.is_relation and f.name != "person"
        ]
        return self.model.objects.filter(person=person).select_related(*related)


_REGISTRY = {}


def register(section):
    if section.slug in _REGISTRY or section.slug == "general":
        raise ValueError(f"Раздел карточки «{section.slug}» уже есть")
    _REGISTRY[section.slug] = section


def all_sections():
    return sorted(_REGISTRY.values(), key=lambda s: s.order)


def get_section(slug):
    try:
        return _REGISTRY[slug]
    except KeyError:
        raise Http404("Раздел карточки не найден") from None


# --- Разделы personnel ---

for _section in [
    Section(
        "documents",
        "Документы",
        models.IdentityDocument,
        ("document_type", "series", "number", "issue_date", "issued_by", "valid_until"),
        order=10,
    ),
    Section(
        "addresses",
        "Адреса",
        models.Address,
        ("address_type", "__str__", "registration_date", "date_from", "date_to"),
        order=20,
    ),
    Section(
        "relatives",
        "Родственники",
        models.Relative,
        (
            "relation",
            "last_name",
            "first_name",
            "patronymic",
            "birth_date",
            "is_dependent",
        ),
        order=30,
    ),
    Section(
        "education",
        "Образование",
        models.Education,
        ("education_type", "institution", "speciality", "graduation_date", "is_main"),
        order=40,
    ),
    Section(
        "assignments",
        "Назначения",
        models.Assignment,
        (
            "department",
            "position",
            "status",
            "order_number",
            "order_date",
            "date_from",
            "date_to",
        ),
        order=50,
    ),
    Section(
        "languages", "Языки", models.LanguageSkill, ("language", "level"), order=60
    ),
    Section(
        "professions",
        "Профессии",
        models.PersonProfession,
        ("profession", "worker_category", "speciality", "date_from", "is_main"),
        order=70,
    ),
    Section(
        "passes",
        "Пропуска",
        models.Pass,
        ("number", "office", "date_from", "date_to"),
        order=80,
    ),
    Section(
        "attributes",
        "Доп. атрибуты",
        models.AdditionalAttribute,
        ("attribute", "value", "date_from", "date_to", "note"),
        order=90,
    ),
]:
    register(_section)
