# from django.contrib.auth import views as auth_views
# from django.urls import path

# from .views import home, register_view

# urlpatterns = [
#     path("", home, name="home"),
#     path("register/", register_view, name="register"),
#     path(
#         "login/",
#         auth_views.LoginView.as_view(template_name="accounts/login.html"),
#         name="login",
#     ),
#     path(
#         "logout/",
#         auth_views.LogoutView.as_view(),
#         name="logout",
#     ),
# ]
from django.contrib.auth import views as auth_views
from django.urls import path

from .views import (
    PasswordSetupConfirmView,
    home,
    login_denied,
    login_identifier,
    login_password,
    login_setup_pending,
    register_view,
)

urlpatterns = [
    path("", home, name="home"),
    path("register/", register_view, name="register"),
    path("login/", login_identifier, name="login"),
    path("login/password/", login_password, name="login_password"),
    path("login/not-found/", login_denied, name="login_denied"),
    path("login/setup/", login_setup_pending, name="login_setup_pending"),
    path(
        "login/set-password/<uidb64>/<token>/",
        PasswordSetupConfirmView.as_view(),
        name="password_setup_confirm",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
]