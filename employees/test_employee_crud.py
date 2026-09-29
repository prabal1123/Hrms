from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from organizations.models import Organization, OrganizationMember
from .models import Employee
from .forms import EmployeeForm

User = get_user_model()


class EmployeeCRUDTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin_user", password="password123")
        self.org = Organization.objects.create(name="Acme Corp", created_by=self.user)
        self.membership = OrganizationMember.objects.create(
            organization=self.org,
            user=self.user,
            role="admin",
        )

    def test_auto_generated_employee_id(self):
        # setUp() creates an admin OrganizationMember, which auto-creates its
        # own Employee row (see OrganizationMember.save()). So employee_id
        # numbering here starts after that auto-created record, not at 0001.
        starting_count = Employee.objects.filter(organization=self.org).count()

        emp1 = Employee.objects.create(
            organization=self.org,
            first_name="John",
            last_name="Doe",
        )
        self.assertTrue(emp1.employee_id.startswith(f"acm-{self.org.id}-"))
        self.assertTrue(emp1.employee_id.endswith(f"{starting_count + 1:04d}"))

        emp2 = Employee.objects.create(
            organization=self.org,
            first_name="Jane",
            last_name="Smith",
        )
        self.assertTrue(emp2.employee_id.endswith(f"{starting_count + 2:04d}"))

    def test_employee_form_saves_financial_fields(self):
        form_data = {
            "first_name": "Alice",
            "last_name": "Walker",
            "email": "alice@example.com",
            "phone": "9876543210",
            "salary": "45000.00",
            "pf": "1800.00",
            "esi": "500.00",
            "other_deductions": "200.00",
            "is_active": True,
            "weekly_off": "6",
        }
        form = EmployeeForm(
            data=form_data,
            organization=self.org,
            can_change_access=True,
            acting_user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        emp = form.save()
        
        self.assertEqual(emp.salary, Decimal("45000.00"))
        self.assertEqual(emp.pf, Decimal("1800.00"))
        self.assertEqual(emp.esi, Decimal("500.00"))
        self.assertEqual(emp.total_deductions, Decimal("2500.00"))
        self.assertEqual(emp.net_salary, Decimal("42500.00"))

    def test_non_admin_cannot_edit_financial_fields(self):
        emp = Employee.objects.create(
            organization=self.org,
            first_name="Bob",
            salary=Decimal("50000.00"),
        )
        # can_change_access=False mimics manager/member view
        form = EmployeeForm(
            instance=emp,
            organization=self.org,
            can_change_access=False,
            acting_user=self.user,
        )
        self.assertNotIn("salary", form.fields)
        self.assertNotIn("pf", form.fields)
        self.assertNotIn("access_group", form.fields)