from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.services import GrantLoginError, grant_login, public_domain
from organizations.models import OrganizationMember
from .bulk_import import batch, columns as import_columns, files as import_files, parse_upload
from .bulk_import.commit import commit_rows
from .forms import AttendanceForm, EmployeeForm, EmployeeImportUploadForm, EmployeeSelfForm, LeaveForm
from .models import Attendance, Employee, Leave, SalaryRecord
from . import permissions
from .payroll_service import calculate_employee_payroll, get_month_range
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings
from decimal import Decimal
from django.db.models import Sum
import json
from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from . import permissions

from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def get_membership(user, org_id):
    return get_object_or_404(OrganizationMember, organization_id=org_id, user=user)


@login_required
def employee_dashboard(request, org_id):
    membership = get_membership(request.user, org_id)
    employee = Employee.objects.filter(
        organization_id=org_id, 
        user_id=request.user.id
    ).first()

    context = {
        "organization": membership.organization,
        "current_org": membership.organization,
        "org_id": org_id,
        "membership": membership,
        "employee": employee,
        "is_self": True,
        "can_edit": bool(employee),
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

    is_admin_or_owner = membership.role in ("owner", "admin")

    form_kwargs = {
        "organization": membership.organization,
        "can_change_access": is_admin_or_owner,
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
        # Safe boolean check for creation stage (no employee instance exists yet)
        "can_edit_sensitive": is_admin_or_owner,
    })


@login_required
def employee_detail(request, uuid):
    employee = get_object_or_404(
        Employee.objects.select_related("organization", "user", "supervisor"), 
        uuid=uuid
    )
    membership = get_membership(request.user, employee.organization_id)

    is_self = bool(employee.user_id and employee.user_id == request.user.id)
    can_manage_employees = membership.role in ("owner", "admin", "manager")

    if membership.role == "member" and not is_self:
        messages.error(request, "Access restricted to your own profile.")
        return redirect("employee_dashboard", org_id=employee.organization_id)

    can_edit = can_manage_employees or is_self
    can_view_sensitive = is_self or permissions.can_view_sensitive(membership, employee)
    can_grant_login = permissions.is_admin(membership) and employee.user_id is None
    context = {
        "employee": employee,
        "organization": membership.organization,
        "current_org": membership.organization,
        "org_id": employee.organization_id,
        "membership": membership,
        "is_self": is_self,
        "can_edit": can_edit,
        "can_manage_employees": can_manage_employees,
        "can_grant_login": can_grant_login,  # <-- 2. Expose to template
        "can_view_sensitive": can_view_sensitive,
    }
    return render(request, "employees/detail.html", context)



# @login_required
# def employee_grant_login(request, uuid):
#     employee = get_object_or_404(Employee.objects.select_related("organization"), uuid=uuid)
#     membership = get_membership(request.user, employee.organization_id)

#     if not permissions.is_admin(membership):
#         messages.error(request, "Only admins can grant login access.")
#         return redirect("employee_dashboard", org_id=employee.organization_id)

#     if request.method == "POST":
#         try:
#             user = grant_login(employee)

#             if user.email:
#                 form = PasswordResetForm(data={"email": user.email})
#                 if form.is_valid():
#                     host = request.get_host()
#                     # Ensure port 8082 is always present for the EC2 IP
#                     if "18.61.200.14" in host and ":8082" not in host:
#                         host = "18.61.200.14:8082"

#                     form.save(
#                         request=request,
#                         use_https=False,
#                         domain_override=host,
#                         from_email=settings.DEFAULT_FROM_EMAIL,
#                     )
#                     messages.success(
#                         request,
#                         f"Login created for {user.email}. A password setup link has been sent to their inbox.",
#                     )
#                 else:
#                     messages.warning(
#                         request,
#                         f"Login created for {user.email}, but could not validate email to send setup link.",
#                     )
#             else:
#                 messages.success(
#                     request,
#                     "Login created, but no email is on file to send a password link.",
#                 )
#         except GrantLoginError as exc:
#             messages.error(request, str(exc))

#     return redirect("employee_detail", uuid=employee.uuid)

