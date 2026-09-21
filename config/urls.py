from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("org/", include("organizations.urls")),
    path("projects/", include("projects.urls")),
    path("employees/", include("employees.urls")),
]
