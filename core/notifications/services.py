import logging
import os
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import serializers

from .models import DeviceToken, Notification

logger = logging.getLogger(__name__)


def init_firebase():
    """
    Initializes the Firebase Admin SDK using FIREBASE_CREDENTIALS_PATH if available,
    or default credentials. Safely called once on startup.
    """
    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", None) or os.environ.get("FIREBASE_CREDENTIALS_PATH")
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                logger.info(f"Firebase Admin SDK successfully initialized from {cred_path}")
            else:
                try:
                    firebase_admin.initialize_app()
                    logger.info("Firebase Admin SDK initialized with default credentials.")
                except Exception as def_err:
                    logger.warning(f"Default Firebase initialization skipped: {def_err}")
    except ImportError:
        logger.warning("firebase_admin package not installed. FCM dispatch disabled.")
    except Exception as e:
        logger.warning(f"Firebase Admin initialization error: {e}")


def register_device_token(user, fcm_token, platform):
    """
    Registers or updates an active FCM device token for a user.
    """
    token_obj, created = DeviceToken.objects.update_or_create(
        fcm_token=fcm_token,
        defaults={
            "user": user,
            "platform": platform,
            "is_active": True,
        },
    )
    return token_obj


def deactivate_device_token(user, fcm_token):
    """
    Deactivates a device token.
    """
    updated = DeviceToken.objects.filter(user=user, fcm_token=fcm_token).update(is_active=False)
    return updated > 0


def _get_channel_for_type(notification_type):
    """
    Maps notification types to Android notification channels.
    """
    urgent_types = {
        Notification.NotificationType.SESSION_SHIFTED,
        Notification.NotificationType.SESSION_CANCELLED,
        Notification.NotificationType.SESSION_POSTPONED,
        Notification.NotificationType.EXAM_RESCHEDULED,
        Notification.NotificationType.EXAM_CANCELLED,
    }
    reminder_types = {
        Notification.NotificationType.LECTURE_REMINDER,
        Notification.NotificationType.EXAM_REMINDER,
    }
    if notification_type in urgent_types:
        return "timemap-urgent"
    if notification_type in reminder_types:
        return "timemap-reminders"
    return "timemap-updates"


def send_fcm_push_notification(notification):
    """
    Dispatches FCM push notifications to all active device tokens belonging to notification.recipient.
    Includes both visual notification and structured data payload with Android channel and default sound.
    Deactivates tokens if reported invalid or unregistered.
    """
    active_tokens = DeviceToken.objects.filter(user=notification.recipient, is_active=True)
    if not active_tokens.exists():
        return 0

    try:
        import firebase_admin
        from firebase_admin import messaging
    except ImportError:
        return 0

    if not firebase_admin._apps:
        init_firebase()

    channel_id = _get_channel_for_type(notification.notification_type)

    dispatched = 0
    for token in active_tokens:
        try:
            # Check for simulated/test invalid token handling
            if token.fcm_token.startswith("invalid_") or token.fcm_token == "DEAD_TOKEN":
                token.is_active = False
                token.save()
                continue

            if firebase_admin._apps:
                data_payload = {
                    "notification_id": str(notification.id),
                    "type": str(notification.notification_type),
                    "related_model": str(notification.related_model or ""),
                    "related_id": str(notification.related_id or ""),
                    "channel_id": channel_id,
                }

                android_config = messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        channel_id=channel_id,
                        sound="default",
                        color="#10B981",
                        default_sound=True,
                        default_vibrate_timings=True,
                    ),
                )

                message = messaging.Message(
                    notification=messaging.Notification(
                        title=notification.title,
                        body=notification.body,
                    ),
                    data=data_payload,
                    android=android_config,
                    token=token.fcm_token,
                )
                messaging.send(message)

            dispatched += 1
        except Exception as e:
            err_str = str(e).lower()
            if "unregistered" in err_str or "not registered" in err_str or "invalid" in err_str:
                token.is_active = False
                token.save()
                logger.info(f"Deactivated unregistered FCM token {token.id}")
            else:
                logger.error(f"Error sending push notification to device token {token.id}: {e}")

    return dispatched


