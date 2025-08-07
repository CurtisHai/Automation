from django.test import TestCase
from django.contrib.auth.models import User

class BookingAppTests(TestCase):
    def setUp(self):
        self.reg_user = User.objects.create_user(username='testingreg', password='test1325')
        self.admin_user = User.objects.create_superuser(username='testing', password='test1325', email='admin@example.com')

    def test_login_lockout_after_five_failures(self):
        """After 5 failed attempts the account should be locked."""
        login_url = '/login/'
        for _ in range(5):
            self.client.post(login_url, {'username': 'testingreg', 'password': 'wrong'})
        response = self.client.post(login_url, {'username': 'testingreg', 'password': 'wrong'})
        self.assertContains(response, 'Account locked', status_code=200)

    def test_admin_panel_access_control(self):
        admin_url = '/admin-b4a939d29b7cda4b/'
        # admin user should have access
        self.client.login(username='testing', password='test1325')
        admin_response = self.client.get(admin_url)
        self.assertEqual(admin_response.status_code, 200)
        self.client.logout()
        # regular user should be redirected or forbidden
        self.client.login(username='testingreg', password='test1325')
        reg_response = self.client.get(admin_url)
        self.assertIn(reg_response.status_code, [302, 403])

        