@login_required
def employee_grant_login(request, uuid):
    employee = get_object_or_404(Employee.objects.select_related("organization"), uuid=uuid)
    membership = get_membership(request.user, employee.organization_id)

    if not permissions.is_admin(membership):
        messages.error(request, "Only admins can grant login access.")
        return redirect("employee_dashboard", org_id=employee.organization_id)

    if request.method == "POST":
        try:
            user = grant_login(employee)

            if user.email:
                # 1. Determine host, correcting for the missing :8082 on EC2
                host = public_domain(request)
                protocol = "https" if request.is_secure() else "http"
                base_url = f"{protocol}://{host}"

                # 2. Build one-time password setup token & link
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                setup_url = f"{base_url}/login/set-password/{uid}/{token}/"

                # 3. Deliver password setup email directly
                email_subject = "Set up your account password"
                email_body = (
                    f"Hello {user.first_name or 'there'},\n\n"
                    f"Your login for {membership.organization.name} has been provisioned.\n"
                    f"Please click the link below to set your password and access your dashboard:\n\n"
                    f"{setup_url}\n\n"
                    f"This link will expire shortly.\n"
                )

                send_mail(
                    subject=email_subject,
                    message=email_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

                messages.success(
                    request,
                    f"Login created for {user.email}. A password setup link has been sent to their inbox.",
                )
            else:
                messages.success(
                    request,
                    "Login created, but no email is on file to send a password link.",
                )
        except GrantLoginError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.warning(
                request,
                f"Login was created, but failed to send setup email: {exc}",
            )

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


@login_required
def leave_list(request, org_id):
    membership = get_membership(request.user, org_id)
    is_member = membership.role == "member"

    current_employee = Employee.objects.filter(
        organization=membership.organization, 
        user=request.user
    ).first()

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
            item.status = "pending"
            item.save()
            messages.success(request, "Leave request submitted successfully.")
            return redirect("leave_list", org_id=employee.organization_id)
        else:
            for field, errs in form.errors.items():
                messages.error(request, f"{field}: {', '.join(errs)}")
    else:
        form = LeaveForm()

    return render(
        request,
        "employees/leave_form.html",
        {
            "form": form,
            "employee": employee,
            "organization": membership.organization,
            "current_org": membership.organization,
            "org_id": employee.organization_id,
        },
    )


@login_required
def employee_update(request, uuid):
    employee = get_object_or_404(
        Employee.objects.select_related("organization", "user"), 
        uuid=uuid
    )
    membership = get_membership(request.user, employee.organization_id)

    is_self = bool(employee.user_id and employee.user_id == request.user.id)
    can_manage = membership.role in ("owner", "admin", "manager")

    if membership.role == "member" and not is_self:
        messages.error(request, "You are only authorized to edit your own profile.")
        return redirect("employee_dashboard", org_id=employee.organization_id)
    elif membership.role != "member" and not can_manage:
        messages.error(request, "You do not have permission to edit employees.")
        return redirect("employee_list", org_id=employee.organization_id)

    is_member = (membership.role == "member")
    can_change_access = membership.role in ("owner", "admin")

    if is_member:
        FormClass = EmployeeSelfForm
        form_kwargs = {}
    else:
        FormClass = EmployeeForm
        form_kwargs = {
            "organization": membership.organization,
            "can_change_access": can_change_access,
            "acting_user": request.user,
        }

    if request.method == "POST":
        form = FormClass(request.POST, instance=employee, **form_kwargs)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Profile updated successfully." if is_member else "Employee updated successfully."
            )
            if is_member:
                return redirect("employee_dashboard", org_id=employee.organization_id)
            return redirect("employee_detail", uuid=employee.uuid)
        else:
            for field, errs in form.errors.items():
                messages.error(request, f"{field}: {', '.join(errs)}")
    else:
        form = FormClass(instance=employee, **form_kwargs)

    # Safe sensitive-field check passing employee instance
    if hasattr(permissions, "can_edit_sensitive"):
        try:
            can_edit_sensitive = permissions.can_edit_sensitive(membership, employee)
        except TypeError:
            can_edit_sensitive = permissions.can_edit_sensitive(membership)
    else:
        can_edit_sensitive = can_change_access

    context = {
        "form": form,
        "organization": membership.organization,
        "current_org": membership.organization,
        "org_id": employee.organization_id,
        "editing": True,
        "employee": employee,
        "is_member": is_member,
        "can_edit_sensitive": can_edit_sensitive,
    }
    return render(request, "employees/form.html", context)


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


