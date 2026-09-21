"""
Service helpers for the onboarding checklist.

All writes to EmployeeChecklistEntry should go through `set_checklist_status`
so the rules live in one place (used by the bulk importer now, and by the
checklist screens later):

- the item and the employee must belong to the same organization
- `completed_on` only exists while the status is "done"
- marking "done" without a date defaults to today
"""

from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone

from .models import (
    CHECKLIST_DONE,
    CHECKLIST_STATUS_CHOICES,
    ChecklistItem,
    EmployeeChecklistEntry,
)

# Items every organization starts with. Admins can rename, add or deactivate
# items afterwards; this list only seeds new organizations.
DEFAULT_CHECKLIST_ITEMS = ("AVSEC Training", "Police Verification")

_VALID_STATUSES = {value for value, _label in CHECKLIST_STATUS_CHOICES}


def ensure_default_items(organization):
    """
    Create any missing default items for `organization`. Safe to call
    repeatedly: existing items (matched case-insensitively) are left alone.
    Returns the list of items that were newly created.
    """
    existing = set(
        ChecklistItem.objects.filter(organization=organization)
        .annotate(lname=Lower("name"))
        .values_list("lname", flat=True)
    )
    last_order = (
        ChecklistItem.objects.filter(organization=organization)
        .order_by("-order")
        .values_list("order", flat=True)
        .first()
    ) or 0

    created = []
    for name in DEFAULT_CHECKLIST_ITEMS:
        if name.lower() in existing:
            continue
        last_order += 10
        created.append(
            ChecklistItem.objects.create(
                organization=organization, name=name, order=last_order
            )
        )
    return created


@transaction.atomic
def set_checklist_status(employee, item, status, *, completed_on=None, marked_by=None):
    """
    Create or update `employee`'s entry for `item`. Returns the entry.

    Raises ValueError for an unknown status or when the employee and item
    belong to different organizations.
    """
    if status not in _VALID_STATUSES:
        raise ValueError(f"Unknown checklist status: {status!r}")
    if employee.organization_id != item.organization_id:
        raise ValueError(
            "Checklist item and employee belong to different organizations."
        )

    if status == CHECKLIST_DONE:
        completed_on = completed_on or timezone.localdate()
    else:
        completed_on = None

    entry, _created = EmployeeChecklistEntry.objects.update_or_create(
        employee=employee,
        item=item,
        defaults={
            "status": status,
            "completed_on": completed_on,
            "marked_by": marked_by,
        },
    )
    return entry
