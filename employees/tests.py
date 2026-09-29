from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from organizations.models import Organization, OrganizationMember
from employees.models import Employee, Attendance, Leave
from projects.models import Project


User = get_user_model()

class EmployeeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="hrmanager", password="password123")
        self.client.login(username="hrmanager", password="password123")

        self.org = Organization.objects.create(name="People Corp", created_by=self.user)
        OrganizationMember.objects.create(user=self.user, organization=self.org, role="owner")

        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="EMP101",
            first_name="Alice",
            last_name="Smith",
            salary=Decimal("50000.00"),
            pf=Decimal("2000.00"),
            esi=Decimal("500.00"),
            other_deductions=Decimal("500.00")
        )

    def test_salary_calculation_properties(self):
        self.assertEqual(self.employee.total_deductions, Decimal("3000.00"))
        self.assertEqual(self.employee.net_salary, Decimal("47000.00"))

    def test_employee_has_valid_uuid(self):
        self.assertIsNotNone(self.employee.uuid)

    def test_employee_list_view(self):
        response = self.client.get(reverse("employee_list", args=[self.org.id]))
        self.assertEqual(response.status_code, 200)

    def test_employee_detail_view_by_uuid(self):
        response = self.client.get(reverse("employee_detail", args=[self.employee.uuid]))
        self.assertEqual(response.status_code, 200)

    def test_attendance_creation(self):
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=date.today(),
            status="present"
        )
        self.assertEqual(attendance.status, "present")

    def test_leave_creation(self):
        leave = Leave.objects.create(
            employee=self.employee,
            start_date=date.today(),
            end_date=date.today(),
            leave_type="annual",
            status="pending"
        )
        self.assertEqual(leave.status, "pending")


class EmployeeProjectAssignmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="hrmanager2", password="password123")
        self.client.login(username="hrmanager2", password="password123")

        self.org = Organization.objects.create(name="Assign Corp", created_by=self.user)
        OrganizationMember.objects.create(user=self.user, organization=self.org, role="owner")

        self.member_user = User.objects.create_user(username="justmember", password="password123")
        OrganizationMember.objects.create(user=self.member_user, organization=self.org, role="member")

        self.project_a = Project.objects.create(organization=self.org, name="Project A")
        self.project_b = Project.objects.create(organization=self.org, name="Project B")

        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="EMP201",
            first_name="Bob",
            last_name="Jones",
        )

    def test_employee_defaults_to_no_project(self):
        self.assertIsNone(self.employee.project)

    def test_employee_project_can_be_assigned_and_cleared(self):
        self.employee.project = self.project_a
        self.employee.save()
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.project, self.project_a)

        self.employee.project = None
        self.employee.save()
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.project)

    def test_employee_project_set_null_on_project_delete(self):
        self.employee.project = self.project_a
        self.employee.save()
        self.project_a.delete()
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.project)

    def test_assign_projects_view_get(self):
        response = self.client.get(reverse("employee_assign_projects", args=[self.org.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bob")
        self.assertContains(response, "Project A")

    def test_assign_projects_view_post_updates_project(self):
        response = self.client.post(
            reverse("employee_assign_projects", args=[self.org.id]),
            {f"project_{self.employee.id}": str(self.project_b.id)},
        )
        self.assertEqual(response.status_code, 302)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.project, self.project_b)

    def test_assign_projects_view_post_clears_project(self):
        self.employee.project = self.project_a
        self.employee.save()

        response = self.client.post(
            reverse("employee_assign_projects", args=[self.org.id]),
            {f"project_{self.employee.id}": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.project)

    def test_assign_projects_view_blocked_for_member(self):
        self.client.logout()
        self.client.login(username="justmember", password="password123")
        response = self.client.get(reverse("employee_assign_projects", args=[self.org.id]))
        self.assertEqual(response.status_code, 302)


class PayrollProjectFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="payrolladmin", password="password123")
        self.client.login(username="payrolladmin", password="password123")

        self.org = Organization.objects.create(name="Payroll Corp", created_by=self.user)
        OrganizationMember.objects.create(user=self.user, organization=self.org, role="owner")

        self.project_a = Project.objects.create(organization=self.org, name="Project A")
        self.project_b = Project.objects.create(organization=self.org, name="Project B")

        self.emp_a = Employee.objects.create(
            organization=self.org, employee_id="PA01", first_name="Ann", last_name="A",
            project=self.project_a, salary=Decimal("30000.00"),
        )
        self.emp_b = Employee.objects.create(
            organization=self.org, employee_id="PB01", first_name="Bea", last_name="B",
            project=self.project_b, salary=Decimal("30000.00"),
        )
        self.emp_none = Employee.objects.create(
            organization=self.org, employee_id="PN01", first_name="Cal", last_name="C",
            salary=Decimal("30000.00"),
        )

    def test_payroll_unfiltered_shows_all_employees(self):
        response = self.client.get(reverse("payroll", args=[self.org.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ann")
        self.assertContains(response, "Bea")
        self.assertContains(response, "Cal")

    def test_payroll_project_filter_narrows_roster(self):
        response = self.client.get(reverse("payroll", args=[self.org.id]), {"project_id": self.project_a.id})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PA01")
        self.assertNotContains(response, "PB01")
        self.assertNotContains(response, "PN01")