# ---------------------------------------------------------------------------
# Bulk import (admin / owner only)
# ---------------------------------------------------------------------------

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _import_membership(request, org_id):
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

    start_str = request.GET.get("start_date") or request.POST.get("start_date")
    end_str = request.GET.get("end_date") or request.POST.get("end_date")
    month_str = request.GET.get("month") or request.POST.get("month")

    start_date = None
    end_date = None

    if start_str and end_str:
        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
            if start_date > end_date:
                start_date, end_date = end_date, start_date
        except (ValueError, TypeError):
            start_date, end_date = None, None

    if month_str:
        try:
            year, month = map(int, month_str.split("-"))
        except (ValueError, TypeError):
            year, month = (end_date.year, end_date.month) if end_date else (today.year, today.month)
    elif end_date:
        year, month = end_date.year, end_date.month
    else:
        year, month = today.year, today.month

    if not start_date or not end_date:
        start_date, end_date = get_month_range(year, month)

    selected_month_date = date(year, month, 1)
    selected_month_str = f"{year:04d}-{month:02d}"
    total_days = (end_date - start_date).days + 1

    employees = permissions.scoped_report_queryset(membership).filter(
        is_active=True
    ).order_by("employee_id")

    selected_emp_id = request.GET.get("employee_id")
    selected_employee = employees.filter(id=selected_emp_id).first() if selected_emp_id else None

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


@login_required
def employee_payslip(request, org_id, employee_id):
    membership = get_membership(request.user, org_id)
    employee = get_object_or_404(Employee, id=employee_id, organization_id=org_id)

    if membership.role == "member" and employee.user_id != request.user.id:
        messages.error(request, "Access restricted to your own payslip.")
        return redirect("employee_dashboard", org_id=org_id)
    elif membership.role != "member" and not permissions.can_view_payroll(membership):
        messages.error(request, "Access restricted to management.")
        return redirect("employee_dashboard", org_id=org_id)

    start_str = request.GET.get("start_date")
    end_str = request.GET.get("end_date")
    month_str = request.GET.get("month")

    today = timezone.localdate()
    if start_str and end_str:
        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
        except (ValueError, TypeError):
            start_date, end_date = None, None
    else:
        start_date, end_date = None, None

    if month_str:
        try:
            year, month = map(int, month_str.split("-"))
        except (ValueError, TypeError):
            year, month = today.year, today.month
    elif end_date:
        year, month = end_date.year, end_date.month
    else:
        year, month = today.year, today.month

    if not start_date or not end_date:
        start_date, end_date = get_month_range(year, month)

    calc = calculate_employee_payroll(employee, year, month, start_date, end_date)

    saved_record = SalaryRecord.objects.filter(
        organization=membership.organization,
        employee=employee,
        year=year,
        month=month,
    ).first()

    context = {
        "organization": membership.organization,
        "employee": employee,
        "calc": calc,
        "saved_record": saved_record,
        "start_date": start_date,
        "end_date": end_date,
        "pay_period": f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",
        "pay_month": date(year, month, 1).strftime("%B %Y"),
    }
    return render(request, "employees/payslip.html", context)

