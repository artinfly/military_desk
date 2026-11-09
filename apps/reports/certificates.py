"""Справки о бронировании и редактирование макета без исполнения кода шаблона."""

import re

from django import forms
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.core.widgets import use_reference_picker
from apps.personnel.models import Person
from apps.references.models import Department

from .models import DEFAULT_BODY, CertificateTemplate
from .services.common import day, text, workshop

FIELDS = (
    "ФИО",
    "ГодРождения",
    "ДатаРождения",
    "ТабельныйНомер",
    "Должность",
    "Цех",
    "ГруппаУчёта",
    "Звание",
    "Состав",
    "ВУС",
    "Серия",
    "Номер",
    "ПриказНомер",
    "Дата",
)
PLACEHOLDER = re.compile(r"{{\s*([^{}]+?)\s*}}")
VIEW_PERMISSIONS = ("personnel.view_person", "military.view_militaryrecord")
EDIT_PERMISSIONS = (
    "reports.view_certificatetemplate",
    "reports.change_certificatetemplate",
)


def template_data():
    return CertificateTemplate.objects.order_by("pk").first() or CertificateTemplate()


def certificate_people():
    return (
        Person.objects.filter(
            dismissal_date__isnull=True,
            military__is_reserved=True,
        )
        .select_related(
            "department",
            "military__accounting_group",
            "military__rank",
            "military__reserve_composition",
            "military__speciality",
        )
        .order_by("department__number", "last_name", "first_name", "pk")
    )


def certificate_text(person, body, today):
    military = person.military
    values = dict(
        zip(
            FIELDS,
            (
                person.full_name,
                str(person.birth_date.year),
                day(person.birth_date),
                person.tab_number,
                person.position,
                workshop(person),
                text(military.accounting_group),
                text(military.rank),
                text(military.reserve_composition),
                text(military.speciality),
                military.document_series,
                military.document_number,
                military.reservation_document,
                day(today),
            ),
            strict=True,
        )
    )
    return PLACEHOLDER.sub(
        lambda match: values.get(match[1].strip()) or "________", body
    )


class CertificateSelectionForm(forms.Form):
    department = forms.ModelChoiceField(
        Department.objects.filter(is_active=True),
        label="Цех",
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        use_reference_picker(self.fields["department"])


class CertificateTemplateForm(forms.ModelForm):
    revision = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = CertificateTemplate
        fields = ("name", "organization", "body")
        widgets = {"body": forms.Textarea(attrs={"rows": 16})}

    def clean_body(self):
        body = self.cleaned_data["body"]
        unknown = set(PLACEHOLDER.findall(body)) - set(FIELDS)
        if unknown:
            raise forms.ValidationError(
                "Неизвестные поля: " + ", ".join(sorted(unknown))
            )
        if "{{" in PLACEHOLDER.sub("", body) or "}}" in PLACEHOLDER.sub("", body):
            raise forms.ValidationError("Проверьте скобки полей: {{ФИО}}.")
        return body


class CertificatesView(View):
    def get(self, request, pk=None):
        if not request.user.has_perms(VIEW_PERMISSIONS):
            raise PermissionDenied("Нет доступа к справкам")
        template = template_data()
        form = CertificateSelectionForm(request.GET or None)
        people = certificate_people()
        if pk is not None:
            people = [get_object_or_404(people, pk=pk)]
        elif request.GET and form.is_valid():
            people = people.filter(department=form.cleaned_data["department"])
        else:
            return render(
                request,
                "reports/certificates.html",
                {
                    "page_title": "Справки о бронировании",
                    "form": form,
                    "can_edit": request.user.has_perms(EDIT_PERMISSIONS),
                },
            )
        today = timezone.localdate()
        return render(
            request,
            "reports/certificate_print.html",
            {
                "page_title": template.name,
                "template": template,
                "certificates": [
                    (p, certificate_text(p, template.body, today)) for p in people
                ],
            },
        )


class CertificateTemplateView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perms(EDIT_PERMISSIONS):
            raise PermissionDenied("Нет права изменять шаблон справки")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        template = template_data()
        return self.render(
            request,
            CertificateTemplateForm(
                instance=template,
                initial={
                    "revision": template.updated_at.isoformat() if template.pk else "",
                },
            ),
        )

    def post(self, request):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(486174, 2)")
            template = (
                CertificateTemplate.objects.select_for_update().order_by("pk").first()
            )
            template = template or CertificateTemplate()
            form = CertificateTemplateForm(request.POST, instance=template)
            if form.is_valid():
                revision = template.updated_at.isoformat() if template.pk else ""
                if form.cleaned_data["revision"] != revision:
                    form.add_error(
                        None,
                        "Шаблон уже изменён. Откройте его заново перед сохранением.",
                    )
                else:
                    form.instance.updated_by = request.user
                    form.save()
                    return redirect("reports:certificates")
        return self.render(request, form)

    def render(self, request, form):
        return render(
            request,
            "reports/certificate_template.html",
            {
                "page_title": "Шаблон справки",
                "form": form,
                "fields": FIELDS,
                "default_body": DEFAULT_BODY,
            },
        )
