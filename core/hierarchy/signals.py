from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Department, Program


@receiver(post_save, sender=Department)
def create_default_program(sender, instance, created, **kwargs):
    """
    Auto-create a default program when a new department is created.
    The default program has the same name as the department, a code
    derived from the department code, and the department's max_level.
    """
    if created:
        Program.objects.create(
            department=instance,
            name=instance.name,
            code=f"{instance.code}GEN",
            max_level=instance.max_level,
            is_default=True,
        )


@receiver(post_save, sender=Program)
def sync_department_max_level(sender, instance, **kwargs):
    """
    When a default program's max_level changes, sync it back to the department.
    """
    if instance.is_default:
        dept = instance.department
        if dept.max_level != instance.max_level:
            Department.objects.filter(pk=dept.pk).update(max_level=instance.max_level)
