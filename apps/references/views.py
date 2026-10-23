"""Страницы справочников: каталог, список, добавление и правка.

Смотреть справочники могут все вошедшие; добавлять и менять — у кого есть
стандартные права Django на этот справочник (add_/change_<модель>).
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import FormView, ListView, TemplateView

from .registry import get_reference, sections

STATUS_CHOICES = {
    "active": "Действующие",
    "inactive": "Недействующие",
    "all": "Все",
}


class CatalogView(TemplateView):
    """Каталог: все справочники по разделам с числом записей."""

    template_name = "references/catalog.html"
    extra_context = {"page_title": "Справочники"}

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_module_perms("references"):
            raise PermissionDenied("Нет доступа к справочникам")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        visible = [
            (title, [ref for ref in refs if user.has_perm(ref.perm("view"))])
            for title, refs in sections()
        ]
        context["sections"] = [
            (title, [(ref, ref.model.objects.count()) for ref in refs])
            for title, refs in visible
            if refs
        ]
        return context


class ReferenceMixin:
    """Справочник из адреса (/references/<slug>/…) — в self.ref и в контексте."""

    def dispatch(self, request, *args, **kwargs):
        self.ref = get_reference(kwargs["slug"])
        if not request.user.has_perm(self.ref.perm("view")):
            raise PermissionDenied("Нет доступа к справочнику")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ref"] = self.ref
        return context


class ReferenceListView(ReferenceMixin, ListView):
    """Список записей справочника с поиском и фильтром по «Действует»."""

    template_name = "references/list.html"
    paginate_by = 50

    def get_queryset(self):
        queryset = self.ref.model.objects.all()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(code__icontains=query)
            )
        status = self.status()
        if status != "all":
            queryset = queryset.filter(is_active=status == "active")
        return queryset

    def status(self):
        status = self.request.GET.get("status", "active")
        return status if status in STATUS_CHOICES else "active"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        meta = self.ref.model._meta
        user = self.request.user
        context.update(
            page_title=self.ref.title,
            columns=[
                meta.get_field(name).verbose_name for name in self.ref.list_fields
            ],
            rows=[
                (obj, [getattr(obj, name) for name in self.ref.list_fields])
                for obj in context["object_list"]
            ],
            query=self.request.GET.get("q", ""),
            status=self.status(),
            status_choices=STATUS_CHOICES,
            can_add=user.has_perm(self.ref.perm("add")),
            can_change=user.has_perm(self.ref.perm("change")),
        )
        return context


class ReferenceFormView(ReferenceMixin, FormView):
    """Добавление (pk нет в адресе) и правка записи справочника."""

    template_name = "references/form.html"

    def dispatch(self, request, *args, **kwargs):
        self.ref = get_reference(kwargs["slug"])
        self.object = (
            get_object_or_404(self.ref.model, pk=kwargs["pk"])
            if "pk" in kwargs
            else None
        )
        if not request.user.has_perm(self.ref.perm("change" if self.object else "add")):
            raise PermissionDenied("Нет прав на изменение справочника")
        return super(ReferenceMixin, self).dispatch(request, *args, **kwargs)

    def get_form_class(self):
        return modelform_factory(self.ref.model, fields=self.ref.form_fields)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.object
        return kwargs

    def form_valid(self, form):
        obj = form.save()
        action = "изменена" if self.object else "добавлена"
        messages.success(self.request, f"Запись «{obj}» {action}")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("references:list", args=[self.ref.slug])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object"] = self.object
        context["page_title"] = (
            f"{self.ref.title}: {self.object}"
            if self.object
            else f"{self.ref.title}: новая запись"
        )
        return context
