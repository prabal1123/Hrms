import re

from django.contrib.auth.models import User

from employees.models import Employee

# Only strings made of digits and common phone punctuation are treated as phones.
PHONE_PATTERN = re.compile(r"^[\d\s\-\+\(\)\.]+$")
PHONE_MATCH_DIGITS = 10


def _last_digits(value):
    digits = re.sub(r"\D", "", value or "")
    return digits[-PHONE_MATCH_DIGITS:] if len(digits) >= PHONE_MATCH_DIGITS else ""


def _find_by_email(identifier):
    # The unique index from 4a guarantees at most one match for non-blank emails.
    return User.objects.filter(email__iexact=identifier).first()


def _find_by_username(identifier):
    exact = User.objects.filter(username=identifier).first()
    if exact:
        return exact
    matches = list(User.objects.filter(username__iexact=identifier)[:2])
    return matches[0] if len(matches) == 1 else None


def _find_by_phone(identifier):
    target = _last_digits(identifier)
    if not target:
        return None

    # Phone is encrypted, so it can't be queried in the DB. Only employees
    # with a linked login can be login candidates; decrypt and compare here.
    user_ids = set()
    for employee in Employee.objects.filter(user__isnull=False).only("id", "user_id", "phone"):
        if _last_digits(employee.phone) == target:
            user_ids.add(employee.user_id)

    # Zero or several different users: treat as not found, never guess.
    if len(user_ids) != 1:
        return None
    return User.objects.filter(pk=user_ids.pop()).first()


def find_user(identifier):
    """
    Return the User matching an email, username or phone number, or None.
    Only finds the user. It never checks passwords or decides routing.
    """
    identifier = (identifier or "").strip()
    if not identifier:
        return None

    if "@" in identifier:
        return _find_by_email(identifier)

    user = _find_by_username(identifier)
    if user:
        return user

    if PHONE_PATTERN.match(identifier):
        return _find_by_phone(identifier)

    return None