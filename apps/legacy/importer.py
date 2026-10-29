"""Перенос данных из старой базы «stol» в учётные карточки и воинский учёт.

Вход — таблицы старой базы как {таблица: [строки-словари]} (source.read);
выход — записи проекта и итог Report. Вызывать внутри одной транзакции
(это делает команда import_legacy). Удалённые в старой программе записи
(delete_bit) не переносятся.
"""

from collections import defaultdict

from apps.military import models as mil
from apps.personnel import models as pers
from apps.references import models as ref

from .references import References
from .report import Report
from .source import end_date, is_deleted, text

# Пол в старой базе — буква; латинские M/F встречаются в выгрузках
GENDERS = {"М": "М", "M": "М", "Ж": "Ж", "F": "Ж"}
FOREIGN_PASSPORT = "Заграничный паспорт"


def _rows(tables, table):
    """Строки таблицы без удалённых."""
    return [row for row in tables.get(table, []) if not is_deleted(row)]


def _by_card(tables, table, key="account_card_id"):
    """Строки таблицы, сгруппированные по карточке."""
    grouped = defaultdict(list)
    for row in _rows(tables, table):
        grouped[row[key]].append(row)
    return grouped


class LegacyImporter:
    def __init__(self, tables):
        self.tables = tables
        self.report = Report()
        self.refs = References(tables, self.report)
        self.people = {}  # account_id -> Person
        self.houses = {
            row["id_house"]: text(row["house_num"])
            for row in tables.get("nsi_houses", [])
        }

    def run(self):
        self.refs.load()
        self.import_people()
        self.import_military()
        self.import_sections()
        return self.report

    def ref(self, table, old_id, where):
        return self.refs.get(table, old_id, where)

    def bulk(self, what, objects):
        """Сохраняет записи раздела одной командой и записывает количество в итог."""
        if objects:
            objects[0].__class__.objects.bulk_create(objects, batch_size=1000)
        self.report.count(what, len(objects))

    # --- Карточки ---

    def import_people(self):
        personal = {
            r["account_card_id"]: r for r in _rows(self.tables, "personal_data")
        }
        assignments = _by_card(self.tables, "assigments")
        cards, seen = [], set()
        for row in sorted(
            _rows(self.tables, "account_cards"), key=lambda r: r["account_id"]
        ):
            tab = text(row["tab_number"], 20)
            where = f"карточка {tab}"
            if tab in seen:
                self.report.problem(f"{where}: повтор табельного номера — пропущена")
                continue
            seen.add(tab)
            data = personal.get(row["account_id"], {})
            last = self.last_assignment(assignments.get(row["account_id"], []))
            gender = GENDERS.get(text(row["gender"])[:1].upper())
            if gender is None:
                self.report.problem(
                    f"{where}: неизвестный пол «{row['gender']}», указан «М»"
                )
            person = pers.Person(
                tab_number=tab,
                last_name=text(row["surname"], 100),
                first_name=text(row["name"], 100),
                patronymic=text(row["patronymic"], 100),
                gender=gender or "М",
                birth_date=row["birth_date"],
                birth_place=text(row["birth_place"], 500),
                citizenship=text(data.get("sitizenship"), 100),
                inn=text(data.get("inn"), 12),
                snils=text(data.get("snils"), 14),
                phone=text(data.get("phone"), 50),
                email=text(data.get("email"), 254),
                card_number=text(data.get("card_num"), 20),
                employment_date=row["employment_date"],
                dismissal_date=end_date(row["dismissal_date"]),
                department=self.department(row, last, where),
                position=text(
                    row["curr_position"] or (last or {}).get("job_title"), 255
                ),
                hire_type=text(row["hire_type"], 255),
                hire_source=text(row["hire_source"], 255),
                is_svo=bool(row["is_svo"]),
            )
            self.people[row["account_id"]] = person
            cards.append(person)
        self.bulk("Учётные карточки", cards)
        self.import_documents(personal)

    @staticmethod
    def last_assignment(rows):
        dated = [r for r in rows if r.get("order_date") or r.get("from_date")]
        return max(
            dated, key=lambda r: (r.get("order_date") or r["from_date"]), default=None
        )

    def department(self, card, last, where):
        """Цех: из последнего назначения, иначе по номеру — первому слову curr_dep."""
        if last and last.get("division"):
            return self.ref("nsi_departments", last["division"], where)
        number_ = text(card["curr_dep"]).split(" ")[0]
        if not number_:
            return None
        if not hasattr(self, "departments_by_number"):
            self.departments_by_number = {}
            for department in ref.Department.objects.exclude(number=""):
                self.departments_by_number.setdefault(department.number, department)
        found = self.departments_by_number.get(number_)
        if found is None:
            self.report.problem(f"{where}: не найден цех «{card['curr_dep']}»")
        return found

    def import_documents(self, personal):
        """Документы (personal_properties) и прежняя фамилия."""
        by_data_id = {
            r["personal_data_id"]: r["account_card_id"] for r in personal.values()
        }
        foreign = None
        documents, changed = [], []
        for row in _rows(self.tables, "personal_properties"):
            person = self.people.get(by_data_id.get(row["personal_id"]))
            if person is None:
                continue
            where = f"карточка {person.tab_number}"
            if text(row["before_lastname"]) and not person.previous_last_name:
                person.previous_last_name = text(row["before_lastname"], 100)
                person.last_name_changed_on = row["date_change_lastname"]
                changed.append(person)
            kind = self.ref("nsi_mil_registration_docs", row["document_type"], where)
            if kind and text(row["doc_number"]):
                documents.append(
                    pers.IdentityDocument(
                        person=person,
                        document_type=kind,
                        series=text(row["series"], 20),
                        number=text(row["doc_number"], 30),
                        issue_date=row["issue_date"],
                        issued_by=text(row["place_doc"], 500),
                        subdivision_code=text(row["subdivision_code"], 10),
                        valid_until=row["valid_until"],
                        note=text(row["note"], 500),
                    )
                )
            if text(row["int_passport_number"]):
                foreign = (
                    foreign
                    or ref.RegistrationDocument.objects.get_or_create(
                        name=FOREIGN_PASSPORT
                    )[0]
                )
                documents.append(
                    pers.IdentityDocument(
                        person=person,
                        document_type=foreign,
                        series=text(row["int_passport_series"], 20),
                        number=text(row["int_passport_number"], 30),
                        issued_by=text(row["int_issue_by"], 500),
                        issue_date=row["int_from_date"],
                        valid_until=row["int_by_date"],
                    )
                )
        pers.Person.objects.bulk_update(
            changed, ["previous_last_name", "last_name_changed_on"], batch_size=1000
        )
        self.bulk("Документы", documents)

    # --- Воинский учёт ---

    def import_military(self):
        info = {r["account_card_id"]: r for r in _rows(self.tables, "mil_ids_info")}
        cards = {r["account_id"]: r for r in _rows(self.tables, "account_cards")}
        records, nationality = [], []
        for account_id, person in self.people.items():
            card, row = cards[account_id], info.get(account_id)
            if row is None and not (card["mil_duty_id"] or card["mil_rank_id"]):
                continue
            row = row or {}
            where = f"карточка {person.tab_number}"

            def get(table, column, row=row, where=where):
                return self.ref(table, row.get(column), where)

            records.append(
                mil.MilitaryRecord(
                    person=person,
                    duty=self.ref("nsi_military_duties", card["mil_duty_id"], where),
                    rank=self.ref("nsi_military_ranks", card["mil_rank_id"], where),
                    document_type=get("nsi_mil_registration_docs", "mil_reg_doc_id"),
                    document_series=text(row.get("mil_doc_series"), 20),
                    document_number=text(row.get("mil_doc_number"), 30),
                    document_date=row.get("issue_date"),
                    speciality=get("nsi_vuses", "vus_id"),
                    accounting_group=get(
                        "nsi_accounting_groups", "accounting_group_id"
                    ),
                    reserve_category=get(
                        "nsi_reserve_categories", "reserve_category_id"
                    ),
                    reserve_composition=get(
                        "nsi_reserves_composition", "reserve_comp_id"
                    ),
                    fitness_category=get(
                        "nsi_cats_for_mil_service", "suit_category_id"
                    ),
                    commissariat=get(
                        "nsi_military_commissariarts", "mil_commissariat_id"
                    ),
                    special_account_type=get("nsi_specials", "special_id"),
                    mobilization_order=text(row.get("mob_order_number"), 50),
                    mobilization_letter=text(row.get("mob_order_liter"), 50),
                    gpz=text(row.get("gpz"), 30),
                    note=text(row.get("note"), 500),
                    is_reserved=bool(row.get("is_spec")),
                    reservation_document=text(row.get("spec_order"), 50),
                    unreservation_order=text(row.get("unbooked_ordernum"), 50),
                )
            )
            if text(row.get("nationality")):
                person.nationality = text(row["nationality"], 100)
                nationality.append(person)
        self.bulk("Воинский учёт", records)
        pers.Person.objects.bulk_update(nationality, ["nationality"], batch_size=1000)

    # --- Разделы карточки ---

    def section(self, what, table, build):
        """Раздел: для каждой строки build(person, row, where) -> запись или None."""
        objects = []
        for row in _rows(self.tables, table):
            person = self.people.get(row["account_card_id"])
            if person is None:
                continue
            obj = build(person, row, f"{table}, карточка {person.tab_number}")
            if obj is not None:
                objects.append(obj)
        self.bulk(what, objects)

    def import_sections(self):
        r = self.ref
        self.section(
            "Приписка к военкомату",
            "com_history",
            lambda p, row, w: (
                mil.CommissariatRegistration(
                    person=p,
                    commissariat=c,
                    date_from=row["from_date"],
                    date_to=end_date(row["by_date"]),
                )
                if (c := r("nsi_military_commissariarts", row["comm"], w))
                else None
            ),
        )
        self.section(
            "Увольнения забронированных",
            "diss_spec",
            lambda p, row, w: (
                mil.ReservationDismissal(
                    person=p,
                    order=text(row["spec_order"], 50),
                    dismissal_date=row["dissmissal_date"],
                )
            ),
        )
        self.section(
            "Образование",
            "education",
            lambda p, row, w: (
                pers.Education(
                    person=p,
                    education_type=text(row["education_type"], 255),
                    institution=text(row["institution_name"], 500),
                    study_form=text(row["edu_form"], 100),
                    speciality=text(row["speciality"], 500),
                    qualification=text(row["qualification"], 500),
                    program=text(row["educational_program"], 500),
                    training_direction=text(row["training_direction"], 500),
                    admission_date=row["admission_date"],
                    graduation_date=row["graduation_date"],
                    document=text(row["document"], 255),
                    document_series=text(row["series"], 20),
                    document_number=text(row["doc_num"], 30),
                    document_date=row["issue_date"],
                    is_main=bool(row["main_specialization"]),
                    note=text(row["note"], 500),
                )
            ),
        )
        self.section("Адреса", "addresses", self.address)
        self.section(
            "Назначения",
            "assigments",
            lambda p, row, w: (
                pers.Assignment(
                    person=p,
                    department=r("nsi_departments", row["division"], w),
                    position=text(row["job_title"], 255),
                    grade=text(row["rank"], 20),
                    employee_category=text(row["employee_cat"], 255),
                    order_kind=text(row["kind_order"], 255),
                    order_number=text(row["order_num"], 50),
                    order_date=row["order_date"],
                    date_from=row["from_date"] or row["start_date"],
                    date_to=end_date(row["by_date"] or row["finish_date"]),
                )
            ),
        )
        self.section(
            "Родственники",
            "relatives",
            lambda p, row, w: (
                pers.Relative(
                    person=p,
                    relation=relation,
                    last_name=text(row["last_name"], 100) or "—",
                    first_name=text(row["name"], 100),
                    patronymic=text(row["patronymic"], 100),
                    birth_date=row["birth_date"],
                    death_date=row["death_date"],
                    is_dependent=bool(row["is_dependent"]),
                )
                if (relation := r("nsi_relation_types", row["relation_degree"], w))
                else None
            ),
        )
        self.section("Доп. атрибуты", "additional_attributes", lambda p, row, w: (
            pers.AdditionalAttribute(
                person=p, attribute=attribute,
                value=r("nsi_hot_spots_values", row["attribute_value"], w),
                date_from=row["from_date"], date_to=end_date(row["by_date"]),
                note=text(row["note"], 500),
            ) if (attribute := r("nsi_hot_spots", row["attribute_name"], w)) else None
        ))  # fmt: skip

    def address(self, person, row, where):
        r = self.ref
        phone = f"{text(row['phone_code'])} {text(row['phone_number'])}".strip()
        return pers.Address(
            person=person,
            address_type=r("nsi_addresses_types", row["type_address"], where),
            country=text(row["country"], 100),
            postal_code=text(row["index"], 10),
            region=r("nsi_regions", row["region"], where),
            district=text(row["district"], 255),
            city=r("nsi_cities", row["city"], where),
            street=r("nsi_streets", row["street"], where),
            house=self.houses.get(row["house"], text(row["house"]))[:20],
            apartment=text(row["apartment"], 10),
            registration_date=row["registration_date"],
            phone=phone[:50],
            kladr_code=text(row["kladr_code"], 30),
            okato=text(row["okato"], 20),
            oktmo=text(row["oktmo"], 20),
            ifns=text(row["ifns"], 10),
            note=text(row["note"], 500),
            date_from=row["from_date"],
            date_to=end_date(row["by_date"]),
        )
