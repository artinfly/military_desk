"""Чтение старой базы «stol» (только чтение) и мелкие правила её данных."""

from datetime import date

import psycopg
from psycopg.rows import dict_row
from psycopg.types.datetime import DateLoader, TimestampLoader

# Таблицы, из которых берутся данные (остальные — служебные или 1-го отдела)
TABLES = [
    # Справочники
    "nsi_accounting_groups", "nsi_addresses_types", "nsi_cats_for_mil_service",
    "nsi_cities", "nsi_departments", "nsi_hot_spots", "nsi_hot_spots_values",
    "nsi_houses", "nsi_mil_registration_docs", "nsi_military_commissariarts",
    "nsi_military_duties", "nsi_military_ranks", "nsi_regions",
    "nsi_relation_types", "nsi_reserve_categories", "nsi_reserves_composition",
    "nsi_specials", "nsi_streets", "nsi_vuses",
    # Карточки и разделы
    "account_cards", "personal_data", "personal_properties", "mil_ids_info",
    "com_history", "diss_spec", "education", "addresses", "assigments",
    "relatives", "additional_attributes",
]  # fmt: skip

# В старой базе «без даты окончания» записано как 31.12.2099
NO_END = date(2099, 12, 31)


def _empty_if_invalid(loader):
    """Загрузчик, который читает недопустимую для Python дату как пустую.

    В старой базе встречаются даты до нашей эры («0001-01-01 BC») — так старая
    программа записывала пустую дату. В Python таких дат нет, без этого чтение
    обрывается ошибкой «date too small».
    """

    class SafeLoader(loader):
        def load(self, data):
            try:
                return super().load(data)
            except psycopg.DataError:
                return None

    return SafeLoader


def read(host, port, dbname, user, password):
    """Все нужные таблицы: {таблица: [строка как словарь]}."""
    with psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        row_factory=dict_row,
        options="-c default_transaction_read_only=on",
    ) as connection:
        connection.adapters.register_loader("date", _empty_if_invalid(DateLoader))
        connection.adapters.register_loader(
            "timestamp", _empty_if_invalid(TimestampLoader)
        )
        return {
            table: connection.execute(f"SELECT * FROM public.{table}").fetchall()
            for table in TABLES
        }


def is_deleted(row):
    """Запись помечена удалённой (delete_bit = 1 или is_deleted)."""
    bit = row.get("delete_bit")
    return str(bit) in ("1", "True") or row.get("is_deleted") is True


def end_date(value):
    """Дата окончания: 31.12.2099 и позже — «без окончания»."""
    return None if value is None or value >= NO_END else value


def text(value, limit=None):
    """Строка без пробелов по краям; None — пустая строка."""
    result = "" if value is None else str(value).strip()
    return result[:limit] if limit else result
