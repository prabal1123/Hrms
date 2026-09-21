"""
Column definitions and header matching for the employee bulk import.

The column list is plain Python (one place to edit). Header matching is
forgiving: case, extra spaces and full stops are ignored, and each column can
list aliases, so "PAN NO.", "Pan No" and "pan no" all match the same column.

Besides the fixed columns, every ACTIVE checklist item of the organization gets
a date column called "Date of <item name>" (e.g. "Date of AVSEC Training").
"""

from dataclasses import dataclass

from employees.models import ChecklistItem

# How many rows from the top are searched for the header row.
HEADER_SCAN_ROWS = 5

# Column kinds understood by employees.bulk_import.cleaning.clean_value
FULL_NAME = "full_name"
EMAIL = "email"
TEXT = "text"
PHONE = "phone"
DATE = "date"
AADHAR = "aadhar"
PAN = "pan"
IFSC = "ifsc"


@dataclass(frozen=True)
class ImportColumn:
    key: str  # Employee field name, "full_name", or "checklist:<item id>"
    label: str  # canonical header text
    display_name: str  # shown in messages and the preview table
    kind: str
    required: bool = False
    max_length: int | None = None
    aliases: tuple[str, ...] = ()
    multiline: bool = False
    item_id: int | None = None  # set only for checklist columns

    @property
    def is_checklist(self):
        return self.item_id is not None

    @property
    def all_labels(self):
        return (self.label,) + self.aliases


def normalize_label(value):
    """Lower-case, drop full stops, collapse whitespace: 'PAN  NO.' -> 'pan no'."""
    text = "" if value is None else str(value)
    text = text.replace(".", "").replace("\xa0", " ")
    return " ".join(text.lower().split())


# Order here is the order of the preview table.
STATIC_COLUMNS = (
    ImportColumn("full_name", "Emp Name", "Employee Name", FULL_NAME, required=True,
                 aliases=("Employee Name", "Name")),
    ImportColumn("email", "Mail ID", "Email", EMAIL, required=True, max_length=150,
                 aliases=("Email", "Email ID", "E-mail", "Mail")),
    ImportColumn("phone", "Mobile No.", "Mobile Number", PHONE, max_length=50,
                 aliases=("Mobile", "Mobile Number", "Phone", "Phone No.", "Contact No.")),
    ImportColumn("designation", "Designation", "Designation", TEXT, max_length=100),
    ImportColumn("aadhar_no", "Aadhar No.", "Aadhar Number", AADHAR,
                 aliases=("Aadhaar No.", "Aadhar", "Aadhaar", "Aadhar Number")),
    ImportColumn("pan_no", "PAN NO.", "PAN Number", PAN,
                 aliases=("PAN", "PAN Number")),
    ImportColumn("bank_name", "NAME OF BANK", "Bank Name", TEXT, max_length=100,
                 aliases=("Bank Name", "Bank")),
    ImportColumn("bank_account_no", "Bank A/C No.", "Bank Account No.", TEXT, max_length=50,
                 aliases=("Bank Account No.", "Bank Account Number", "Account No.", "A/C No.")),
    ImportColumn("ifsc_no", "IFSC No.", "IFSC Code", IFSC, max_length=20,
                 aliases=("IFSC", "IFSC Code")),
    # "Adress" is the spelling used in the existing sheets; both spellings match.
    ImportColumn("address", "Emp Adress", "Address", TEXT, max_length=500, multiline=True,
                 aliases=("Emp Address", "Address")),
    ImportColumn("date_joined", "Date of Joining", "Date of Joining", DATE,
                 aliases=("Joining Date", "DOJ")),
    ImportColumn("uan_no", "UAN No.", "UAN Number", TEXT, max_length=50,
                 aliases=("UAN", "UAN Number")),
    ImportColumn("esic_no", "ESIC No.", "ESIC Number", TEXT, max_length=50,
                 aliases=("ESIC", "ESIC Number", "ESI No.")),
)


def build_columns(organization):
    """Static columns plus one date column per active checklist item."""
    columns = list(STATIC_COLUMNS)
    items = ChecklistItem.objects.filter(organization=organization, is_active=True)
    for item in items:
        columns.append(
            ImportColumn(
                key=f"checklist:{item.id}",
                label=f"Date of {item.name}",
                display_name=f"{item.name} (date)",
                kind=DATE,
                item_id=item.id,
            )
        )
    return columns


def _label_map(columns):
    """normalized header text -> column. On a clash the earlier column wins."""
    mapping = {}
    for column in columns:
        for label in column.all_labels:
            mapping.setdefault(normalize_label(label), column)
    return mapping


def find_header_row(rows, columns):
    """Index of the first row (within HEADER_SCAN_ROWS) containing every required column, else None."""
    required = [c for c in columns if c.required]
    for index, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        cells = {normalize_label(cell) for cell in row if cell is not None}
        if required and all(
            any(normalize_label(label) in cells for label in column.all_labels)
            for column in required
        ):
            return index
    return None


def match_headers(header_row, columns):
    """
    Map columns to sheet positions.

    Returns (positions, ignored, duplicates):
      positions   {column.key: index in the row}
      ignored     header texts that matched no column (typos, extra columns)
      duplicates  header texts that repeat a column already matched
    """
    label_map = _label_map(columns)
    positions, ignored, duplicates = {}, [], []
    for index, cell in enumerate(header_row):
        normalized = normalize_label(cell)
        if not normalized:
            continue
        column = label_map.get(normalized)
        if column is None:
            ignored.append(str(cell).strip())
        elif column.key in positions:
            duplicates.append(str(cell).strip())
        else:
            positions[column.key] = index
    return positions, ignored, duplicates
