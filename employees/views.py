from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.services import GrantLoginError, grant_login
from organizations.models import OrganizationMember
from .bulk_import import batch, columns as import_columns, files as import_files, parse_upload
from .bulk_import.commit import commit_rows
from .forms import AttendanceForm, EmployeeForm, EmployeeImportUploadForm, EmployeeSelfForm, LeaveForm
from .models import Attendance, Employee, Leave
from . import permissions
from datetime import date
from .models import SalaryRecord
from .payroll_service import calculate_employee_payroll, get_month_range


def get_membership(user, org_id):
    return get_object_or_404(OrganizationMember, organization_id=org_id, user=user)


@login_required
def employee_dashboard(request, org_id):
    membership = get_membership(request.user, org_id)
    employee = get_object_or_404(
        Employee.objects.select_related("organization").prefetch_related("projects", "actions", "attendances", "leaves"),
        user=request.user,
        organization=membership.organization
    )
    today = timezone.localdate()

    attendance = employee.attendances.all().order_by("-date")[:30]
    today_attendance = employee.attendances.filter(date=today).first()

    context = {
        "employee": employee,
        "organization": membership.organization,
        "current_org": membership.organization,
        "org_id": org_id,
        "projects": employee.projects.all(),
        "my_actions": employee.actions.all(),
        "attendance": attendance,
        "today_attendance": today_attendance,
        "leaves": employee.leaves.all()[:30],
    }
    return render(request, "employees/employee_dashboard.html", context)


@login_required
def employee_list(request, org_id):
    membership = get_membership(request.user, org_id)
    if membership.role == "member":
        messages.error(request, "Access restricted to management.")
        return redirect("employee_dashboard", org_id=org_id)

    employees = permissions.visible_employees_queryset(membership).prefetch_related("projects")
    return render(request, "employees/list.html", {
        "organization": membership.organization, 
        "employees": employees, 
        "org_id": org_id, 
        "current_org": membership.organization,
        "can_view_salary_column": permissions.is_admin(membership),
        "can_import": permissions.is_admin(membership),
    })


@login_required
def employee_create(request, org_id):
    membership = get_membership(request.user, org_id)
    if membership.role == "member":
        messages.error(request, "Access restricted to management.")
        return redirect("employee_dashboard", org_id=org_id)

    # Only owners and admins may assign a supervisor, set the access group,
    # or set salary/PF/ESI/deductions.
    form_kwargs = {
        "organization": membership.organization,
        "can_change_access": membership.role in ("owner", "admin"),
        "acting_user": request.user,
    }

    if request.method == "POST":
        form = EmployeeForm(request.POST, **form_kwargs)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.organization = membership.organization
            employee.save()
            messages.success(request, "Employee added successfully.")
            return redirect("employee_detail", uuid=employee.uuid)
    else:
        form = EmployeeForm(**form_kwargs)
    return render(request, "employees/form.html", {
    "form": form, 
    "organization": membership.organization, 
    "org_id": org_id, 
    "current_org": membership.organization,
    "can_edit_sensitive": permissions.can_edit_sensitive(membership),
    })


@login_required
def employee_detail(request, uuid):
    employee = get_object_or_404(
        Employee.objects.select_related("organization").prefetch_related("projects"),
        uuid=uuid,
    )

    membership = get_membership(request.user, employee.organization_id)

    # Members may only view their own employee profile.
    if membership.role == "member" and employee.user_id != request.user.id:
        messages.error(request, "Access restricted.")
        return redirect("employee_dashboard", org_id=employee.organization_id)

    can_view_salary = permissions.can_view_salary(membership, employee)
    can_view_records = permissions.can_view_record(membership, employee)
    can_manage_leave_here = permissions.can_manage_leave(membership, employee)
    can_manage_attendance_here = permissions.can_manage_attendance(membership, employee)
    can_grant_login = permissions.is_admin(membership) and employee.user_id is None
    can_view_sensitive = permissions.can_view_sensitive(membership, employee)

    attendance = employee.attendances.all()[:30] if can_view_records else Attendance.objects.none()
    leaves = employee.leaves.all()[:30] if can_view_records else Leave.objects.none()

    return render(request, "employees/detail.html", {
        "employee": employee, 
        "organization": membership.organization,
        "membership": membership,
        "attendance": attendance, 
        "leaves": leaves,
        "current_org": membership.organization,
        "can_view_salary": can_view_salary,
        "can_view_records": can_view_records,
        "can_manage_leave": can_manage_leave_here,
        "can_manage_attendance": can_manage_attendance_here,
        "can_grant_login": can_grant_login,
        "can_view_sensitive": can_view_sensitive,
    })


