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

    def test_sidebar_footer(self):
        """Внизу панели: имя и логин, выход; администрирование — персоналу."""
        admin_link = f'href="{reverse("admin:index")}"'
        self.client.force_login(
            User.objects.create_user("petrov", last_name="Петров", first_name="Иван")
        )
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Петров И.")
        self.assertContains(response, "petrov")
        self.assertContains(response, reverse("accounts:logout"))
        self.assertNotContains(response, admin_link)
        self.assertNotIn("Админка", self.menu_labels(response))

        self.client.force_login(User.objects.create_user("admin", is_staff=True))
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, admin_link)
        self.assertNotIn("Админка", self.menu_labels(response))
