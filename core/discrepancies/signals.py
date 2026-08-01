import datetime
from accounts.models import User
from courses.models import Course, CourseAccessGrant
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.forms.models import model_to_dict
from scheduling.models import ExamSitting, LectureSession, TimetableEntry
from venues.models import Venue

from .middleware import get_current_user
from .models import AuditLog, DiscrepancyRequest

AUDITED_MODELS = [
    Venue,
    Course,
    CourseAccessGrant,
    TimetableEntry,
    LectureSession,
    ExamSitting,
    DiscrepancyRequest,
]


def resolve_user(obj):
    """
    Safely resolves a User model instance from either a User instance or a Profile (AdminOfficer, Student, LecturerStaff).
    """
    if not obj:
        return None
    if isinstance(obj, User):
        return obj
    if hasattr(obj, "user") and isinstance(obj.user, User):
        return obj.user
    return None


def clean_snapshot(dict_data):
    """
    Converts model_to_dict dictionary values to JSON-serializable types.
    """
    cleaned = {}
    for key, value in dict_data.items():
        if isinstance(value, (datetime.date, datetime.time, datetime.datetime)):
            cleaned[key] = value.isoformat()
        elif hasattr(value, "id"):
            cleaned[key] = value.id
        elif isinstance(value, (list, tuple)):
            cleaned[key] = [item.id if hasattr(item, "id") else str(item) for item in value]
        else:
            cleaned[key] = value
    return cleaned


@receiver(post_save)
def audit_log_post_save(sender, instance, created, **kwargs):
    if sender not in AUDITED_MODELS:
        return

    actor = resolve_user(get_current_user())

    if not actor:
        if hasattr(instance, "initiated_by"):
            actor = resolve_user(instance.initiated_by)
        elif hasattr(instance, "created_by"):
            actor = resolve_user(instance.created_by)

    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    after_snap = clean_snapshot(model_to_dict(instance))

    AuditLog.objects.create(
        actor=actor,
        action=action,
        target_model=sender.__name__,
        target_id=instance.id,
        before_snapshot=None if created else {},
        after_snapshot=after_snap,
    )


@receiver(post_delete)
def audit_log_post_delete(sender, instance, **kwargs):
    if sender not in AUDITED_MODELS:
        return

    actor = resolve_user(get_current_user())

    if not actor:
        if hasattr(instance, "initiated_by"):
            actor = resolve_user(instance.initiated_by)
        elif hasattr(instance, "created_by"):
            actor = resolve_user(instance.created_by)

    before_snap = clean_snapshot(model_to_dict(instance))

    AuditLog.objects.create(
        actor=actor,
        action=AuditLog.Action.DELETE,
        target_model=sender.__name__,
        target_id=instance.id,
        before_snapshot=before_snap,
        after_snapshot=None,
    )
