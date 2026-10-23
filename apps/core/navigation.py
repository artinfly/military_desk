"""Боковое меню сайта.

Раздел — словарь с заголовком (title) и пунктами (items). Пункт:
    label       подпись в меню
    url_name    имя адреса (как в {% url %})
    namespace   пункт подсвечен на всех страницах этого раздела адресов (необязательно)
    staff_only  показывать только сотрудникам с доступом в админку (необязательно)
    perm        показывать только при этом праве, например "personnel.view_person"
    module      показывать при любом праве в этом приложении, например "references"

Каждое новое приложение добавляет сюда свой раздел.
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
        ],
    },
    {
        "title": "Администрирование",
        "items": [
            {"label": "Админка", "url_name": "admin:index", "staff_only": True},
        ],
    },
]
