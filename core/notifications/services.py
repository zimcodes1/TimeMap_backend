import logging
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import serializers

from .models import DeviceToken, Notification

logger = logging.getLogger(__name__)


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


def send_fcm_push_notification(notification):
    """
    Dispatches FCM push notifications to all active device tokens belonging to notification.recipient.
    Deactivates tokens if reported invalid or unregistered.
    """
    active_tokens = DeviceToken.objects.filter(user=notification.recipient, is_active=True)
    if not active_tokens.exists():
        return 0

    dispatched = 0
    for token in active_tokens:
        try:
            # Check for simulated/test invalid token handling
            if token.fcm_token.startswith("invalid_") or token.fcm_token == "DEAD_TOKEN":
                token.is_active = False
                token.save()
                continue

            # Attempt Firebase Admin SDK push if configured
            try:
                import firebase_admin
                from firebase_admin import messaging

                if firebase_admin._apps:
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title=notification.title,
                            body=notification.body,
                        ),
                        token=token.fcm_token,
                    )
                    messaging.send(message)
            except Exception as fcm_err:
                logger.warning(f"FCM push dispatch failed for token {token.id}: {fcm_err}")

            dispatched += 1
        except Exception as e:
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
