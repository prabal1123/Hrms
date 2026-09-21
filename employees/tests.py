from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from organizations.models import Organization, OrganizationMember
from employees.models import Employee, Attendance, Leave

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