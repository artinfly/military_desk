"""Повторная загрузка кадровых данных с сохранением ручного бронирования."""

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from apps.military.models import MilitaryRecord
from apps.military.services import update_reserved_dismissed
from apps.personnel.models import Person

from .importer import LegacyImporter, remember_sources
from .models import ImportBatch, SourceRow

PERSON_FIELDS = {
    "tab_number",
    "last_name",
    "first_name",
    "patronymic",
    "gender",
    "birth_date",
    "birth_place",
    "employment_date",
    "dismissal_date",
    "department",
    "position",
    "hire_type",
    "hire_source",
    "is_svo",
    "inn",
    "snils",
}
PRESERVED_FIELDS = {
    "identitydocument": {"valid_until", "subdivision_code", "note"},
    "address": {
        "country",
        "district",
        "date_from",
        "date_to",
        "phone",
        "oktmo",
        "ifns",
    },
    "assignment": {"grade"},
}


class HRImporter(LegacyImporter):
    def __init__(self, tables, actor):
        super().__init__(tables)
        self.actor = actor
        self.changed_ids = set()
        self.personal_ids = {
            str(r["account_card_id"]) for r in tables.get("personal_data", [])
        }

    def import_military(self):
        before = {p.pk: p.nationality for p in self.people.values()}
        super().import_military()
        self.changed_ids.update(
            p.pk for p in self.people.values() if before[p.pk] != p.nationality
        )

    def bulk(self, what, objects):
        if not objects:
            self.report.count(what, 0)
            return
        model = objects[0].__class__
        sources = dict(
            SourceRow.objects.filter(
                table__in={
                    getattr(obj, "_legacy_source", ("", ""))[0] for obj in objects
                }
            ).values_list("key", "target_id")
        )
        existing = {o.pk: o for o in model.objects.filter(pk__in=sources.values())}
        if model is Person:
            by_tab = {
                o.tab_number: o
                for o in Person.objects.select_for_update().order_by("pk")
            }
        elif model is MilitaryRecord:
            by_person = {
                o.person_id: o
                for o in model.objects.filter(
                    person_id__in=[o.person_id for o in objects]
                )
            }
        created = updated = unchanged = 0
        new_objects, changed_objects, updated_fields = [], [], set()
        for obj in objects:
            marker = getattr(obj, "_legacy_source", None)
            old = existing.get(sources.get(marker[1])) if marker else None
            if model is Person:
                tab_match = by_tab.get(obj.tab_number)
                if old and tab_match and old.pk != tab_match.pk:
                    raise ValidationError(
                        "Табельный номер связан с другой карточкой. Проверьте кадровую выгрузку."
                    )
                old = old or tab_match
            elif model is MilitaryRecord:
                old = by_person.get(obj.person_id)
            elif old and old.person_id != obj.person_id:
                raise ValidationError(
                    "Исходная запись раздела связана с другой карточкой."
                )
            fields = [
                f
                for f in model._meta.concrete_fields
                if not f.primary_key
                and f.name not in ("created_at", "updated_at", "updated_by", "person")
            ]
            if model is Person:
                fields = [f for f in fields if f.name in PERSON_FIELDS]
                if marker and marker[1] not in self.personal_ids:
                    fields = [f for f in fields if f.name not in ("inn", "snils")]
            else:
                fields = [
                    f
                    for f in fields
                    if f.name not in PRESERVED_FIELDS.get(model._meta.model_name, set())
                ]
            if model is MilitaryRecord:
                protected = {
                    "is_reserved",
                    "reservation_document",
                    "unreservation_order",
                }
                if old and (old.is_reserved or old.unreservation_order):
                    protected.add("special_account_type")
                if old and old.is_reserved:
                    protected.update(
                        ("document_series", "document_number", "document_date")
                    )
                fields = [f for f in fields if f.name not in protected]
            if old:
                obj.pk = old.pk
                changed = [
                    f.attname
                    for f in fields
                    if getattr(obj, f.attname) != getattr(old, f.attname)
                ]
                for f in fields:
                    setattr(old, f.attname, getattr(obj, f.attname))
                if changed:
                    if hasattr(old, "updated_at"):
                        old.updated_at = timezone.now()
                        changed.append("updated_at")
                    changed_objects.append(old)
                    updated_fields.update(changed)
                    updated += 1
                else:
                    unchanged += 1
                # Последующие этапы используют экземпляры из self.people.
                if model is Person:
                    for f in model._meta.concrete_fields:
                        setattr(obj, f.attname, getattr(old, f.attname))
            else:
                obj.clean_fields(
                    exclude=[f.name for f in model._meta.fields if f.is_relation]
                )
                obj.clean()
                new_objects.append(obj)
                created += 1
                changed = True
                if model is Person:
                    by_tab[obj.tab_number] = obj
            if changed and obj.pk:
                self.changed_ids.add(obj.pk if model is Person else obj.person_id)
        model.objects.bulk_create(new_objects, batch_size=1000)
        if changed_objects:
            model.objects.bulk_update(
                changed_objects, sorted(updated_fields), batch_size=500
            )
        for obj in new_objects:
            self.changed_ids.add(obj.pk if model is Person else obj.person_id)
        remember_sources(objects)
        self.report.count(f"{what}: добавлено", created)
        self.report.count(f"{what}: обновлено", updated)
        self.report.count(f"{what}: без изменений", unchanged)


def import_hr(tables, actor, checksum, *, dry_run=False):
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(486174, 1)")
        importer = HRImporter(tables, actor)
        report = importer.run()
        for table, count in tables.get("__diagnostics__", {}).items():
            report.problem(
                f"{table}: повторные значения исходных записей — {count}; использованы последние строки файла."
            )
        result = update_reserved_dismissed(actor=actor)
        report.count("Снята бронь у уволенных", result.unreserved)
        Person.objects.filter(pk__in=importer.changed_ids).update(
            updated_by=actor, updated_at=timezone.now()
        )
        if not dry_run:
            ImportBatch.objects.create(
                created_by=actor, kind="hr", checksum=checksum, counts=report.counts
            )
        else:
            transaction.set_rollback(True)
    return report
