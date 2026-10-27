"""Справочники (НСИ).

Все справочники построены на общей абстрактной модели Reference: название, код,
порядок и признак «Действует». Записи не удаляются, а помечаются недействующими:
на них ссылаются учётные карточки. Недействующие не предлагаются при выборе
(Model.objects.active()).

Код — номер записи в старой программе и в выгрузке из кадровой системы
(vus.csv ссылается на звания, ВУС и т.п. по этим номерам); по нему же
переносятся данные из старой базы.
"""

from django.db import models
from django.db.models import Q


class ReferenceQuerySet(models.QuerySet):
    def active(self):
        """Только действующие записи — для выбора в формах."""
        return self.filter(is_active=True)


class Reference(models.Model):
    """Общий шаблон справочника. Своей таблицы нет (abstract)."""

    name = models.CharField(
        "Название",
        max_length=255,
        unique=True,
        error_messages={"unique": "Запись с таким названием уже есть."},
    )
    code = models.CharField(
        "Код",
        max_length=50,
        blank=True,
        help_text="Номер в старой программе и в выгрузке из кадровой системы.",
    )
    sort_order = models.PositiveIntegerField(
        "Порядок",
        default=0,
        help_text="Порядок в списках; при равном — по названию.",
    )
    is_active = models.BooleanField("Действует", default=True)

    objects = ReferenceQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ["sort_order", "name"]
        constraints = [
            # Код уникален, если заполнен
            models.UniqueConstraint(
                fields=["code"],
                condition=~Q(code=""),
                name="%(app_label)s_%(class)s_unique_code",
                violation_error_message="Запись с таким кодом уже есть.",
            )
        ]

    def __str__(self):
        return self.name


# --- Воинский учёт ---


class MilitaryRank(Reference):
    is_officer = models.BooleanField(
        "Офицерское",
        default=False,
        help_text="Для фильтра «Офицеры» и отчёта по численности.",
    )

    class Meta(Reference.Meta):
        verbose_name = "воинское звание"
        verbose_name_plural = "воинские звания"


class MilitaryDuty(Reference):
    class Meta(Reference.Meta):
        verbose_name = "военная обязанность"
        verbose_name_plural = "военная обязанность"


class MilitarySpeciality(Reference):
    in_reservation_list = models.BooleanField(
        "В перечне для приложения 1",
        default=False,
        help_text="ВУС из перечня: человек попадает в приложение 1 формы бронирования.",
    )

    class Meta(Reference.Meta):
        verbose_name = "ВУС"
        verbose_name_plural = "ВУС"


class MilitaryCommissariat(Reference):
    class Meta(Reference.Meta):
        verbose_name = "военкомат"
        verbose_name_plural = "военкоматы"


class ReserveCategory(Reference):
    class Meta(Reference.Meta):
        verbose_name = "категория запаса"
        verbose_name_plural = "категории запаса"


class ReserveComposition(Reference):
    class Meta(Reference.Meta):
        verbose_name = "состав запаса"
        verbose_name_plural = "составы запаса"


class FitnessCategory(Reference):
    class Meta(Reference.Meta):
        verbose_name = "категория годности"
        verbose_name_plural = "категории годности к военной службе"


class AccountingGroup(Reference):
    class Meta(Reference.Meta):
        verbose_name = "группа учёта"
        verbose_name_plural = "группы учёта"


class SpecialAccountType(Reference):
    class Meta(Reference.Meta):
        verbose_name = "вид спецучёта"
        verbose_name_plural = "виды специального учёта"


class ArmyPosition(Reference):
    class Meta(Reference.Meta):
        verbose_name = "должность в армии"
        verbose_name_plural = "должности в армии"


class RegistrationDocument(Reference):
    in_reservation_appendix = models.BooleanField(
        "Отдельно в приложении 2",
        default=False,
        help_text="Люди с таким документом идут в приложение 2 формы бронирования, "
        "а не в саму форму и приложение 1.",
    )

    class Meta(Reference.Meta):
        verbose_name = "документ воинского учёта"
        verbose_name_plural = "документы воинского учёта"


