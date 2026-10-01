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

        # If course filter is passed, return venues matching course scope via optimizer filter_allowed_venues
        params = getattr(self.request, "query_params", getattr(self.request, "GET", {}))
        course_param = params.get("course") or params.get("course_id")
        if course_param:
            from courses.models import Course, CourseAccessGrant
            from scheduling.optimizer.models.course import CourseData
            from scheduling.optimizer.models.venue import VenueData
            from scheduling.optimizer.preprocessing.venues import filter_allowed_venues
            try:
                course = (
                    Course.objects.select_related(
                        "owning_department__faculty__school",
                        "owning_faculty__school",
                        "owning_school",
                    )
                    .prefetch_related("access_grants")
                    .filter(Q(id=course_param) if str(course_param).isdigit() else Q(code__iexact=str(course_param)))
                    .first()
                )
                if course:
                    recv_dept_ids = tuple(
                        grant.granted_to_department_id
                        for grant in course.access_grants.filter(status=CourseAccessGrant.Status.APPROVED)
                        if grant.granted_to_department_id
                    )
                    dept_id = course.owning_department_id
                    fac_id = course.owning_faculty_id or (
                        course.owning_department.faculty_id if course.owning_department else None
                    )
                    sch_id = course.owning_school_id or (
                        course.owning_faculty.school_id
                        if course.owning_faculty
                        else (
                            course.owning_department.faculty.school_id
                            if course.owning_department and course.owning_department.faculty
                            else None
                        )
                    )

                    c_data = CourseData(
                        id=course.id,
                        code=course.code,
                        title=course.title,
                        level=course.level,
                        department_id=dept_id or 0,
                        department_name=course.owning_department.name if course.owning_department else "",
                        course_type=course.course_type,
                        owning_level=course.owning_level,
                        faculty_id=fac_id,
                        school_id=sch_id,
                        receiving_department_ids=recv_dept_ids,
                        is_general=(course.owning_level == Course.OwningLevel.GENERAL),
                    )

                    venues_qs = Venue.objects.filter(is_active=True).select_related(
                        "owning_department", "owning_faculty", "owning_school"
                    )
                    v_data = [
                        VenueData(
                            id=v.id,
                            name=v.name,
                            venue_type=v.venue_type,
                            capacity=v.capacity,
                            owning_level=v.owning_level,
                            owning_department_id=v.owning_department_id,
                            owning_faculty_id=v.owning_faculty_id,
                            owning_school_id=v.owning_school_id,
                        )
                        for v in venues_qs
                    ]

                    allowed_ids = filter_allowed_venues(c_data, v_data)
                    if allowed_ids:
                        return venues_qs.filter(id__in=allowed_ids).order_by("name")
            except Exception:
                pass

        if user.role == "admin" and hasattr(user, "admin_profile"):
            admin_prof = user.admin_profile
            level = admin_prof.level

            if level == "university":
                return Venue.objects.all().order_by("name")
            elif level == "school":
                if not admin_prof.scope_school:
                    return Venue.objects.none()
                return Venue.objects.filter(
                    Q(owning_level=Venue.OwningLevel.SCHOOL, owning_school=admin_prof.scope_school)
                    | Q(owning_level=Venue.OwningLevel.FACULTY, owning_faculty__school=admin_prof.scope_school)
                    | Q(owning_level=Venue.OwningLevel.DEPARTMENT, owning_department__faculty__school=admin_prof.scope_school)
                ).distinct().order_by("name")
            elif level == "faculty":
                if not admin_prof.scope_faculty:
                    return Venue.objects.none()
                return Venue.objects.filter(
                    Q(owning_level=Venue.OwningLevel.FACULTY, owning_faculty=admin_prof.scope_faculty)
                    | Q(owning_level=Venue.OwningLevel.DEPARTMENT, owning_department__faculty=admin_prof.scope_faculty)
                ).distinct().order_by("name")
            elif level == "department":
                if not admin_prof.scope_department:
                    return Venue.objects.none()
                return Venue.objects.filter(
                    Q(owning_level=Venue.OwningLevel.DEPARTMENT, owning_department=admin_prof.scope_department)
                    | Q(owning_level=Venue.OwningLevel.FACULTY, owning_faculty=admin_prof.scope_department.faculty)
                ).distinct().order_by("name")

        if user.role == "lecturer" and hasattr(user, "lecturer_profile"):
            lec_dept = user.lecturer_profile.department
            if lec_dept:
                fac = lec_dept.faculty
                sch = fac.school if fac else None
                conds = Q(owning_department=lec_dept)
                if fac:
                    conds |= Q(owning_faculty=fac)
                if sch:
                    conds |= Q(owning_school=sch)
                return Venue.objects.filter(conds, is_active=True).distinct().order_by("name")

        if user.role == "student" and hasattr(user, "student_profile"):
            stu_dept = user.student_profile.department
            if stu_dept:
                fac = stu_dept.faculty
                sch = fac.school if fac else None
                conds = Q(owning_department=stu_dept)
                if fac:
                    conds |= Q(owning_faculty=fac)
                if sch:
                    conds |= Q(owning_school=sch)
                return Venue.objects.filter(conds, is_active=True).distinct().order_by("name")

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

        exclude_session = request.query_params.get("exclude_session")
        if exclude_session:
            try:
                sessions = sessions.exclude(id=int(exclude_session))
            except (ValueError, TypeError):
                pass

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
