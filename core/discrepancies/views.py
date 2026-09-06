from accounts.models import AdminOfficer
from accounts.permissions import (
    IsAdminUserRole,
    IsPasswordResetDone,
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from hierarchy.models import Department, Faculty
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from .models import AuditLog, DiscrepancyRequest
from .serializers import AuditLogSerializer, DiscrepancyRequestSerializer
from .services import (
    approve_discrepancy_request,
    reject_discrepancy_request,
    withdraw_discrepancy_request,
)


class DiscrepancyRequestViewSet(viewsets.ModelViewSet):
    serializer_class = DiscrepancyRequestSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, IsAdminUserRole]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or user.role != "admin" or not hasattr(user, "admin_profile") or not user.admin_profile:
            return DiscrepancyRequest.objects.none()

        admin_prof = user.admin_profile
        base_qs = DiscrepancyRequest.objects.all()

        if admin_prof.level == AdminOfficer.Level.DEPARTMENT:
            # Department admins do not oversee lower admins; they only see requests initiated by them or routed to them
            base_qs = base_qs.filter(
                Q(initiated_by=user) | Q(routed_to=admin_prof)
            )

        elif admin_prof.level == AdminOfficer.Level.FACULTY:
            # Faculty admins see: initiated by them, routed to them, or involving departments under their faculty
            if admin_prof.scope_faculty:
                dept_ids = Department.objects.filter(faculty=admin_prof.scope_faculty).values_list("id", flat=True)
                base_qs = base_qs.filter(
                    Q(initiated_by=user)
                    | Q(routed_to=admin_prof)
                    | Q(routed_to__scope_department_id__in=dept_ids)
                    | Q(initiated_by__admin_profile__scope_department_id__in=dept_ids)
                    | Q(proposed_venue__owning_department_id__in=dept_ids)
                    | Q(lecture_session__timetable_entry__course__owning_department_id__in=dept_ids)
                    | Q(timetable_entry__course__owning_department_id__in=dept_ids)
                )
            else:
                base_qs = base_qs.filter(Q(initiated_by=user) | Q(routed_to=admin_prof))

        elif admin_prof.level == AdminOfficer.Level.SCHOOL:
            # School admins oversee faculties and departments in their school
            if admin_prof.scope_school:
                dept_ids = Department.objects.filter(faculty__school=admin_prof.scope_school).values_list("id", flat=True)
                fac_ids = Faculty.objects.filter(school=admin_prof.scope_school).values_list("id", flat=True)
                base_qs = base_qs.filter(
                    Q(initiated_by=user)
                    | Q(routed_to=admin_prof)
                    | Q(routed_to__scope_faculty_id__in=fac_ids)
                    | Q(routed_to__scope_department_id__in=dept_ids)
                    | Q(initiated_by__admin_profile__scope_department_id__in=dept_ids)
                    | Q(proposed_venue__owning_department_id__in=dept_ids)
                    | Q(proposed_venue__owning_faculty_id__in=fac_ids)
                    | Q(lecture_session__timetable_entry__course__owning_department_id__in=dept_ids)
                    | Q(timetable_entry__course__owning_department_id__in=dept_ids)
                )
            else:
                base_qs = base_qs.filter(Q(initiated_by=user) | Q(routed_to=admin_prof))

        # Filter by department query param (for overseeing admins)
        department_param = self.request.query_params.get("department")
        if department_param:
            try:
                dept_id = int(department_param)
                allowed_depts = get_user_scope_departments(user)
                if not allowed_depts.filter(id=dept_id).exists():
                    return DiscrepancyRequest.objects.none()

                base_qs = base_qs.filter(
                    Q(routed_to__scope_department_id=dept_id)
                    | Q(initiated_by__admin_profile__scope_department_id=dept_id)
                    | Q(proposed_venue__owning_department_id=dept_id)
                    | Q(lecture_session__timetable_entry__course__owning_department_id=dept_id)
                    | Q(timetable_entry__course__owning_department_id=dept_id)
                )
            except (ValueError, TypeError):
                pass

        # Filter by status if provided
        status_param = self.request.query_params.get("status")
        if status_param:
            base_qs = base_qs.filter(status=status_param)

        # Filter by request type if provided
        req_type_param = self.request.query_params.get("request_type")
        if req_type_param:
            base_qs = base_qs.filter(request_type=req_type_param)

        # Sub-tab scope filter (e.g. routed to me, or initiated by me)
        scope_param = self.request.query_params.get("scope")
        if scope_param == "routed":
            base_qs = base_qs.filter(routed_to=admin_prof)
        elif scope_param == "initiated":
            base_qs = base_qs.filter(initiated_by=user)

        return base_qs.distinct().order_by("-created_at")

    def get_object(self):
        return super().get_object()

    def perform_create(self, serializer):
        serializer.save()

    @extend_schema(summary="Approve a pending discrepancy request", responses={200: DiscrepancyRequestSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        discrepancy = self.get_object()
        approved = approve_discrepancy_request(discrepancy, request.user)
        serializer = self.get_serializer(approved)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(summary="Reject a pending discrepancy request", responses={200: DiscrepancyRequestSerializer})
    @action(detail=True, methods=["post"])
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
