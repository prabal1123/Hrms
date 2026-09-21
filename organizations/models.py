from django.contrib.auth.models import User
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Organization(models.Model):
    name = models.CharField(max_length=150)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="organizations_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class OrganizationMember(models.Model):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("member", "Member"),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="organization_memberships"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_org_user",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.organization.name} ({self.role})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Ensure user exists and import locally to prevent circular imports
        if self.user and (is_new or self.role in ["member", "manager", "admin"]):
            from employees.models import Employee
            Employee.objects.get_or_create(
                user=self.user,
                organization=self.organization,
                defaults={
                    "first_name": getattr(self.user, "first_name", "") or getattr(self.user, "email", "User").split("@")[0],
                    "last_name": getattr(self.user, "last_name", ""),
                    "is_active": True,
                }
            )
