"""Справочники старой базы (nsi_*) → справочники проекта.

Запись ищется по коду (код = номер записи в старой базе), затем по названию;
если нет — создаётся. Удалённые в старой базе (delete_bit) переносятся
как «не действует». Города, улицы и цеха сопоставляются только по коду:
их названия не уникальны.
"""

from dataclasses import dataclass, field

from apps.references import models as ref
from apps.references.reservation import mark_reservation_flags

from .source import is_deleted, text

# Виды учёта: в старой базе название — это код
SPECIAL_NAMES = {"X4": "Спец. учёт", "R7": "Команда", "H9": "Общий учёт"}
# Офицерские звания (как в отчёте численности старой программы)
OFFICER_RANKS = {
    "Мл. лейтенант", "Младший лейтенант", "Лейтенант", "Ст. лейтенант",
    "Старший лейтенант", "Капитан", "Майор", "Подполковник", "Полковник",
}  # fmt: skip


@dataclass(frozen=True)
class RefTable:
    table: str
    id: str  # колонка номера записи
    name: str  # колонка названия
    model: type
    by_code_only: bool = False  # названия не уникальны — искать только по коду
    extra: dict = field(default_factory=dict)  # колонка старой базы -> поле справочника


REF_TABLES = [
    RefTable("nsi_accounting_groups", "accounting_group_id", "accounting_group", ref.AccountingGroup),
    RefTable("nsi_addresses_types", "id_type", "type_name", ref.AddressType),
    RefTable("nsi_cats_for_mil_service", "suit_category_id", "suitability_category", ref.FitnessCategory),
    RefTable("nsi_cities", "city_id", "city", ref.City, by_code_only=True),
    RefTable("nsi_departments", "id_department", "name_department", ref.Department,
             by_code_only=True, extra={"dep_number": "number"}),
    RefTable("nsi_hot_spots", "id_hot_spot", "hot_spot_name", ref.AttributeType),
    RefTable("nsi_hot_spots_values", "value_id", "value", ref.AttributeValue),
    RefTable("nsi_mil_registration_docs", "mil_reg_doc_id", "mil_reg_document", ref.RegistrationDocument),
    RefTable("nsi_military_commissariarts", "military_commissariart_id", "military_commissariart",
             ref.MilitaryCommissariat),
    RefTable("nsi_military_duties", "mil_duty_id", "military_duty", ref.MilitaryDuty),
    RefTable("nsi_military_ranks", "mil_rank_id", "military_rank", ref.MilitaryRank),
    RefTable("nsi_regions", "region_id", "region", ref.Region),
    RefTable("nsi_relation_types", "type_id", "type_name", ref.RelationType),
    RefTable("nsi_reserve_categories", "reserve_category_id", "reserve_category", ref.ReserveCategory),
    RefTable("nsi_reserves_composition", "reserve_comp_id", "reserve_composition", ref.ReserveComposition),
    RefTable("nsi_specials", "special_id", "special", ref.SpecialAccountType),
    RefTable("nsi_streets", "street_id", "street", ref.Street, by_code_only=True),
    RefTable("nsi_vuses", "vus_id", "vus", ref.MilitarySpeciality),
]  # fmt: skip


class References:
    """Сопоставление «таблица + старый номер» → запись справочника проекта."""

    def __init__(self, tables, report):
        self.tables = tables
        self.report = report
        self.maps = {}  # таблица -> {старый номер: запись}

    def load(self):
        for spec in REF_TABLES:
            self.maps[spec.table] = self._load(spec)
        officers = ref.MilitaryRank.objects.filter(name__in=OFFICER_RANKS)
        officers.update(is_officer=True)
        mark_reservation_flags(ref.MilitarySpeciality, ref.RegistrationDocument)

    def _load(self, spec):
        model = spec.model
        existing = list(model.objects.all())

        # Повторы в старой базе (одно и то же название — несколько записей)
        # сводятся к одной записи. Для цехов повтор — совпадение номера и
        # названия; города и улицы с одинаковым названием — разные записи.
        def twin(name, values):
            if not spec.by_code_only:
                return name
            return (name, *values) if spec.extra else None

        by_code = {obj.code: obj for obj in existing if obj.code}
        by_twin = {
            twin(obj.name, [getattr(obj, f) for f in spec.extra.values()]): obj
            for obj in existing
        }
        mapping, created = {}, 0
        for row in self.tables.get(spec.table, []):
            old_id = row[spec.id]
            code, name = text(old_id, 50), text(row[spec.name], 255)
            if spec.table == "nsi_specials":
                code = name.upper()
                name = SPECIAL_NAMES.get(code, name)
            name = name or f"Без названия ({code})"
            values = {new: text(row.get(old)) for old, new in spec.extra.items()}
            key = twin(name, values.values())
            obj = by_code.get(code) or (by_twin.get(key) if key else None)
            if obj is None:
                obj = model.objects.create(
                    name=name, code=code, is_active=not is_deleted(row), **values
                )
                by_code[code] = obj
                if key:
                    by_twin[key] = obj
                created += 1
            mapping[old_id] = obj
        self.report.count(f"Справочник «{model._meta.verbose_name_plural}»", created)
        return mapping

    def get(self, table, old_id, where=""):
        """Запись справочника по старому номеру; неизвестный номер — в проблемы."""
        if old_id is None or old_id == "":
            return None
        obj = self.maps[table].get(old_id)
        if obj is None and str(old_id) == "0":
            return None  # 0 в старой базе — «не заполнено» (значение по умолчанию)
        if obj is None:
            self.report.problem(f"{where}: нет записи {old_id} в {table}")
        return obj
