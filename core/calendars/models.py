from accounts.models import User
from django.db import models


class CalendarConnection(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="calendar_connection")
    provider = models.CharField(max_length=20, default="google")
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_expires_at = models.DateTimeField()
    connected_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"CalendarConnection ({self.provider}) for {self.user.identifier}"
