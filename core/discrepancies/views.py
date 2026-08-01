from accounts.permissions import (
    IsAdminUserRole,
    IsPasswordResetDone,
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AuditLog, DiscrepancyRequest
from .serializers import AuditLogSerializer, DiscrepancyRequestSerializer
from .services import (
    approve_discrepancy_request,
    reject_discrepancy_request,
    withdraw_discrepancy_request,
)


class DiscrepancyRequestViewSet(viewsets.ModelViewSet):
    serializer_class = DiscrepancyRequestSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        user = self.request.user
        if user.role != "admin" or not hasattr(user, "admin_profile"):
            return DiscrepancyRequest.objects.filter(initiated_by=user).distinct()

        admin_prof = user.admin_profile
        dept_qs = get_user_scope_departments(user)
        fac_qs = get_user_scope_faculties(user)
        sch_qs = get_user_scope_schools(user)

        return DiscrepancyRequest.objects.filter(
            Q(initiated_by=user)
            | Q(routed_to=admin_prof)
            | Q(proposed_venue__owning_department__in=dept_qs)
            | Q(proposed_venue__owning_faculty__in=fac_qs)
            | Q(proposed_venue__owning_school__in=sch_qs)
            | Q(timetable_entry__venue__owning_department__in=dept_qs)
            | Q(lecture_session__venue__owning_department__in=dept_qs)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save()

    @extend_schema(summary="Approve a pending discrepancy request", responses={200: DiscrepancyRequestSerializer})
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsPasswordResetDone, IsAdminUserRole])
    def approve(self, request, pk=None):
        discrepancy = self.get_object()
        approved = approve_discrepancy_request(discrepancy, request.user)
        serializer = self.get_serializer(approved)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(summary="Reject a pending discrepancy request", responses={200: DiscrepancyRequestSerializer})
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsPasswordResetDone, IsAdminUserRole])
    def reject(self, request, pk=None):
        discrepancy = self.get_object()
        reason = request.data.get("reason", "")
        rejected = reject_discrepancy_request(discrepancy, request.user, reason=reason)
        serializer = self.get_serializer(rejected)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(summary="Withdraw a pending discrepancy request", responses={200: DiscrepancyRequestSerializer})
    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        discrepancy = self.get_object()
        withdrawn = withdraw_discrepancy_request(discrepancy, request.user)
        serializer = self.get_serializer(withdrawn)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        user = self.request.user
        if user.role != "admin" or not hasattr(user, "admin_profile"):
            return AuditLog.objects.filter(actor=user).order_by("-timestamp")

        # Admin scope filtering
        dept_qs = get_user_scope_departments(user)
        dept_ids = list(dept_qs.values_list("id", flat=True))

        # Return audit logs created by actor in scope or targeting objects in scope
        return AuditLog.objects.order_by("-timestamp")
