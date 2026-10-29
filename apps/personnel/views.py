"""Страницы учётных карточек: список, карточка с вкладками, правка карточки и разделов.

Смотреть может каждый вошедший; добавлять, менять и удалять — у кого есть права
Django на соответствующую модель (personnel.change_person, military.add_commissariatregistration…).
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.display import EMPTY, display_value, field_label, field_rows

from .filters import PersonFilterForm
from .forms import GENERAL_FIELDSETS, PersonForm
from .models import Person
from .sections import MILITARY, PERSONAL, all_sections, get_section
from .services import search_people, sort_people

# Колонки списка: (ключ сортировки или None, заголовок)
COLUMNS = [
    ("tab_number", "Таб. номер"),
    ("name", "ФИО"),
    ("rank", "Звание"),
    (None, "Пол"),
    ("birth_date", "Дата рождения"),
    ("dismissal_date", "Дата увольнения"),
    ("duty", "Военная обязанность"),
    ("department", "Место работы"),
    (None, "Учёт"),
    (None, "Бронь"),
    (None, "СВО"),
]


def require_perm(user, perm):
    if not user.has_perm(perm):
        raise PermissionDenied("Недостаточно прав")


def card_url(person, tab="general"):
    url = reverse("personnel:detail", args=[person.pk])
    return url if tab == "general" else f"{url}?tab={tab}"


def mark_changed(person, user):
    """Отметить в карточке, кто и когда её изменил (при правке любого раздела)."""
    Person.objects.filter(pk=person.pk).update(
        updated_at=timezone.now(), updated_by=user
    )


def bound_fieldsets(form, fieldsets):
    """[(заголовок, [поля формы]), …] для вывода формы по группам."""
    return [(title, [form[name] for name in names]) for title, names in fieldsets]


# --- Список ---


class ViewPersonRequired:
    """Смотреть карточки — только с правом personnel.view_person."""

    def dispatch(self, request, *args, **kwargs):
        require_perm(request.user, "personnel.view_person")
        return super().dispatch(request, *args, **kwargs)


class PersonListView(ViewPersonRequired, ListView):
    """Список учётных карточек с фильтрами (как главное окно старой программы)."""

    template_name = "personnel/person_list.html"
    paginate_by = 50
    extra_context = {"page_title": "Учётные карточки"}

    def get_queryset(self):
        self.form = PersonFilterForm(self.request.GET or None)
        filters = self.form.cleaned_data if self.form.is_valid() else {}
        people, self.sort = sort_people(
            search_people(filters), self.request.GET.get("sort", "")
        )
        return people

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        params.pop("sort", None)
        context.update(
            form=self.form,
            sort=self.sort,
            columns=[
                {
                    "title": title,
                    "key": key,
                    "active": key and self.sort.lstrip("-") == key,
                    "descending": self.sort.startswith("-"),
                    # Повторный клик по той же колонке меняет направление
                    "next": f"-{key}" if key and self.sort == key else key,
                }
                for key, title in COLUMNS
            ],
            filter_params=params.urlencode(),
            has_filters=any(
                v for k, v in self.request.GET.items() if k not in ("page", "sort")
            ),
            can_add=self.request.user.has_perm("personnel.add_person"),
        )
        return context


# --- Карточка ---


class PersonDetailView(ViewPersonRequired, DetailView):
    """Карточка с вкладками; открытая вкладка — в адресе (?tab=…)."""

    template_name = "personnel/person_detail.html"
    queryset = Person.objects.select_related("department", "updated_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        person, user = self.object, self.request.user
        tab = self.request.GET.get("tab", "general")
        # Вкладки разделов — только те, что пользователю можно смотреть
        sections = [s for s in all_sections() if user.has_perm(s.perm("view"))]
        context.update(
            page_title=person.full_name,
            tab=tab,
            tab_groups=[
                (group, items)
                for group in (PERSONAL, MILITARY)
                if (items := [s for s in sections if s.group == group])
            ],
            military=(
                getattr(person, "military", None)
                if user.has_perm("military.view_militaryrecord")
                else None
            ),
            can_change_person=user.has_perm("personnel.change_person"),
            can_delete_person=user.has_perm("personnel.delete_person"),
        )
        if tab == "general":
            context["general"] = [
                (title, field_rows(person, names)) for title, names in GENERAL_FIELDSETS
            ]
            return context

        section = get_section(tab)
        require_perm(user, section.perm("view"))
        context.update(
            section=section,
            can_add=user.has_perm(section.perm("add")),
            can_change=user.has_perm(section.perm("change")),
            can_delete=user.has_perm(section.perm("delete")),
        )
        if section.single:
            record = section.items(person).first()  # со справочниками одним запросом
            context["record"] = record
            if record:
                context["record_fieldsets"] = [
                    (title, field_rows(record, names))
                    for title, names in section.fieldsets
                ]
        else:
            context["headers"] = [
                "Адрес" if col == "__str__" else field_label(section.model, col)
                for col in section.columns
            ]
            context["rows"] = [
                (
                    item,
                    [
                        (
                            str(item) or EMPTY
                            if col == "__str__"
                            else display_value(item, col)
                        )
                        for col in section.columns
                    ],
                )
                for item in section.items(person)
            ]
        return context


class PersonFormView(View):
    """Добавление (без pk) и правка основных данных карточки."""

    template_name = "personnel/person_form.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.person = (
            get_object_or_404(Person, pk=kwargs["pk"]) if "pk" in kwargs else None
        )

    def dispatch(self, request, *args, **kwargs):
        require_perm(
            request.user,
            "personnel.change_person" if self.person else "personnel.add_person",
        )
        return super().dispatch(request, *args, **kwargs)

    def render(self, form):
        return render(
            self.request,
            self.template_name,
            {
                "form": form,
                "fieldsets": bound_fieldsets(form, GENERAL_FIELDSETS),
                "person": self.person,
                "page_title": (
                    self.person.full_name if self.person else "Новая учётная карточка"
                ),
                "cancel_url": (
                    card_url(self.person) if self.person else reverse("personnel:list")
                ),
            },
        )

    def get(self, request, *args, **kwargs):
        return self.render(PersonForm(instance=self.person))

    def post(self, request, *args, **kwargs):
        form = PersonForm(request.POST, instance=self.person)
        if not form.is_valid():
            return self.render(form)
        person = form.save(commit=False)
        person.updated_by = request.user
        person.save()
        messages.success(
            request, "Карточка сохранена" if self.person else "Карточка создана"
        )
        return redirect(card_url(person))


class PersonDeleteView(View):
    template_name = "personnel/confirm_delete.html"

    def dispatch(self, request, *args, **kwargs):
        require_perm(request.user, "personnel.delete_person")
        self.person = get_object_or_404(Person, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            {
                "page_title": "Удаление карточки",
                "question": f"Удалить учётную карточку «{self.person}» со всеми разделами?",
                "cancel_url": card_url(self.person),
            },
        )

    def post(self, request, *args, **kwargs):
        name = str(self.person)
        self.person.delete()
        messages.success(request, f"Карточка «{name}» удалена")
        return redirect("personnel:list")


# --- Разделы карточки ---


class SectionFormView(View):
    """Добавление и правка записи раздела; для одиночного раздела — одна запись на карточку."""

    template_name = "personnel/section_form.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.person = get_object_or_404(Person, pk=kwargs["pk"])
        self.section = get_section(kwargs["slug"])
        model = self.section.model
        if self.section.single:
            self.item = model.objects.filter(person=self.person).first()
        elif "item" in kwargs:
            self.item = get_object_or_404(model, pk=kwargs["item"], person=self.person)
        else:
            self.item = None

    def dispatch(self, request, *args, **kwargs):
        require_perm(request.user, self.section.perm("change" if self.item else "add"))
        return super().dispatch(request, *args, **kwargs)

    def render(self, form):
        title = self.section.title
        fieldsets = self.section.fieldsets or ((None, tuple(form.fields)),)
        return render(
            self.request,
            self.template_name,
            {
                "form": form,
                "fieldsets": bound_fieldsets(form, fieldsets),
                "person": self.person,
                "section": self.section,
                "page_title": f"{title}: {'изменение' if self.item else 'добавление'}",
                "cancel_url": card_url(self.person, self.section.slug),
            },
        )

    def get(self, request, *args, **kwargs):
        return self.render(self.section.form_class()(instance=self.item))

    def post(self, request, *args, **kwargs):
        form = self.section.form_class()(request.POST, instance=self.item)
        if not form.is_valid():
            return self.render(form)
        item = form.save(commit=False)
        item.person = self.person
        item.save()
        mark_changed(self.person, request.user)
        messages.success(request, f"{self.section.title}: сохранено")
        return redirect(card_url(self.person, self.section.slug))


class SectionDeleteView(View):
    template_name = "personnel/confirm_delete.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.person = get_object_or_404(Person, pk=kwargs["pk"])
        self.section = get_section(kwargs["slug"])
        self.item = get_object_or_404(
            self.section.model, pk=kwargs["item"], person=self.person
        )

    def dispatch(self, request, *args, **kwargs):
        require_perm(request.user, self.section.perm("delete"))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            {
                "page_title": f"{self.section.title}: удаление",
                "question": f"Удалить запись «{self.item}» из раздела «{self.section.title}»?",
                "cancel_url": card_url(self.person, self.section.slug),
            },
        )

    def post(self, request, *args, **kwargs):
        try:
            self.item.delete()
        except ProtectedError:
            messages.error(request, "Запись используется и не может быть удалена")
        else:
            mark_changed(self.person, request.user)
            messages.success(request, f"{self.section.title}: запись удалена")
        return redirect(card_url(self.person, self.section.slug))
