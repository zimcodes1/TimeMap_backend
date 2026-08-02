from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeviceTokenViewSet, NotificationViewSet

router = DefaultRouter()
router.register("inbox", NotificationViewSet, basename="notification-inbox")
router.register("devices", DeviceTokenViewSet, basename="device-token")

urlpatterns = [
    path("", include(router.urls)),
]
