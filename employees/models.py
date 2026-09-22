
import uuid
import re
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.functions import Lower
from django.contrib.auth import get_user_model
from organizations.models import Organization
from .fields import EncryptedCharField, EncryptedDecimalField
from .validators import validate_aadhar, validate_pan
from django.utils import timezone
from datetime import time, datetime, timedelta

User = get_user_model()

WEEKDAY_CHOICES = (
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
)

# class Employee(models.Model):
#     uuid = models.UUIDField(
#         default=uuid.uuid4,
#         unique=True,
#         editable=False,
#         db_index=True,
#     )
#     organization = models.ForeignKey(
#         Organization, on_delete=models.CASCADE, related_name="employees"
#     )
#     # Links this employee record to the logged-in user account.
#     # Nullable because pre-existing Employee rows won't have a user set
#     # until they're backfilled (see migration notes).
#     user = models.ForeignKey(
#         User,
#         on_delete=models.CASCADE,
#         related_name="employee_profiles",
#         null=True,
#         blank=True,
#     )
#     employee_id = models.CharField(max_length=50, editable=False)
#     first_name = models.CharField(max_length=80)
#     last_name = models.CharField(max_length=80, blank=True)

#     # --- Encrypted PII & Financial Fields ---
#     email = EncryptedCharField(max_length=254, blank=True)
#     phone = EncryptedCharField(max_length=50, blank=True)
#     date_joined = models.DateField(null=True, blank=True)

#     salary = EncryptedDecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
#     pf = EncryptedDecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
#     esi = EncryptedDecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
#     other_deductions = EncryptedDecimalField(
#         max_digits=12, decimal_places=2, default=Decimal("0"), blank=True
#     )
#     # ----------------------------------------

#     is_active = models.BooleanField(default=True)
#     payroll_confirmed = models.BooleanField(default=False)

#     # The person this employee reports to. Set by admins only (enforced in
#     # EmployeeForm). SET_NULL so deleting a supervisor never deletes reports.
#     supervisor = models.ForeignKey(
#         "self",
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name="direct_reports",
#     )

#     # --- Job / bank details (not sensitive on their own) ---
#     designation = models.CharField(max_length=100, blank=True)
#     bank_name = models.CharField(max_length=100, blank=True)
#     ifsc_no = models.CharField(max_length=20, blank=True)

#     # --- Encrypted identity, statutory and contact details ---
#     # NOTE on max_length: for encrypted fields the DB column stores the Fernet
#     # token, which is ~1.4x the plaintext length plus ~100 characters. The
#     # lengths below are sized for the token so the columns also work on
#     # databases that enforce varchar length (e.g. PostgreSQL). Tighter limits
#     # on the plaintext (12 digits, 10 chars, ...) are enforced by validators
#     # and by the bulk importer.
#     aadhar_no = EncryptedCharField(
#         max_length=512, blank=True, validators=[validate_aadhar]
#     )
#     pan_no = EncryptedCharField(
#         max_length=512, blank=True, validators=[validate_pan]
#     )
#     bank_account_no = EncryptedCharField(max_length=512, blank=True)
#     uan_no = EncryptedCharField(max_length=512, blank=True)
#     esic_no = EncryptedCharField(max_length=512, blank=True)
#     address = EncryptedCharField(max_length=4000, blank=True)

#     class Meta:
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["organization", "employee_id"],
#                 name="unique_employee_id_per_org",
#             ),
#             models.UniqueConstraint(
#                 fields=["organization", "user"],
#                 name="unique_employee_user_per_org",
#             ),
#         ]
#         ordering = ["first_name", "last_name"]

#     def save(self, *args, **kwargs):
#         if not self.employee_id:
#             with transaction.atomic():
#                 # Extract clean alphabetic prefix from org name (fallback to 'org' if empty)
#                 org_prefix = re.sub(r'[^a-zA-Z]', '', self.organization.name)[:3].lower()
#                 if not org_prefix:
#                     org_prefix = "org"

