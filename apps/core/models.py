"""Общие абстрактные модели для приложений проекта (своих таблиц у core нет)."""

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

    class Meta:
        abstract = True
