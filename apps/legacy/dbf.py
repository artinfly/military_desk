"""DBF III/IV без перекодирования исходных полей и без изменения файлов на диске.

Описание формата: https://blogs.embarcadero.com/dbase-dbf-file-structure/
"""

import csv
import io
import re
import struct
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.personnel.models import Person


class DbfTable:
    def __init__(self, raw):
        if len(raw) < 33 or raw[0] not in (3, 4):
            raise ValidationError("Нужен DBF III/IV без memo-полей.")
        self.count, self.header_length, self.record_length = struct.unpack_from(
            "<IHH", raw, 4
        )
        if self.header_length < 33 or self.header_length > len(raw):
            raise ValidationError("Повреждён заголовок DBF.")
        self.raw = raw
        self.fields = {}
        offset = 1
        position = 32
        while position < self.header_length and raw[position] != 13:
            descriptor = raw[position : position + 32]
            if len(descriptor) != 32:
                raise ValidationError("Оборвано описание полей DBF.")
            try:
                name = descriptor[:11].split(b"\0")[0].decode("ascii").upper()
            except UnicodeError as error:
                raise ValidationError("Некорректное имя поля DBF.") from error
            kind, size = chr(descriptor[11]), descriptor[16]
            if not name or name in self.fields or not size or kind not in "CNDFL":
                raise ValidationError("Неподдерживаемое или повторное поле DBF.")
            self.fields[name] = (offset, size, kind)
            offset += size
            position += 32
        if position >= self.header_length or offset != self.record_length:
            raise ValidationError("Размер записи DBF не совпадает с описанием полей.")
        if self.header_length + self.count * self.record_length > len(raw):
            raise ValidationError("Файл DBF обрывается до последней записи.")

    def require(self, names):
        missing = set(names) - self.fields.keys()
        if missing:
            raise ValidationError("В DBF нет полей: " + ", ".join(sorted(missing)))

    def records(self):
        for i in range(self.count):
            start = self.header_length + i * self.record_length
            record = bytearray(self.raw[start : start + self.record_length])
            if record[0] == 42:
                continue
            if record[0] != 32:
                raise ValidationError(
                    f"Повреждена отметка удаления DBF в записи {i + 1}."
                )
            yield i + 1, record

    def value(self, record, name):
        start, size, kind = self.fields[name]
        value = (
            bytes(record[start : start + size])
            .strip()
            .decode("ascii", errors="replace")
        )
        if kind in "NF" and value:
            try:
                number = Decimal(value)
                if number.is_finite() and number == number.to_integral_value():
                    return str(int(number))
            except InvalidOperation:
                pass
        return value

    def set(self, record, name, value):
        start, size, kind = self.fields[name]
        raw = str(value or "").encode("ascii")
        if len(raw) > size:
            raise ValidationError(f"Значение не помещается в поле {name}.")
        record[start : start + size] = (
            raw.rjust(size) if kind in "NF" else raw.ljust(size)
        )

    def build(self, records):
        header = bytearray(self.raw[: self.header_length])
        today = timezone.localdate()
        header[1:4] = bytes((today.year - 1900, today.month, today.day))
        struct.pack_into("<I", header, 4, len(records))
        header[28] = 0  # исходные индексы не сопровождают новый файл
        for position in range(32, self.header_length - 1, 32):
            header[position + 31] = 0
        return bytes(header) + b"".join(records) + b"\x1a"


def integer_in_range(value, low, high):
    try:
        number = Decimal(value)
        return (
            number.is_finite()
            and number == number.to_integral_value()
            and low <= number <= high
        )
    except InvalidOperation:
        return False


