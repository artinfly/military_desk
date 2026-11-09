import hashlib

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .dbf import conversion_zip, convert_dbf, spr_dbf
from .exchange import import_extended, parse_extended
from .forms import DbfForm, ProfessionCodeForm, UploadForm
from .hr_importer import import_hr
from .hr_source import parse_hr
from .models import ImportBatch, ProfessionCode
from .permissions import EXPORT_PERMISSIONS, IMPORT_PERMISSIONS


def file_response(content, filename, content_type):
    from django.utils.http import content_disposition_header

    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = content_disposition_header(True, filename)
    return response


class ExchangeView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("legacy.view_importbatch"):
            raise PermissionDenied("Нет доступа к обмену данными")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return self.render(request)

    def render(self, request, **context):
        return render(
            request,
            "legacy/exchange.html",
            {
                "page_title": "Обмен данными",
                "upload_form": UploadForm(auto_id="hr_%s"),
                "dbf_form": DbfForm(auto_id="dbf_%s"),
                "can_import": request.user.has_perms(IMPORT_PERMISSIONS),
                "can_export": request.user.has_perms(EXPORT_PERMISSIONS),
                "can_edit_codes": request.user.has_perm("legacy.change_professioncode"),
                "batches": ImportBatch.objects.select_related("created_by")[:10],
                **context,
            },
        )

    def post(self, request):
        if request.POST.get("action") == "dbf":
            if not request.user.has_perms(EXPORT_PERMISSIONS):
                raise PermissionDenied("Нет доступа к данным выгрузки")
            form = DbfForm(request.POST, request.FILES, auto_id="dbf_%s")
            if form.is_valid():
                try:
                    file = form.cleaned_data["file"]
                    converted = convert_dbf(
                        file.read(),
                        form.cleaned_data["kind"],
                        ProfessionCode.objects.values_list("code", flat=True),
                    )
                    return file_response(
                        conversion_zip(converted),
                        f"{form.cleaned_data['kind']}.zip",
                        "application/zip",
                    )
                except ValidationError as error:
                    form.add_error(None, error)
            return self.render(request, dbf_form=form)
        if not request.user.has_perms(IMPORT_PERMISSIONS):
            raise PermissionDenied("Недостаточно прав для кадровой загрузки")
        form = UploadForm(request.POST, request.FILES, auto_id="hr_%s")
        if not form.is_valid():
            return self.render(request, upload_form=form)
        dry_run = request.POST.get("action") != "import"
        if not dry_run and not form.cleaned_data["confirm"]:
            form.add_error(
                "confirm", "Отметьте применение изменений или сначала проверьте файл."
            )
            return self.render(request, upload_form=form)
        try:
            file = form.cleaned_data["file"]
            checksum = hashlib.file_digest(file, "sha256").hexdigest()
            file.seek(0)
            if form.cleaned_data["kind"] == "hr":
                result = import_hr(
                    parse_hr(file), request.user, checksum, dry_run=dry_run
                )
            else:
                result = import_extended(
                    parse_extended(file), request.user, checksum, dry_run=dry_run
                )
        except ValidationError as error:
            form.add_error(None, error)
            return self.render(request, upload_form=form)
        # Новый пустой файл в форме: браузер не хранит персональные данные в HTML.
        return self.render(request, result=result, dry_run=dry_run)


class SprView(View):
    def get(self, request):
        if not request.user.has_perms(EXPORT_PERMISSIONS):
            raise PermissionDenied("Нет доступа к данным выгрузки")
        rows = (
            ProfessionCode.objects.filter(personnelcode__isnull=False)
            .exclude(row_number=None)
            .values_list("row_number", "code")
            .distinct()
            .order_by("row_number", "code")
        )
        if not rows:
            return render(
                request, "legacy/empty_spr.html", {"page_title": "Справочник строк"}
            )
        return file_response(spr_dbf(rows), "spr.dbf", "application/octet-stream")


class CodesView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("legacy.change_professioncode"):
            raise PermissionDenied("Нет права изменять коды первого отдела")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        query = request.GET.get("q", "").strip()[:30]
        codes = ProfessionCode.objects.all()
        if query:
            codes = codes.filter(code__icontains=query)
        if request.GET.get("unmapped"):
            codes = codes.filter(row_number__isnull=True)
        page = Paginator(codes, 50).get_page(request.GET.get("page"))
        params = request.GET.copy()
        params.pop("page", None)
        return render(
            request,
            "legacy/codes.html",
            {
                "page_title": "Коды первого отдела",
                "query": query,
                "rows": [(code, ProfessionCodeForm(instance=code)) for code in page],
                "page_obj": page,
                "is_paginated": page.has_other_pages(),
                "filter_params": params.urlencode(),
            },
        )

    def post(self, request):
        try:
            code = get_object_or_404(ProfessionCode, pk=request.POST.get("code"))
        except (TypeError, ValueError):
            return HttpResponseBadRequest("Некорректный код записи")
        form = ProfessionCodeForm(request.POST, instance=code)
        if form.is_valid():
            form.save()
            return redirect("legacy:codes")
        return render(
            request,
            "legacy/code_form.html",
            {"page_title": f"Код {code}", "form": form},
        )
