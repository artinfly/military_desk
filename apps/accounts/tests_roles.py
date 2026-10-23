"""Роли: группы с правами и что каждая роль может на сайте."""

from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from apps.military.models import MilitaryRecord
from apps.personnel.models import Person
from apps.personnel.tests import make_person
from apps.references import models as ref

from .roles import ADMIN, OPERATOR, ROLES, VIEWER, sync_roles
from .testing import make_user


def perms(role):
    return {
        f"{p.content_type.app_label}.{p.codename}"
        for p in Group.objects.get(name=role).permissions.select_related("content_type")
    }


class RoleGroupsTests(TestCase):
    def test_groups_created_after_migrate(self):
        self.assertEqual(
            set(Group.objects.values_list("name", flat=True)) & set(ROLES), set(ROLES)
        )
        viewer, operator, admin = perms(VIEWER), perms(OPERATOR), perms(ADMIN)
        self.assertTrue(all(p.split(".")[1].startswith("view_") for p in viewer))
        self.assertIn("personnel.view_person", viewer)
        self.assertIn("military.delete_rankassignment", operator)
        self.assertNotIn("personnel.delete_person", operator)
        self.assertNotIn("references.change_militaryrank", operator)
        self.assertIn("personnel.delete_person", admin)
        self.assertIn("references.add_militaryrank", admin)
        self.assertTrue(viewer < operator < admin)

    def test_sync_is_idempotent_and_resets_manual_changes(self):
        group = Group.objects.get(name=VIEWER)
        group.permissions.add(Permission.objects.get(codename="delete_person"))
        before = sync_roles()
        self.assertEqual(sync_roles(), before)
        self.assertNotIn("personnel.delete_person", perms(VIEWER))
        self.assertEqual(Group.objects.filter(name=VIEWER).count(), 1)


class RoleAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.person = make_person()
        MilitaryRecord.objects.create(person=cls.person)

    def menu(self, response):
        return [i["label"] for s in response.context["menu"] for i in s["items"]]

    def test_without_role(self):
        self.client.force_login(make_user("nobody"))
        home = self.client.get(reverse("core:home"))
        self.assertContains(home, "нет роли")
        self.assertEqual(self.menu(home), ["Главная"])
        for url in [
            reverse("personnel:list"),
            reverse("personnel:detail", args=[self.person.pk]),
            reverse("references:catalog"),
            reverse("references:list", args=["military-ranks"]),
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)
                self.assertContains(response, "Нет доступа", status_code=403)

    def test_viewer(self):
        self.client.force_login(make_user("viewer", VIEWER))
        home = self.client.get(reverse("core:home"))
        self.assertContains(home, "Ваши роли: Просмотр")
        self.assertEqual(
            self.menu(home), ["Главная", "Учётные карточки", "Справочники"]
        )
        card = self.client.get(
            reverse("personnel:detail", args=[self.person.pk]), {"tab": "military"}
        )
        self.assertEqual(card.status_code, 200)
        self.assertFalse(card.context["can_change"])
        edit = reverse("personnel:section_single", args=[self.person.pk, "military"])
        self.assertEqual(self.client.get(edit).status_code, 403)

    def test_operator(self):
        self.client.force_login(make_user("operator", OPERATOR))
        edit = reverse("personnel:section_single", args=[self.person.pk, "military"])
        self.assertEqual(self.client.post(edit, {"gpz": "1"}).status_code, 302)
        self.assertEqual(
            self.client.get(
                reverse("personnel:edit", args=[self.person.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("personnel:delete", args=[self.person.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("references:add", args=["military-ranks"])
            ).status_code,
            403,
        )

    def test_admin_role(self):
        self.client.force_login(make_user("chief", ADMIN))
        self.assertEqual(
            self.client.get(
                reverse("references:add", args=["military-ranks"])
            ).status_code,
            200,
        )
        self.client.post(reverse("personnel:delete", args=[self.person.pk]))
        self.assertFalse(ref.MilitaryRank.objects.exists())  # справочник не тронут
        self.assertFalse(Person.objects.filter(pk=self.person.pk).exists())
