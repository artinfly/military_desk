"""Редактируемый текст справки: только текст и известные поля карточки."""

from django.conf import settings
from django.db import models

DEFAULT_BODY = """Выдана {{ФИО}}, {{ДатаРождения}} года рождения, работающему в должности {{Должность}}, цех {{Цех}}.

Группа учёта: {{ГруппаУчёта}}. Воинское звание: {{Звание}}.
Состав: {{Состав}}. ВУС: {{ВУС}}.
Документ воинского учёта: {{Серия}} {{Номер}}.
Приказ о бронировании: {{ПриказНомер}}.

Справка выдана для предъявления по месту требования.

Дата: {{Дата}}
Подпись: ____________________"""


class CertificateTemplate(models.Model):
    name = models.CharField(
        "Название шаблона", max_length=150, default="Справка о бронировании"
    )
    organization = models.CharField("Организация", max_length=255, blank=True)
    body = models.TextField("Текст справки", default=DEFAULT_BODY)
    updated_at = models.DateTimeField("Изменён", auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
    )

    class Meta:
        verbose_name = "шаблон справки"
        verbose_name_plural = "шаблоны справок"

    def __str__(self):
        return self.name
