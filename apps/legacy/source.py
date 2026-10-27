"""Чтение старой базы «stol» (только чтение) и мелкие правила её данных."""

from datetime import date

import psycopg
from psycopg.rows import dict_row

# Таблицы, из которых берутся данные (остальные — служебные или 1-го отдела)
TABLES = [
    # Справочники
    "nsi_accounting_groups", "nsi_activities", "nsi_addresses_types",
    "nsi_army_positions", "nsi_cats_for_mil_service", "nsi_cities",
    "nsi_departments", "nsi_family_statuses", "nsi_filials", "nsi_hot_spots",
    "nsi_hot_spots_values", "nsi_houses", "nsi_language_types",
    "nsi_mil_registration_docs", "nsi_military_commissariarts",
    "nsi_military_duties", "nsi_military_ranks", "nsi_places_of_issue",
    "nsi_professions", "nsi_regions", "nsi_relation_types", "nsi_removal_reasons",
    "nsi_reserve_categories", "nsi_reserves_composition", "nsi_rewards",
    "nsi_specials", "nsi_streets", "nsi_types_production", "nsi_vuses",
    "nsi_work_statuses", "nsi_workers_category",
    # Карточки и разделы
    "account_cards", "personal_data", "personal_properties", "mil_ids_info",
    "com_history", "diss_spec", "ranks", "mil_service", "mil_trainings", "oaths",
    "removal_regs", "rewards", "special_accounts", "education", "addresses",
    "assigments", "relatives", "languages", "professions", "passes",
    "additional_attributes",
]  # fmt: skip

# В старой базе «без даты окончания» записано как 31.12.2099
NO_END = date(2099, 12, 31)


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


def number(value):
    """Целое число из строки или числа; не число — None."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
