from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

from employees.models import Employee
from organizations.models import OrganizationMember


class GrantLoginError(Exception):
    """Raised with a user-friendly message when a login can't be created."""


def grant_login(employee):
    """
    Create a login (unusable password) for `employee`, link it, and add an
    Employee-level membership. Returns the new User.

    Order matters: employee.user is linked BEFORE the membership is created,
    because OrganizationMember.save() runs Employee.get_or_create(user, org)
    and would otherwise create a duplicate Employee.
    """
    try:
        with transaction.atomic():
            employee = (
                Employee.objects.select_for_update()
                .select_related("organization")
                .get(pk=employee.pk)
            )

            if employee.user_id:
                raise GrantLoginError("This employee already has a login.")

            email = (employee.email or "").strip().lower()
            if not email:
                raise GrantLoginError(
                    "Add an email to this employee before granting login."
                )
            if len(email) > 150:
                raise GrantLoginError("This email is too long to use as a username.")
            if (
                User.objects.filter(email__iexact=email).exists()
                or User.objects.filter(username__iexact=email).exists()
            ):
                raise GrantLoginError(
                    "Another account already uses this email."
                )

            user = User(
                username=email,
                email=email,
                first_name=employee.first_name,
                last_name=employee.last_name,
            )
            user.set_unusable_password()
            user.save()

            employee.user = user
            employee.save(update_fields=["user"])

            OrganizationMember.objects.create(
                organization=employee.organization,
                user=user,
                role="member",
            )
            return user
    except IntegrityError:
        raise GrantLoginError("Could not create the login. Please try again.")