@login_required
def employee_grant_login(request, uuid):
    employee = get_object_or_404(Employee.objects.select_related("organization"), uuid=uuid)
    membership = get_membership(request.user, employee.organization_id)

    # Admin/owner only, enforced server-side even if the button is hidden.
    if not permissions.is_admin(membership):
        messages.error(request, "Only admins can grant login access.")
        return redirect("employee_dashboard", org_id=employee.organization_id)

    if request.method == "POST":
        try:
            user = grant_login(employee)
            messages.success(
                request,
                f"Login created for {user.email}. They can set their password "
                "the first time they log in.",
            )
        except GrantLoginError as exc:
            messages.error(request, str(exc))

    return redirect("employee_detail", uuid=employee.uuid)


@login_required
def attendance_list(request, org_id):
    membership = get_membership(request.user, org_id)

    employee = Employee.objects.filter(organization=membership.organization, user=request.user).first()
    today = timezone.localdate()
    today_attendance = Attendance.objects.filter(employee=employee, date=today).first() if employee else None
    attendance_records = Attendance.objects.filter(employee=employee).order_by("-date")[:30] if employee else []

    context = {
        "organization": membership.organization,
        "org_id": org_id,
        "current_org": membership.organization,
        "employee": employee,
        "today_attendance": today_attendance,
        "attendance_records": attendance_records,
    }

    if membership.role != "member":
        context["records"] = Attendance.objects.filter(
            employee__in=permissions.scoped_report_queryset(membership)
        ).select_related("employee").order_by("-date", "employee__first_name")[:200]

    return render(request, "employees/attendance.html", context)


@login_required
def org_attendance_view(request, org_id):
    membership = get_membership(request.user, org_id)
    employee = Employee.objects.filter(
        organization=membership.organization,
        user=request.user
    ).first()

    if employee is None:
        messages.error(request, "No employee profile is linked to your account.")
        return redirect("employee_dashboard", org_id=org_id)

    now = timezone.localtime()
    attendance_date = now.date()

    if request.method == "POST":
        attendance, _ = Attendance.objects.get_or_create(
            employee=employee,
            date=attendance_date,
        )

        if attendance.check_in is None:
            attendance.check_in = now
            attendance.status = "PRESENT"
            attendance.save()
            messages.success(request, f"Checked in successfully at {now.strftime('%I:%M %p')}.")
        elif attendance.check_out is None:
            attendance.check_out = now
            attendance.save()
            messages.success(request, f"Checked out successfully at {now.strftime('%I:%M %p')}.")
        else:
            messages.info(request, "Attendance already completed for today.")

        return redirect("org_attendance", org_id=org_id)

    all_attendance = Attendance.objects.filter(employee=employee).order_by("-date")
    today_attendance = all_attendance.filter(date=attendance_date).first()
    attendance_records = all_attendance[:30]

    return render(
        request,
        "employees/attendance.html",
        {
            "employee": employee,
            "today_attendance": today_attendance,
            "attendance_records": attendance_records,
            "organization": membership.organization,
            "current_org": membership.organization,
            "org_id": org_id,
        }
    )


