"""
Field validators for employee identity / statutory numbers.

Defined once here so the model, forms and the bulk importer all enforce the
same rules. Values are validated in their *normalized* form (Aadhar: digits
only, PAN: upper-case, no spaces); normalization itself is done by the caller
(the importer, or a form's clean method).
"""

from django.core.validators import RegexValidator

AADHAR_PATTERN = r"^\d{12}$"
PAN_PATTERN = r"^[A-Z]{5}\d{4}[A-Z]$"

AADHAR_MESSAGE = "Aadhar No. must be exactly 12 digits."
PAN_MESSAGE = "PAN No. format looks invalid (e.g. ABCDE1234F)."

validate_aadhar = RegexValidator(AADHAR_PATTERN, AADHAR_MESSAGE, code="invalid_aadhar")
validate_pan = RegexValidator(PAN_PATTERN, PAN_MESSAGE, code="invalid_pan")
