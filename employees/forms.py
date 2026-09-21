from django import forms
from django.db import transaction
from django.db.models import Q

from organizations.models import OrganizationMember
from .models import Employee, Attendance, Leave

# What the admin sees  ->  what is stored in OrganizationMember.role
ACCESS_GROUP_CHOICES = [
    ("admin", "Admin"),
    ("supervisor", "Supervisor"),
    ("employee", "Employee"),
]
ROLE_TO_GROUP = {
    "owner": "admin",
    "admin": "admin",
    "manager": "supervisor",
    "member": "employee",
}
GROUP_TO_ROLE = {
    "admin": "admin",
    "supervisor": "manager",
    "employee": "member",
}
NO_LOGIN_CHOICES = [("", "No login account linked")]

# Login roles that are allowed to be someone's supervisor.
SUPERVISOR_ROLES = ("owner", "admin", "manager")

# Fields that only an Admin/Owner may see or edit. Supervisors and members
# never get these on the form, even with a hand-crafted POST.
ADMIN_ONLY_FIELDS = ("supervisor", "access_group", "salary", "pf", "esi", "other_deductions")


class EmployeeSelfForm(forms.ModelForm):
    """Limited form for an employee editing their OWN profile.

    Only these fields exist on the form, so salary, PF, ESI, deductions,
    active status, supervisor and access group can never be changed
    through it, even with a hand-crafted POST.
    """

    class Meta:
        model = Employee
        fields = ["first_name", "last_name", "email", "phone"]


class EmployeeForm(forms.ModelForm):
    access_group = forms.ChoiceField(
        choices=ACCESS_GROUP_CHOICES,
        required=False,
        label="Access group",
    )

    class Meta:
        model = Employee
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "date_joined",
            "salary",
            "pf",
            "esi",
            "other_deductions",
            "is_active",
            "supervisor",
        ]
        widgets = {
            "date_joined": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(
        self,
        *args,
        organization=None,
        can_change_access=False,
        acting_user=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._membership = None

        # Supervisor, access group, and salary/PF/ESI/deductions are
        # admin-only. For everyone else these fields are removed entirely,
        # so a hand-crafted POST containing them is simply ignored.
        if not can_change_access:
            for name in ADMIN_ONLY_FIELDS:
                self.fields.pop(name, None)
            return

        org_id = organization.id if organization else self.instance.organization_id
        self._setup_supervisor_field(org_id)

        # Access group only exists when editing an existing employee.
        if self.instance.pk is None:
            self.fields.pop("access_group")
            return

        field = self.fields["access_group"]

        if self.instance.user_id:
            self._membership = OrganizationMember.objects.filter(
                organization_id=self.instance.organization_id,
                user_id=self.instance.user_id,
            ).first()
        membership = self._membership

        # Locked cases use disabled=True: Django ignores any posted value for a
        # disabled field and uses the initial value, so it can't be tampered with.
        if membership is None:
            field.choices = NO_LOGIN_CHOICES
            field.initial = ""
            field.disabled = True
            field.help_text = (
                "This employee has no login account yet, so there is no "
                "access group to set."
            )
            return

        field.initial = ROLE_TO_GROUP.get(membership.role, "employee")

        if membership.role == "owner":
            field.disabled = True
            field.help_text = "The organization owner is always an Admin."
        elif acting_user is None or membership.user_id == acting_user.id:
            field.disabled = True
            field.help_text = "You can't change your own access group."
        else:
            field.help_text = "Only admins can change this."

    def _setup_supervisor_field(self, org_id):
        field = self.fields["supervisor"]
        field.empty_label = "— No supervisor —"
        field.help_text = (
            "Only employees whose login is Supervisor or Admin can be selected."
        )

        if org_id is None:
            field.queryset = Employee.objects.none()
            return

        eligible = Q(
            is_active=True,
            user__organization_memberships__organization_id=org_id,
            user__organization_memberships__role__in=SUPERVISOR_ROLES,
        )
        # Keep the current supervisor selectable even if they no longer
        # qualify (e.g. deactivated), otherwise saving would silently clear it.
        if self.instance.pk and self.instance.supervisor_id:
            eligible |= Q(pk=self.instance.supervisor_id)

        queryset = Employee.objects.filter(organization_id=org_id).filter(eligible)
        if self.instance.pk:
            # Nobody can be their own supervisor.
            queryset = queryset.exclude(pk=self.instance.pk)
        field.queryset = queryset.distinct()

    def clean(self):
        cleaned = super().clean()
        field = self.fields.get("access_group")
        membership = self._membership

        if field is not None and not field.disabled and membership is not None:
            new_group = cleaned.get("access_group")
            if (
                new_group
                and GROUP_TO_ROLE[new_group] == "member"
                and membership.role != "member"
            ):
                count = self.instance.direct_reports.count()
                if count:
                    self.add_error(
                        "access_group",
                        f"This person still supervises {count} employee(s). "
                        "Reassign them to another supervisor before changing "
                        "this person to Employee.",
                    )
        return cleaned

    def save(self, commit=True):
        employee = super().save(commit=False)
        if not commit:
            return employee
        with transaction.atomic():
            employee.save()
            self.save_m2m()
            self._save_access_group()
        return employee

    def _save_access_group(self):
        field = self.fields.get("access_group")
        membership = self._membership
        if field is None or field.disabled or membership is None:
            return
        if membership.role == "owner":
            return  # never change the owner

        new_group = self.cleaned_data.get("access_group")
        if not new_group:
            return
        new_role = GROUP_TO_ROLE[new_group]
        if membership.role != new_role:
            membership.role = new_role
            membership.save(update_fields=["role"])


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ["date", "status", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class LeaveForm(forms.ModelForm):
    class Meta:
        model = Leave
        fields = ["start_date", "end_date", "leave_type", "status", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }