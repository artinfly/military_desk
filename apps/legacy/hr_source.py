"""Кадровый vus.csv: TSV, индексы колонок совпадают с действующим загрузчиком."""

import csv
import io
from collections import defaultdict
from datetime import datetime

from django.core.exceptions import ValidationError

from .references import REF_TABLES

MAX_FILE_SIZE = 200 * 1024 * 1024


def decode_upload(file):
    if getattr(file, "size", 0) > MAX_FILE_SIZE:
        raise ValidationError("Размер файла превышает 200 МБ.")
    raw = file.read(MAX_FILE_SIZE + 1)
    if len(raw) > MAX_FILE_SIZE:
        raise ValidationError("Размер файла превышает 200 МБ.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1251")


def parse_hr(file):
    source = csv.reader(
        io.StringIO(decode_upload(file)), delimiter="\t", quoting=csv.QUOTE_NONE
    )
    next(source, None)  # служебная строка кадровой системы
    tables = defaultdict(dict)
    specs = {s.table: s for s in REF_TABLES}
    replaced = defaultdict(int)

    def put(table, key, data):
        row = defaultdict(lambda: None, data)
        previous = tables[table].get(str(key))
        if previous is not None and dict(previous) != dict(row):
            if table == "account_cards" and any(
                previous[c] != row[c]
                for c in ("tab_number", "birth_date", "surname", "name")
            ):
                raise ValidationError(
                    f"Строка {line}: разные сотрудники с одним идентификатором карточки."
                )
            # В кадровом файле повторяются строки соединённых разделов.
            # Как в действующем загрузчике, последнее значение исходной записи имеет приоритет.
            replaced[table] += 1
        tables[table][str(key)] = row

    for line, fields in enumerate(source, 2):
        if not any(fields):
            continue
        if len(fields) < 286:
            raise ValidationError(f"Строка {line}: ожидается не менее 286 колонок TSV.")

        def value(index):
            return fields[index].strip()

        def integer(index):
            v = value(index)
            if not v:
                return None
            if not v.isascii() or not v.isdigit():
                raise ValidationError(
                    f"Строка {line}, колонка {index}: ожидается целый код."
                )
            return int(v)

        def date_(index):
            v = value(index)
            if not v or v in ("00.00.0000", "01.01.0001"):
                return None
            try:
                return datetime.strptime(v, "%d.%m.%Y").date()
            except ValueError as error:
                raise ValidationError(
                    f"Строка {line}, колонка {index}: некорректная дата."
                ) from error

        def reference(table, id_column, title_column):
            key = (
                (value(id_column) or None)
                if table in ("nsi_cities", "nsi_streets")
                else integer(id_column)
            )
            if key is not None:
                spec = specs[table]
                data = {spec.id: key, spec.name: value(title_column)}
                if table == "nsi_departments":
                    # Поле содержит «942 Бюро ...», а не только номер цеха.
                    data["dep_number"] = (
                        value(276).split(maxsplit=1)[0] if value(276) else ""
                    )
                put(table, key, data)
            return key

        account_id = integer(1)
        if account_id is None or not value(2):
            raise ValidationError(
                f"Строка {line}: нет идентификатора карточки или табельного номера."
            )
        if (
            not date_(10)
            or not value(3)
            or not value(4)
            or value(8).upper() not in ("М", "Ж", "M", "F")
        ):
            raise ValidationError(f"Строка {line}: проверьте ФИО, пол и дату рождения.")
        put(
            "account_cards",
            account_id,
            dict(
                account_id=account_id,
                tab_number=value(2),
                surname=value(3),
                name=value(4),
                patronymic=value(5),
                gender=value(8),
                birth_date=date_(10),
                employment_date=date_(11),
                dismissal_date=date_(12),
                birth_place=value(28),
                mil_duty_id=reference("nsi_military_duties", 13, 14),
                mil_rank_id=reference("nsi_military_ranks", 6, 7),
                is_svo=value(281).lower() in ("1", "да", "true", "t", "+"),
                curr_dep=value(282),
                curr_position=value(283),
                hire_type=value(284),
                hire_source=value(285),
            ),
        )
        put(
            "mil_ids_info",
            account_id,
            dict(
                account_card_id=account_id,
                accounting_group_id=reference("nsi_accounting_groups", 53, 54),
                reserve_category_id=reference("nsi_reserve_categories", 55, 56),
                reserve_comp_id=reference("nsi_reserves_composition", 57, 58),
                suit_category_id=reference("nsi_cats_for_mil_service", 59, 60),
                mil_commissariat_id=reference("nsi_military_commissariarts", 61, 62),
                special_id=reference("nsi_specials", 63, 64),
                nationality=value(65),
                mob_order_number=value(69),
                mob_order_liter=value(70),
                vus_id=reference("nsi_vuses", 71, 72),
                gpz=value(73),
                note=value(74),
                mil_reg_doc_id=reference("nsi_mil_registration_docs", 51, 52),
                mil_doc_series=value(66),
                mil_doc_number=value(67),
                issue_date=date_(68),
            ),
        )
        if integer(17) is not None:
            key = integer(17)
            put(
                "personal_data",
                account_id,
                dict(
                    account_card_id=account_id,
                    personal_data_id=key,
                    snils=value(47),
                    inn=value(46),
                ),
            )
            put(
                "personal_properties",
                key,
                dict(
                    personal_property_id=key,
                    personal_id=key,
                    document_type=reference("nsi_mil_registration_docs", 18, 19),
                    series=value(20),
                    doc_number=value(21),
                    issue_date=date_(22),
                    place_doc=value(24),
                ),
            )
        if integer(174) is not None:
            key = integer(174)
            put(
                "relatives",
                key,
                dict(
                    relative_id=key,
                    account_card_id=account_id,
                    relation_degree=reference("nsi_relation_types", 175, 176),
                    last_name=value(177),
                    name=value(178),
                    patronymic=value(179),
                    birth_date=date_(180),
                    death_date=date_(181),
                    is_dependent=value(182).lower() in ("1", "да", "true", "t"),
                ),
            )
        if integer(222) is not None:
            key = integer(222)
            put(
                "education",
                key,
                dict(
                    education_id=key,
                    account_card_id=account_id,
                    education_type=value(223),
                    admission_date=date_(224),
                    graduation_date=date_(225),
                    main_specialization=value(226).lower() in ("1", "да", "true", "t"),
                    institution_name=value(227),
                    edu_form=value(228),
                    qualification=value(229),
                    document=value(230),
                    speciality=value(231),
                    educational_program=value(232),
                    series=value(234),
                    doc_num=value(235),
                    issue_date=date_(236),
                    note=value(240),
                    training_direction=value(241),
                ),
            )
        if integer(146) is not None:
            key = integer(146)
            house_id = value(173) or None
            if house_id:
                put(
                    "nsi_houses",
                    house_id,
                    dict(id_house=house_id, house_num=value(167)),
                )
            put(
                "addresses",
                key,
                dict(
                    address_id=key,
                    account_card_id=account_id,
                    index=value(158),
                    region=reference("nsi_regions", 159, 160),
                    city=reference("nsi_cities", 162, 163),
                    street=reference("nsi_streets", 164, 165),
                    registration_date=date_(166),
                    house=house_id or value(167),
                    apartment=value(168),
                    okato=value(169),
                    note=value(170),
                    kladr_code=value(171),
                    type_address=reference("nsi_addresses_types", 147, 148),
                ),
            )
        if integer(109) is not None and value(116):
            key = str(integer(109)) + value(116).replace(".", "")
            put(
                "assigments",
                key,
                dict(
                    assigment_id=key,
                    account_card_id=account_id,
                    tab_num=value(2),
                    start_date=date_(111),
                    finish_date=date_(112),
                    from_date=date_(113),
                    by_date=date_(114),
                    order_num=value(115),
                    order_date=date_(116),
                    division=reference("nsi_departments", 117, 118),
                    job_title=value(119),
                    kind_order=value(120),
                    employee_cat=value(121),
                ),
            )
        if integer(133) is not None:
            key = integer(133)
            put(
                "additional_attributes",
                key,
                dict(
                    attribute_id=key,
                    account_card_id=account_id,
                    from_date=date_(134),
                    by_date=date_(135),
                    note=value(136),
                    attribute_name=reference("nsi_hot_spots", 137, 138),
                    attribute_value=reference("nsi_hot_spots_values", 139, 140),
                ),
            )
        if integer(277) is not None:
            comm = reference("nsi_military_commissariarts", 277, 278)
            start, end = date_(279), date_(280)
            put(
                "com_history",
                f"{account_id}/{comm}/{start}/{end}",
                dict(
                    account_card_id=account_id,
                    comm=comm,
                    from_date=start,
                    by_date=end,
                ),
            )
    if not tables["account_cards"]:
        raise ValidationError("В файле нет учётных карточек.")
    result = {table: list(rows.values()) for table, rows in tables.items()}
    result["__diagnostics__"] = dict(replaced)
    return result
