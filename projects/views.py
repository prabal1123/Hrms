from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from organizations.models import Organization
from organizations.utils import get_user_membership
from projects.models import Project, Action
from employees.models import Employee
from .forms import ProjectForm, ActionForm

@login_required
def organization_projects(request, org_id):
    membership = get_object_or_404(
        __import__("organizations.models", fromlist=["OrganizationMember"]).OrganizationMember,
        organization_id=org_id,
        user=request.user,
    )

    organization = membership.organization
    request.current_org = organization

    # Management sees every project in the organization.
    if membership.role in ["owner", "admin", "manager"]:
        projects = organization.projects.all().order_by("-created_at")

    # Members see only projects where their Employee is assigned.
    else:
        employee = Employee.objects.filter(
            organization=organization,
            user=request.user,
        ).first()

        if employee:
            projects = employee.projects.filter(
                organization=organization
            ).order_by("-created_at")
        else:
            projects = Project.objects.none()

    return render(request, "projects/list.html", {
        "organization": organization,
        "current_org": organization,
        "projects": projects,
        "membership": membership,
    })

@login_required
def project_detail(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("organization"),
        pk=pk,
        organization__members__user=request.user
    )
    request.current_org = project.organization
    return render(request, "projects/detail.html", {
        "project": project,
        "current_project": project,
        "current_org": project.organization,
        "organization": project.organization,
    })

@login_required
def project_dashboard(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("organization"),
        pk=pk,
        organization__members__user=request.user
    )
    request.current_org = project.organization

    membership = get_user_membership(request.user, project.organization)
    team = project.employees.filter(is_active=True)

    # Owner/admin/manager: full management view, unchanged from before.
    if membership and membership.role in ["owner", "admin", "manager"]:
        actions = project.actions.select_related("employee").all()
        return render(request, "projects/dashboard.html", {
            "project": project,
            "current_project": project,
            "current_org": project.organization,
            "organization": project.organization,
            "actions": actions,
            "team": team,
        })

    # Member: scoped view — only their own actions on this project, no
    # management controls (no "add action", no "edit team").
    employee = Employee.objects.filter(
        organization=project.organization,
        user=request.user
    ).first()

    my_actions = (
        project.actions.select_related("employee").filter(employee=employee)
        if employee else project.actions.none()
    )

    return render(request, "projects/dashboard_member.html", {
        "project": project,
        "current_project": project,
        "current_org": project.organization,
        "organization": project.organization,
        "actions": my_actions,
        "team": team,
    })

@login_required
def project_team(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("organization"),
        pk=pk,
        organization__members__user=request.user
    )
    request.current_org = project.organization

    membership = get_user_membership(request.user, project.organization)

    if not membership or membership.role == "member":
        from django.contrib import messages
        messages.error(request, "Access restricted to management.")
        return redirect("project_dashboard", pk=project.id)

    team_members = project.employees.filter(is_active=True)
    return render(request, "projects/team.html", {
        "project": project,
        "current_project": project,
        "current_org": project.organization,
        "organization": project.organization,
        "team_members": team_members,
    })

@login_required
def project_create(request, org_id):
    org = get_object_or_404(
        Organization,
        pk=org_id,
        members__user=request.user,
        members__role__in=["owner", "admin", "manager"]
    )
    request.current_org = org
    if request.method == "POST":
        form = ProjectForm(request.POST, organization=org)
        if form.is_valid():
            project = form.save(commit=False)
            project.organization = org
            project.save()
            form.save_m2m()
            return redirect("project_dashboard", pk=project.id)
    else:
        form = ProjectForm(organization=org)

    return render(request, "projects/create.html", {
        "form": form,
        "current_org": org,
        "organization": org,
    })

@login_required
def action_create(request, pk=None, project_id=None):
    project_pk = pk or project_id
    project = get_object_or_404(
        Project.objects.select_related("organization"),
        pk=project_pk,
        organization__members__user=request.user
    )
    request.current_org = project.organization

    membership = get_user_membership(request.user, project.organization)

    if not membership or membership.role == "member":
        from django.contrib import messages
        messages.error(request, "Access restricted to management.")
        return redirect("project_dashboard", pk=project.id)

    if request.method == "POST":
        form = ActionForm(request.POST, project=project)
        if form.is_valid():
            action = form.save(commit=False)
            action.project = project
            action.save()
            return redirect("project_dashboard", pk=project.id)
    else:
        form = ActionForm(project=project)

    return render(request, "projects/action_form.html", {
        "form": form,
        "project": project,
        "current_project": project,
        "current_org": project.organization,
        "organization": project.organization,
    })

create_project = project_create