# @login_required
# def leave_list(request, org_id):
#     membership = get_membership(request.user, org_id)
    
#     # Strict Privacy Scoping: Members see only their leaves; Admins see all
#     # company leaves; Supervisors see only their direct reports' leaves.
#     if membership.role == "member":
#         employee = Employee.objects.filter(organization=membership.organization, user=request.user).first()
#         records = Leave.objects.filter(employee=employee).order_by("-start_date") if employee else Leave.objects.none()
#     else:
#         records = Leave.objects.filter(
#             employee__in=permissions.scoped_report_queryset(membership)
#         ).select_related("employee").order_by("-start_date", "employee__first_name")[:200]

#     employee = None

#     if membership.role == "member":
#         employee = Employee.objects.filter(
#             organization=membership.organization,
#             user=request.user,
#         ).first()

#     return render(request, "employees/leave.html", {
#         "organization": membership.organization,
#         "records": records,
#         "org_id": org_id,
#         "current_org": membership.organization,
#         "is_member": membership.role == "member",
#         "employee": employee,
#     })

@login_required
def leave_list(request, org_id):
    membership = get_membership(request.user, org_id)
    is_member = membership.role == "member"

    # The logged-in user's own linked employee profile (regardless of role)
    current_employee = Employee.objects.filter(
        organization=membership.organization, 
        user=request.user
    ).first()

    # Strict Privacy Scoping:
    # - Members see only their own leave records
    # - Admins/Supervisors see their scoped organization/reportee leaves
    if is_member:
        records = (
            Leave.objects.filter(employee=current_employee).order_by("-start_date")
            if current_employee else Leave.objects.none()
        )
    else:
        records = (
            Leave.objects.filter(
                employee__in=permissions.scoped_report_queryset(membership)
            )
            .select_related("employee")
            .order_by("-start_date", "employee__first_name")[:200]
        )

    return render(request, "employees/leave.html", {
        "organization": membership.organization,
        "records": records,
        "org_id": org_id,
        "current_org": membership.organization,
        "is_member": is_member,
        "employee": current_employee,
        "can_manage_leave": not is_member,
    })


@login_required
def attendance_create(request, employee_id):
    employee = get_object_or_404(Employee, pk=employee_id)
    membership = get_membership(request.user, employee.organization_id)

    if not permissions.can_manage_attendance(membership, employee):
        messages.error(request, "Access restricted to management.")
        return redirect("employee_dashboard", org_id=employee.organization_id)
    if request.method == "POST":
        form = AttendanceForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.employee = employee
            item.save()
            messages.success(request, "Attendance recorded.")
            return redirect("employee_detail", uuid=employee.uuid)
    else:
        form = AttendanceForm()
    return render(request, "employees/attendance_form.html", {"form": form, "employee": employee})


@login_required
def leave_create(request, employee_id):
    employee = get_object_or_404(Employee, pk=employee_id)
    membership = get_membership(request.user, employee.organization_id)

    if membership.role == "member" and employee.user_id != request.user.id:
        messages.error(request, "You can only apply for your own leave.")
        return redirect("leave_list", org_id=employee.organization_id)

    if request.method == "POST":
        form = LeaveForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.employee = employee
            # Never trust a posted status: every new leave request starts
            # pending and can only change via leave_review, which is
            # permission-checked. This closes the self-approval bug.
            item.status = "pending"
            item.save()
            messages.success(request, "Leave request recorded.")
            return redirect("employee_detail", uuid=employee.uuid)
    else:
        form = LeaveForm()
    return render(request, "employees/leave_form.html", {"form": form, "employee": employee})


# @login_required
# def employee_update(request, uuid):
#     employee = get_object_or_404(Employee.objects.select_related("organization"), uuid=uuid)
#     membership = get_membership(request.user, employee.organization_id)

#     is_member = membership.role == "member"

