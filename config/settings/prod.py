"""Настройки для рабочего сервера: отладка выключена, адреса сайта обязательны."""

from .base import *  # noqa: F403
from .base import env, env_list

DEBUG = False

# Адреса, по которым открывается сайт (например, имя сервера), — только из .env
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")

# Cookie входа и защиты форм — только по защищённому соединению, если сайт на HTTPS
SESSION_COOKIE_SECURE = env("HTTPS", "False") == "True"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
