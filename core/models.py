"""Таблицы базы данных: каждая модель (класс) — одна таблица, каждое поле — колонка."""

from django.db import models

# --- Справочники ---


class MilitaryRank(models.Model):
    """Воинское звание (справочник).

    Записи не удаляются, а помечаются недействующими (is_active=False):
    на звание могут ссылаться карточки, и они не должны ломаться.
    """

    name = models.CharField("Воинское звание", max_length=100, unique=True)
    is_active = models.BooleanField("Действует", default=True)

    class Meta:
        verbose_name = "воинское звание"
        verbose_name_plural = "воинские звания"
        ordering = ["name"]

    def __str__(self):
        return self.name