#     # Employees may edit only their own profile (limited fields).
#     if is_member and employee.user_id != request.user.id:
#         messages.error(request, "You can only edit your own profile.")
#         return redirect("employee_dashboard", org_id=employee.organization_id)

#     # Only owners and admins may see or change the access group, supervisor,
#     # and salary/PF/ESI/deductions (enforced inside EmployeeForm).
#     can_change_access = membership.role in ("owner", "admin")

#     if is_member:
#         # Limited form: name, email, phone only. No salary, no access group.
#         form_kwargs = {}
#         FormClass = EmployeeSelfForm
#     else:
#         form_kwargs = {
#             "organization": membership.organization,
#             "can_change_access": can_change_access,
#             "acting_user": request.user,
#         }
#         FormClass = EmployeeForm

#     if request.method == "POST":
#         form = FormClass(request.POST, instance=employee, **form_kwargs)
#         if form.is_valid():
#             form.save()
#             messages.success(request, "Profile updated successfully." if is_member else "Employee updated successfully.")
#             return redirect("employee_detail", uuid=employee.uuid)
#     else:
#         form = FormClass(instance=employee, **form_kwargs)

#     return render(request, "employees/form.html", {
#     "form": form,
#     "organization": membership.organization,
#     "org_id": employee.organization_id,
#     "current_org": membership.organization,
#     "editing": True,
#     "employee": employee,
#     "can_edit_sensitive": permissions.can_edit_sensitive(membership),
#     })

@login_required
def employee_update(request, uuid):
    employee = get_object_or_404(Employee.objects.select_related("organization"), uuid=uuid)
    membership = get_membership(request.user, employee.organization_id)

    is_member = membership.role == "member"

    # Employees may edit only their own profile (limited fields).
    if is_member and employee.user_id != request.user.id:
        messages.error(request, "You can only edit your own profile.")
        return redirect("employee_dashboard", org_id=employee.organization_id)

    # Only owners and admins may see or change access, supervisor, salary/deductions
    can_change_access = membership.role in ("owner", "admin")

    if is_member:
        form_kwargs = {}
        FormClass = EmployeeSelfForm
    else:
        form_kwargs = {
            "organization": membership.organization,
            "can_change_access": can_change_access,
            "acting_user": request.user,
        }
        FormClass = EmployeeForm

    if request.method == "POST":
        form = FormClass(request.POST, instance=employee, **form_kwargs)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully." if is_member else "Employee updated successfully.")
            return redirect("employee_detail", uuid=employee.uuid)
        else:
            # SURFACE VALIDATION ERRORS:
            for field, errs in form.errors.items():
                messages.error(request, f"{field}: {', '.join(errs)}")
    else:
        form = FormClass(instance=employee, **form_kwargs)

    return render(request, "employees/form.html", {
        "form": form,
        "organization": membership.organization,
        "org_id": employee.organization_id,
        "current_org": membership.organization,
        "editing": True,
        "employee": employee,
        "can_edit_sensitive": permissions.can_edit_sensitive(membership),
    })


@login_required
def employee_deactivate(request, uuid):
    employee = get_object_or_404(Employee, uuid=uuid)
    membership = get_membership(request.user, employee.organization_id)

    if membership.role == "member":
        messages.error(request, "Access restricted to management.")
        return redirect("employee_dashboard", org_id=employee.organization_id)

    if request.method == "POST":
        employee.is_active = not employee.is_active
        employee.save(update_fields=["is_active"])
        state = "activated" if employee.is_active else "deactivated"
        messages.success(request, f"Employee {state}.")

    return redirect("employee_detail", uuid=employee.uuid)


