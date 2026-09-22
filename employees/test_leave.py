from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from organizations.models import Organization, OrganizationMember
from .models import Employee, Leave

User = get_user_model()


class LeaveWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="password123")
        self.worker = User.objects.create_user(username="worker", password="password123")
        self.org = Organization.objects.create(name="Logistics Ltd")

        OrganizationMember.objects.create(organization=self.org, user=self.admin, role="admin")
        OrganizationMember.objects.create(organization=self.org, user=self.worker, role="member")

        self.employee = Employee.objects.create(
            organization=self.org,
            user=self.worker,
            first_name="Bruce",
            last_name="Banner",
        )

    def test_leave_creation_defaults_to_pending(self):
        start = date(2026, 10, 1)
        end = date(2026, 10, 3)
        leave = Leave.objects.create(
            employee=self.employee,
            start_date=start,
            end_date=end,
            leave_type="annual",
            reason="Vacation",
        )
        self.assertEqual(leave.status, "pending")

    def test_leave_approval_workflow(self):
        leave = Leave.objects.create(
            employee=self.employee,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 6),
            leave_type="sick",
        )
        # Simulate approval action
        leave.status = "approved"
        leave.save(update_fields=["status"])
        leave.refresh_from_db()
        self.assertEqual(leave.status, "approved")