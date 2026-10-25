"""Выгрузка отчётов в Excel."""

from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.views import View

from apps.personnel.filters import PersonFilterForm
from apps.personnel.services import search_people, sort_people

from .excel import build_workbook, xlsx_response
from .services import FILTER_REPORT_HEADERS, filter_report_rows


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
