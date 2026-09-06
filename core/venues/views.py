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
        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            return Venue.objects.all()

        if user.role == "admin" and hasattr(user, "admin_profile"):
            admin_prof = user.admin_profile
            level = admin_prof.level

            if level == "university":
                return Venue.objects.all()
            elif level == "school":
                if not admin_prof.scope_school:
                    return Venue.objects.none()
                return Venue.objects.filter(
                    Q(owning_level=Venue.OwningLevel.SCHOOL, owning_school=admin_prof.scope_school)
                    | Q(owning_level=Venue.OwningLevel.FACULTY, owning_faculty__school=admin_prof.scope_school)
                    | Q(owning_level=Venue.OwningLevel.DEPARTMENT, owning_department__faculty__school=admin_prof.scope_school)
                ).distinct()
            elif level == "faculty":
                if not admin_prof.scope_faculty:
                    return Venue.objects.none()
                return Venue.objects.filter(
                    Q(owning_level=Venue.OwningLevel.FACULTY, owning_faculty=admin_prof.scope_faculty)
                    | Q(owning_level=Venue.OwningLevel.DEPARTMENT, owning_department__faculty=admin_prof.scope_faculty)
                ).distinct()
            elif level == "department":
                if not admin_prof.scope_department:
                    return Venue.objects.none()
                return Venue.objects.filter(
                    Q(owning_level=Venue.OwningLevel.DEPARTMENT, owning_department=admin_prof.scope_department)
                    | Q(owning_level=Venue.OwningLevel.FACULTY, owning_faculty=admin_prof.scope_department.faculty)
                ).distinct()

        return Venue.objects.none()

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

    @extend_schema(summary="Get available time ranges for a venue on a given date (8am-6pm operating hours)")
    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
        import datetime
        from scheduling.models import LectureSession, TimetableEntry

        venue = self.get_object()
        date_str = request.query_params.get("date")
        if not date_str:
            date_val = datetime.date.today()
        else:
            try:
                date_val = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid date format, use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # Standard operating hours: 8:00 AM to 6:00 PM (08:00 to 18:00)
        day_start = datetime.time(8, 0, 0)
        day_end = datetime.time(18, 0, 0)

        # Find all active sessions on this venue for the given date
        sessions = LectureSession.objects.filter(
            venue=venue,
            session_date=date_val,
        ).exclude(status__in=[LectureSession.Status.CANCELLED, LectureSession.Status.POSTPONED]).order_by("session_start_time")

        booked_slots = []
        for s in sessions:
            booked_slots.append((s.session_start_time, s.session_end_time))

        entries = TimetableEntry.objects.filter(
            venue=venue,
            recurrence_start_date=date_val,
        ).exclude(status__in=[TimetableEntry.Status.CANCELLED, TimetableEntry.Status.POSTPONED]).order_by("start_time")

        for e in entries:
            if not any(b[0] == e.start_time and b[1] == e.end_time for b in booked_slots):
                booked_slots.append((e.start_time, e.end_time))

        booked_slots.sort(key=lambda x: x[0])

        # Compute free intervals between 08:00 and 18:00
        free_slots = []
        curr = day_start

        for b_start, b_end in booked_slots:
            if b_start > curr:
                free_slots.append((curr, min(b_start, day_end)))
            if b_end > curr:
                curr = max(curr, b_end)

        if curr < day_end:
            free_slots.append((curr, day_end))

        # Format human-readable available time range string
        formatted_slots = []
        slots_json = []
        for f_start, f_end in free_slots:
            if f_start >= f_end:
                continue
            start_fmt = f_start.strftime("%-I:%M %p") if hasattr(f_start, "strftime") else str(f_start)
            end_fmt = f_end.strftime("%-I:%M %p") if hasattr(f_end, "strftime") else str(f_end)
            formatted_slots.append(f"{start_fmt} - {end_fmt}")
            slots_json.append({
                "start": f_start.strftime("%H:%M:%S"),
                "end": f_end.strftime("%H:%M:%S"),
                "label": f"{start_fmt} - {end_fmt}",
            })

        display_text = ", ".join(formatted_slots) if formatted_slots else "No available time slots (Fully booked)"

        return Response({
            "venue_id": venue.id,
            "venue_name": venue.name,
            "date": str(date_val),
            "operating_hours": "8:00 AM - 6:00 PM",
            "available_time_ranges": f"Available time: {display_text}",
            "slots": slots_json,
            "booked_slots": [
                {"start": b[0].strftime("%H:%M:%S"), "end": b[1].strftime("%H:%M:%S")}
                for b in booked_slots
            ],
        }, status=status.HTTP_200_OK)
