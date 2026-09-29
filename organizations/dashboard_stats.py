from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Count, Min, Q
from django.utils import timezone

from employees.models import Attendance, Employee, Leave, SalaryRecord
from projects.models import Action

PRESENT, HALF, LEAVE, ABSENT, OFF = "present", "half", "leave", "absent", "off"


def _day_status(emp, day, att_map, leave_map):
    """Mirrors employees.payroll_service.calculate_employee_payroll (exception model)."""
    if day.weekday() == emp.weekly_off:
        return OFF
    att = att_map.get((emp.id, day))
    if att == "ABSENT":
        return ABSENT
    if day in leave_map.get(emp.id, ()):
        return LEAVE
    if att == "HALF_DAY":
        return HALF
    if att == "LEAVE":
        return LEAVE
    return PRESENT


def _tone(pct):
    if pct is None:
        return "muted"
    return "good" if pct >= 90 else "warn" if pct >= 75 else "bad"


def build_dashboard(org, show_salary=False):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    days = [month_start + timedelta(days=i) for i in range((today - month_start).days + 1)]

    employees = list(Employee.objects.filter(organization=org, is_active=True))
    emp_ids = [e.id for e in employees]

    att_map = {
        (a.employee_id, a.date): a.status
        for a in Attendance.objects.filter(
            employee_id__in=emp_ids, date__gte=month_start, date__lte=today
        )
    }
    leave_map = defaultdict(set)
    for lv in Leave.objects.filter(
        employee_id__in=emp_ids, status="approved",
        start_date__lte=today, end_date__gte=month_start,
    ):
        cur = max(lv.start_date, month_start)
        while cur <= min(lv.end_date, today):
            leave_map[lv.employee_id].add(cur)
            cur += timedelta(days=1)

    # Month-to-date totals per employee: [present_weight, working_days]
    per_emp = {e.id: [0.0, 0] for e in employees}
    for d in days:
        for e in employees:
            s = _day_status(e, d, att_map, leave_map)
            if s == OFF:
                continue
            per_emp[e.id][1] += 1
            if s == PRESENT:
                per_emp[e.id][0] += 1
            elif s == HALF:
                per_emp[e.id][0] += 0.5

    # Today
    today_status = {e.id: _day_status(e, today, att_map, leave_map) for e in employees}
    counts = Counter(today_status.values())
    present_today = counts[PRESENT] + counts[HALF]

    # Payroll / pending
    confirmed_ids = set(
        SalaryRecord.objects.filter(
            organization=org, year=today.year, month=today.month, confirmed=True
        ).values_list("employee_id", flat=True)
    )
    payroll_pending = sum(1 for e in employees if e.id not in confirmed_ids)
    pending_leaves = Leave.objects.filter(
        employee__organization=org, status="pending"
    ).count()
    overdue_actions = (
        Action.objects.filter(project__organization=org, due_date__lt=today)
        .exclude(status="done")
        .count()
    )
    pending_total = pending_leaves + payroll_pending + overdue_actions

    # Project cards
    open_q = ~Q(actions__status="done")
    projects = org.projects.annotate(
        open_actions=Count("actions", filter=open_q, distinct=True),
        overdue_actions=Count(
            "actions", filter=open_q & Q(actions__due_date__lt=today), distinct=True
        ),
        next_due=Min("actions__due_date", filter=open_q),
    ).order_by("-created_at")

    cards = []
    for p in projects:
        team = [e for e in p.team_members.all() if e.id in per_emp]
        worked = sum(per_emp[e.id][0] for e in team)
        working = sum(per_emp[e.id][1] for e in team)
        att_pct = round(worked / working * 100) if working else None
        confirmed = sum(1 for e in team if e.id in confirmed_ids)

        working_today = sum(1 for e in team if today_status[e.id] != OFF)
        present_here = sum(1 for e in team if today_status[e.id] in (PRESENT, HALF))
        away = [e.first_name for e in team if today_status[e.id] in (ABSENT, LEAVE)]

        cards.append({
            "project": p,
            "team_count": len(team),
            "avatars": [
                ((e.first_name[:1] + e.last_name[:1]) or "?").upper() for e in team[:4]
            ],
            "extra": max(0, len(team) - 4),
            "att_pct": att_pct,
            "att_tone": _tone(att_pct),
            "present_today": present_here,
            "working_today": working_today,
            "away_names": away[:3],
            "away_extra": max(0, len(away) - 3),
            "confirmed": confirmed,
            "payroll_pct": round(confirmed / len(team) * 100) if team else 0,
            "payroll_cost": sum((e.salary or 0) for e in team) if show_salary else None,
            "open_actions": p.open_actions,
            "overdue_actions": p.overdue_actions,
            "next_due": p.next_due,
            "next_due_overdue": bool(p.next_due and p.next_due < today),
        })

    return {
        "month_label": today.strftime("%B %Y"),
        "kpi": {
            "active": len(employees),
            "present_today": present_today,
            "on_leave_today": counts[LEAVE],
            "pending_total": pending_total,
            "payroll_confirmed": len(employees) - payroll_pending,
        },
        "pending_leaves": pending_leaves,
        "payroll_pending": payroll_pending,
        "overdue_actions": overdue_actions,
        "project_cards": cards,
    }