from django.db.models.signals import post_save
from django.dispatch import receiver

from organizations.models import Organization

from .checklist import ensure_default_items


@receiver(post_save, sender=Organization)
def seed_checklist_for_new_organization(sender, instance, created, **kwargs):
    """Every new organization starts with the default checklist items."""
    if created:
        ensure_default_items(instance)
