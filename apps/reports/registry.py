"""Реестр отчётов: какие есть, кому доступны, нужен ли период.

По реестру строятся страница «Отчёты» и скачивание. Новый отчёт: функция
params -> [(лист, шапка, строки)] в services/ + строка здесь.
«Отчёт по фильтру» сюда не входит: он строится из списка карточек (кнопка там).
"""

from dataclasses import dataclass

from django.http import Http404

from .services import counts, lists

# Отчёты по воинскому учёту видят все, кому доступен воинский учёт
MILITARY_VIEW = "military.view_militaryrecord"


@dataclass(frozen=True)
class Report:
    slug: str  # часть адреса: /reports/<slug>/
    title: str
    description: str
    build: object  # функция params -> [(лист, шапка, строки)]
    period: str = ""  # подпись периода («Дата приёма»), пусто — отчёт без периода
    perm: str = MILITARY_VIEW


REPORTS = [
    Report(
        "headcount",
        "Численность",
        "Работающие, военнообязанные, бронь, команда, офицеры, водители, призывники.",
        counts.report_sheets,
    ),
    Report(
        "vus",
        "ВУС по видам учёта",
        "Работающие военнообязанные: по каждой ВУС — бронь (X4), команда (R7), общий учёт (H9).",
        lists.vus_by_account,
    ),
    Report(
        "reservation",
        "Форма бронирования",
        "Работающие военнообязанные без внешних совместителей; листы «Приложение 1» "
        "(ВУС из перечня) и «Приложение 2» (документ, отмеченный в справочнике).",
        lists.reservation_form,
    ),
    Report(
        "hired",
        "Принятые с бронью и в команду",
        "Работающие с видом учёта X4 или R7, принятые за период.",
        lists.hired,
        period="Дата приёма",
    ),
    Report(
        "reserved-dismissed",
        "Спец. уволенные",
        "Уволенные забронированные: удостоверение и дата увольнения.",
        lists.reserved_dismissed,
        period="Дата увольнения",
    ),
    Report(
        "conscripts",
        "Призывники",
        "Работающие призывники: образование, адрес, военкомат, должность.",
        lists.conscripts,
    ),
]


def get_report(slug):
    for report in REPORTS:
        if report.slug == slug:
            return report
    raise Http404("Нет такого отчёта")


def available(user):
    """Отчёты, доступные пользователю."""
    return [report for report in REPORTS if user.has_perm(report.perm)]
