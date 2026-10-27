"""Отчёты в Excel: страница «Отчёты», скачивание из реестра и «Отчёт по фильтру»."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from apps.personnel.filters import PersonFilterForm
from apps.personnel.services import search_people, sort_people

from .excel import build_sheets, build_workbook, xlsx_response
from .forms import PeriodForm
from .registry import available, get_report
from .services.filter_report import FILTER_REPORT_HEADERS, filter_report_rows


class FilterReportView(View):
    """«Отчёт по фильтру»: люди из списка карточек с теми же фильтрами и сортировкой."""

    def get(self, request):
        if not request.user.has_perm("personnel.view_person"):
            raise PermissionDenied("Нет доступа к учётным карточкам")
        form = PersonFilterForm(request.GET or None)
        filters = form.cleaned_data if form.is_valid() else {}
        people, _sort = sort_people(search_people(filters), request.GET.get("sort", ""))
        content = build_workbook(
            "Отчёт по фильтру", FILTER_REPORT_HEADERS, filter_report_rows(people)
        )
        today = timezone.localdate().strftime("%d.%m.%Y")
        return xlsx_response(content, f"Отчёт по фильтру {today}.xlsx")


class ReportListView(View):
    """Страница «Отчёты»: доступные отчёты; у отчётов с периодом — поля «с — по»."""

    def get(self, request):
        reports = available(request.user)
        if not reports:
            raise PermissionDenied("Нет доступа к отчётам")
        return render(
            request,
            "reports/report_list.html",
            {"page_title": "Отчёты", "reports": reports, "period_form": PeriodForm()},
        )


class ReportDownloadView(View):
    """Скачивание отчёта из реестра в Excel."""

    def get(self, request, slug):
        report = get_report(slug)
        if not request.user.has_perm(report.perm):
            raise PermissionDenied("Нет доступа к отчёту")
        form = PeriodForm(request.GET)
        if not form.is_valid():
            messages.error(
                request, " ".join(form.errors.get("__all__", ["Неверный период."]))
            )
            return redirect("reports:list")
        content = build_sheets(report.build(form.cleaned_data))
        today = timezone.localdate().strftime("%d.%m.%Y")
        return xlsx_response(content, f"{report.title} {today}.xlsx")
