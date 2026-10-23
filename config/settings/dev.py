"""Настройки для разработки (домашний компьютер): режим отладки, локальные адреса."""

from .base import *  # noqa: F403
from .base import INSTALLED_APPS, env_list

DEBUG = True

# Генератор вымышленных данных (manage.py seed_demo) — только для разработки
INSTALLED_APPS = [*INSTALLED_APPS, "apps.demo"]
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

# Письма не отправляются, а печатаются в консоль
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
