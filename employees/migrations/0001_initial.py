from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("organizations", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="Employee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(max_length=50)),
                ("first_name", models.CharField(max_length=80)),
                ("last_name", models.CharField(blank=True, max_length=80)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("date_joined", models.DateField(blank=True, null=True)),
                ("salary", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("pf", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("esi", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("other_deductions", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("is_active", models.BooleanField(default=True)),
                ("payroll_confirmed", models.BooleanField(default=False)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="employees", to="organizations.organization")),
            ],
            options={
                "ordering": ["first_name", "last_name"],
                "constraints": [
                    models.UniqueConstraint(fields=("organization", "employee_id"), name="unique_employee_id_per_org"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Attendance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("status", models.CharField(choices=[("present", "Present"), ("absent", "Absent"), ("half_day", "Half Day")], max_length=20)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance", to="employees.employee")),
            ],
            options={
                "ordering": ["-date"],
                "constraints": [
                    models.UniqueConstraint(fields=("employee", "date"), name="unique_attendance_per_day"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Leave",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("leave_type", models.CharField(choices=[("annual", "Annual"), ("sick", "Sick"), ("unpaid", "Unpaid"), ("other", "Other")], max_length=30)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("reason", models.TextField(blank=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leaves", to="employees.employee")),
            ],
            options={"ordering": ["-start_date"]},
        ),
    ]