def csv_bytes(headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(headers)
    writer.writerows(
        [
            (
                "'" + value
                if isinstance(value, str)
                and value.startswith(("=", "+", "-", "@", "\t", "\r"))
                else value
            )
            for value in row
        ]
        for row in rows
    )
    return buffer.getvalue().encode("utf-8-sig")


@dataclass
class Converted:
    name: str
    content: bytes
    source_count: int
    accepted: int
    rejected: list
    duplicates: int
    missing_codes: set


def convert_dbf(raw, kind, known_codes=()):
    table = DbfTable(raw)
    if kind == "proff":
        table.require(("TAB_N", "OKPD", "PRIZNAK", "CATEG_ID", "MIL", "UCHET"))
        key_field = "TAB_N"
    elif kind == "kadr":
        table.require(("TABNOM", "ZK", "MER", "PROF", "SPECUH", "SOSTAV"))
        key_field = "TABNOM"
    else:
        raise ValidationError("Неизвестный вид обмена DBF.")
    people = {
        p.tab_number.upper(): p
        for p in Person.objects.select_related(
            "military__special_account_type", "military__duty"
        )
    }
    result, rejected, seen, missing = [], [], set(), set()
    known = set(known_codes)
    duplicates = 0
    for number, record in table.records():
        value = lambda name: table.value(record, name)
        tab = value(key_field).upper()
        person = people.get(tab)
        military = getattr(person, "military", None) if person else None
        account = (
            military.special_account_type.code
            if military and military.special_account_type
            else ""
        )
        reasons = []
        if not tab:
            reasons.append("Нет табельного номера")
        if kind == "proff":
            if not re.fullmatch(r"[0-9]{6}", value("OKPD")):
                reasons.append("ОКПДТР должен содержать 6 цифр")
            if not integer_in_range(value("PRIZNAK"), 1, 5):
                reasons.append("PRIZNAK должен быть от 1 до 5")
            if not integer_in_range(value("CATEG_ID"), 1, 6):
                reasons.append("CATEG_ID должен быть от 1 до 6")
            if account in ("X4", "R7") and value("MIL").upper() in ("N", "P"):
                reasons.append("Вид учёта несовместим со значением MIL")
        else:
            if value("MER") in ("05", "07", "08", "15"):
                reasons.append("MER исключён из выгрузки")
            if value("ZK"):
                reasons.append("ZK заполнено")
            if not re.fullmatch(r"[0-9]{6}", value("PROF")):
                reasons.append("PROF должен содержать 6 цифр")
            liable = (
                military and military.duty and military.duty.name == "Военнообязанный"
            )
            output_account = (
                {"X4": "2", "R7": "1", "H9": "3"}.get(account, "") if liable else ""
            )
            # Проверка выходного значения тоже обязательна: старый загрузчик её пропускал.
            if (value("SPECUH") or output_account) and not integer_in_range(
                value("SOSTAV"), 1, 10
            ):
                reasons.append("При спецучёте SOSTAV должен быть от 1 до 10")
        if reasons:
            rejected.append((number, tab, " | ".join(reasons)))
            continue
        if kind == "kadr":
            if tab in seen:
                duplicates += 1
                continue
            seen.add(tab)
            table.set(record, "SPECUH", output_account)
            if value("PROF") not in known:
                missing.add(value("PROF"))
        else:
            table.set(record, "UCHET", account)
        result.append(record)
    return Converted(
        "proff.dbf" if kind == "proff" else "kadr940.dbf",
        table.build(result),
        table.count,
        len(result),
        rejected,
        duplicates,
        missing,
    )


def conversion_zip(converted):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(converted.name, converted.content)
        archive.writestr(
            "Отклонённые.csv",
            csv_bytes(("Запись", "Табельный номер", "Причина"), converted.rejected),
        )
        archive.writestr(
            "Нераспределённые коды.csv",
            csv_bytes(("ОКПДТР",), [(c,) for c in sorted(converted.missing_codes)]),
        )
        archive.writestr(
            "Итог.txt",
            f"Исходных записей: {converted.source_count}\nВыгружено: {converted.accepted}\nОтклонено: {len(converted.rejected)}\nПовторных табельных номеров: {converted.duplicates}\n".encode(
                "utf-8-sig"
            ),
        )
    return buffer.getvalue()


def spr_dbf(rows):
    """Справочник строк первого отдела: NS N(2), DA1 N(7)."""
    rows = list(rows)
    header = bytearray(97)
    header[0] = 3
    struct.pack_into("<IHH", header, 4, 0, 97, 10)
    for position, name, size in ((32, b"NS", 2), (64, b"DA1", 7)):
        header[position : position + len(name)] = name
        header[position + 11] = ord("N")
        header[position + 16] = size
    header[96] = 13
    table = DbfTable(bytes(header))
    records = []
    for number, code in rows:
        record = bytearray(b" " * 10)
        table.set(record, "NS", number)
        table.set(record, "DA1", code)
        records.append(record)
    return table.build(records)
