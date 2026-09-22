from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from organizations.models import Organization
from .models import Employee, Attendance

User = get_user_model()


class AttendanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test_emp", password="password123")
        self.org = Organization.objects.create(name="TechCorp")
        self.employee = Employee.objects.create(
            organization=self.org,
            user=self.user,
            first_name="Mark",
            last_name="Ruffalo",
        )

    def test_create_daily_attendance(self):
        today = timezone.localdate()
        att = Attendance.objects.create(
            employee=self.employee,
            date=today,
            status="PRESENT",
            check_in=timezone.now(),
            check_in_latitude=17.3850,
            check_in_longitude=78.4867,
        )
        self.assertEqual(att.status, "PRESENT")
        self.assertIsNotNone(att.check_in)

    def test_attendance_unique_per_day_constraint(self):
        today = timezone.localdate()
        Attendance.objects.create(
            employee=self.employee,
            date=today,
            status="PRESENT",
        )
        with self.assertRaises(Exception):
            Attendance.objects.create(
                employee=self.employee,
                date=today,
                status="HALF_DAY",
            )