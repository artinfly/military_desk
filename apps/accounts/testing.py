"""Помощники для тестов: пользователь с ролью."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


def make_user(username, role=None, **kwargs):
    """Пользователь с ролью (группа создаётся сама после migrate, см. roles.py)."""
    user = get_user_model().objects.create_user(username, **kwargs)
    if role:
        user.groups.add(Group.objects.get(name=role))
    return user
