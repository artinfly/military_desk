"""Названия строк NS, видимые в справочнике старого «Стола»."""

CATEGORY_NAMES = {
    1: "Руководители",
    2: "Специалисты",
    5: "Обрабатывающее производство",
    12: "Другие служащие",
    13: "Рабочие — всего",
    16: "Сельскохозяйственное производство",
    17: "Локомотивные бригады",
    18: "Водители",
}


def category_choices(current=None):
    choices = {number: f"{number} — {name}" for number, name in CATEGORY_NAMES.items()}
    if current is not None and current not in choices:
        choices[current] = f"{current} — сохранённая строка"
    return [("", "Не распределён")] + sorted(choices.items())
