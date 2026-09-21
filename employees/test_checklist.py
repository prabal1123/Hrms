from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from employees.checklist import (
    DEFAULT_CHECKLIST_ITEMS,
    ensure_default_items,
    set_checklist_status,
)
from employees.models import (
    CHECKLIST_DONE,
    CHECKLIST_NOT_APPLICABLE,
    CHECKLIST_PENDING,
    ChecklistItem,
    Employee,
    EmployeeChecklistEntry,
)
from organizations.models import Organization

User = get_user_model()


class ChecklistTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", password="pw-owner-123")
        self.org = Organization.objects.create(name="Acme", created_by=self.user)
        self.other_org = Organization.objects.create(name="Other Co", created_by=self.user)
        self.emp = Employee.objects.create(organization=self.org, first_name="Asha")
        self.avsec = ChecklistItem.objects.get(organization=self.org, name="AVSEC Training")
        self.police = ChecklistItem.objects.get(organization=self.org, name="Police Verification")


class DefaultItemTests(ChecklistTestBase):
    def test_new_organization_gets_default_items_in_order(self):
        names = list(self.org.checklist_items.values_list("name", flat=True))
        self.assertEqual(names, list(DEFAULT_CHECKLIST_ITEMS))

    def test_each_organization_has_its_own_items(self):
        self.assertEqual(self.other_org.checklist_items.count(), len(DEFAULT_CHECKLIST_ITEMS))
        self.assertFalse(
            set(self.org.checklist_items.values_list("pk", flat=True))
            & set(self.other_org.checklist_items.values_list("pk", flat=True))
        )

    def test_ensure_default_items_is_idempotent(self):
        self.assertEqual(ensure_default_items(self.org), [])
        self.assertEqual(self.org.checklist_items.count(), len(DEFAULT_CHECKLIST_ITEMS))

    def test_ensure_default_items_restores_a_missing_one_without_duplicating(self):
        self.police.delete()
        created = ensure_default_items(self.org)
        self.assertEqual([i.name for i in created], ["Police Verification"])
        self.assertEqual(self.org.checklist_items.count(), 2)

    def test_ensure_default_items_matches_names_case_insensitively(self):
        ChecklistItem.objects.filter(pk=self.avsec.pk).update(name="avsec training")
        self.assertEqual(ensure_default_items(self.org), [])

    def test_custom_items_sort_after_defaults(self):
        custom = ChecklistItem.objects.create(organization=self.org, name="Offer letter", order=100)
        self.assertEqual(list(self.org.checklist_items.all())[-1], custom)


class ItemConstraintTests(ChecklistTestBase):
    def test_item_name_unique_per_org_case_insensitively(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ChecklistItem.objects.create(organization=self.org, name="AVSEC TRAINING")

    def test_same_name_allowed_in_different_orgs(self):
        # other_org was also seeded with "AVSEC Training" -> proves it coexists
        self.assertTrue(
            ChecklistItem.objects.filter(organization=self.other_org, name="AVSEC Training").exists()
        )


class SetStatusTests(ChecklistTestBase):
    def test_done_with_explicit_date(self):
        entry = set_checklist_status(self.emp, self.avsec, CHECKLIST_DONE, completed_on=date(2026, 3, 1))
        self.assertEqual(entry.status, CHECKLIST_DONE)
        self.assertEqual(entry.completed_on, date(2026, 3, 1))

    def test_done_without_date_defaults_to_today(self):
        entry = set_checklist_status(self.emp, self.avsec, CHECKLIST_DONE)
        self.assertEqual(entry.completed_on, timezone.localdate())

    def test_non_done_statuses_clear_the_date(self):
        set_checklist_status(self.emp, self.avsec, CHECKLIST_DONE, completed_on=date(2026, 3, 1))
        for status in (CHECKLIST_PENDING, CHECKLIST_NOT_APPLICABLE):
            entry = set_checklist_status(
                self.emp, self.avsec, status, completed_on=date(2026, 3, 1)
            )
            self.assertEqual(entry.status, status)
            self.assertIsNone(entry.completed_on)

    def test_updating_reuses_the_same_row(self):
        set_checklist_status(self.emp, self.avsec, CHECKLIST_PENDING)
        set_checklist_status(self.emp, self.avsec, CHECKLIST_DONE)
        self.assertEqual(EmployeeChecklistEntry.objects.filter(employee=self.emp).count(), 1)

    def test_records_who_marked_it(self):
        entry = set_checklist_status(self.emp, self.avsec, CHECKLIST_DONE, marked_by=self.user)
        self.assertEqual(entry.marked_by, self.user)

    def test_items_are_tracked_independently(self):
        set_checklist_status(self.emp, self.avsec, CHECKLIST_DONE)
        set_checklist_status(self.emp, self.police, CHECKLIST_NOT_APPLICABLE)
        statuses = dict(self.emp.checklist_entries.values_list("item__name", "status"))
        self.assertEqual(
            statuses,
            {"AVSEC Training": CHECKLIST_DONE, "Police Verification": CHECKLIST_NOT_APPLICABLE},
        )

    def test_unknown_status_rejected(self):
        with self.assertRaises(ValueError):
            set_checklist_status(self.emp, self.avsec, "complete")
        self.assertFalse(EmployeeChecklistEntry.objects.exists())

    def test_cross_organization_rejected(self):
        foreign_item = ChecklistItem.objects.get(organization=self.other_org, name="AVSEC Training")
        with self.assertRaises(ValueError):
            set_checklist_status(self.emp, foreign_item, CHECKLIST_DONE)
        self.assertFalse(EmployeeChecklistEntry.objects.exists())


class EntryIntegrityTests(ChecklistTestBase):
    def test_database_refuses_a_date_on_a_non_done_entry(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmployeeChecklistEntry.objects.create(
                employee=self.emp, item=self.avsec,
                status=CHECKLIST_PENDING, completed_on=date(2026, 3, 1),
            )

    def test_database_refuses_duplicate_entries(self):
        EmployeeChecklistEntry.objects.create(employee=self.emp, item=self.avsec)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmployeeChecklistEntry.objects.create(employee=self.emp, item=self.avsec)

    def test_model_validation_rejects_cross_org_entry(self):
        foreign_item = ChecklistItem.objects.get(organization=self.other_org, name="AVSEC Training")
        entry = EmployeeChecklistEntry(employee=self.emp, item=foreign_item)
        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_deleting_an_employee_removes_their_entries(self):
        set_checklist_status(self.emp, self.avsec, CHECKLIST_DONE)
        self.emp.delete()
        self.assertFalse(EmployeeChecklistEntry.objects.exists())
        self.assertTrue(ChecklistItem.objects.filter(pk=self.avsec.pk).exists())
