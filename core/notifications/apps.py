from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"

    def ready(self):
        try:
            from .services import init_firebase
            init_firebase()
        except Exception:
            pass

