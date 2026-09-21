from django.urls import path
from .views import create_organization, organization_detail

urlpatterns = [
    path("create/", create_organization, name="organization_create"),
    path("<int:pk>/", organization_detail, name="organization_detail"),
]
