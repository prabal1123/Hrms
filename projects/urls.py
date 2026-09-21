from django.urls import path
from . import views

urlpatterns = [
    path("org/<int:org_id>/projects/", views.organization_projects, name="organization_projects"),
    path("org/<int:org_id>/create/", views.create_project, name="project_create"),
    path("<int:pk>/", views.project_detail, name="project_detail"),
    path("<int:pk>/dashboard/", views.project_dashboard, name="project_dashboard"),
    path("<int:pk>/team/", views.project_team, name="project_team"),
    path("<int:project_id>/actions/create/", views.action_create, name="action_create"),
]
