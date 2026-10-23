from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserModelTests(TestCase):
    def test_names(self):
        user = User(
            username="ivanov",
            last_name="Иванов",
            first_name="Иван",
            patronymic="Петрович",
        )
        self.assertEqual(user.full_name, "Иванов Иван Петрович")
        self.assertEqual(user.short_name, "Иванов И.П.")
        self.assertEqual(str(user), "Иванов Иван Петрович")

    def test_names_without_surname(self):
        user = User(username="operator")
        self.assertEqual(user.full_name, "")
        self.assertEqual(user.short_name, "operator")
        self.assertEqual(str(user), "operator")


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("operator", password="Пароль-для-теста-1")

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(reverse("core:home"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next=/")

    def test_login_and_logout(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "operator", "password": "Пароль-для-теста-1"},
        )
        self.assertRedirects(response, reverse("core:home"))
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_password(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "operator", "password": "не тот"}
        )
        self.assertContains(response, "Неверный логин или пароль")
        self.assertNotIn("_auth_user_id", self.client.session)
