import calendar
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from .models import Attendance, Leave, SalaryRecord
from decimal import Decimal, ROUND_HALF_UP

def get_month_range(year, month):
    """Returns the (first_day, last_day) dates for a calendar month."""
    _, last_day = calendar.monthrange(year, month)
    return date(year, month, 1), date(year, month, last_day)


def calculate_employee_payroll(employee, year=None, month=None, start_date=None, end_date=None):
    if not start_date or not end_date:
        from calendar import monthrange
        if not year or not month:
            today = timezone.localdate()
            year, month = today.year, today.month
        _, last_day = monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

    total_days = (end_date - start_date).days + 1

    # Explicit attendance exceptions in range
    attendances = {
        a.date: a for a in Attendance.objects.filter(
            employee=employee,
            date__gte=start_date,
            date__lte=end_date
        )
    }

    # Approved leaves covering range
    leaves = Leave.objects.filter(
        employee=employee,
        status="approved",
        start_date__lte=end_date,
        end_date__gte=start_date
    )
    leave_days_map = {}
    for l in leaves:
        cur = max(l.start_date, start_date)
        while cur <= min(l.end_date, end_date):
            leave_days_map[cur] = l.leave_type
            cur += timedelta(days=1)

    calendar_days = []
    present_days = Decimal("0.0")
    paid_leave_days = Decimal("0.0")
    unpaid_leave_days = Decimal("0.0")
    absent_days = Decimal("0.0")
    half_days = Decimal("0.0")

    curr = start_date
    emp_weekly_off = getattr(employee, "weekly_off", 6)

    while curr <= end_date:
        is_weekend = (curr.weekday() == emp_weekly_off)
        att = attendances.get(curr)
        leave_type = leave_days_map.get(curr)

        day_info = {
            "date": curr,
            "day": curr.day,
            "weekday": curr.strftime("%a"),
            "is_weekend": is_weekend,
            "status": "PRESENT",
        }

        if is_weekend:
            day_info["status"] = "WEEKEND"
        elif att and att.status == "ABSENT":
            day_info["status"] = "ABSENT"
            absent_days += Decimal("1.0")
        elif leave_type:
            if leave_type == "unpaid":
                day_info["status"] = "A"  # Unpaid leave counts as absence from pay
                unpaid_leave_days += Decimal("1.0")
            else:
                day_info["status"] = "LEAVE"
                paid_leave_days += Decimal("1.0")
        elif att and att.status == "HALF_DAY":
            day_info["status"] = "HALF_DAY"
            half_days += Decimal("1.0")
            present_days += Decimal("0.5")
        elif att and att.status == "LEAVE":
            day_info["status"] = "LEAVE"
            paid_leave_days += Decimal("1.0")
        else:
            # Exception Model: Non-off working days default to PRESENT
            day_info["status"] = "PRESENT"
            present_days += Decimal("1.0")

        calendar_days.append(day_info)
        curr += timedelta(days=1)

    payable_days = min(Decimal(total_days), present_days + paid_leave_days)

    base_salary = employee.salary or Decimal("0.00")
    if total_days > 0 and base_salary > 0:
        daily_rate = base_salary / Decimal(total_days)
        gross_earned = (daily_rate * payable_days).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        gross_earned = Decimal("0.00")

    pf = Decimal(str(getattr(employee, "pf", 0) or "0.00"))
    esi = Decimal(str(getattr(employee, "esi", 0) or "0.00"))
    other_deductions = Decimal(str(getattr(employee, "other_deductions", 0) or "0.00"))
    total_deductions = pf + esi + other_deductions
    net_salary = max(Decimal("0.00"), gross_earned - total_deductions)

    return {
        "employee": employee,
        "year": year,
        "month": month,
        "payroll_start": start_date,
        "payroll_end": end_date,
        "total_days": total_days,
        "present_days": present_days,
        "paid_leave_days": paid_leave_days,
        "unpaid_leave_days": unpaid_leave_days,
        "absent_days": absent_days,
        "half_days": half_days,
        "payable_days": payable_days,
        "base_salary": base_salary,
        "gross_earned": gross_earned,
        "pf": pf,
        "esi": esi,
        "other_deductions": other_deductions,
        "total_deductions": total_deductions,
        "net_salary": net_salary,
        "calendar_days": calendar_days,
    }


