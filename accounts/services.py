# from django.contrib.auth.models import User
# from django.db import IntegrityError, transaction
# from django.db.models import Q

# from employees.models import Employee
# from organizations.models import OrganizationMember


# class GrantLoginError(Exception):
#     """Raised with a user-friendly message when a login can't be created."""


# def grant_login(employee):
#     """
#     Create a login (unusable password) for `employee`, link it, and add an
#     Employee-level membership. Returns the new User.

#     Order matters: employee.user is linked BEFORE the membership is created,
#     because OrganizationMember.save() runs Employee.get_or_create(user, org)
#     and would otherwise create a duplicate Employee.
#     """
#     try:
#         with transaction.atomic():
#             employee = (
#                 Employee.objects.select_for_update()
#                 .select_related("organization")
#                 .get(pk=employee.pk)
#             )

#             if employee.user_id:
#                 raise GrantLoginError("This employee already has a login.")

#             email = (employee.email or "").strip().lower()
#             if not email:
#                 raise GrantLoginError(
#                     "Add an email to this employee before granting login."
#                 )
#             if len(email) > 150:
#                 raise GrantLoginError("This email is too long to use as a username.")
#             if (
#                 User.objects.filter(email__iexact=email).exists()
#                 or User.objects.filter(username__iexact=email).exists()
#             ):
#                 raise GrantLoginError(
#                     "Another account already uses this email."
#                 )

#             user = User(
#                 username=email,
#                 email=email,
#                 first_name=employee.first_name,
#                 last_name=employee.last_name,
#             )
#             user.set_unusable_password()
#             user.save()

#             employee.user = user
#             employee.save(update_fields=["user"])

#             OrganizationMember.objects.create(
#                 organization=employee.organization,
#                 user=user,
#                 role="member",
#             )
#             return user
#     except IntegrityError:
#         raise GrantLoginError("Could not create the login. Please try again.")

# def find_existing_login(email):
#     """
#     The User whose email or username equals `email` (case-insensitive), or None.

#     Raises GrantLoginError if the email matches more than one account: we never
#     guess which one is meant.
#     """
#     email = (email or "").strip().lower()
#     if not email:
#         return None
#     matches = list(
#         User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email))[:2]
#     )
#     if len(matches) > 1:
#         raise GrantLoginError(
#             "This email matches more than one account, so it can't be linked automatically."
#         )
#     return matches[0] if matches else None


# def link_existing_login(employee):
#     """
#     Link `employee` to the EXISTING login that uses their email, and add an
#     Employee-level membership in the employee's organization. Returns the User.

#     Used when the same person is added to a second organization: they keep one
#     login (and password) and get one Employee record per organization.

#     Only accounts that already belong to at least one organization can be
#     linked, so a registered account that has no organization yet is left alone
#     and can still create its own.

#     As in grant_login(), employee.user is linked BEFORE the membership is
#     created, so OrganizationMember.save() finds the employee instead of
#     creating a duplicate.
#     """
#     try:
#         with transaction.atomic():
#             employee = (
#                 Employee.objects.select_for_update()
#                 .select_related("organization")
#                 .get(pk=employee.pk)
#             )

#             if employee.user_id:
#                 raise GrantLoginError("This employee already has a login.")

#             user = find_existing_login(employee.email)
#             if user is None:
#                 raise GrantLoginError("No existing account uses this email.")

#             memberships = OrganizationMember.objects.filter(user=user)
#             if not memberships.exists():
#                 raise GrantLoginError(
#                     "This account isn't part of any organization yet, so it can't be added."
#                 )
#             if (
#                 memberships.filter(organization=employee.organization_id).exists()
#                 or Employee.objects.filter(
#                     organization=employee.organization_id, user=user
#                 ).exists()
#             ):
#                 raise GrantLoginError("This person is already in this organization.")

#             employee.user = user
#             employee.save(update_fields=["user"])

#             OrganizationMember.objects.create(
#                 organization=employee.organization,
#                 user=user,
#                 role="member",
#             )
#             return user
#     except IntegrityError:
#         raise GrantLoginError("Could not link the login. Please try again.")
    

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Q

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


def find_existing_login(email):
    """
    The User whose email or username equals `email` (case-insensitive), or None.

    Raises GrantLoginError if the email matches more than one account: we never
    guess which one is meant.
    """
    email = (email or "").strip().lower()
    if not email:
        return None
    matches = list(
        User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email))[:2]
    )
    if len(matches) > 1:
        raise GrantLoginError(
            "This email matches more than one account, so it can't be linked automatically."
        )
    return matches[0] if matches else None


def link_existing_login(employee):
    """
    Link `employee` to the EXISTING login that uses their email, and add an
    Employee-level membership in the employee's organization. Returns the User.

    Used when the same person is added to a second organization: they keep one
    login (and password) and get one Employee record per organization.

    Only accounts that already belong to at least one organization can be
    linked, so a registered account that has no organization yet is left alone
    and can still create its own.

    As in grant_login(), employee.user is linked BEFORE the membership is
    created, so OrganizationMember.save() finds the employee instead of
    creating a duplicate.
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

            user = find_existing_login(employee.email)
            if user is None:
                raise GrantLoginError("No existing account uses this email.")

            memberships = OrganizationMember.objects.filter(user=user)
            if not memberships.exists():
                raise GrantLoginError(
                    "This account isn't part of any organization yet, so it can't be added."
                )
            if (
                memberships.filter(organization=employee.organization_id).exists()
                or Employee.objects.filter(
                    organization=employee.organization_id, user=user
                ).exists()
            ):
                raise GrantLoginError("This person is already in this organization.")

            employee.user = user
            employee.save(update_fields=["user"])

            OrganizationMember.objects.create(
                organization=employee.organization,
                user=user,
                role="member",
            )
            return user
    except IntegrityError:
        raise GrantLoginError("Could not link the login. Please try again.")
    