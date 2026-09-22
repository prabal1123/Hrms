
from django.urls import path
from . import views

urlpatterns = [
    path("org/<int:org_id>/employees/", views.employee_list, name="employee_list"),
    path("org/<int:org_id>/employees/create/", views.employee_create, name="employee_create"),
    path("org/<int:org_id>/employees/import/", views.employee_import, name="employee_import"),
    path("org/<int:org_id>/employees/import/template/", views.employee_import_template, name="employee_import_template"),
    path("org/<int:org_id>/employees/import/problems/", views.employee_import_problems, name="employee_import_problems"),
    path("employees/<uuid:uuid>/", views.employee_detail, name="employee_detail"),
    path("org/<int:org_id>/payroll/", views.payroll, name="payroll"),
    path("org/<int:org_id>/attendance/", views.attendance_list, name="attendance_list"),
    path("employees/<int:employee_id>/attendance/create/", views.attendance_create, name="attendance_create"),
    path("org/<int:org_id>/leave/", views.leave_list, name="leave_list"),
    path("employees/<int:employee_id>/leave/create/", views.leave_create, name="leave_create"),
    path("org/<int:org_id>/my-attendance/", views.org_attendance_view, name="org_attendance"),
    path("org/<int:org_id>/dashboard/", views.employee_dashboard, name="employee_dashboard"),
    path("employees/<uuid:uuid>/edit/", views.employee_update, name="employee_update"),
    path("employees/<uuid:uuid>/deactivate/", views.employee_deactivate, name="employee_deactivate"),
    path("employees/<uuid:uuid>/grant-login/", views.employee_grant_login, name="employee_grant_login"),
    path("attendance/<int:pk>/edit/", views.attendance_update, name="attendance_update"),
    path("attendance/<int:pk>/delete/", views.attendance_delete, name="attendance_delete"),
    path("leave/<int:pk>/<str:action>/", views.leave_review, name="leave_review"),
    path("leave/<int:pk>/cancel/", views.leave_cancel, name="leave_cancel"),
    path("org/<int:org_id>/payroll/payslip/<int:employee_id>/", views.employee_payslip, name="employee_payslip"),
    path("org/<int:org_id>/my-payslips/", views.my_payslips, name="my_payslips"),
]