"""Вывод значений полей модели для просмотра: даты, «Да/Нет», выбор, пустые."""

from datetime import date, datetime

from django.utils import timezone

EMPTY = "—"


def display_value(obj, name):
    """Значение поля obj.name в виде текста для просмотра."""
    field = obj._meta.get_field(name)
    if field.choices:
        value = getattr(obj, f"get_{name}_display")()
    else:
        value = getattr(obj, name)
    if value is None or value == "":
        return EMPTY
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


def field_label(model, name):
    label = str(model._meta.get_field(name).verbose_name)
    return label[:1].upper() + label[1:]


def field_rows(obj, names):
    """[(подпись, значение), …] для блока «поле: значение»."""
    return [(field_label(type(obj), name), display_value(obj, name)) for name in names]
