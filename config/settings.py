"""Единые настройки Django проекта «Военно-учётный стол».

Локальные значения берутся из переменных окружения и необязательного .env.
Для разработки укажите DEBUG=True, для рабочего сервера — DEBUG=False.
Секреты и коды воинского учёта никогда не хранятся в Git.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Экспортированные сервером переменные имеют приоритет над файлом .env.
load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    """Получить настройку; без значения по умолчанию она обязательна."""
    value = os.getenv(name, default)
    if value is None:
        raise ImproperlyConfigured(
            f"Не задана переменная {name} (см. .env.example)."
        )
    return value


def env_bool(name, default=False):
    """Прочитать логическую настройку из 1/0, true/false, yes/no, on/off."""
    value = env(name, str(default)).strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ImproperlyConfigured(f"Некорректное логическое значение {name}.")


def env_list(name, default=""):
    """Список значений, разделённых запятыми."""
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# Общие параметры. Откладка по умолчанию выключена (fail closed).
SECRET_KEY = env("SECRET_KEY")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else ""
)
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Для рабочего сервера задайте ALLOWED_HOSTS.")

# Реальные коды задаются исключительно в закрытой конфигурации установки.
MILITARY_ACCOUNT_CODES = {
    role: env(f"MILITARY_ACCOUNT_{role.upper()}_CODE", "").strip().upper()
    for role in ("reserved", "team", "general")
}
_configured_codes = [code for code in MILITARY_ACCOUNT_CODES.values() if code]
if len(_configured_codes) != len(set(_configured_codes)):
    raise ImproperlyConfigured("Укажите разные коды для видов учёта.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.accounts",
    "apps.references",
    "apps.personnel",
    "apps.military",
    "apps.reports",
    # Здесь же работает текущий кадровый обмен и перенос старой базы.
    "apps.legacy",
]
if DEBUG:
    # Только вымышленные данные; команда seed_demo недоступна в production.
    INSTALLED_APPS.append("apps.demo")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    # Запрещает браузерное кеширование страниц с персональными данными.
    "apps.core.middleware.PrivatePagesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.navigation",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", "military_desk_test"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", "localhost"),
        "PORT": env("DB_PORT", "5432"),
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Нескольким сервисам на одном хосте нужны уникальные имена cookie.
SESSION_COOKIE_NAME = env("SESSION_COOKIE_NAME", "sessionid")
CSRF_COOKIE_NAME = env("CSRF_COOKIE_NAME", "csrftoken")

LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Yekaterinburg"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Различаются только свойства окружения, а не набор отдельных settings-модулей.
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = True
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }
    # Доверять заголовкам прокси только при правильно настроенном nginx.
    USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST")
    if env_bool("SECURE_PROXY_SSL_HEADER"):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

    # HTTPS включается для рабочей установки с TLS (в том числе через прокси).
    SESSION_COOKIE_SECURE = env_bool("HTTPS")
    CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    CSRF_COOKIE_HTTPONLY = True
