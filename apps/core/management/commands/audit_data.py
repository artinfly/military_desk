"""Проверка перенесённых данных без изменений и без персональных данных в выводе."""

from django.core.management.base import BaseCommand
from django.db.models import F, Q

from apps.military.models import CommissariatRegistration
from apps.military.services import snils_digits
from apps.personnel.models import AdditionalAttribute, Address, Assignment, Person
from apps.references.models import RegistrationDocument, SpecialAccountType
from apps.reports.services.lists import reservation_people


class Command(BaseCommand):
    help = "Проверить данные без изменений; в выводе только количества."

    def handle(self, *args, **options):
        self.stdout.write("Проверка только чтения. Персональные данные не выводятся.")
        self.stdout.write(f"Карточек всего: {Person.objects.count()}")
        self.stdout.write(
            f"Работающих: {Person.objects.filter(dismissal_date__isnull=True).count()}"
        )
        self.stdout.write(
            f"Без воинской записи: {Person.objects.filter(military__isnull=True).count()}"
        )
        seen = {}
        malformed = 0
        for value in (
            Person.objects.exclude(snils="").values_list("snils", flat=True).iterator()
        ):
            number = snils_digits(value)
            if len(number) != 11:
                malformed += 1
            else:
                seen[number] = seen.get(number, 0) + 1
        self.stdout.write(f"СНИЛС с количеством цифр не 11: {malformed}")
        self.stdout.write(
            f"Повторяющихся СНИЛС (групп): {sum(count > 1 for count in seen.values())}"
        )
        for model in (
            Address,
            Assignment,
            AdditionalAttribute,
            CommissariatRegistration,
        ):
            count = model.objects.filter(date_to__lt=F("date_from")).count()
            self.stdout.write(
                f"{model._meta.verbose_name_plural}: обратных периодов — {count}"
            )
        h9 = SpecialAccountType.objects.filter(code="H9", is_active=True).exists()
        self.stdout.write(f"Действующий H9: {'есть' if h9 else 'ОТСУТСТВУЕТ'}")
        document = RegistrationDocument.objects.filter(code="3767")
        self.stdout.write(
            f"Документ 3767: найдено {document.count()}, в приложении 2 — {document.filter(in_reservation_appendix=True).count()}"
        )
        people = reservation_people()
        separate = Q(military__document_type__in_reservation_appendix=True)
        self.stdout.write(
            f"Форма к распоряжению, строк данных: {people.exclude(separate).count()}"
        )
        self.stdout.write(
            f"Приложение 1, строк данных: {people.exclude(separate).filter(military__speciality__in_reservation_list=True).count()}"
        )
        self.stdout.write(
            f"Приложение 2, строк данных: {people.filter(separate).count()}"
        )
        self.stdout.write(
            "В Excel дополнительно есть строка заголовков на каждом листе. Расхождение со старой базой определяется сверкой состава, не только количества."
        )
