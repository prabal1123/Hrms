from datetime import date
from decimal import Decimal
from django.test import TestCase
from organizations.models import Organization
from .models import Employee, Attendance, Leave, SalaryRecord
from .payroll_service import calculate_employee_payroll

class PayrollTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Apex Systems")
        self.employee = Employee.objects.create(
            organization=self.org,
            first_name="Tony",
            last_name="Stark",
            salary=Decimal("60000.00"),
            pf=Decimal("1800.00"),
            esi=Decimal("1200.00"),
            other_deductions=Decimal("0.00"),
        )

    def test_custom_cross_month_cycle_proration(self):
        # Range: Aug 19 to Sep 19 (32 total days)
        start_date = date(2026, 8, 19)
        end_date = date(2026, 9, 19)

        # Mark 10 days present
        for i in range(10):
            d = date(2026, 8, 20) + __import__('datetime').timedelta(days=i)
            Attendance.objects.create(
                employee=self.employee,
                date=d,
                status="PRESENT",
            )

        # Add 2 approved leave days
        Leave.objects.create(
            employee=self.employee,
            start_date=date(2026, 9, 5),
            end_date=date(2026, 9, 6),
            leave_type="annual",
            status="approved",
        )

        calc = calculate_employee_payroll(
            self.employee,
            year=2026,
            month=9,
            start_date=start_date,
            end_date=end_date,
        )

        self.assertEqual(calc["total_days"], 32)
        self.assertEqual(calc["present_days"], Decimal("10.0"))
        self.assertEqual(calc["paid_leave_days"], Decimal("2.0"))
        self.assertEqual(calc["payable_days"], Decimal("12.0"))

        # Gross: (60,000 / 32) * 12 = 22,500.00
        expected_gross = round((Decimal("60000.00") / Decimal(32)) * Decimal(12), 2)
        self.assertEqual(calc["gross_earned"], expected_gross)

    def test_salary_record_persistence(self):
        record = SalaryRecord.objects.create(
            organization=self.org,
            employee=self.employee,
            year=2026,
            month=9,
            payroll_start=date(2026, 8, 19),
            payroll_end=date(2026, 9, 19),
            total_days=32,
            present_days=Decimal("15.0"),
            paid_leave_days=Decimal("0.0"),
            base_salary=Decimal("60000.00"),
            pf=Decimal("1800.00"),
            esi=Decimal("1200.00"),
            other_deductions=Decimal("0.00"),
            gross_earned=Decimal("28125.00"),
            net_salary=Decimal("25125.00"),
            confirmed=True,
        )
        self.assertEqual(record.payable_days, Decimal("15.0"))
        self.assertEqual(record.total_deductions, Decimal("3000.00"))
        self.assertIsNotNone(record.generated_at)
        self.assertIsNotNone(record.updated_at)