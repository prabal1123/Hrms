from organizations.models import OrganizationMember
from projects.models import Project

def user_organizations(request):
    if not request.user.is_authenticated:
        return {
            "user_organizations": [],
            "sidebar_projects": [],
            "current_org": None,
        }

    memberships = list(
        OrganizationMember.objects.filter(user=request.user).select_related("organization")
    )

    # Use request.current_org if set; otherwise fallback to user's first organization.
    current_org = getattr(request, "current_org", None)
    if not current_org and memberships:
        current_org = memberships[0].organization

    # Resolve the user's membership for the current organization once.
    # Templates can then use current_membership.role directly.
    current_membership = None
    if current_org:
        for membership in memberships:
            if membership.organization_id == current_org.id:
                current_membership = membership
                break

    sidebar_projects = []
    if current_org:
        sidebar_projects = Project.objects.filter(organization=current_org)

    return {
        "user_organizations": memberships,
        "current_org": current_org,
        "current_membership": current_membership,
        "sidebar_projects": sidebar_projects,
    }

current_organization = user_organizations
