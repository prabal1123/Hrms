# Django Organization / Project / Employee / Payroll MVP

A simple Django application implementing:

1. User registration
2. Registration redirects to login
3. First successful login redirects to Create Organization
4. Organization creator is silently inserted into OrganizationMember as `owner`
5. Organization page shows the user's organization and projects
6. No "create another organization" option after an organization exists
7. Create project
8. View project
9. Project dashboard + actions
10. Actions can be assigned to employees belonging to the project's organization
11. Employee management with salary, PF, ESI and other deductions
12. Employee detail page with separate Attendance and Leave sections
13. Payroll review table showing salary, deductions and calculated net salary

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Main URLs

- `/register/`
- `/login/`
- `/org/create/`
- `/org/<org_id>/`
- `/projects/org/<org_id>/create/`
- `/projects/<project_id>/`
- `/projects/<project_id>/dashboard/`
- `/employees/org/<org_id>/`
- `/employees/org/<org_id>/add/`
- `/employees/<employee_id>/`
- `/employees/org/<org_id>/payroll/`
- `/admin/`

## Data relationships

User
  -> OrganizationMember
  -> Organization

Organization
  -> Projects
  -> Employees

Project
  -> Actions
  -> Action.employee -> Employee

Employee
  -> Attendance
  -> Leave
  -> Payroll fields (salary, PF, ESI, other deductions)

## Important MVP notes

This is intentionally a basic application. Before production use, add:

- PostgreSQL instead of SQLite
- HTTPS and secure production settings
- Environment variables for secrets
- Email verification / OTP if required
- Password reset and MFA
- Fine-grained organization roles and permissions
- Audit logging
- Payroll period / payslip / approval models
- Attendance bulk upload and monthly attendance
- Leave balance and approval workflow
- Database backups and restore testing
- Rate limiting / brute-force protection
- Security headers and production deployment configuration
- Automated tests and CI/CD


### Navigation and project team
The updated MVP uses a simpler navigation model: Overview, Projects, Employees and Payroll. Selecting a project opens its dashboard directly. Each project has an explicit team: use **Manage team** to connect organization employees to the project. Project actions can only be assigned to employees who are members of that project team.

After updating an existing checkout, run:
```bash
python manage.py migrate
```
