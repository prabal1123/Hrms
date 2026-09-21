from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from employees import permissions
from employees.models import Employee
from organizations.models import Organization, OrganizationMember

User = get_user_model()

AADHAR = "123412341234"
PAN = "ABCDE1234F"
ACCOUNT = "50100123456789"


def raw_column(employee, column):
    """Read the value exactly as stored in the DB, bypassing decryption."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {column} FROM employees_employee WHERE id = %s", [employee.pk]
        )
        return cursor.fetchone()[0]


class EncryptedStorageTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user("owner", password="pw-owner-123")
        self.org = Organization.objects.create(name="Acme", created_by=owner)
        self.emp = Employee.objects.create(
            organization=self.org,
            first_name="Asha",
            designation="Security Officer",
            bank_name="SBI",
            ifsc_no="SBIN0001234",
            aadhar_no=AADHAR,
            pan_no=PAN,
            bank_account_no=ACCOUNT,
            uan_no="100200300400",
            esic_no="3100012345",
            address="12 MG Road, Mumbai 400001",
        )

    def test_sensitive_values_are_encrypted_at_rest(self):
        for column, plaintext in [
            ("aadhar_no", AADHAR),
            ("pan_no", PAN),
            ("bank_account_no", ACCOUNT),
            ("uan_no", "100200300400"),
            ("esic_no", "3100012345"),
            ("address", "12 MG Road, Mumbai 400001"),
        ]:
            stored = raw_column(self.emp, column)
            self.assertTrue(stored.startswith("gAAAAA"), column)
            self.assertNotIn(plaintext, stored, column)

    def test_values_round_trip_through_the_orm(self):
        fresh = Employee.objects.get(pk=self.emp.pk)
        self.assertEqual(fresh.aadhar_no, AADHAR)
        self.assertEqual(fresh.pan_no, PAN)
        self.assertEqual(fresh.bank_account_no, ACCOUNT)
        self.assertEqual(fresh.address, "12 MG Road, Mumbai 400001")

    def test_plain_fields_are_not_encrypted(self):
        self.assertEqual(raw_column(self.emp, "designation"), "Security Officer")
        self.assertEqual(raw_column(self.emp, "bank_name"), "SBI")
        self.assertEqual(raw_column(self.emp, "ifsc_no"), "SBIN0001234")

    def test_new_fields_are_optional(self):
        bare = Employee.objects.create(organization=self.org, first_name="Bare")
        fresh = Employee.objects.get(pk=bare.pk)
        for field in ("aadhar_no", "pan_no", "bank_account_no", "uan_no",
                      "esic_no", "address", "designation", "bank_name", "ifsc_no"):
            self.assertEqual(getattr(fresh, field), "", field)
        fresh.full_clean()  # blank values must validate


class ValidatorTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user("owner", password="pw-owner-123")
        org = Organization.objects.create(name="Acme", created_by=owner)
        self.emp = Employee.objects.create(organization=org, first_name="Asha")

    def assertInvalid(self, field, value):
        setattr(self.emp, field, value)
        with self.assertRaises(ValidationError) as ctx:
            self.emp.full_clean()
        self.assertIn(field, ctx.exception.message_dict)

    def test_valid_values_pass(self):
        self.emp.aadhar_no = AADHAR
        self.emp.pan_no = PAN
        self.emp.full_clean()

    def test_bad_aadhar_rejected(self):
        for bad in ("12345", "1234123412345", "12341234123a", "1234 1234 1234"):
            self.assertInvalid("aadhar_no", bad)

    def test_bad_pan_rejected(self):
        for bad in ("abcde1234f", "ABCDE12345", "ABCD1234FG", "ABCDE1234"):
            self.assertInvalid("pan_no", bad)


class SensitivePermissionTests(TestCase):
    """can_view_sensitive is stricter than salary: admins and self only."""

    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pw-owner-123")
        self.org = Organization.objects.create(name="Acme", created_by=self.owner)

        def member(user, role):
            membership = OrganizationMember.objects.create(
                organization=self.org, user=user, role=role
            )
            # OrganizationMember.save() auto-creates the linked Employee.
            employee = Employee.objects.get(organization=self.org, user=user)
            return membership, employee

        def new_user(username):
            return User.objects.create_user(username, password="pw-test-12345")

        self.owner_m, self.owner_e = member(self.owner, "owner")
        self.admin_m, self.admin_e = member(new_user("admin"), "admin")
        self.mgr_m, self.mgr_e = member(new_user("mgr"), "manager")
        self.mem_m, self.mem_e = member(new_user("mem"), "member")
        self.other_m, self.other_e = member(new_user("other"), "member")
        self.no_login = Employee.objects.create(organization=self.org, first_name="NoLogin")

        # mem reports to mgr
        self.mem_e.supervisor = self.mgr_e
        self.mem_e.save()

    def test_admin_and_owner_can_view_anyone(self):
        for membership in (self.owner_m, self.admin_m):
            for emp in (self.mem_e, self.mgr_e, self.no_login):
                self.assertTrue(permissions.can_view_sensitive(membership, emp))

    def test_supervisor_cannot_view_even_direct_reports(self):
        self.assertTrue(permissions.can_view_salary(self.mgr_m, self.mem_e))  # salary: yes
        self.assertFalse(permissions.can_view_sensitive(self.mgr_m, self.mem_e))  # sensitive: no

    def test_everyone_can_view_their_own(self):
        for membership, emp in ((self.mgr_m, self.mgr_e), (self.mem_m, self.mem_e)):
            self.assertTrue(permissions.can_view_sensitive(membership, emp))

    def test_member_cannot_view_others(self):
        self.assertFalse(permissions.can_view_sensitive(self.mem_m, self.other_e))
        self.assertFalse(permissions.can_view_sensitive(self.mem_m, self.no_login))

    def test_only_admins_can_edit(self):
        self.assertTrue(permissions.can_edit_sensitive(self.owner_m))
        self.assertTrue(permissions.can_edit_sensitive(self.admin_m))
        self.assertFalse(permissions.can_edit_sensitive(self.mgr_m))
        self.assertFalse(permissions.can_edit_sensitive(self.mem_m))


class DetailPageTests(TestCase):
    CARD = "Identity &amp; bank details"

    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pw-owner-123")
        self.org = Organization.objects.create(name="Acme", created_by=self.owner)
        OrganizationMember.objects.create(organization=self.org, user=self.owner, role="owner")

        self.mgr = User.objects.create_user("mgr", password="pw-test-12345")
        OrganizationMember.objects.create(organization=self.org, user=self.mgr, role="manager")
        self.mgr_e = Employee.objects.get(organization=self.org, user=self.mgr)

        self.mem = User.objects.create_user("mem", password="pw-test-12345")
        OrganizationMember.objects.create(organization=self.org, user=self.mem, role="member")
        self.emp = Employee.objects.get(organization=self.org, user=self.mem)
        self.emp.supervisor = self.mgr_e
        self.emp.aadhar_no = AADHAR
        self.emp.pan_no = PAN
        self.emp.designation = "Guard"
        self.emp.address = "12 MG Road"
        self.emp.save()
        self.url = reverse("employee_detail", args=[self.emp.uuid])

    def get(self, user):
        self.client.force_login(user)
        return self.client.get(self.url)

    def test_admin_sees_details_card(self):
        response = self.get(self.owner)
        self.assertContains(response, self.CARD)
        self.assertContains(response, AADHAR)
        self.assertContains(response, PAN)
        self.assertContains(response, "12 MG Road")
        self.assertContains(response, "Guard")

    def test_employee_sees_own_details(self):
        response = self.get(self.mem)
        self.assertContains(response, self.CARD)
        self.assertContains(response, AADHAR)

    def test_supervisor_does_not_see_details_but_still_sees_designation(self):
        response = self.get(self.mgr)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.CARD)
        self.assertNotContains(response, AADHAR)
        self.assertNotContains(response, PAN)
        self.assertNotContains(response, "12 MG Road")
        self.assertContains(response, "Guard")  # designation isn't sensitive
