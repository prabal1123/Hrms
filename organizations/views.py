from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import OrganizationForm
from .models import Organization, OrganizationMember

@login_required
def create_organization(request):
    # One organization per user in this basic version.
    existing = OrganizationMember.objects.filter(user=request.user).first()
    if existing:
        return redirect("organization_detail", pk=existing.organization_id)

    if request.method == "POST":
        form = OrganizationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                org = form.save(commit=False)
                org.created_by = request.user
                org.save()

                # Silent owner membership creation.
                OrganizationMember.objects.create(
                    organization=org,
                    user=request.user,
                    role="owner",
                )
            return redirect("organization_detail", pk=org.pk)
    else:
        form = OrganizationForm()

    return render(request, "organizations/create.html", {"form": form})

@login_required
def organization_detail(request, pk):
    membership = get_object_or_404(
        OrganizationMember.objects.select_related("organization"),
        organization_id=pk,
        user=request.user,
    )
    
    # Block regular members from viewing the organization overview page
    if membership.role == 'member':
        messages.error(request, "Access restricted to management.")
        return redirect("employee_dashboard", org_id=pk)

    org = membership.organization
    projects = org.projects.all().order_by("-created_at")
    return render(
        request,
        "organizations/detail.html",
        {"organization": org, "membership": membership, "projects": projects},
    )