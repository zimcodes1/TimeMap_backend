from accounts.permissions import IsAdminUserRole, IsPasswordResetDone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AdminAnalyticsResponseSerializer,
    AnalyticsQueryParamSerializer,
    ClassRepAnalyticsResponseSerializer,
    LecturerAnalyticsResponseSerializer,
)
from .services import (
    get_admin_analytics,
    get_class_rep_analytics,
    get_lecturer_analytics,
)


class ClassRepAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    @extend_schema(
        summary="Class Representative Lecture Hold Analytics",
        parameters=[AnalyticsQueryParamSerializer],
        responses={200: ClassRepAnalyticsResponseSerializer},
    )
    def get(self, request):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        data = get_class_rep_analytics(
            student_user=request.user,
            start_date=start_date,
            end_date=end_date,
        )
        return Response(data, status=status.HTTP_200_OK)


class LecturerAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    @extend_schema(
        summary="Lecturer Lecture Hold Analytics",
        parameters=[AnalyticsQueryParamSerializer],
        responses={200: LecturerAnalyticsResponseSerializer},
    )
    def get(self, request):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        course_id = request.query_params.get("course_id")

        data = get_lecturer_analytics(
            lecturer_user=request.user,
            start_date=start_date,
            end_date=end_date,
            course_id=course_id,
        )
        return Response(data, status=status.HTTP_200_OK)


class AdminAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsPasswordResetDone, IsAdminUserRole]

    @extend_schema(
        summary="Admin Scope & Lecturer Analytics",
        parameters=[AnalyticsQueryParamSerializer],
        responses={200: AdminAnalyticsResponseSerializer},
    )
    def get(self, request):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        lecturer_id = request.query_params.get("lecturer_id")
        course_id = request.query_params.get("course_id")

        data = get_admin_analytics(
            admin_user=request.user,
            start_date=start_date,
            end_date=end_date,
            lecturer_id=lecturer_id,
            course_id=course_id,
        )
        return Response(data, status=status.HTTP_200_OK)
