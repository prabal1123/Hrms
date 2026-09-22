"""
Central authorization helpers for employees, attendance, leave and payroll.

Views should call these instead of inline `membership.role == "..."` checks.
This is the single place that encodes the Step 3 rules:

- Admins (owner/admin) see and manage everything.
- Supervisors (manager) see the full employee list, but salary/PF/ESI,
  attendance and leave only for their DIRECT reports (not chains). They
  can never approve/reject their own leave, and can never edit salary
  or open payroll.
- Employees (member) see only their own data.
- Identity / bank details (Aadhar, PAN, bank account, UAN, ESIC, address) are
  stricter than salary: only admins and the employee themselves. Supervisors
  never see them, not even for direct reports.
"""

from .models import Employee

ADMIN_ROLES = ("owner", "admin")
SUPERVISOR_ROLE = "manager"
MEMBER_ROLE = "member"


def is_admin(membership):
    return membership.role in ADMIN_ROLES


def is_supervisor(membership):
    return membership.role == SUPERVISOR_ROLE


def is_plain_member(membership):
    return membership.role == MEMBER_ROLE


def get_acting_employee(membership):
    """The Employee record linked to this membership's user, if any."""
    return Employee.objects.filter(
        organization=membership.organization, user=membership.user
    ).first()


def is_direct_report(membership, employee, acting_employee=None):
    """True if `employee` reports directly to the user behind `membership`."""
    if acting_employee is None:
        acting_employee = get_acting_employee(membership)
    if acting_employee is None:
        return False
    return employee.supervisor_id == acting_employee.id


def visible_employees_queryset(membership):
    """
    Employees whose basic info (name, list row) this user may see.
    Admin/Supervisor: everyone in the org. Member: self only.
    """
    organization = membership.organization
    if is_admin(membership) or is_supervisor(membership):
        return Employee.objects.filter(organization=organization)
    return Employee.objects.filter(organization=organization, user_id=membership.user_id)


def scoped_report_queryset(membership):
    """
    Employees whose attendance/leave rows this user may see in BULK views
    (attendance list, leave list). Admin: everyone. Supervisor: direct
    reports only. Member: self only.
    """
    organization = membership.organization
    if is_admin(membership):
        return Employee.objects.filter(organization=organization)
    if is_supervisor(membership):
        acting_employee = get_acting_employee(membership)
        if acting_employee is None:
            return Employee.objects.none()
        return Employee.objects.filter(
            organization=organization, supervisor_id=acting_employee.id
        )
    return Employee.objects.filter(organization=organization, user_id=membership.user_id)


def can_manage_employee(membership, employee):
    """
    Admin: any employee in the org. Supervisor: only their direct reports.
    Used as the base rule for editing/viewing someone else's sensitive data.
    """
    if is_admin(membership):
        return True
    if is_supervisor(membership):
        return is_direct_report(membership, employee)
    return False


def can_view_salary(membership, employee):
    """Salary / PF / ESI / other_deductions visibility."""
    if employee.user_id == membership.user_id:
        return True
    return can_manage_employee(membership, employee)


def can_view_record(membership, employee):
    """Attendance / leave visibility for someone else's record."""
    if employee.user_id == membership.user_id:
        return True
    return can_manage_employee(membership, employee)


def can_manage_attendance(membership, employee):
    """Create/edit/delete attendance rows for `employee`."""
    return can_manage_employee(membership, employee)


def can_manage_leave(membership, employee):
    """Approve/reject leave for `employee`. Never your own, if you're a Supervisor."""
    if is_supervisor(membership) and employee.user_id == membership.user_id:
        return False
    return can_manage_employee(membership, employee)


def can_view_payroll(membership):
    """Admin: full payroll. Supervisor: view-only, scoped to direct reports."""
    return is_admin(membership) or is_supervisor(membership)


def can_edit_payroll(membership):
    """Only admins may confirm/unconfirm payroll rows."""
    return is_admin(membership)


def can_view_sensitive(membership, employee):
    """
    Aadhar / PAN / bank details / UAN / ESIC / address.
    Admin/owner, or the employee themselves. Deliberately NOT extended to
    supervisors (unlike salary).
    """
    if employee.user_id is not None and employee.user_id == membership.user_id:
        return True
    return is_admin(membership)


def can_edit_sensitive(membership):
    """Only admins may change identity / bank details."""
    return is_admin(membership)


def can_manage_employees(membership):
    """Return True if the user has administrative or management privileges over employees."""
    if not membership:
        return False
    return membership.role in ("owner", "admin", "manager")