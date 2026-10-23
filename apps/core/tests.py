from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class MenuTests(TestCase):
    def menu_labels(self, response):
        return [
            item["label"]
            for section in response.context["menu"]
            for item in section["items"]
        ]

    def test_home_and_active_item(self):
        self.client.force_login(User.objects.create_user("operator"))
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1 class="page-title">Главная</h1>', html=True)
        active = [
            item["label"]
            for s in response.context["menu"]
            for item in s["items"]
            if item["active"]
        ]
        self.assertEqual(active, ["Главная"])

    def test_admin_item_only_for_staff(self):
        self.client.force_login(User.objects.create_user("operator"))
        self.assertNotIn(
            "Админка", self.menu_labels(self.client.get(reverse("core:home")))
        )

        self.client.force_login(User.objects.create_user("admin", is_staff=True))
        self.assertIn(
            "Админка", self.menu_labels(self.client.get(reverse("core:home")))
        )
