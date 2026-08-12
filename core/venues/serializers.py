from hierarchy.models import Department, Faculty, School
from rest_framework import serializers

from .models import Facility, Venue


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = ("id", "name")


class VenueSerializer(serializers.ModelSerializer):
    facilities_details = FacilitySerializer(source="facilities", many=True, read_only=True)
    owning_department_name = serializers.ReadOnlyField(source="owning_department.name")
    owning_faculty_name = serializers.ReadOnlyField(source="owning_faculty.name")
    owning_school_name = serializers.ReadOnlyField(source="owning_school.name")

    class Meta:
        model = Venue
        fields = (
            "id",
            "name",
            "venue_type",
            "capacity",
            "exam_capacity",
            "facilities",
            "facilities_details",
            "owning_level",
            "owning_department",
            "owning_department_name",
            "owning_faculty",
            "owning_faculty_name",
            "owning_school",
            "owning_school_name",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return attrs

        user = request.user
        owning_level = attrs.get("owning_level")
        owning_dept = attrs.get("owning_department")
        owning_fac = attrs.get("owning_faculty")
        owning_sch = attrs.get("owning_school")

        # Validate that only matching ownership field is set
        if owning_level == Venue.OwningLevel.DEPARTMENT and not owning_dept:
            raise serializers.ValidationError({"owning_department": "owning_department is required when owning_level is 'department'."})
        if owning_level == Venue.OwningLevel.FACULTY and not owning_fac:
            raise serializers.ValidationError({"owning_faculty": "owning_faculty is required when owning_level is 'faculty'."})
        if owning_level == Venue.OwningLevel.SCHOOL and not owning_sch:
            raise serializers.ValidationError({"owning_school": "owning_school is required when owning_level is 'school'."})

        # Creation-time ownership guardrails based on requesting admin's level
        if user.role == "admin" and hasattr(user, "admin_profile"):
            admin_prof = user.admin_profile
            if admin_prof.level == "department":
                if admin_prof.scope_department and (owning_level != Venue.OwningLevel.DEPARTMENT or owning_dept != admin_prof.scope_department):
                    raise serializers.ValidationError("Department admins can only create department-owned venues for their own department.")
            elif admin_prof.level == "faculty":
                if owning_level == Venue.OwningLevel.SCHOOL:
                    raise serializers.ValidationError("Faculty admins cannot create school-level owned venues.")
                if admin_prof.scope_faculty and owning_level == Venue.OwningLevel.FACULTY and owning_fac != admin_prof.scope_faculty:
                    raise serializers.ValidationError("Faculty admins can only create faculty-owned venues for their own faculty.")
                if admin_prof.scope_faculty and owning_level == Venue.OwningLevel.DEPARTMENT and owning_dept and owning_dept.faculty != admin_prof.scope_faculty:
                    raise serializers.ValidationError("Faculty admins can only create venues for departments within their faculty.")

        return attrs
