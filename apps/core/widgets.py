"""Выбор записи большого справочника без загрузки всех записей в HTML."""

from django import forms
from django.urls import reverse

SEARCHABLE_MODELS = {
    "department",
    "region",
    "city",
    "street",
    "militaryspeciality",
    "militarycommissariat",
    "attributetype",
    "attributevalue",
}


class ReferenceSelect(forms.Select):
    template_name = "core/widgets/reference_select.html"

    def __init__(self, slug, attrs=None):
        super().__init__(attrs)
        self.slug = slug

    def optgroups(self, name, value, attrs=None):
        # ModelChoiceIterator содержит queryset формы: только действующие записи
        # и сохранённое значение, даже если его уже пометили недействующим.
        field = self.choices.field
        selected = {str(v) for v in value if v not in (None, "")}
        options = []
        if field.empty_label is not None:
            options.append(
                self.create_option(
                    name, "", field.empty_label, not selected, 0, attrs=attrs
                )
            )
        if selected:
            try:
                objects = list(field.queryset.filter(pk__in=selected))
            except (ValueError, TypeError):
                objects = []
            for obj in objects:
                options.append(
                    self.create_option(
                        name,
                        str(obj.pk),
                        field.label_from_instance(obj),
                        True,
                        len(options),
                        attrs=attrs,
                    )
                )
        return [(None, options, 0)]

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["picker_value"] = (widget["value"] or [""])[0]
        widget["picker_empty_label"] = (
            self.choices.field.empty_label or "— не выбрано —"
        )
        widget["picker_value_label"] = widget["picker_empty_label"]
        widget["picker_required"] = self.is_required
        for _group, options, _index in widget["optgroups"]:
            for option in options:
                if option["selected"] and option["value"]:
                    widget["picker_value_label"] = option["label"]
        context["widget"]["picker_url"] = reverse(
            "references:choices", args=[self.slug]
        )
        context["widget"]["picker_title"] = self.choices.field.label or "Справочник"
        return context

    def id_for_label(self, id_):
        return f"{id_}_display" if id_ else id_

    def use_required_attribute(self, initial):
        # Значение отправляется скрытым полем; обязательность проверяет форма Django.
        return False


def use_reference_picker(field):
    queryset = getattr(field, "queryset", None)
    if queryset is None or queryset.model._meta.model_name not in SEARCHABLE_MODELS:
        return field
    # Импорт отложен: реестр использует модели приложений.
    from apps.references.registry import REFERENCES

    reference = next((r for r in REFERENCES if r.model is queryset.model), None)
    if reference:
        field.widget = ReferenceSelect(reference.slug, attrs=field.widget.attrs)
        field.widget.is_required = field.required
        field.widget.choices = field.choices
    return field
