from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from organizations.models import Organization, OrganizationMember
from employees.models import Employee
from projects.models import Project, Action

User = get_user_model()

class ProjectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="projectlead", password="password123")
        self.client.login(username="projectlead", password="password123")

        self.org = Organization.objects.create(name="Dev Org", created_by=self.user)
        OrganizationMember.objects.create(user=self.user, organization=self.org, role="owner")

        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="EMP001",
            first_name="Dev",
            last_name="Lead"
        )
        self.project = Project.objects.create(
            organization=self.org,
            name="Platform Alpha",
            description="Core system"
        )
        self.project.employees.add(self.employee)

    def test_project_dashboard_view(self):
        response = self.client.get(reverse("project_dashboard", args=[self.project.id]))
        self.assertEqual(response.status_code, 200)

    def test_project_team_view(self):
        response = self.client.get(reverse("project_team", args=[self.project.id]))
        self.assertEqual(response.status_code, 200)

    def test_action_creation(self):
        action = Action.objects.create(
            project=self.project,
            employee=self.employee,
            title="Setup DB",
            status="in_progress"
        )
        self.assertEqual(action.project, self.project)
        self.assertEqual(action.status, "in_progress")
