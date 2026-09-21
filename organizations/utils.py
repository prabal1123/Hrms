from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from organizations.models import Organization, OrganizationMember

def get_user_membership(user, organization):
    if not user.is_authenticated:
        raise PermissionDenied("Authentication required.")
    return OrganizationMember.objects.filter(user=user, organization=organization).first()

def require_org_role(allowed_roles=None):
    if allowed_roles is None:
        allowed_roles = ["owner", "admin", "manager", "member"]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            org_id = kwargs.get("org_id") or kwargs.get("organization_id")
            if not org_id and "pk" in kwargs:
                org_id = kwargs.get("pk")

            org = get_object_or_404(Organization, id=org_id)
            membership = get_user_membership(request.user, org)

            if not membership or membership.role not in allowed_roles:
                raise PermissionDenied("You do not have permission to access this organization.")

            request.org_membership = membership
            request.current_org = org
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
