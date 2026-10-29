"""Боковое меню сайта.

Раздел — словарь с заголовком (title) и пунктами (items). Пункт:
    label       подпись в меню
    url_name    имя адреса (как в {% url %})
    namespace   пункт подсвечен на всех страницах этого раздела адресов (необязательно)
    perm        показывать только при этом праве, например "personnel.view_person"
    module      показывать при любом праве в этом приложении, например "references"

Каждое новое приложение добавляет сюда свой раздел.
Администрирование и выход — внизу панели (templates/base.html), не здесь.
"""

MENU = [
    {
        "title": "",
        "items": [
            {"label": "Главная", "url_name": "core:home"},
        ],
    },
    {
        "title": "Данные",
        "items": [
            {
                "label": "Учётные карточки",
                "url_name": "personnel:list",
                "namespace": "personnel",
                "perm": "personnel.view_person",
            },
            {
                "label": "Справочники",
                "url_name": "references:catalog",
                "namespace": "references",
                "module": "references",
            },
            {
                "label": "Отчёты",
                "url_name": "reports:list",
                "namespace": "reports",
                "perm": "military.view_militaryrecord",
            },
            {
                "label": "Операции",
                "url_name": "military:operations",
                "namespace": "military",
                "perm": "military.change_militaryrecord",
            },
        ],
    },
]
