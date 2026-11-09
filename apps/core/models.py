"""Общие абстрактные модели для приложений проекта (своих таблиц у core нет)."""

from django.core.exceptions import ValidationError
from django.db import models


class TimeStampedModel(models.Model):
    """Даты создания и последнего изменения записи."""

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Изменено", auto_now=True)

    class Meta:
        abstract = True


class PeriodModel(models.Model):
    """Период действия записи: «с» и «по» (пусто — без ограничения)."""

    date_from = models.DateField("С", null=True, blank=True)
    date_to = models.DateField("По", null=True, blank=True)

    def clean(self):
        super().clean()
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValidationError(
                {"date_to": "Дата окончания не может быть раньше даты начала."}
            )

    class Meta:
        abstract = True