@login_required
def payroll_summary_pdf(request, org_id):
    membership = get_membership(request.user, org_id)

    if not permissions.can_view_payroll(membership):
        messages.error(request, "Access restricted to management.")
        return redirect("employee_dashboard", org_id=org_id)

    organization = membership.organization
    today = timezone.localdate()

    # Parse cycle parameters
    start_str = request.GET.get("start_date")
    end_str = request.GET.get("end_date")
    month_str = request.GET.get("month")

    start_date = None
    end_date = None

    if start_str and end_str:
        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
            if start_date > end_date:
                start_date, end_date = end_date, start_date
        except (ValueError, TypeError):
            start_date, end_date = None, None

    if month_str:
        try:
            year, month = map(int, month_str.split("-"))
        except (ValueError, TypeError):
            year, month = (end_date.year, end_date.month) if end_date else (today.year, today.month)
    elif end_date:
        year, month = end_date.year, end_date.month
    else:
        year, month = today.year, today.month

    if not start_date or not end_date:
        start_date, end_date = get_month_range(year, month)

    total_days = (end_date - start_date).days + 1
    selected_month_date = date(year, month, 1)

    # Fetch employees
    employees = permissions.scoped_report_queryset(membership).filter(
        is_active=True
    ).order_by("employee_id")

    saved_records = {
        sr.employee_id: sr for sr in SalaryRecord.objects.filter(
            organization=organization,
            year=year,
            month=month,
        )
    }

    payroll_data = []
    totals = {
        "base_salary": Decimal("0.00"),
        "gross_earned": Decimal("0.00"),
        "pf": Decimal("0.00"),
        "esi": Decimal("0.00"),
        "other_deductions": Decimal("0.00"),
        "total_deductions": Decimal("0.00"),
        "net_salary": Decimal("0.00"),
    }

    for emp in employees:
        calc = calculate_employee_payroll(emp, year, month, start_date, end_date)
        record = saved_records.get(emp.id)
        calc["record"] = record
        calc["confirmed"] = record.confirmed if record else False

        # Accumulate totals
        totals["base_salary"] += calc["base_salary"]
        totals["gross_earned"] += calc["gross_earned"]
        totals["pf"] += calc["pf"]
        totals["esi"] += calc["esi"]
        totals["other_deductions"] += calc["other_deductions"]
        totals["total_deductions"] += calc["total_deductions"]
        totals["net_salary"] += calc["net_salary"]

        payroll_data.append(calc)

    context = {
        "organization": organization,
        "payroll_data": payroll_data,
        "totals": totals,
        "start_date": start_date,
        "end_date": end_date,
        "total_days": total_days,
        "pay_period": f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",
        "pay_month": selected_month_date.strftime("%B %Y"),
        "generated_at": timezone.now(),
    }
    return render(request, "employees/payroll_summary_pdf.html", context)


@login_required
def my_payslips(request, org_id):
    membership = get_membership(request.user, org_id)
    employee = Employee.objects.filter(
        organization_id=org_id, 
        user_id=request.user.id
    ).first()

    if not employee:
        messages.error(request, "No employee record linked to your account.")
        return redirect("employee_dashboard", org_id=org_id)

    today = timezone.localdate()

    # Retrieve all locked historical salary records for this employee
    records = SalaryRecord.objects.filter(
        organization=membership.organization,
        employee=employee,
    ).order_by("-year", "-month")

    # Generate quick selectors for the last 6 months so members can preview unfinalized months too
    cycles = []
    current_year, current_month = today.year, today.month

    for i in range(6):
        target_month = current_month - i
        target_year = current_year
        while target_month <= 0:
            target_month += 12
            target_year -= 1

        cycle_start, cycle_end = get_month_range(target_year, target_month)
        matching_record = records.filter(year=target_year, month=target_month).first()

        cycles.append({
            "year": target_year,
            "month": target_month,
            "month_label": date(target_year, target_month, 1).strftime("%B %Y"),
            "start_date": cycle_start,
            "end_date": cycle_end,
            "month_str": f"{target_year:04d}-{target_month:02d}",
            "record": matching_record,
            "is_locked": bool(matching_record and matching_record.confirmed),
        })

    context = {
        "organization": membership.organization,
        "current_org": membership.organization,
        "org_id": org_id,
        "employee": employee,
        "cycles": cycles,
    }
    return render(request, "employees/my_payslips.html", context)

