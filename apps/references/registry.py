"""Реестр справочников: какие есть, в каком разделе каталога и под каким адресом.

По реестру строятся каталог, списки, формы и админка. Новый справочник:
модель в models.py + строка здесь.
"""

from dataclasses import dataclass

from django.http import Http404

from . import models

# Поля общего шаблона Reference; всё остальное у модели — её собственные поля
BASE_FIELDS = ("id", "name", "code", "sort_order", "is_active")


@dataclass(frozen=True)
class ReferenceType:
    slug: str  # часть адреса: /references/<slug>/
    model: type
    section: str

    @property
    def title(self):
        name = self.model._meta.verbose_name_plural
        return name[:1].upper() + name[1:]

    @property
    def extra_fields(self):
        """Собственные поля справочника (номер цеха, адрес филиала, код ОКПДТР…)."""
        return [f.name for f in self.model._meta.fields if f.name not in BASE_FIELDS]

    @property
    def form_fields(self):
        """Поля формы: название, собственные поля, код, порядок, «Действует»."""
        return ["name", *self.extra_fields, "code", "sort_order", "is_active"]

    @property
    def list_fields(self):
        """Колонки списка: название и собственные поля."""
        return ["name", *self.extra_fields]

    def perm(self, action):
        """Имя права Django на действие (add/change) с этим справочником."""
        return f"{self.model._meta.app_label}.{action}_{self.model._meta.model_name}"


MILITARY = "Воинский учёт"
WORK = "Работа на предприятии"
ADDRESS = "Адреса"
OTHER = "Прочее"

REFERENCES = [
    ReferenceType("military-ranks", models.MilitaryRank, MILITARY),
    ReferenceType("military-duties", models.MilitaryDuty, MILITARY),
    ReferenceType("military-specialities", models.MilitarySpeciality, MILITARY),
    ReferenceType("commissariats", models.MilitaryCommissariat, MILITARY),
    ReferenceType("reserve-categories", models.ReserveCategory, MILITARY),
    ReferenceType("reserve-compositions", models.ReserveComposition, MILITARY),
    ReferenceType("fitness-categories", models.FitnessCategory, MILITARY),
    ReferenceType("accounting-groups", models.AccountingGroup, MILITARY),
    ReferenceType("special-account-types", models.SpecialAccountType, MILITARY),
    ReferenceType("army-positions", models.ArmyPosition, MILITARY),
    ReferenceType("registration-documents", models.RegistrationDocument, MILITARY),
    ReferenceType("issuing-authorities", models.IssuingAuthority, MILITARY),
    ReferenceType("removal-reasons", models.RemovalReason, MILITARY),
    ReferenceType("awards", models.Award, MILITARY),
    ReferenceType("departments", models.Department, WORK),
    ReferenceType("production-types", models.ProductionType, WORK),
    ReferenceType("branches", models.Branch, WORK),
    ReferenceType("worker-categories", models.WorkerCategory, WORK),
    ReferenceType("professions", models.Profession, WORK),
    ReferenceType("work-statuses", models.WorkStatus, WORK),
    ReferenceType("activities", models.Activity, WORK),
    ReferenceType("regions", models.Region, ADDRESS),
    ReferenceType("cities", models.City, ADDRESS),
    ReferenceType("streets", models.Street, ADDRESS),
    ReferenceType("address-types", models.AddressType, ADDRESS),
    ReferenceType("attribute-types", models.AttributeType, OTHER),
    ReferenceType("attribute-values", models.AttributeValue, OTHER),
    ReferenceType("family-statuses", models.FamilyStatus, OTHER),
    ReferenceType("relation-types", models.RelationType, OTHER),
    ReferenceType("languages", models.Language, OTHER),
]

_BY_SLUG = {ref.slug: ref for ref in REFERENCES}


def get_reference(slug):
    """Справочник по части адреса или 404."""
    try:
        return _BY_SLUG[slug]
    except KeyError:
        raise Http404("Справочник не найден") from None


def sections():
    """Справочники по разделам каталога: [(раздел, [ReferenceType, …]), …]."""
    grouped = {}
    for ref in REFERENCES:
        grouped.setdefault(ref.section, []).append(ref)
    return list(grouped.items())
