from django.db import migrations

# Frozen copy of the defaults at the time of this migration. Migrations must not
# import application code that can change later.
DEFAULT_ITEMS = ("AVSEC Training", "Police Verification")


def seed_default_items(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    ChecklistItem = apps.get_model("employees", "ChecklistItem")

    for org in Organization.objects.all():
        existing = {n.lower() for n in ChecklistItem.objects.filter(organization=org).values_list("name", flat=True)}
        order = 0
        for name in DEFAULT_ITEMS:
            order += 10
            if name.lower() not in existing:
                ChecklistItem.objects.create(organization=org, name=name, order=order)


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0009_onboarding_checklist"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        # Reverse is a no-op: removing items would also remove employees' entries.
        migrations.RunPython(seed_default_items, migrations.RunPython.noop),
    ]
