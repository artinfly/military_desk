"""Роли пользователей — группы Django с набором прав.

Права Django создаются сами: на каждую модель — view (смотреть), add, change, delete.
Роль описывается так: для приложения — какие действия разрешены; исключения —
отдельные права, которые роли не даются.

Группы создаются и обновляются после каждого migrate (сигнал post_migrate,
см. apps.py) — на новом сервере настраивать ничего не нужно. Вручную: manage.py sync_roles.
Права, добавленные группе вручную в админке, при синхронизации сбрасываются к описанию.
"""

from django.contrib.auth.models import Group, Permission

ALL = ("view", "add", "change", "delete")

VIEWER = "Просмотр"
OPERATOR = "Оператор"
ADMIN = "Администратор учёта"

ROLES = {
    VIEWER: {
        "apps": {
            "references": ("view",),
            "personnel": ("view",),
            "military": ("view",),
        },
        "except": (),
    },
    OPERATOR: {
        "apps": {"references": ("view",), "personnel": ALL, "military": ALL},
        # Удалить карточку целиком — только администратор учёта
        "except": ("personnel.delete_person",),
    },
    ADMIN: {
        "apps": {"references": ALL, "personnel": ALL, "military": ALL},
        "except": (),
    },
}


def role_permissions(role):
    """Права роли (queryset Permission) по описанию в ROLES."""
    spec = ROLES[role]
    ids = []
    for app_label, actions in spec["apps"].items():
        for perm in Permission.objects.filter(content_type__app_label=app_label):
            if perm.codename.split("_", 1)[0] in actions:
                ids.append(perm.pk)
    permissions = Permission.objects.filter(pk__in=ids)
    for label, codename in (p.split(".") for p in spec["except"]):
        permissions = permissions.exclude(
            content_type__app_label=label, codename=codename
        )
    return permissions


def sync_roles():
    """Создаёт группы ролей и выставляет им права по описанию. Возвращает {роль: число прав}."""
    result = {}
    for role in ROLES:
        group, _created = Group.objects.get_or_create(name=role)
        permissions = list(role_permissions(role))
        group.permissions.set(permissions)
        result[role] = len(permissions)
    return result


# Приложения, права которых входят в роли
ROLE_APPS = {label for spec in ROLES.values() for label in spec["apps"]}


def sync_roles_after_migrate(sender, **kwargs):
    """Обработчик post_migrate: роли актуальны после каждого migrate.

    Права приложения появляются, когда post_migrate приходит для него самого,
    поэтому синхронизация запускается после каждого приложения из ролей —
    последний запуск видит все права.
    """
    if sender.label in ROLE_APPS:
        sync_roles()
