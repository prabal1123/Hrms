import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0013_employee_weekly_off_alter_employee_other_deductions'),
        ('projects', '0002_project_employees'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='project',
            field=models.ForeignKey(
                blank=True,
                help_text='Project this employee is assigned to. Leave blank for NA.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='team_members',
                to='projects.project',
            ),
        ),
    ]