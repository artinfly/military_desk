"""Роли видов учёта. Значения задаются только в локальной конфигурации."""

from django.conf import settings
from django.core.exceptions import ValidationError


def account_code(role):
    return settings.MILITARY_ACCOUNT_CODES.get(role, "")


def booking_codes():
    return tuple(code for role in ("reserved", "team") if (code := account_code(role)))


def require_account_codes():
    codes = {role: account_code(role) for role in ("reserved", "team", "general")}
    if not all(codes.values()):
        raise ValidationError("Виды учёта не настроены. Обратитесь к администратору.")
    return codes
