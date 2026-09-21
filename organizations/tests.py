from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from organizations.models import Organization, OrganizationMember

User = get_user_model()

class OrganizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="orguser", password="password123")
        self.client.login(username="orguser", password="password123")
        self.org = Organization.objects.create(
            name="Acme Corp",
            created_by=self.user
        )
        OrganizationMember.objects.create(
            user=self.user,
            organization=self.org,
            role="owner"
        )

    def test_organization_create_view(self):
        response = self.client.post(
            reverse("organization_create"),
            {"name": "New Corp"}
        )
        self.assertIn(response.status_code, [200, 302])

    def test_organization_detail_view(self):
        response = self.client.get(reverse("organization_detail", args=[self.org.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "organizations/detail.html")
