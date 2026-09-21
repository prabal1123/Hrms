from django.contrib import admin
from .models import Action, Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "created_at")
    filter_horizontal = ("employees",)

admin.site.register(Action)
