"""
Holds a validated preview between the "upload" request and the "confirm" request.

The preview contains Aadhar / PAN / bank numbers, and Django sessions live in
the database, so the payload is encrypted with the same Fernet key used for
the encrypted model fields before it goes into the session.
"""

import json
import uuid
from datetime import date

from employees.fields import FernetCipher

SESSION_KEY = "employee_import_batch"


def _text(value):
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def report_to_payload(report):
    return {
        "columns": [{"key": c.key, "name": c.display_name} for c in report.columns],
        "rows": [
            {
                "n": row.row_number,
                "status": row.status,
                "notes": row.notes,
                "values": {key: _text(value) for key, value in row.values.items()},
                "data": {
                    key: value.isoformat() if isinstance(value, date) else value
                    for key, value in row.data.items()
                },
                "checklist": {str(i): d.isoformat() for i, d in row.checklist.items()},
            }
            for row in report.rows
        ],
    }


def store_batch(request, org_id, payload):
    token = uuid.uuid4().hex
    request.session[SESSION_KEY] = {
        "token": token,
        "org_id": org_id,
        "blob": FernetCipher.encrypt(json.dumps(payload)),
    }
    return token


def load_batch(request, org_id, token):
    """The stored payload, or None if there is none / it belongs to another org / token is stale."""
    stored = request.session.get(SESSION_KEY)
    if not stored or not token or stored.get("token") != token or stored.get("org_id") != org_id:
        return None
    return json.loads(FernetCipher.decrypt(stored["blob"]))


def clear_batch(request):
    request.session.pop(SESSION_KEY, None)
