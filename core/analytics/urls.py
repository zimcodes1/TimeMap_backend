from django.urls import path

from .views import AdminAnalyticsView, ClassRepAnalyticsView, LecturerAnalyticsView

urlpatterns = [
    path("class-rep/", ClassRepAnalyticsView.as_view(), name="analytics-class-rep"),
    path("lecturer/", LecturerAnalyticsView.as_view(), name="analytics-lecturer"),
    path("admin/", AdminAnalyticsView.as_view(), name="analytics-admin"),
]
