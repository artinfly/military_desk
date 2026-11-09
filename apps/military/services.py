"""Массовые операции воинского учёта (как в старой программе, меню «Операции»).

Каждая операция выполняется целиком в одной транзакции: или всё, или ничего.
"""

import re
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook

from apps.personnel.models import Person
from apps.references.models import SpecialAccountType

from .models import MilitaryRecord, ReservationDismissal

# Код группы «Общий учёт» — её ставят при разбронировании
GENERAL_ACCOUNT_CODE = "H9"


def snils_digits(value):
    """СНИЛС без пробелов и дефисов: «926-581-417 72» → «92658141772»."""
    return re.sub(r"\D", "", str(value or ""))


def _mark_people(ids, actor):
    changes = {"updated_at": timezone.now()}
    if actor is not None:
        changes["updated_by"] = actor
    Person.objects.filter(pk__in=set(ids)).update(**changes)


def _lock_records(queryset):
    # Один порядок блокировок во всех массовых операциях: карточки, затем воинские записи.
    ids = list(queryset.values_list("person_id", flat=True))
    list(Person.objects.filter(pk__in=ids).order_by("pk").select_for_update())
    return list(queryset.order_by("pk").select_for_update())


@transaction.atomic
def change_account_type(old_type, new_type, *, actor=None):
    """Смена группы учёта у незабронированных: old_type → new_type (None — убрать группу).

    Возвращает число изменённых записей.
    """
    if old_type == new_type:
        return 0
    records = _lock_records(
        MilitaryRecord.objects.filter(special_account_type=old_type, is_reserved=False)
    )
    _mark_people([r.person_id for r in records], actor)
    return MilitaryRecord.objects.filter(pk__in=[r.pk for r in records]).update(
        special_account_type=new_type, updated_at=timezone.now()
    )


@dataclass
class DismissedUpdate:
    removed: int  # снова работают — убраны из спец. уволенных
    added: int  # уволенные забронированные — добавлены
    unreserved: int  # уволенным снята бронь


@transaction.atomic
def update_reserved_dismissed(*, actor=None):
    """Синхронизирует увольнения забронированных, блокируя карточки перед изменениями."""
    dates = dict(Person.objects.values_list("pk", "dismissal_date"))
    dismissed_ids = [pk for pk, date_ in dates.items() if date_ is not None]
    history = list(ReservationDismissal.objects.values_list("pk", "person_id"))
    removed_people = {person for pk, person in history if dates.get(person) is None}
    reserved_people = set(
        MilitaryRecord.objects.filter(
            is_reserved=True, person_id__in=dismissed_ids
        ).values_list("person_id", flat=True)
    )
    candidates = list(
        Person.objects.filter(pk__in=reserved_people | removed_people)
        .order_by("pk")
        .select_for_update()
    )
    # Повторно читаем состояние после блокировки: сотрудника могли принять обратно.
    current_dates = {p.pk: p.dismissal_date for p in candidates}
    working_ids = {pk for pk, date_ in current_dates.items() if date_ is None}
    removed_ids = [pk for pk, person in history if person in working_ids]
    removed, _ = ReservationDismissal.objects.filter(pk__in=removed_ids).delete()
    reserved = list(
        MilitaryRecord.objects.filter(
            is_reserved=True,
            person_id__in=[
                pk for pk, date_ in current_dates.items() if date_ is not None
            ],
        )
        .order_by("pk")
        .select_for_update()
    )
    existing = set(ReservationDismissal.objects.values_list("person_id", "order"))
    new = [
        ReservationDismissal(
            person_id=record.person_id,
            order=record.reservation_document,
            dismissal_date=current_dates[record.person_id],
        )
        for record in reserved
        if (record.person_id, record.reservation_document) not in existing
    ]
    ReservationDismissal.objects.bulk_create(new)
    unreserved = MilitaryRecord.objects.filter(pk__in=[r.pk for r in reserved]).update(
        is_reserved=False, updated_at=timezone.now()
    )
    _mark_people(list(working_ids) + [r.person_id for r in reserved], actor)
    return DismissedUpdate(removed, len(new), unreserved)


def read_snils_file(file):
    """СНИЛС из файла Excel: первая колонка, со второй строки (первая — заголовок)."""
    if getattr(file, "size", 0) > 10 * 1024 * 1024:
        raise ValidationError("Файл слишком большой: допустимо до 10 МБ.")
    book = load_workbook(file, read_only=True, data_only=False)
    try:
        sheet = book.worksheets[0]
        result = []
        for number, row in enumerate(
            sheet.iter_rows(min_row=2, max_col=1, values_only=True), 2
        ):
            if number > 50001:
                raise ValidationError(
                    "В файле больше 50 000 строк. Разделите список на части."
                )
            value = row[0]
            if value is None or not str(value).strip():
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if value < 0 or value != int(value):
                    raise ValidationError(f"Строка {number}: неверный СНИЛС.")
                value = str(int(value)).zfill(11)
            raw = str(value).strip()
            snils = snils_digits(raw)
            if len(snils) != 11 or re.search(r"[^0-9\s-]", raw):
                raise ValidationError(
                    f"Строка {number}: СНИЛС должен содержать 11 цифр. Формулы не поддерживаются."
                )
            result.append(snils)
        if not result:
            raise ValidationError("В первой колонке со второй строки не найдены СНИЛС.")
        return list(dict.fromkeys(result))
    finally:
        book.close()


