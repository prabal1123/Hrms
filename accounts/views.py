import logging
import time

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetConfirmView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import (
    FirstPasswordSetupForm,
    IdentifierForm,
    PasswordStepForm,
    RegisterForm,
)
from .lookup import find_user
from .services import public_domain
from organizations.models import OrganizationMember

logger = logging.getLogger(__name__)

SESSION_USER_KEY = "login_user_id"
SESSION_NEXT_KEY = "login_next"
SESSION_LAST_SENT_KEY = "setup_link_last_sent"
RESEND_SECONDS = 60


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Requirement: registration succeeds, then redirect to login.
            return redirect("login")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


def _safe_next(request, candidate):
    """Return `candidate` only if it points back to this site, else ''."""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return ""


def _pending_user(request):
    """The user matched in step 1 (stored in the session), or None."""
    user_id = request.session.get(SESSION_USER_KEY)
    if not user_id:
        return None
    return User.objects.filter(pk=user_id).first()


def _mask_email(email):
    """n***@example.com, so the page doesn't reveal the full address."""
    local, _, domain = (email or "").partition("@")
    if not domain:
        return "your email"
    return f"{local[:1]}***@{domain}"


def login_identifier(request):
    """Step 1: ask for email / phone / username and route accordingly."""
    if request.user.is_authenticated:
        return redirect("home")

    next_value = _safe_next(
        request, request.POST.get("next") or request.GET.get("next") or ""
    )

    if request.method == "POST":
        form = IdentifierForm(request.POST)
        if form.is_valid():
            user = find_user(form.cleaned_data["identifier"])
            request.session.pop(SESSION_USER_KEY, None)
            request.session[SESSION_NEXT_KEY] = next_value

            # Unknown or deactivated accounts both go to the denial page.
            if user is None or not user.is_active:
                return redirect("login_denied")

            request.session[SESSION_USER_KEY] = user.pk
            if not user.has_usable_password():
                return redirect("login_setup_pending")
            return redirect("login_password")
    else:
        # Arriving fresh (or via "Not you?") always starts over.
        request.session.pop(SESSION_USER_KEY, None)
        request.session[SESSION_NEXT_KEY] = next_value
        form = IdentifierForm()

    return render(request, "accounts/login.html", {"form": form, "next": next_value})


def login_password(request):
    """Step 2: password for the user matched in step 1."""
    if request.user.is_authenticated:
        return redirect("home")

    user = _pending_user(request)
    if user is None:
        return redirect("login")
    if not user.has_usable_password():
        return redirect("login_setup_pending")

    if request.method == "POST":
        form = PasswordStepForm(request.POST)
        if form.is_valid():
            authed = authenticate(
                request,
                username=user.get_username(),
                password=form.cleaned_data["password"],
            )
            if authed is not None:
                next_url = _safe_next(request, request.session.get(SESSION_NEXT_KEY, ""))
                login(request, authed)
                request.session.pop(SESSION_USER_KEY, None)
                request.session.pop(SESSION_NEXT_KEY, None)
                return redirect(next_url or "home")
            form.add_error(None, "Incorrect password. Please try again.")
    else:
        form = PasswordStepForm()

    return render(request, "accounts/login_password.html", {
        "form": form,
        "pending_user": user,
    })


def login_denied(request):
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "accounts/login_denied.html")


def login_setup_pending(request):
    """First-time setup: GET shows the page, POST emails a one-time link."""
    if request.user.is_authenticated:
        return redirect("home")

    user = _pending_user(request)
    if user is None:
        return redirect("login")
    if not user.is_active:
        return redirect("login_denied")
    if user.has_usable_password():
        return redirect("login_password")

    if request.method == "POST":
        now = int(time.time())
        last_sent = request.session.get(SESSION_LAST_SENT_KEY, 0)

        if now - last_sent < RESEND_SECONDS:
            messages.error(
                request,
                "A link was just sent. Please wait a minute before requesting another.",
            )
        elif not user.email:
            messages.error(
                request,
                "This account has no email on file. Please contact your admin.",
            )
        else:
            form = FirstPasswordSetupForm({"email": user.email}, target_user=user)
            if form.is_valid():
                try:
                    form.save(
                        request=request,
                        use_https=request.is_secure(),
                        domain_override=public_domain(request),
                        email_template_name="accounts/setup_email.txt",
                        subject_template_name="accounts/setup_email_subject.txt",
                    )
                    request.session[SESSION_LAST_SENT_KEY] = now
                    messages.success(
                        request,
                        f"Setup link sent to {_mask_email(user.email)}. "
                        "Check your inbox.",
                    )
                except Exception:
                    logger.exception("Could not send setup email")
                    messages.error(
                        request,
                        "We couldn't send the email right now. Please try again "
                        "later or contact your admin.",
                    )
            else:
                messages.error(request, "We couldn't send the email. Please contact your admin.")
        return redirect("login_setup_pending")

    return render(request, "accounts/login_setup_pending.html", {
        "pending_user": user,
        "masked_email": _mask_email(user.email),
    })


class PasswordSetupConfirmView(PasswordResetConfirmView):
    """Django's token-checked 'choose a password' view with our templates."""

    template_name = "accounts/password_setup_confirm.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, "Your password has been set. You can now log in."
        )
        return response


@login_required
def home(request):
    membership = (
        OrganizationMember.objects
        .select_related("organization")
        .filter(user=request.user)
        .first()
    )
    if not membership:
        return redirect("organization_create")

    if membership.role == "member":
        return redirect("employee_dashboard", org_id=membership.organization_id)

    return redirect("organization_detail", pk=membership.organization_id)