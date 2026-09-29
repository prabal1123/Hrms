from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0003_migrate_m2m_to_employee_project'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='project',
            name='employees',
        ),
    ]