@dataclass
class UnreserveResult:
    unreserved: int = 0
    not_found: list = field(default_factory=list)  # СНИЛС, которых нет среди работающих


@transaction.atomic
def unreserve_by_snils(snils_list, order, *, actor=None):
    """Разбронирование работающих по списку СНИЛС.

    Бронь снимается, группа учёта — «Общий учёт», в карточку пишется номер
    приказа о разбронировании, удостоверение об отсрочке очищается.
    """
    general = (
        SpecialAccountType.objects.active().filter(code=GENERAL_ACCOUNT_CODE).first()
    )
    if general is None:
        raise ValidationError(
            "В справочнике нет действующего вида учёта H9 (Общий учёт). Операция отменена; обратитесь к администратору."
        )
    if not snils_list or not order.strip() or len(order) > 50:
        raise ValidationError("Укажите список СНИЛС и номер приказа (до 50 символов).")
    records = MilitaryRecord.objects.filter(
        person__dismissal_date__isnull=True
    ).exclude(person__snils="")
    by_snils = {}
    for pk, snils in records.values_list("pk", "person__snils"):
        by_snils.setdefault(snils_digits(snils), []).append(pk)

    result = UnreserveResult()
    found = []
    for snils in dict.fromkeys(snils_list):  # без повторов, порядок файла
        if snils in by_snils:
            if len(by_snils[snils]) != 1:
                raise ValidationError(
                    f"СНИЛС {snils} указан у нескольких работающих сотрудников. Исправьте дубли; операция отменена."
                )
            found.extend(by_snils[snils])
        else:
            result.not_found.append(snils)
    locked = _lock_records(records.filter(pk__in=found))
    _mark_people([r.person_id for r in locked], actor)
    result.unreserved = MilitaryRecord.objects.filter(
        pk__in=[r.pk for r in locked]
    ).update(
        updated_at=timezone.now(),
        is_reserved=False,
        special_account_type=general,
        unreservation_order=order,
        reservation_document="",
    )
    return result


@dataclass
class ReserveResult:
    reserved: int = 0
    not_found: list = field(default_factory=list)


@transaction.atomic
def reserve_by_snils(snils_list, order, account_type, *, actor=None):
    """Бронирование работающих. При неоднозначном СНИЛС вся операция отменяется."""
    if not snils_list or not order.strip() or len(order) > 50:
        raise ValidationError("Укажите список СНИЛС и приказ (до 50 символов).")
    if not account_type.is_active or account_type.code not in ("X4", "R7"):
        raise ValidationError("Для бронирования нужен действующий вид учёта X4 или R7.")
    people = Person.objects.filter(dismissal_date__isnull=True).exclude(snils="")
    by_snils = {}
    for pk, snils in people.values_list("pk", "snils"):
        by_snils.setdefault(snils_digits(snils), []).append(pk)
    result, found = ReserveResult(), []
    for snils in dict.fromkeys(snils_list):
        if len(snils) != 11 or not snils.isascii() or not snils.isdigit():
            raise ValidationError("СНИЛС должен содержать 11 цифр.")
        ids = by_snils.get(snils, [])
        if len(ids) > 1:
            raise ValidationError(
                "СНИЛС указан у нескольких работающих сотрудников. Исправьте дубли; операция отменена."
            )
        if ids:
            found.extend(ids)
        else:
            result.not_found.append(snils)
    # Запись воинского учёта должна существовать: неполные карточки не бронируются автоматически.
    locked_people = list(
        Person.objects.filter(pk__in=found).order_by("pk").select_for_update()
    )
    records = list(
        MilitaryRecord.objects.filter(person_id__in=found)
        .order_by("pk")
        .select_for_update()
    )
    if len(records) != len(locked_people):
        raise ValidationError(
            "У части сотрудников нет воинского учёта. Заполните карточки; операция отменена."
        )
    if any(p.dismissal_date for p in locked_people):
        raise ValidationError(
            "Кадровые данные изменились во время операции. Повторите загрузку."
        )
    _mark_people(found, actor)
    result.reserved = MilitaryRecord.objects.filter(
        pk__in=[r.pk for r in records]
    ).update(
        is_reserved=True,
        special_account_type=account_type,
        reservation_document=order.strip(),
        unreservation_order="",
        updated_at=timezone.now(),
    )
    return result