@login_required
def attendance_exceptions(request, org_id):
    """
    Daily Exception Dashboard: Lists employees for a selected date.
    All non-weekly-off staff are considered PRESENT by default.
    Admins/supervisors toggle absences or half-days.
    """
    membership = get_membership(request.user, org_id)
    if not (permissions.is_admin(membership) or membership.role in ("manager", "supervisor")):
        messages.error(request, "Access restricted to management.")
        return redirect("employee_dashboard", org_id=org_id)

    target_date_str = request.GET.get("date")
    if target_date_str:
        try:
            target_date = date.fromisoformat(target_date_str)
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    employees = permissions.scoped_report_queryset(membership).filter(is_active=True).order_by("employee_id")

    records_by_emp = {
        att.employee_id: att
        for att in Attendance.objects.filter(employee__in=employees, date=target_date)
    }

    leaves_by_emp = {
        lv.employee_id: lv
        for lv in Leave.objects.filter(
            employee__in=employees,
            status="approved",
            start_date__lte=target_date,
            end_date__gte=target_date,
        )
    }

    roster = []
    day_weekday = target_date.weekday()

    for emp in employees:
        rec = records_by_emp.get(emp.id)
        leave = leaves_by_emp.get(emp.id)
        is_weekly_off = (getattr(emp, "weekly_off", 6) == day_weekday)

        if is_weekly_off:
            status = "WEEKEND"
        elif rec:
            status = rec.status
        elif leave:
            status = "LEAVE"
        else:
            status = "PRESENT"

        roster.append({
            "employee": emp,
            "status": status,
            "is_weekly_off": is_weekly_off,
            "leave": leave,
        })

    context = {
        "organization": membership.organization,
        "org_id": org_id,
        "target_date": target_date,
        "roster": roster,
        "can_edit": permissions.can_manage_attendance(membership, None),
    }
    return render(request, "employees/attendance_exceptions.html", context)


@require_POST
@login_required
def toggle_attendance_exception(request, org_id):
    """
    AJAX endpoint for exception toggles:
    - PRESENT deletes the Attendance row (falls back to default present).
    - ABSENT / HALF_DAY updates or creates the Attendance record.
    """
    membership = get_membership(request.user, org_id)
    if not (permissions.is_admin(membership) or membership.role in ("manager", "supervisor")):
        return JsonResponse({"status": "error", "message": "Permission denied."}, status=403)

    try:
        data = json.loads(request.body)
        employee_id = data.get("employee_id")
        target_date = date.fromisoformat(data.get("date"))
        new_status = data.get("status")
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"status": "error", "message": "Invalid request payload."}, status=400)

    emp = get_object_or_404(permissions.scoped_report_queryset(membership), id=employee_id)

    if new_status == "PRESENT":
        Attendance.objects.filter(employee=emp, date=target_date).delete()
    elif new_status in ("ABSENT", "HALF_DAY"):
        Attendance.objects.update_or_create(
            employee=emp,
            date=target_date,
            defaults={
                "status": new_status,
                "marked_by": request.user,
            }
        )
    else:
        return JsonResponse({"status": "error", "message": "Unsupported status."}, status=400)

    return JsonResponse({"status": "success", "new_status": new_status})


@login_required
def leave_apply_management(request, org_id):
    """
    Allows Admins and Supervisors to assign leaves for any employee.
    Auto-approved and defaults to unpaid.
    """
    membership = get_membership(request.user, org_id)
    if not (permissions.is_admin(membership) or membership.role in ("manager", "supervisor")):
        messages.error(request, "Permission denied.")
        return redirect("employee_dashboard", org_id=org_id)

    employees = permissions.scoped_report_queryset(membership).filter(is_active=True).order_by("first_name")

    if request.method == "POST":
        emp_id = request.POST.get("employee_id")
        start_date_str = request.POST.get("start_date")
        end_date_str = request.POST.get("end_date")
        leave_type = request.POST.get("leave_type", "unpaid")
        reason = request.POST.get("reason", "").strip()

        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
            if start_date > end_date:
                start_date, end_date = end_date, start_date

            target_emp = get_object_or_404(employees, id=emp_id)

            Leave.objects.create(
                employee=target_emp,
                start_date=start_date,
                end_date=end_date,
                leave_type=leave_type,
                reason=reason or "Assigned by Management",
                status="approved",
            )
            messages.success(
                request,
                f"Approved {leave_type} leave recorded for {target_emp.first_name} {target_emp.last_name}.",
            )
            return redirect("attendance_exceptions", org_id=org_id)
        except (ValueError, TypeError) as exc:
            messages.error(request, f"Failed to record leave: {exc}")

    context = {
        "organization": membership.organization,
        "org_id": org_id,
        "employees": employees,
    }
    return render(request, "employees/leave_apply_management.html", context)
