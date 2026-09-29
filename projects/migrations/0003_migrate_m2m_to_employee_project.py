from django.db import migrations


def copy_m2m_to_fk(apps, schema_editor):
    """
    Business rule change: an employee now belongs to at most ONE project
    (Employee.project), instead of the old many-to-many Project.employees.

    For each project, assign it to every employee currently linked to it via
    the old M2M who doesn't already have a project set. If an employee was
    linked to more than one project under the old M2M, they keep the first
    project encountered here (ordered by Project.created_at) and a warning
    is printed so it can be reviewed manually after migrating.
    """
    Project = apps.get_model('projects', 'Project')
    Employee = apps.get_model('employees', 'Employee')

    reassigned_conflicts = []

    for project in Project.objects.order_by('created_at', 'id'):
        employee_ids = list(project.employees.values_list('id', flat=True))
        for employee_id in employee_ids:
            current_project_id = Employee.objects.filter(pk=employee_id).values_list(
                'project_id', flat=True
            ).first()
            if current_project_id is None:
                Employee.objects.filter(pk=employee_id).update(project_id=project.id)
            elif current_project_id != project.id:
                reassigned_conflicts.append((employee_id, current_project_id, project.id))

    if reassigned_conflicts:
        print(
            "\n[projects.0003] NOTE: the following employees were linked to more "
            "than one project under the old many-to-many relationship. Each kept "
            "their FIRST project assignment; review these manually if the wrong "
            "one 'won':"
        )
        for employee_id, kept_project_id, skipped_project_id in reassigned_conflicts:
            print(
                f"  employee_id={employee_id} kept project_id={kept_project_id}, "
                f"did NOT get project_id={skipped_project_id}"
            )


def restore_fk_to_m2m(apps, schema_editor):
    """Reverse: repopulate the M2M from Employee.project."""
    Employee = apps.get_model('employees', 'Employee')

    for employee in Employee.objects.exclude(project_id=None):
        employee.project.employees.add(employee)


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_project_employees'),
        ('employees', '0014_employee_project'),
    ]

    operations = [
        migrations.RunPython(copy_m2m_to_fk, restore_fk_to_m2m),
    ]