"""Общая сборка отчётов Excel: оформленные таблицы и ответ для скачивания."""

from datetime import date
from io import BytesIO
from urllib.parse import quote

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="2E2E2E")
HEADER_FONT = Font(bold=True, color="FFFFFF")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADER_ALIGNMENT = Alignment(vertical="center", wrap_text=True)
BODY_ALIGNMENT = Alignment(vertical="top", wrap_text=True)


def _fill_sheet(sheet, title, headers, rows):
    """Пишет строки последовательно, применяя один общий стиль для каждой роли."""
    if not isinstance(rows, (list, tuple)):
        rows = list(rows)
    sheet.title = title[:31]
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"
    widths = [len(str(header)) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            if value is not None and widths[index] < 58:
                widths[index] = max(widths[index], len(str(value)))
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = min(width + 2, 60)

    def cells(row, *, header=False):
        # Openpyxl повторно использует ячейку после сериализации. Все поля стиля
        # задаются явно, чтобы формат даты не переходил на следующие значения.
        cell = WriteOnlyCell(sheet)
        cell.alignment = HEADER_ALIGNMENT if header else BODY_ALIGNMENT
        if header:
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
        date_cell = WriteOnlyCell(sheet)
        date_cell.alignment = HEADER_ALIGNMENT if header else BODY_ALIGNMENT
        date_cell.number_format = "DD.MM.YYYY"
        for value in row:
            target = date_cell if isinstance(value, date) else cell
            target.value = (
                ILLEGAL_CHARACTERS_RE.sub("", value)
                if isinstance(value, str)
                else value
            )
            if isinstance(value, str):
                target.data_type = "s"
            yield target

    sheet.append(cells(headers, header=True))
    for row in rows:
        sheet.append(cells(row))


def build_sheets(sheets):
    """Книга из листов [(название, шапка, строки)]. Возвращает байты файла."""
    book = Workbook(write_only=True)
    for title, headers, rows in sheets:
        _fill_sheet(book.create_sheet(), title, headers, rows)
    content = BytesIO()
    book.save(content)
    return content.getvalue()


def build_workbook(title, headers, rows):
    """Книга с одним листом."""
    return build_sheets([(title, headers, rows)])


def xlsx_response(content, filename):
    """Ответ «скачать файл»; имя файла может быть по-русски."""
    response = HttpResponse(content, content_type=XLSX)
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response