# def calculate_employee_payroll(employee, year, month, start_date=None, end_date=None):
#     """
#     Computes attendance, approved leave, and prorated earnings.
#     If custom cycle dates aren't provided, defaults to the full calendar month.
#     """
#     if not start_date or not end_date:
#         start_date, end_date = get_month_range(year, month)

#     total_days = (end_date - start_date).days + 1

#     # Fetch daily attendance records in range
#     attendances = {
#         a.date: a for a in Attendance.objects.filter(
#             employee=employee,
#             date__gte=start_date,
#             date__lte=end_date
#         )
#     }

#     # Fetch approved leaves covering any day in range
#     leaves = Leave.objects.filter(
#         employee=employee,
#         status="approved",
#         start_date__lte=end_date,
#         end_date__gte=start_date
#     )
#     leave_dates = set()
#     for l in leaves:
#         cur = max(l.start_date, start_date)
#         while cur <= min(l.end_date, end_date):
#             leave_dates.add(cur)
#             cur += timedelta(days=1)

#     calendar_days = []
#     present_days = Decimal("0.0")
#     paid_leave_days = Decimal("0.0")

#     curr = start_date
#     while curr <= end_date:
#         att = attendances.get(curr)
#         day_status = "ABSENT"
#         is_weekend = curr.weekday() >= 5  # Saturday & Sunday

#         if att:
#             if att.status == "PRESENT":
#                 day_status = "PRESENT"
#                 present_days += Decimal("1.0")
#             elif att.status == "HALF_DAY":
#                 day_status = "HALF_DAY"
#                 present_days += Decimal("0.5")
#             elif att.status == "LEAVE":
#                 day_status = "LEAVE"
#                 paid_leave_days += Decimal("1.0")
#             elif att.status == "ABSENT":
#                 day_status = "ABSENT"
#         elif curr in leave_dates:
#             day_status = "LEAVE"
#             paid_leave_days += Decimal("1.0")
#         elif is_weekend:
#             day_status = "WEEKEND"

#         calendar_days.append({
#             "date": curr,
#             "day": curr.day,
#             "weekday": curr.strftime("%a"),
#             "status": day_status,
#             "is_weekend": is_weekend
#         })
#         curr += timedelta(days=1)

#     payable_days = min(Decimal(total_days), present_days + paid_leave_days)

#     # Base rate snapshot
#     base_salary = employee.salary or Decimal("0.00")
#     if total_days > 0 and base_salary > 0:
#         gross_earned = round((base_salary / Decimal(total_days)) * payable_days, 2)
#     else:
#         gross_earned = Decimal("0.00")

#     pf = employee.pf or Decimal("0.00")
#     esi = employee.esi or Decimal("0.00")
#     other_deductions = employee.other_deductions or Decimal("0.00")
#     total_deductions = pf + esi + other_deductions
#     net_salary = max(Decimal("0.00"), gross_earned - total_deductions)

#     return {
#         "employee": employee,
#         "year": year,
#         "month": month,
#         "payroll_start": start_date,
#         "payroll_end": end_date,
#         "total_days": total_days,
#         "present_days": present_days,
#         "paid_leave_days": paid_leave_days,
#         "payable_days": payable_days,
#         "base_salary": base_salary,
#         "gross_earned": gross_earned,
#         "pf": pf,
#         "esi": esi,
#         "other_deductions": other_deductions,
#         "total_deductions": total_deductions,
#         "net_salary": net_salary,
#         "calendar_days": calendar_days,
#     }