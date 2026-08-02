from accounts.models import User
from django.db import models


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        DISCREPANCY_APPROVED = "discrepancy_approved", "Discrepancy Approved"
        DISCREPANCY_REJECTED = "discrepancy_rejected", "Discrepancy Rejected"
        SESSION_SHIFTED = "session_shifted", "Session Shifted"
        SESSION_CANCELLED = "session_cancelled", "Session Cancelled"
        REPORTING_WINDOW_OPEN = "reporting_window_open", "Reporting Window Open"
        SESSION_UNREPORTED = "session_unreported", "Session Unreported"

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=40, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    body = models.TextField()
    related_model = models.CharField(max_length=100, null=True, blank=True)
    related_id = models.IntegerField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification to {self.recipient.identifier}: {self.title}"


class DeviceToken(models.Model):
    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"
        WEB = "web", "Web"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="device_tokens")
    fcm_token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"DeviceToken ({self.platform}) for {self.user.identifier}"
