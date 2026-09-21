"""
Apply a previewed import: create each employee, give them a login (or link the
login they already have in another organization), set checklist dates.

Every row runs in its own savepoint, so one bad row is reported and the rest
still import (instead of one error rolling back / crashing the whole batch).
Conflicts are re-checked here because the data may have changed since the preview.
"""

import logging
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction

from accounts.services import (
    GrantLoginError,
    find_existing_login,
    grant_login,
    link_existing_login,
)
from employees.checklist import set_checklist_status
from employees.models import CHECKLIST_DONE, ChecklistItem, Employee

from .engine import READY, WARNING, OrganizationIndex

logger = logging.getLogger(__name__)


class RowFailed(Exception):
    pass


@dataclass
class CommitResult:
    created: list = field(default_factory=list)  # (row number, employee id, email)
    failed: list = field(default_factory=list)  # (row number, reason)
    linked: list = field(default_factory=list)  # row numbers linked to an existing login


def _conflict(data, index):
    email = data["email"]
    if email in index.email:
        return f"An employee with this email already exists ({index.email[email]})."
    for key, label in (("aadhar_no", "Aadhar No."), ("pan_no", "PAN No.")):
        value = data.get(key)
        if value and value in getattr(index, key):
            return f"{label} already belongs to employee {getattr(index, key)[value]}."
    return None


def commit_rows(payload_rows, organization, marked_by):
    result = CommitResult()
    index = OrganizationIndex(organization)
    items = {item.id: item for item in ChecklistItem.objects.filter(organization=organization)}

    for row in payload_rows:
        if row["status"] not in (READY, WARNING):
            continue
        data = dict(row["data"])
        if data.get("date_joined"):
            data["date_joined"] = date.fromisoformat(data["date_joined"])
        checklist = {int(k): date.fromisoformat(v) for k, v in row["checklist"].items()}
        linked = False

        try:
            with transaction.atomic():
                message = _conflict(data, index)
                if message:
                    raise RowFailed(message)
                employee = Employee(organization=organization, **data)
                employee.save()
                # Same person already has a login (another organization)? Reuse it.
                if find_existing_login(data["email"]) is not None:
                    link_existing_login(employee)
                    linked = True
                else:
                    grant_login(employee)
                for item_id, done_on in checklist.items():
                    item = items.get(item_id)
                    if item is not None:
                        set_checklist_status(
                            employee, item, CHECKLIST_DONE,
                            completed_on=done_on, marked_by=marked_by,
                        )
        except (RowFailed, GrantLoginError) as exc:
            result.failed.append((row["n"], str(exc)))
            continue
        except Exception:
            logger.exception("Bulk import: row %s failed", row["n"])
            result.failed.append((row["n"], "Unexpected error. This row was not imported."))
            continue

        index.email[data["email"]] = employee.employee_id
        for key in ("aadhar_no", "pan_no"):
            if data.get(key):
                getattr(index, key)[data[key]] = employee.employee_id
        result.created.append((row["n"], employee.employee_id, data["email"]))
        if linked:
            result.linked.append(row["n"])
    return result