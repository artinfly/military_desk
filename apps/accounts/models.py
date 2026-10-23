"""Пользователь системы (сотрудник военно-учётного стола)."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Пользователь: стандартный пользователь Django + отчество, подразделение, должность.

    Входят по логину; адрес почты необязателен и при создании администратора не спрашивается.
    """

    patronymic = models.CharField("Отчество", max_length=150, blank=True)
    department = models.CharField("Подразделение", max_length=255, blank=True)
    position = models.CharField("Должность", max_length=255, blank=True)

    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        ordering = ["last_name", "first_name", "username"]

    def __str__(self):
        return self.full_name or self.username

    @property
    def full_name(self):
        """«Иванов Иван Иванович» (пустые части пропускаются)."""
        parts = (self.last_name, self.first_name, self.patronymic)
        return " ".join(part for part in parts if part)

    @property
    def short_name(self):
        """«Иванов И.И.» — для подписей и меню; без фамилии — логин."""
        if not self.last_name:
            return self.username
        initials = "".join(
            f"{part[0]}." for part in (self.first_name, self.patronymic) if part
        )
        return f"{self.last_name} {initials}".strip()