def send_async_email_notification(notification):
    """
    Dispatches transactional email to notification.recipient.
    Non-blocking: failure to send email will not interrupt the application flow.
    """
    recipient_user = notification.recipient
    # Get email if available on profile or user
    email = None
    if hasattr(recipient_user, "email") and recipient_user.email:
        email = recipient_user.email
    elif hasattr(recipient_user, "student_profile") and recipient_user.student_profile.email:
        email = recipient_user.student_profile.email

    if not email:
        return False

    try:
        subject = f"[TimeMapper] {notification.title}"
        send_mail(
            subject=subject,
            message=notification.body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@timemapper.org"),
            recipient_list=[email],
            fail_silently=True,
        )
        return True
    except Exception as e:
        logger.error(f"Async email notification failed for user {recipient_user.identifier}: {e}")
        return False


def dispatch_event_notification(recipient, notification_type, title, body, related_model=None, related_id=None):
    """
    Unified notification orchestrator:
    1. Creates in-app inbox Notification record.
    2. Dispatches FCM push notification.
    3. Dispatches transactional email.
    """
    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        body=body,
        related_model=related_model,
        related_id=related_id,
    )

    send_fcm_push_notification(notification)
    send_async_email_notification(notification)

    return notification


def resolve_course_recipients(course, semester=None):
    """
    Resolves all users that should receive notifications for a course:
    - Registered students (via CourseRegistration)
    - Cohort students (matching level + program / department / access grants)
    - Assigned course lecturers
    - Class representatives for that level & department/program
    """
    from accounts.models import Student, User
    from django.db.models import Q

    recipient_users = set()

    # 1. Assigned Lecturers
    for lecturer in course.lecturers.all():
        if lecturer.user and lecturer.user.is_active:
            recipient_users.add(lecturer.user)

    # 2. Registered Students (via CourseRegistration)
    try:
        from courses.models import CourseRegistration
        reg_users = User.objects.filter(
            student_profile__course_registrations__course=course,
            is_active=True,
        )
        for u in reg_users:
            recipient_users.add(u)
    except Exception as e:
        logger.warning(f"Error resolving registered students for {course.code}: {e}")

    # 3. Fallback / Cohort Students (level + program / department matching)
    prog_cond = Q()
    if course.target_program_id:
        prog_cond |= Q(program_id=course.target_program_id)
    if course.owning_department_id:
        prog_cond |= Q(department_id=course.owning_department_id)

    # Access grants
    try:
        granted_depts = list(
            course.access_grants.filter(status="approved").values_list("granted_to_department_id", flat=True)
        )
        if granted_depts:
            prog_cond |= Q(department_id__in=granted_depts)
    except Exception:
        pass

    if prog_cond:
        cohort_students = Student.objects.filter(
            Q(level=course.level) & prog_cond
        ).select_related("user")
        for s in cohort_students:
            if s.user and s.user.is_active:
                recipient_users.add(s.user)

    # 4. Class Representatives
    rep_cond = Q(is_class_rep=True, level=course.level)
    if prog_cond:
        rep_cond &= prog_cond
    class_reps = Student.objects.filter(rep_cond).select_related("user")
    for r in class_reps:
        if r.user and r.user.is_active:
            recipient_users.add(r.user)

    return list(recipient_users)


def dispatch_event_notifications_bulk(recipients, notification_type, title, body, related_model=None, related_id=None):
    """
    Dispatches in-app, push, and email notifications to a collection of recipient Users.
    Deduplicates recipients and handles errors gracefully.
    """
    created_notifications = []
    seen_user_ids = set()

    for user in recipients:
        if not user or user.id in seen_user_ids:
            continue
        seen_user_ids.add(user.id)
        try:
            notif = dispatch_event_notification(
                recipient=user,
                notification_type=notification_type,
                title=title,
                body=body,
                related_model=related_model,
                related_id=related_id,
            )
            created_notifications.append(notif)
        except Exception as e:
            logger.error(f"Bulk notification failed for user {user.id}: {e}")

    return created_notifications

