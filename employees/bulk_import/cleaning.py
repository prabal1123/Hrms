"""
Turn a raw spreadsheet cell into a clean value for one column.

`clean_value(column, raw)` returns `(value, error)`:
  - empty cell            -> (None, None)   (required-ness is the caller's job)
  - valid                 -> (cleaned, None)
  - invalid               -> (None, "message")

Unlike the original importer, an invalid value ALWAYS returns an error, even
for optional columns. The caller decides whether that blocks the row (required
column) or becomes a warning and the value is dropped (optional column).
"""

import re
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from accounts.lookup import PHONE_PATTERN
from employees.validators import validate_aadhar, validate_pan

from .columns import AADHAR, DATE, EMAIL, FULL_NAME, IFSC, PAN, PHONE, TEXT

DATE_TOKEN_RE = re.compile(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}")
# Day-first (Indian convention) for the ambiguous numeric formats.
DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y.%m.%d")
MIN_YEAR, MAX_YEAR = 1900, 2100

# Login by phone matches on the last 10 digits (see accounts.lookup).
PHONE_MIN_DIGITS = 10
# Aadhar may be written 1234 5678 9012 or 1234-5678-9012; nothing else.
AADHAR_ALLOWED_RE = re.compile(r"^[\d\s\-]+$")

NAME_PART_MAX = 80  # Employee.first_name / last_name max_length


def parse_date_cell(raw):
    """Return (date | None, error | None). Accepts Excel dates and common text formats."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, None
    if isinstance(raw, datetime):  # check before date: datetime subclasses date
        parsed = raw.date()
    elif isinstance(raw, date):
        parsed = raw
    else:
        text = str(raw).strip()
        match = DATE_TOKEN_RE.search(text)
        candidate = match.group(0) if match else text.splitlines()[0].strip()
        parsed = None
        for fmt in DATE_FORMATS:
            try:
                parsed = datetime.strptime(candidate, fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            return None, f"Unrecognized date: {raw!r}"
    if not (MIN_YEAR <= parsed.year <= MAX_YEAR):
        return None, f"Date out of range: {raw!r}"
    return parsed, None


def _to_text(column, raw):
    """Cell -> stripped text. Excel numbers come back as int/float; whole floats lose the '.0'."""
    if raw is None:
        return "", None
    if isinstance(raw, bool):
        return None, f"{column.display_name} has an unexpected value."
    if isinstance(raw, (datetime, date)):
        return None, f"{column.display_name} looks like a date, expected text or a number."
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    return str(raw).strip(), None


def _too_long(column, text):
    return column.max_length is not None and len(text) > column.max_length


def _validator_error(validator, value):
    try:
        validator(value)
    except ValidationError as exc:
        return exc.messages[0]
    return None


def clean_value(column, raw):
    if column.kind == DATE:
        parsed, error = parse_date_cell(raw)
        return (None, f"{column.display_name}: {error}") if error else (parsed, None)

    text, error = _to_text(column, raw)
    if error:
        return None, error
    if not text:
        return None, None

    if column.kind == FULL_NAME:
        parts = " ".join(text.split()).split(" ", 1)
        first, last = parts[0], parts[1] if len(parts) > 1 else ""
        if len(first) > NAME_PART_MAX or len(last) > NAME_PART_MAX:
            return None, f"{column.display_name} is too long."
        return {"first_name": first, "last_name": last}, None

    if column.kind == EMAIL:
        email = text.lower()
        if _too_long(column, email):
            return None, f"{column.display_name} is too long (max {column.max_length} characters)."
        try:
            validate_email(email)
        except ValidationError:
            return None, f"{column.display_name} is not a valid email address."
        return email, None

    if column.kind == PHONE:
        digits = re.sub(r"\D", "", text)
        if not PHONE_PATTERN.match(text) or len(digits) < PHONE_MIN_DIGITS:
            return None, (
                f"{column.display_name} must contain at least {PHONE_MIN_DIGITS} digits "
                "and no letters."
            )
        if _too_long(column, text):
            return None, f"{column.display_name} is too long (max {column.max_length} characters)."
        return text, None

    if column.kind == AADHAR:
        if not AADHAR_ALLOWED_RE.match(text):
            return None, f"{column.display_name} may only contain digits, spaces and hyphens."
        digits = re.sub(r"\D", "", text)
        message = _validator_error(validate_aadhar, digits)
        return (None, message) if message else (digits, None)

    if column.kind == PAN:
        pan = re.sub(r"\s+", "", text).upper()
        message = _validator_error(validate_pan, pan)
        return (None, message) if message else (pan, None)

    if column.kind == IFSC:
        ifsc = re.sub(r"\s+", "", text).upper()
        if _too_long(column, ifsc):
            return None, f"{column.display_name} is too long (max {column.max_length} characters)."
        return ifsc, None

    if column.kind == TEXT:
        if not column.multiline:
            text = " ".join(text.split())
        if _too_long(column, text):
            return None, f"{column.display_name} is too long (max {column.max_length} characters)."
        return text, None

    raise ValueError(f"Unknown column kind: {column.kind!r}")
