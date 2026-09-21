from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class AccountTests(TestCase):
    def setUp(self):
        self.username = "testuser"
        self.password = "Secur3P@ssw0rd!"
        self.user = User.objects.create_user(
            username=self.username, password=self.password
        )

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_user_authentication(self):
        logged_in = self.client.login(username=self.username, password=self.password)
        self.assertTrue(logged_in)

    def test_register_page_renders(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
