# from django import forms
# from employees.models import Employee
# from .models import Project, Action

# class ProjectForm(forms.ModelForm):
#     class Meta:
#         model = Project
#         fields = ["name", "description", "employees"]
#         widgets = {
#             "description": forms.Textarea(attrs={"rows": 3}),
#             "employees": forms.CheckboxSelectMultiple(),
#         }

#     def __init__(self, *args, organization=None, **kwargs):
#         super().__init__(*args, **kwargs)
#         if organization:
#             self.fields["employees"].queryset = Employee.objects.filter(
#                 organization=organization,
#                 is_active=True
#             )

# class ActionForm(forms.ModelForm):
#     class Meta:
#         model = Action
#         fields = ["title", "description", "employee", "status", "due_date"]
#         widgets = {
#             "description": forms.Textarea(attrs={"rows": 3}),
#             "due_date": forms.DateInput(attrs={"type": "date"}),
#         }

#     def __init__(self, *args, project=None, **kwargs):
#         super().__init__(*args, **kwargs)
#         if project:
#             self.fields["employee"].queryset = Employee.objects.filter(
#                 organization=project.organization,
#                 is_active=True
#             )


from django import forms
from employees.models import Employee
from .models import Project, Action

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "employees"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            # The CheckboxSelectMultiple widget has been removed from here
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["employees"].queryset = Employee.objects.filter(
                organization=organization,
                is_active=True
            )

class ActionForm(forms.ModelForm):
    class Meta:
        model = Action
        fields = ["title", "description", "employee", "status", "due_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project:
            self.fields["employee"].queryset = Employee.objects.filter(
                organization=project.organization,
                is_active=True
            )