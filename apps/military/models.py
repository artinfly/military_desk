"""Воинский учёт работника.

MilitaryRecord — основные сведения (один на учётную карточку), остальные модели —
история приписки к военкоматам и увольнения забронированных.
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