@login_required
def attendance_update(request, pk):
    attendance = get_object_or_404(Attendance.objects.select_related("employee"), pk=pk)
    membership = get_membership(request.user, attendance.employee.organization_id)

    if not permissions.can_manage_attendance(membership, attendance.employee):
        messages.error(request, "Access restricted to management.")
        return redirect("employee_dashboard", org_id=attendance.employee.organization_id)

    if request.method == "POST":
        form = AttendanceForm(request.POST, instance=attendance)
        if form.is_valid():
            record = form.save(commit=False)
            record.marked_by = request.user
            record.save()
            messages.success(request, "Attendance record updated.")
            return redirect("employee_detail", uuid=attendance.employee.uuid)
    else:
        form = AttendanceForm(instance=attendance)

    return render(request, "employees/attendance_form.html", {
        "form": form, "employee": attendance.employee, "editing": True,
    })


@login_required
def attendance_delete(request, pk):
    attendance = get_object_or_404(Attendance.objects.select_related("employee"), pk=pk)
    membership = get_membership(request.user, attendance.employee.organization_id)

    if not permissions.can_manage_attendance(membership, attendance.employee):
        messages.error(request, "Access restricted to management.")
        return redirect("employee_dashboard", org_id=attendance.employee.organization_id)

    if request.method == "POST":
        employee_uuid = attendance.employee.uuid
        attendance.delete()
        messages.success(request, "Attendance record deleted.")
        return redirect("employee_detail", uuid=employee_uuid)

    return redirect("employee_detail", uuid=attendance.employee.uuid)


@login_required
def leave_review(request, pk, action):
    leave = get_object_or_404(Leave.objects.select_related("employee"), pk=pk)
    membership = get_membership(request.user, leave.employee.organization_id)

    if not permissions.can_manage_leave(membership, leave.employee):
        messages.error(request, "You are not authorized to review this leave request.")
        return redirect("leave_list", org_id=leave.employee.organization_id)

    if action not in ("approve", "reject"):
        messages.error(request, "Invalid action.")
        return redirect("leave_list", org_id=leave.employee.organization_id)

    if request.method == "POST":
        leave.status = "approved" if action == "approve" else "rejected"
        leave.save(update_fields=["status"])
        messages.success(request, f"Leave request {leave.status}.")

    return redirect("leave_list", org_id=leave.employee.organization_id)


@login_required
def leave_cancel(request, pk):
    leave = get_object_or_404(Leave.objects.select_related("employee"), pk=pk)
    membership = get_membership(request.user, leave.employee.organization_id)

    if leave.employee.user_id != request.user.id:
        messages.error(request, "You can only cancel your own leave requests.")
        return redirect("leave_list", org_id=leave.employee.organization_id)

    if leave.status != "pending":
        messages.error(request, "Only pending leave requests can be cancelled.")
        return redirect("leave_list", org_id=leave.employee.organization_id)

    if request.method == "POST":
        leave.delete()
        messages.success(request, "Leave request cancelled.")

    return redirect("leave_list", org_id=leave.employee.organization_id)

# @login_required
# def payroll(request, org_id):
#     membership = get_membership(request.user, org_id)

#     # Members are locked out entirely. Admins get full payroll with the
#     # confirm/unconfirm action. Supervisors get a view-only payroll scoped
#     # to their direct reports only.
#     if not permissions.can_view_payroll(membership):
#         messages.error(request, "Access restricted to management.")
#         return redirect("employee_dashboard", org_id=org_id)

#     can_edit = permissions.can_edit_payroll(membership)
#     organization = membership.organization
#     employees = permissions.scoped_report_queryset(membership).filter(
#         is_active=True
#     ).prefetch_related("projects")

#     if request.method == "POST":
#         # Confirming payroll is admin-only, even if a Supervisor forges a
#         # POST directly to this URL.
#         if not can_edit:
#             messages.error(request, "Only admins can confirm payroll.")
#             return redirect("payroll", org_id=org_id)
#         employee_ids = request.POST.getlist("employee_ids")
#         employees.update(payroll_confirmed=False)
#         employees.filter(id__in=employee_ids).update(payroll_confirmed=True)
#         messages.success(request, "Payroll confirmation status updated.")
#         return redirect("payroll", org_id=org_id)

