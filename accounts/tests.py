from django.test import TestCase, Client
from django.urls import reverse

class AccountsViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_login_page_loads(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_signup_page_loads(self):
        response = self.client.get(reverse('accounts:signup'))
        self.assertEqual(response.status_code, 200)

    def test_profile_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302) # Should redirect to login