#                 # select_for_update() locks the matching row(s) for the
#                 # duration of this transaction, so a second, concurrent
#                 # save() for the same organization has to wait until this
#                 # one commits (and releases the lock) before it can read
#                 # the "last" employee_id. This prevents two concurrent
#                 # requests from both computing the same next_num.
#                 last_emp = (
#                     Employee.objects.select_for_update()
#                     .filter(organization=self.organization)
#                     .order_by("-id")
#                     .first()
#                 )
#                 if last_emp and last_emp.employee_id:
#                     match = re.search(r"(\d+)$", last_emp.employee_id)
#                     next_num = int(match.group(1)) + 1 if match else 1
#                 else:
#                     next_num = 1

#                 # Format: aqu-1-0001
#                 self.employee_id = f"{org_prefix}-{self.organization.id}-{next_num:04d}"
#                 super().save(*args, **kwargs)
#         else:
#             super().save(*args, **kwargs)

#     @property
#     def total_deductions(self):
#         return self.pf + self.esi + self.other_deductions

#     @property
#     def net_salary(self):
#         return self.salary - self.total_deductions

#     def __str__(self):
#         return f"{self.employee_id} - {self.first_name} {self.last_name}".strip()

class Employee(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="employees"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="employee_profiles",
        null=True,
        blank=True,
    )
    employee_id = models.CharField(max_length=50, editable=False)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)

    # --- Working Schedule & Assigned Off ---
    weekly_off = models.PositiveSmallIntegerField(
        choices=WEEKDAY_CHOICES,
        default=6,  # Default Sunday
        help_text="Designated recurring weekly day off (0=Mon, 6=Sun)",
    )

    # --- Encrypted PII & Financial Fields ---
    email = EncryptedCharField(max_length=254, blank=True)
    phone = EncryptedCharField(max_length=50, blank=True)
    date_joined = models.DateField(null=True, blank=True)

    salary = EncryptedDecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    pf = EncryptedDecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    esi = EncryptedDecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    other_deductions = EncryptedDecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0")
    )

    is_active = models.BooleanField(default=True)
    payroll_confirmed = models.BooleanField(default=False)

    supervisor = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports",
    )

    designation = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    ifsc_no = models.CharField(max_length=20, blank=True)

    aadhar_no = EncryptedCharField(
        max_length=512, blank=True, validators=[validate_aadhar]
    )
    pan_no = EncryptedCharField(
        max_length=512, blank=True, validators=[validate_pan]
    )
    bank_account_no = EncryptedCharField(max_length=512, blank=True)
    uan_no = EncryptedCharField(max_length=512, blank=True)
    esic_no = EncryptedCharField(max_length=512, blank=True)
    address = EncryptedCharField(max_length=4000, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "employee_id"],
                name="unique_employee_id_per_org",
            ),
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_employee_user_per_org",
            ),
        ]
        ordering = ["first_name", "last_name"]

    def save(self, *args, **kwargs):
        if not self.employee_id:
            with transaction.atomic():
                org_prefix = re.sub(r"[^a-zA-Z]", "", self.organization.name)[:3].lower()
                if not org_prefix:
                    org_prefix = "org"

                last_emp = (
                    Employee.objects.select_for_update()
                    .filter(organization=self.organization)
                    .order_by("-id")
                    .first()
                )
                if last_emp and last_emp.employee_id:
                    match = re.search(r"(\d+)$", last_emp.employee_id)
                    next_num = int(match.group(1)) + 1 if match else 1
                else:
                    next_num = 1

                self.employee_id = f"{org_prefix}-{self.organization.id}-{next_num:04d}"
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    @property
    def total_deductions(self):
        return self.pf + self.esi + self.other_deductions

    @property
    def net_salary(self):
        return self.salary - self.total_deductions

    def __str__(self):
        return f"{self.employee_id} - {self.first_name} {self.last_name}".strip()
    

ATTENDANCE_STATUS_CHOICES = (
    ('PRESENT', 'Present'),
    ('LATE', 'Late'),
    ('HALF_DAY', 'Half Day'),
    ('ABSENT', 'Absent'),
    ('LEAVE', 'On Leave'),
)


