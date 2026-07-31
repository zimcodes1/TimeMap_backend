from accounts.permissions import (
    IsAdminUserRole,
    IsPasswordResetDone,
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Facility, Venue
from .serializers import FacilitySerializer, VenueSerializer


class FacilityViewSet(viewsets.ModelViewSet):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsPasswordResetDone(), IsAdminUserRole()]
        return super().get_permissions()


class VenueViewSet(viewsets.ModelViewSet):
    serializer_class = VenueSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        user = self.request.user
        dept_qs = get_user_scope_departments(user)
        fac_qs = get_user_scope_faculties(user)
        sch_qs = get_user_scope_schools(user)

        # Scoped queryset for venues owned at or above user scope
        scope_filter = (
            Q(owning_level=Venue.OwningLevel.DEPARTMENT, owning_department__in=dept_qs)
            | Q(owning_level=Venue.OwningLevel.FACULTY, owning_faculty__in=fac_qs)
            | Q(owning_level=Venue.OwningLevel.SCHOOL, owning_school__in=sch_qs)
        )

        return Venue.objects.filter(scope_filter).distinct()

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsPasswordResetDone(), IsAdminUserRole()]
        return super().get_permissions()

    @extend_schema(summary="Deactivate a venue", responses={200: VenueSerializer})
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        venue = self.get_object()
        venue.is_active = False
        venue.save(update_fields=["is_active"])
        return Response(VenueSerializer(venue).data, status=status.HTTP_200_OK)

    @extend_schema(summary="Activate a venue", responses={200: VenueSerializer})
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        venue = self.get_object()
        venue.is_active = True
        venue.save(update_fields=["is_active"])
        return Response(VenueSerializer(venue).data, status=status.HTTP_200_OK)
