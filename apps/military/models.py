"""Воинский учёт работника.

MilitaryRecord — основные сведения (один на учётную карточку), остальные модели —
истории и списки: военкоматы, звания, служба, сборы, присяга, снятие с учёта,
награды, спецучёт, увольнения забронированных.
"""

from django.db import models

from apps.core.models import PeriodModel, TimeStampedModel
from apps.personnel.models import Person
from apps.references import models as ref


def _ref(model, verbose_name, **kwargs):
    """Необязательная ссылка на справочник (удалять используемую запись нельзя)."""
    return models.ForeignKey(
        model,
        verbose_name=verbose_name,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        **kwargs,
    )


class MilitaryRecord(TimeStampedModel):
    """Сведения о воинском учёте (один к одному с учётной карточкой)."""

    person = models.OneToOneField(
        Person,
        verbose_name="Учётная карточка",
        on_delete=models.CASCADE,
        related_name="military",
    )

    # Документ воинского учёта
    document_type = _ref(ref.RegistrationDocument, "Документ воинского учёта")
    document_series = models.CharField("Серия", max_length=20, blank=True)
    document_number = models.CharField("Номер", max_length=30, blank=True)
    document_date = models.DateField("Дата выдачи", null=True, blank=True)
    issued_by = _ref(ref.IssuingAuthority, "Кем выдан")

    # Учётные данные
    duty = _ref(ref.MilitaryDuty, "Военная обязанность")
    rank = _ref(ref.MilitaryRank, "Воинское звание")
    speciality = _ref(ref.MilitarySpeciality, "ВУС")
    accounting_group = _ref(ref.AccountingGroup, "Группа учёта")
    reserve_category = _ref(ref.ReserveCategory, "Категория запаса")
    reserve_composition = _ref(ref.ReserveComposition, "Состав")
    fitness_category = _ref(ref.FitnessCategory, "Категория годности")
    commissariat = _ref(ref.MilitaryCommissariat, "Военкомат")
    special_account_type = _ref(ref.SpecialAccountType, "Вид учёта")
    mobilization_order = models.CharField(
        "Мобпредписание: номер", max_length=50, blank=True
    )
    mobilization_letter = models.CharField(
        "Мобпредписание: литер", max_length=20, blank=True
    )
    gpz = models.CharField("ГПЗ", max_length=30, blank=True)
    note = models.CharField("Примечание", max_length=500, blank=True)

    # Бронирование
    is_reserved = models.BooleanField("Забронирован", default=False)
    reservation_document = models.CharField(
        "Удостоверение об отсрочке (номер)", max_length=50, blank=True
    )
    unreservation_order = models.CharField(
        "Приказ о разбронировании", max_length=50, blank=True
    )

    class Meta:
        verbose_name = "воинский учёт"
        verbose_name_plural = "воинский учёт"

    def __str__(self):
        return f"Воинский учёт: {self.person}"


class MilitarySection(models.Model):
    """Общее для списков воинского учёта: ссылка на карточку."""

    person = models.ForeignKey(
        Person, verbose_name="Учётная карточка", on_delete=models.CASCADE
    )

    class Meta:
        abstract = True


class CommissariatRegistration(MilitarySection, PeriodModel):
    """Приписка к военкомату (история)."""

    commissariat = models.ForeignKey(
        ref.MilitaryCommissariat, verbose_name="Военкомат", on_delete=models.PROTECT
    )

    class Meta:
        verbose_name = "приписка к военкомату"
        verbose_name_plural = "места приписки"
        ordering = ["-date_from"]
        default_related_name = "commissariat_history"
        constraints = [
            models.UniqueConstraint(
                fields=["person", "commissariat", "date_from", "date_to"],
                name="military_commissariat_registration_unique",
            )
        ]

    def __str__(self):
        return str(self.commissariat)


class RankAssignment(MilitarySection, PeriodModel):
    """Присвоение воинского звания (история)."""

    rank = models.ForeignKey(
        ref.MilitaryRank, verbose_name="Звание", on_delete=models.PROTECT
    )
    order = models.CharField("Приказ", max_length=150, blank=True)

    class Meta:
        verbose_name = "присвоение звания"
        verbose_name_plural = "звания"
        ordering = ["-date_from"]
        default_related_name = "rank_history"

    def __str__(self):
        return str(self.rank)


class MilitaryService(MilitarySection, PeriodModel):
    """Прохождение военной службы."""

    unit = models.CharField("Воинская часть", max_length=255, blank=True)
    speciality = _ref(ref.MilitarySpeciality, "ВУС")
    order_in = models.CharField("Приказ о зачислении", max_length=150, blank=True)
    order_out = models.CharField("Приказ об исключении", max_length=150, blank=True)

    class Meta:
        verbose_name = "военная служба"
        verbose_name_plural = "военная служба"
        ordering = ["-date_from"]
        default_related_name = "services"

    def __str__(self):
        return self.unit


