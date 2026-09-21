# import uuid
# import re
# from decimal import Decimal
# from django.db import models, transaction
# from django.contrib.auth import get_user_model
# from organizations.models import Organization
# from .fields import EncryptedCharField, EncryptedDecimalField
# from django.utils import timezone

# User = get_user_model()


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
#         max_digits=12, decimal_places=2, default=Decimal("0")
#     )
#     # ----------------------------------------

#     is_active = models.BooleanField(default=True)
#     payroll_confirmed = models.BooleanField(default=False)

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


# from datetime import time, datetime, timedelta

# ATTENDANCE_STATUS_CHOICES = (
#     ('PRESENT', 'Present'),
#     ('LATE', 'Late'),
#     ('HALF_DAY', 'Half Day'),
#     ('ABSENT', 'Absent'),
#     ('LEAVE', 'On Leave'),
# )


# class Attendance(models.Model):
#     uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True)
#     employee = models.ForeignKey(
#         Employee, on_delete=models.CASCADE, related_name="attendances"
#     )
#     date = models.DateField(default=timezone.localdate)
#     check_in = models.DateTimeField(null=True, blank=True)
#     check_in_latitude = models.FloatField(null=True, blank=True)
#     check_in_longitude = models.FloatField(null=True, blank=True)
#     check_out = models.DateTimeField(null=True, blank=True)
#     check_out_latitude = models.FloatField(null=True, blank=True)
#     check_out_longitude = models.FloatField(null=True, blank=True)
#     status = models.CharField(
#         max_length=10, choices=ATTENDANCE_STATUS_CHOICES, default='ABSENT'
#     )
#     notes = models.TextField(null=True, blank=True)
#     marked_by = models.ForeignKey(
#         User, on_delete=models.SET_NULL, null=True, blank=True,
#         related_name="attendance_marked", help_text="Admin who manually edited this record, if any"
#     )
#     created_at = models.DateTimeField(default=timezone.now)
#     updated_at = models.DateTimeField(default=timezone.now)

#     class Meta:
#         unique_together = ('employee', 'date')
#         ordering = ['-date']
#         verbose_name = "Attendance"
#         verbose_name_plural = "Attendance Records"

#     def __str__(self):
#         return f"{self.employee} - {self.date} - {self.get_status_display()}"


# class Leave(models.Model):
#     employee = models.ForeignKey(
#         Employee, on_delete=models.CASCADE, related_name="leaves"
#     )
#     start_date = models.DateField()
#     end_date = models.DateField()
#     leave_type = models.CharField(
#         max_length=30,
#         choices=[
#             ("annual", "Annual"),
#             ("sick", "Sick"),
#             ("unpaid", "Unpaid"),
#             ("other", "Other"),
#         ],
#     )
#     status = models.CharField(
#         max_length=20,
#         choices=[
#             ("pending", "Pending"),
#             ("approved", "Approved"),
#             ("rejected", "Rejected"),
#         ],
#         default="pending",
#     )
#     reason = models.TextField(blank=True)

#     class Meta:
#         ordering = ["-start_date"]

import uuid
import re
from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth import get_user_model
from organizations.models import Organization
from .fields import EncryptedCharField, EncryptedDecimalField
from django.utils import timezone

User = get_user_model()


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
    # Links this employee record to the logged-in user account.
    # Nullable because pre-existing Employee rows won't have a user set
    # until they're backfilled (see migration notes).
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
    # ----------------------------------------

    is_active = models.BooleanField(default=True)
    payroll_confirmed = models.BooleanField(default=False)

    # The person this employee reports to. Set by admins only (enforced in
    # EmployeeForm). SET_NULL so deleting a supervisor never deletes reports.
    supervisor = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports",
    )

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
                # Extract clean alphabetic prefix from org name (fallback to 'org' if empty)
                org_prefix = re.sub(r'[^a-zA-Z]', '', self.organization.name)[:3].lower()
                if not org_prefix:
                    org_prefix = "org"

                # select_for_update() locks the matching row(s) for the
                # duration of this transaction, so a second, concurrent
                # save() for the same organization has to wait until this
                # one commits (and releases the lock) before it can read
                # the "last" employee_id. This prevents two concurrent
                # requests from both computing the same next_num.
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

                # Format: aqu-1-0001
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


from datetime import time, datetime, timedelta

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