#     return render(request, "employees/payroll.html", {
#         "organization": organization, 
#         "employees": employees, 
#         "org_id": org_id, 
#         "current_org": organization,
#         "can_edit_payroll": can_edit,
#     })


# ---------------------------------------------------------------------------
# Bulk import (admin / owner only)
# ---------------------------------------------------------------------------

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _import_membership(request, org_id):
    """The admin membership for this org, or None (after flashing an error)."""
    membership = get_membership(request.user, org_id)
    if not permissions.is_admin(membership):
        messages.error(request, "Only admins can import employees.")
        return None
    return membership


@login_required
def employee_import(request, org_id):
    membership = _import_membership(request, org_id)
    if membership is None:
        return redirect("home")
    organization = membership.organization
    columns = import_columns.build_columns(organization)
    context = {
        "organization": organization, "current_org": organization, "org_id": org_id,
        "stage": "upload", "columns": columns,
    }

    if request.method == "POST" and request.POST.get("action") == "confirm":
        payload = batch.load_batch(request, org_id, request.POST.get("token", ""))
        if payload is None:
            messages.error(
                request, "This preview has expired or was replaced. Please upload the file again."
            )
            return redirect("employee_import", org_id=org_id)
        result = commit_rows(payload["rows"], organization, request.user)
        batch.clear_batch(request)
        context.update(stage="result", result=result)
        return render(request, "employees/import.html", context)

    if request.method == "POST":
        form = EmployeeImportUploadForm(request.POST, request.FILES)
        if form.is_valid():
            report = parse_upload(form.cleaned_data["file"], organization)
            if not report.ok:
                batch.clear_batch(request)
                context["file_errors"] = report.file_errors
            else:
                payload = batch.report_to_payload(report)
                token = batch.store_batch(request, org_id, payload)
                counts = report.counts
                context.update(
                    stage="preview",
                    token=token,
                    notices=report.notices,
                    column_names=[c["name"] for c in payload["columns"]],
                    rows=[
                        {
                            "n": r["n"], "status": r["status"], "notes": r["notes"],
                            "cells": [r["values"].get(c["key"], "") for c in payload["columns"]],
                        }
                        for r in payload["rows"]
                    ],
                    counts=counts,
                    importable=counts["READY"] + counts["WARNING"],
                    problems=counts["ERROR"] + counts["SKIP"],
                )
    else:
        form = EmployeeImportUploadForm()
    context["form"] = form
    return render(request, "employees/import.html", context)


@login_required
def employee_import_template(request, org_id):
    membership = _import_membership(request, org_id)
    if membership is None:
        return redirect("home")
    content = import_files.build_template(import_columns.build_columns(membership.organization))
    response = HttpResponse(content, content_type=XLSX_TYPE)
    response["Content-Disposition"] = 'attachment; filename="employee_import_template.xlsx"'
    return response


@login_required
def employee_import_problems(request, org_id):
    membership = _import_membership(request, org_id)
    if membership is None:
        return redirect("home")
    payload = batch.load_batch(request, org_id, request.GET.get("token", ""))
    if payload is None:
        messages.error(request, "This preview has expired. Please upload the file again.")
        return redirect("employee_import", org_id=org_id)
    response = HttpResponse(import_files.build_problem_report(payload), content_type=XLSX_TYPE)
    response["Content-Disposition"] = 'attachment; filename="employee_import_problems.xlsx"'
    return response