class Training(MilitarySection):
    """Военные сборы."""

    year = models.PositiveSmallIntegerField("Год", null=True, blank=True)
    days = models.PositiveSmallIntegerField("Дней", null=True, blank=True)
    organization = models.CharField("Где проходил", max_length=255, blank=True)
    speciality = _ref(ref.MilitarySpeciality, "ВУС")

    class Meta:
        verbose_name = "сборы"
        verbose_name_plural = "сборы"
        ordering = ["-year"]
        default_related_name = "trainings"

    def __str__(self):
        return f"Сборы {self.year or ''}".strip()


class Oath(MilitarySection):
    """Военная присяга и размеры обмундирования."""

    date = models.DateField("Дата присяги", null=True, blank=True)
    place = models.CharField("Место", max_length=255, blank=True)
    height = models.PositiveSmallIntegerField("Рост", null=True, blank=True)
    head_size = models.PositiveSmallIntegerField("Размер головы", null=True, blank=True)
    mask_size = models.PositiveSmallIntegerField(
        "Размер противогаза", null=True, blank=True
    )
    clothing_size = models.PositiveSmallIntegerField(
        "Размер одежды", null=True, blank=True
    )
    shoe_size = models.PositiveSmallIntegerField("Размер обуви", null=True, blank=True)

    class Meta:
        verbose_name = "присяга"
        verbose_name_plural = "присяга"
        default_related_name = "oaths"

    def __str__(self):
        return f"Присяга {self.date or ''}".strip()


class Removal(MilitarySection):
    """Снятие с воинского учёта."""

    date = models.DateField("Дата снятия")
    reason = models.ForeignKey(
        ref.RemovalReason, verbose_name="Причина", on_delete=models.PROTECT
    )
    note = models.CharField("Примечание", max_length=500, blank=True)

    class Meta:
        verbose_name = "снятие с учёта"
        verbose_name_plural = "снятие с учёта"
        ordering = ["-date"]
        default_related_name = "removals"

    def __str__(self):
        return f"{self.date}: {self.reason}"


class PersonAward(MilitarySection):
    """Государственная или ведомственная награда."""

    award = models.ForeignKey(
        ref.Award, verbose_name="Награда", on_delete=models.PROTECT
    )
    date = models.DateField("Дата награждения", null=True, blank=True)
    category = models.CharField("Категория", max_length=100, blank=True)
    document_type = models.CharField("Документ", max_length=100, blank=True)
    document_series = models.CharField("Серия", max_length=20, blank=True)
    document_number = models.CharField("Номер", max_length=30, blank=True)
    issued_by = models.CharField("Кем выдан", max_length=255, blank=True)
    note = models.CharField("Примечание", max_length=500, blank=True)

    class Meta:
        verbose_name = "награда"
        verbose_name_plural = "награды"
        ordering = ["-date"]
        default_related_name = "awards"

    def __str__(self):
        return str(self.award)


class SpecialAccount(MilitarySection):
    """Специальный воинский учёт (удостоверение, вид деятельности, период)."""

    series = models.CharField("Серия", max_length=20, blank=True)
    number = models.CharField("Номер", max_length=30, blank=True)
    activity = _ref(ref.Activity, "Вид деятельности")
    paragraph = models.CharField("Пункт перечня", max_length=50, blank=True)
    registered_on = models.DateField("Дата постановки", null=True, blank=True)
    withdrawn_on = models.DateField("Дата снятия", null=True, blank=True)

    class Meta:
        verbose_name = "спецучёт"
        verbose_name_plural = "спецучёт"
        ordering = ["-registered_on"]
        default_related_name = "special_accounts"

    def __str__(self):
        return f"{self.series} {self.number}".strip() or "Спецучёт"


class ReservationDismissal(MilitarySection):
    """Увольнение забронированного работника (для отчёта по спец. уволенным)."""

    order = models.CharField("Номер удостоверения / приказа", max_length=50)
    dismissal_date = models.DateField("Дата увольнения")

    class Meta:
        verbose_name = "увольнение забронированного"
        verbose_name_plural = "увольнения забронированных"
        ordering = ["-dismissal_date"]
        default_related_name = "reservation_dismissals"
        constraints = [
            models.UniqueConstraint(
                fields=["person", "order"], name="military_reservation_dismissal_unique"
            )
        ]

    def __str__(self):
        return f"{self.order} от {self.dismissal_date}"
