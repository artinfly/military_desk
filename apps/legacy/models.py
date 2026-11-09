"""Связи с исходными записями для повторяемого кадрового обмена."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class SourceRow(models.Model):
    table = models.CharField(max_length=60)
    key = models.CharField(max_length=160)
    model = models.CharField(max_length=80)
    target_id = models.PositiveBigIntegerField()
    person = models.ForeignKey("personnel.Person", on_delete=models.CASCADE)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("table", "key"), name="legacy_source_row_unique"
            )
        ]


class ImportBatch(models.Model):
    created_at = models.DateTimeField("Дата загрузки", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    kind = models.CharField("Вид", max_length=40)
    checksum = models.CharField("SHA-256", max_length=64)
    counts = models.JSONField("Итог", default=dict)

    class Meta:
        verbose_name = "загрузка данных"
        verbose_name_plural = "загрузки данных"
        default_permissions = ("view", "add")
        ordering = ("-created_at", "-pk")


class ProfessionCode(models.Model):
    code = models.CharField("ОКПДТР", max_length=7, unique=True)
    row_number = models.PositiveSmallIntegerField(
        "Строка первого отдела (NS)",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
    )

    class Meta:
        verbose_name = "код первого отдела"
        verbose_name_plural = "коды первого отдела"
        ordering = ("code",)

    def __str__(self):
        return self.code


class PersonnelCode(models.Model):
    person = models.OneToOneField("personnel.Person", on_delete=models.CASCADE)
    profession = models.ForeignKey(
        ProfessionCode, on_delete=models.PROTECT, null=True, blank=True
    )
    category = models.CharField("Категория", max_length=100, blank=True)

    class Meta:
        default_permissions = ()
