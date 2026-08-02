from rest_framework import serializers

from .models import DeviceToken, Notification
from .services import register_device_token


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id",
            "recipient",
            "notification_type",
            "title",
            "body",
            "related_model",
            "related_id",
            "read_at",
            "is_read",
            "created_at",
        )
        read_only_fields = fields

    def get_is_read(self, obj):
        return obj.read_at is not None


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = (
            "id",
            "user",
            "fcm_token",
            "platform",
            "is_active",
            "registered_at",
        )
        read_only_fields = ("id", "user", "is_active", "registered_at")

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request else None

        token_obj = register_device_token(
            user=user,
            fcm_token=validated_data.get("fcm_token"),
            platform=validated_data.get("platform"),
        )
        return token_obj
