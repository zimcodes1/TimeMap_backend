from accounts.permissions import IsPasswordResetDone
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import DeviceToken, Notification
from .serializers import DeviceTokenSerializer, NotificationSerializer
from .services import deactivate_device_token


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by("-created_at")

    @extend_schema(summary="Mark notification as read", responses={200: NotificationSerializer})
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        if not notification.read_at:
            notification.read_at = timezone.now()
            notification.save()
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)

    @extend_schema(summary="Mark all inbox notifications as read", responses={200: dict})
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        updated_count = Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response({"message": f"Marked {updated_count} notifications as read.", "updated_count": updated_count}, status=status.HTTP_200_OK)

    @extend_schema(summary="Get unread notification count", responses={200: dict})
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)


class DeviceTokenViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = DeviceTokenSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        return DeviceToken.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save()

    @extend_schema(summary="Deactivate a device token", responses={200: dict})
    @action(detail=False, methods=["post"])
    def deactivate(self, request):
        fcm_token = request.data.get("fcm_token")
        if not fcm_token:
            return Response({"fcm_token": "This field is required."}, status=status.HTTP_400_BAD_REQUEST)

        success = deactivate_device_token(user=request.user, fcm_token=fcm_token)
        return Response({"message": "Device token deactivated successfully.", "success": success}, status=status.HTTP_200_OK)
