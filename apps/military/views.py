"""Страница «Операции»: массовые изменения воинского учёта.

Доступ — у кого есть право менять записи воинского учёта (military.change_militaryrecord).
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.views import View

from . import services
from .forms import ChangeAccountTypeForm, ReserveForm, UnreserveForm

PERM = "military.change_militaryrecord"
# Сколько ненайденных СНИЛС показать в сообщении
NOT_FOUND_SHOWN = 20
DISMISSED_PERMISSIONS = (
    "military.add_reservationdismissal",
    "military.delete_reservationdismissal",
)


class OperationsView(View):
    template_name = "military/operations.html"
    page_title = "Операции"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(PERM):
            raise PermissionDenied("Недостаточно прав")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return self.render(request)

    def post(self, request):
        action = request.POST.get("action")
        if action == "account_type":
            return self.change_account_type(request)
        if action == "dismissed":
            return self.update_dismissed(request)
        if action == "unreserve":
            return self.unreserve(request)
        if action == "reserve":
            return self.reserve(request)
        return redirect("military:operations")

    def render(self, request, **forms):
        context = {
            "page_title": self.page_title,
            "can_update_dismissed": request.user.has_perms(DISMISSED_PERMISSIONS),
            "account_form": forms.get("account_form") or ChangeAccountTypeForm(),
            "unreserve_form": forms.get("unreserve_form") or UnreserveForm(),
            "reserve_form": forms.get("reserve_form") or ReserveForm(prefix="reserve"),
        }
        return render(request, self.template_name, context)

    def change_account_type(self, request):
        form = ChangeAccountTypeForm(request.POST)
        if not form.is_valid():
            return self.render(request, account_form=form)
        old, new = form.cleaned_data["old_type"], form.cleaned_data["new_type"]
        count = services.change_account_type(old, new, actor=request.user)
        messages.success(
            request,
            f"Группа учёта «{old}» → «{new or 'без группы'}»: изменено записей — {count}.",
        )
        return redirect("military:operations")

    def update_dismissed(self, request):
        if not request.user.has_perms(DISMISSED_PERMISSIONS):
            raise PermissionDenied(
                "Нет прав на добавление и удаление увольнений забронированных"
            )
        result = services.update_reserved_dismissed(actor=request.user)
        messages.success(
            request,
            "Спец. уволенные обновлены: добавлено — "
            f"{result.added}, убрано (снова работают) — {result.removed}, "
            f"снята бронь у уволенных — {result.unreserved}.",
        )
        return redirect("military:operations")

    def unreserve(self, request):
        form = UnreserveForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render(request, unreserve_form=form)
        try:
            snils_list = services.read_snils_file(form.cleaned_data["file"])
        except ValidationError as exc:
            form.add_error("file", exc)
            return self.render(request, unreserve_form=form)
        except Exception:  # битый или не тот файл — openpyxl бросает разные ошибки
            form.add_error("file", "Не удалось прочитать файл Excel.")
            return self.render(request, unreserve_form=form)
        try:
            result = services.unreserve_by_snils(
                snils_list, form.cleaned_data["order"], actor=request.user
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.render(request, unreserve_form=form)
        messages.success(request, f"Разбронировано: {result.unreserved}.")
        if result.not_found:
            shown = ", ".join(result.not_found[:NOT_FOUND_SHOWN])
            more = len(result.not_found) - NOT_FOUND_SHOWN
            tail = f" и ещё {more}" if more > 0 else ""
            messages.warning(
                request,
                f"Не найдены среди работающих ({len(result.not_found)}): {shown}{tail}.",
            )
        return redirect("military:operations")

    def reserve(self, request):
        form = ReserveForm(request.POST, request.FILES, prefix="reserve")
        if form.is_valid():
            try:
                snils = services.read_snils_file(form.cleaned_data["file"])
            except ValidationError as error:
                form.add_error(None, error)
                return self.render(request, reserve_form=form)
            except Exception:
                form.add_error("file", "Не удалось прочитать файл Excel.")
                return self.render(request, reserve_form=form)
            try:
                result = services.reserve_by_snils(
                    snils,
                    form.cleaned_data["order"],
                    form.cleaned_data["account_type"],
                    actor=request.user,
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, f"Забронировано: {result.reserved}.")
                if result.not_found:
                    messages.warning(
                        request,
                        f"Не найдены среди работающих: {len(result.not_found)}. "
                        + ", ".join(result.not_found[:NOT_FOUND_SHOWN]),
                    )
                return redirect("military:operations")
        return self.render(request, reserve_form=form)