class Attendance(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True)
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="attendances"
    )
    date = models.DateField(default=timezone.localdate)
    check_in = models.DateTimeField(null=True, blank=True)
    check_in_latitude = models.FloatField(null=True, blank=True)
    check_in_longitude = models.FloatField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    check_out_latitude = models.FloatField(null=True, blank=True)
    check_out_longitude = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=ATTENDANCE_STATUS_CHOICES, default='ABSENT'
    )
    notes = models.TextField(null=True, blank=True)
    marked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="attendance_marked", help_text="Admin who manually edited this record, if any"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date']
        verbose_name = "Attendance"
        verbose_name_plural = "Attendance Records"

    def __str__(self):
        return f"{self.employee} - {self.date} - {self.get_status_display()}"


class Leave(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="leaves"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    leave_type = models.CharField(
        max_length=30,
        choices=[
            ("annual", "Annual"),
            ("sick", "Sick"),
            ("unpaid", "Unpaid"),
            ("other", "Other"),
        ],
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]


# ---------------------------------------------------------------------------
# Onboarding checklist
#
# Each organization has its own list of checklist items (e.g. "AVSEC Training",
# "Police Verification"). An employee's status against an item is stored as an
# EmployeeChecklistEntry; NO entry means "pending", so rows are only created
# once someone actually marks something.
# ---------------------------------------------------------------------------

CHECKLIST_PENDING = "pending"
CHECKLIST_DONE = "done"
CHECKLIST_NOT_APPLICABLE = "not_applicable"

CHECKLIST_STATUS_CHOICES = (
    (CHECKLIST_PENDING, "Pending"),
    (CHECKLIST_DONE, "Done"),
    (CHECKLIST_NOT_APPLICABLE, "Not applicable"),
)


class ChecklistItem(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="checklist_items"
    )
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    # Deactivate instead of deleting, so history on past employees is kept.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "organization",
                name="unique_checklist_item_name_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.organization})"


class EmployeeChecklistEntry(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="checklist_entries"
    )
    item = models.ForeignKey(
        ChecklistItem, on_delete=models.CASCADE, related_name="entries"
    )
    status = models.CharField(
        max_length=20, choices=CHECKLIST_STATUS_CHOICES, default=CHECKLIST_PENDING
    )
    # Only meaningful when status is "done".
    completed_on = models.DateField(null=True, blank=True)
    marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checklist_entries_marked",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Employee checklist entries"
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "item"],
                name="unique_checklist_entry_per_employee_item",
            ),
            models.CheckConstraint(
                condition=models.Q(status="done") | models.Q(completed_on__isnull=True),
                name="checklist_completed_on_only_when_done",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.employee_id
            and self.item_id
            and self.employee.organization_id != self.item.organization_id
        ):
            raise ValidationError(
                "The checklist item and the employee belong to different organizations."
            )

    def __str__(self):
        return f"{self.employee} - {self.item.name}: {self.get_status_display()}"

class SalaryRecord(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="salary_records"
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="salary_records"
    )
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()  # 1-12

    # Snapshot of the rates used (Employee salary/deductions can change later).
    base_salary = models.DecimalField(max_digits=12, decimal_places=2)
    pf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    esi = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    payroll_start = models.DateField()   # e.g. 2026-08-26
    payroll_end = models.DateField()     # e.g. 2026-09-25
    total_days = models.PositiveSmallIntegerField()
    present_days = models.DecimalField(max_digits=5, decimal_places=1)  # supports half-days
    paid_leave_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    # NOTE ON STORED VS. DERIVED AMOUNTS:
    # gross_earned and net_salary are stored concrete fields rather than dynamic
    # properties intentionally. While mechanically derivable, they represent the
    # frozen statutory and monetary commitments printed on issued payslips.
    # Storing them ensures historical payouts never silently recalculate if deduction
    # formulas or rounding rules change in subsequent updates.
    gross_earned = models.DecimalField(max_digits=12, decimal_places=2)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2)

    confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="confirmed_salaries"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "employee", "year", "month"],
                name="unique_salary_record_per_month",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "year", "month"]),
        ]
        ordering = ["-year", "-month"]

    @property
    def total_deductions(self):
        """Sum of snapshot deduction components for UI and slip rendering."""
        return self.pf + self.esi + self.other_deductions

    @property
    def payable_days(self):
        """Total days eligible for payout (present + approved paid leave)."""
        return self.present_days + self.paid_leave_days

    def __str__(self):
        return f"{self.employee.employee_id} - {self.month:02d}/{self.year}"
    