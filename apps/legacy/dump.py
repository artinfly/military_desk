"""Чтение COPY из текстового pg_dump. SQL из файла никогда не исполняется."""

import re
from datetime import date, datetime
from pathlib import Path

from .source import TABLES

COPY = re.compile(r'^COPY public\."?([a-z_]+)"? \(([^)]+)\) FROM stdin;$')
CREATE = re.compile(r'CREATE TABLE public\."?([a-z_]+)"? \(\n(.*?)\n\)', re.S)
ESCAPES = {"b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}
ESCAPE = re.compile(r"\\([0-7]{1,3}|x[0-9a-fA-F]{1,2}|.)")


def unescape(value):
    def replace(match):
        escaped = match[1]
        if escaped.startswith("x") and len(escaped) > 1:
            return chr(int(escaped[1:], 16))
        if escaped[0] in "01234567":
            return chr(int(escaped, 8))
        return ESCAPES.get(escaped, escaped)

    return ESCAPE.sub(replace, value)


def convert(value, kind):
    if value == r"\N":
        return None
    value = unescape(value)
    if kind.startswith(("integer", "bigint", "smallint")):
        return int(value)
    if kind.startswith("boolean"):
        if value not in ("t", "f"):
            raise ValueError("Некорректное логическое значение")
        return value == "t"
    if kind.startswith(("date", "timestamp")):
        if value.endswith(" BC") or value in ("infinity", "-infinity"):
            return None
        return (
            datetime.fromisoformat(value)
            if kind.startswith("timestamp")
            else date.fromisoformat(value)
        )
    return value


def read_dump(path):
    path = Path(path)
    if path.stat().st_size > 250 * 1024 * 1024:
        raise ValueError("SQL-выгрузка превышает 250 МБ")
    raw = path.read_bytes()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("cp1251")
    content = content.replace("\r\n", "\n")
    types = {}
    for table, definition in CREATE.findall(content):
        types[table] = {}
        for line in definition.splitlines():
            column = re.match(r'\s*"?([a-z_]+)"?\s+(.+)', line)
            if column:
                types[table][column[1]] = column[2]
    tables = {}
    current = None
    skipping = False
    for number, line in enumerate(content.splitlines(), 1):
        if current is not None or skipping:
            if line == r"\.":
                current, skipping = None, False
                continue
            if skipping:
                continue
            table, columns = current
            values = line.split("\t")
            if len(values) != len(columns):
                raise ValueError(
                    f"Строка {number}, {table}: число значений не совпадает с колонками"
                )
            try:
                tables[table].append(
                    {
                        column: convert(value, types.get(table, {}).get(column, "text"))
                        for column, value in zip(columns, values, strict=True)
                    }
                )
            except (ValueError, OverflowError) as error:
                raise ValueError(
                    f"Строка {number}, {table}: некорректный тип значения"
                ) from error
        elif match := COPY.fullmatch(line):
            table = match[1]
            if table not in TABLES and table not in ("spr", "emps_spr"):
                skipping = True
                continue
            if table in tables:
                raise ValueError(f"Таблица {table} повторяется в выгрузке")
            tables[table] = []
            current = (table, [c.strip().strip('"') for c in match[2].split(",")])
    if current is not None or skipping:
        raise ValueError("Оборванный блок COPY в SQL-выгрузке")
    if not {"account_cards", "personal_data", "mil_ids_info"} <= tables.keys():
        raise ValueError(
            "Нет обязательных таблиц COPY. Нужен текстовый pg_dump базы stol (.sql)"
        )
    return tables