class IssuingAuthority(Reference):
    class Meta(Reference.Meta):
        verbose_name = "кем выдан"
        verbose_name_plural = "кем выданы документы"


class RemovalReason(Reference):
    class Meta(Reference.Meta):
        verbose_name = "причина снятия с учёта"
        verbose_name_plural = "причины снятия с учёта"


class Award(Reference):
    class Meta(Reference.Meta):
        verbose_name = "награда"
        verbose_name_plural = "награды"


# --- Работа на предприятии ---


class Department(Reference):
    """Цех (подразделение): номер и название; одинаковые названия у разных номеров допустимы."""

    name = models.CharField("Название", max_length=255)
    number = models.CharField("Номер цеха", max_length=20, blank=True)

    class Meta(Reference.Meta):
        verbose_name = "цех"
        verbose_name_plural = "цеха"
        ordering = ["sort_order", "number", "name"]
        constraints = Reference.Meta.constraints + [
            models.UniqueConstraint(
                fields=["number", "name"],
                name="references_department_unique_number_name",
                violation_error_message="Цех с таким номером и названием уже есть.",
            )
        ]

    def __str__(self):
        return f"{self.number} {self.name}".strip()


class ProductionType(Reference):
    level = models.CharField("Уровень", max_length=50, blank=True)

    class Meta(Reference.Meta):
        verbose_name = "производство"
        verbose_name_plural = "производства"


class Branch(Reference):
    address = models.CharField("Адрес", max_length=500, blank=True)

    class Meta(Reference.Meta):
        verbose_name = "филиал"
        verbose_name_plural = "филиалы"


class WorkerCategory(Reference):
    class Meta(Reference.Meta):
        verbose_name = "категория работников"
        verbose_name_plural = "категории работников"


class Profession(Reference):
    okpdtr = models.CharField("Код ОКПДТР", max_length=20, blank=True)

    class Meta(Reference.Meta):
        verbose_name = "профессия"
        verbose_name_plural = "профессии"


class WorkStatus(Reference):
    class Meta(Reference.Meta):
        verbose_name = "статус работника"
        verbose_name_plural = "статусы работника"


class Activity(Reference):
    class Meta(Reference.Meta):
        verbose_name = "вид деятельности"
        verbose_name_plural = "виды деятельности"


# --- Адреса ---


class Region(Reference):
    class Meta(Reference.Meta):
        verbose_name = "регион"
        verbose_name_plural = "регионы"


class City(Reference):
    """Населённый пункт; код — по КЛАДР."""

    name = models.CharField("Название", max_length=255)

    class Meta(Reference.Meta):
        verbose_name = "населённый пункт"
        verbose_name_plural = "населённые пункты"


class Street(Reference):
    """Улица; код — по КЛАДР (у одноимённых улиц в разных городах коды разные)."""

    name = models.CharField("Название", max_length=255)

    class Meta(Reference.Meta):
        verbose_name = "улица"
        verbose_name_plural = "улицы"


class AddressType(Reference):
    class Meta(Reference.Meta):
        verbose_name = "тип адреса"
        verbose_name_plural = "типы адреса"


# --- Дополнительные атрибуты карточки ---


class AttributeType(Reference):
    """Вид дополнительного атрибута (например, участие в боевых действиях)."""

    class Meta(Reference.Meta):
        verbose_name = "вид доп. атрибута"
        verbose_name_plural = "виды доп. атрибутов"


class AttributeValue(Reference):
    class Meta(Reference.Meta):
        verbose_name = "значение доп. атрибута"
        verbose_name_plural = "значения доп. атрибутов"


# --- Прочее ---


class FamilyStatus(Reference):
    class Meta(Reference.Meta):
        verbose_name = "семейное положение"
        verbose_name_plural = "семейное положение"


class RelationType(Reference):
    class Meta(Reference.Meta):
        verbose_name = "степень родства"
        verbose_name_plural = "степени родства"


class Language(Reference):
    class Meta(Reference.Meta):
        verbose_name = "язык"
        verbose_name_plural = "языки"
