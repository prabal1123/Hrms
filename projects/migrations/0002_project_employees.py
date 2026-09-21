from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0001_initial"),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="employees",
            field=models.ManyToManyField(blank=True, related_name="projects", to="employees.employee"),
        ),
    ]
