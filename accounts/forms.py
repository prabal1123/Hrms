from django import forms
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.contrib.auth.models import User

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class IdentifierForm(forms.Form):
    identifier = forms.CharField(
        label="Email, phone or username",
        max_length=254,
        strip=True,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )


class PasswordStepForm(forms.Form):
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autofocus": True, "autocomplete": "current-password"}
        ),
    )


# class FirstPasswordSetupForm(PasswordResetForm):
#     """
#     Django's reset form skips users with no usable password (exactly the
#     state of a freshly granted login). This subclass targets ONE specific
#     user, the one matched in login step 1, and includes them.
#     """

#     def __init__(self, *args, target_user=None, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.target_user = target_user

#     def get_users(self, email):
#         user = self.target_user
#         if user is not None and user.is_active and user.email:
#             yield user

class FirstPasswordSetupForm(PasswordResetForm):
    """
    Django's reset form skips users with no usable password (exactly the
    state of a freshly granted login). This subclass targets ONE specific
    user, the one matched in login step 1, and includes them.
    """

    def __init__(self, *args, target_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_user = target_user

    def get_users(self, email):
        user = self.target_user
        if user is not None and user.is_active and user.email:
            yield user

    def save(self, **kwargs):
        request = kwargs.get("request")
        if request:
            host = request.get_host()
            # If accessed via the EC2 IP without the port, force :8082
            if "18.61.200.14" in host and ":8082" not in host:
                kwargs["domain_override"] = "18.61.200.14:8082"
            else:
                kwargs["domain_override"] = host
        return super().save(**kwargs)