@login_required
def payroll(request, org_id):
    membership = get_membership(request.user, org_id)

    if not permissions.can_view_payroll(membership):
        messages.error(request, "Access restricted to management.")
        return redirect("employee_dashboard", org_id=org_id)

    can_edit = permissions.can_edit_payroll(membership)
    organization = membership.organization
    today = timezone.localdate()

    # Read query/post parameters
    start_str = request.GET.get("start_date") or request.POST.get("start_date")
    end_str = request.GET.get("end_date") or request.POST.get("end_date")
    month_str = request.GET.get("month") or request.POST.get("month")

    start_date = None
    end_date = None
    custom_range = False

    # 1. Parse custom start & end dates if provided
    if start_str and end_str:
        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
            if start_date > end_date:
                start_date, end_date = end_date, start_date
            custom_range = True
        except (ValueError, TypeError):
            start_date, end_date = None, None

    # 2. Determine cycle Year & Month
    if month_str:
        try:
            year, month = map(int, month_str.split("-"))
        except (ValueError, TypeError):
            year, month = (end_date.year, end_date.month) if end_date else (today.year, today.month)
    elif end_date:
        year, month = end_date.year, end_date.month
    else:
        year, month = today.year, today.month

    # If no custom range was provided, default to standard full calendar month
    if not start_date or not end_date:
        start_date, end_date = get_month_range(year, month)

    selected_month_date = date(year, month, 1)
    selected_month_str = f"{year:04d}-{month:02d}"
    total_days = (end_date - start_date).days + 1

    # Fetch active scoped employees
    employees = permissions.scoped_report_queryset(membership).filter(
        is_active=True
    ).order_by("employee_id")

    selected_emp_id = request.GET.get("employee_id")
    selected_employee = employees.filter(id=selected_emp_id).first() if selected_emp_id else None

    # Handle Lock / Save Month Records Action
    if request.method == "POST" and can_edit:
        action = request.POST.get("action")
        if action == "save_month_records":
            for emp in employees:
                calc = calculate_employee_payroll(emp, year, month, start_date, end_date)
                SalaryRecord.objects.update_or_create(
                    organization=organization,
                    employee=emp,
                    year=year,
                    month=month,
                    defaults={
                        "base_salary": calc["base_salary"],
                        "pf": calc["pf"],
                        "esi": calc["esi"],
                        "other_deductions": calc["other_deductions"],
                        "payroll_start": start_date,
                        "payroll_end": end_date,
                        "total_days": calc["total_days"],
                        "present_days": calc["present_days"],
                        "paid_leave_days": calc["paid_leave_days"],
                        "gross_earned": calc["gross_earned"],
                        "net_salary": calc["net_salary"],
                        "confirmed": True,
                        "confirmed_by": request.user,
                        "confirmed_at": timezone.now(),
                    }
                )
            messages.success(
                request,
                f"Payroll saved for {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')} ({selected_month_date.strftime('%B %Y')})."
            )
            redirect_url = f"{request.path}?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}&month={selected_month_str}"
            if selected_emp_id:
                redirect_url += f"&employee_id={selected_emp_id}"
            return redirect(redirect_url)

    # Load existing saved SalaryRecords for this cycle
    saved_records = {
        sr.employee_id: sr for sr in SalaryRecord.objects.filter(
            organization=organization,
            year=year,
            month=month,
        )
    }

    payroll_data = []
    for emp in employees:
        calc = calculate_employee_payroll(emp, year, month, start_date, end_date)
        record = saved_records.get(emp.id)
        calc["record"] = record
        calc["confirmed"] = record.confirmed if record else False
        payroll_data.append(calc)

    single_calc = None
    if selected_employee:
        single_calc = next((item for item in payroll_data if item["employee"].id == selected_employee.id), None)

    context = {
        "organization": organization,
        "current_org": organization,
        "org_id": org_id,
        "can_edit_payroll": can_edit,
        "selected_month_str": selected_month_str,
        "selected_month_date": selected_month_date,
        "start_date": start_date,
        "end_date": end_date,
        "total_days": total_days,
        "employees": employees,
        "selected_employee": selected_employee,
        "payroll_data": payroll_data,
        "single_calc": single_calc,
    }
    return render(request, "employees/payroll.html", context)
