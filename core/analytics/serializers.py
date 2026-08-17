from rest_framework import serializers


class AnalyticsQueryParamSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False, help_text="Start date (YYYY-MM-DD)")
    end_date = serializers.DateField(required=False, help_text="End date (YYYY-MM-DD)")
    course_id = serializers.IntegerField(required=False, help_text="Filter by course ID")
    lecturer_id = serializers.IntegerField(required=False, help_text="Filter by lecturer ID")


class CourseBreakdownItemSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    course_code = serializers.CharField()
    course_title = serializers.CharField()
    total_sessions = serializers.IntegerField()
    held_count = serializers.IntegerField()
    not_held_count = serializers.IntegerField()
    cancelled_count = serializers.IntegerField()
    hold_rate_percentage = serializers.FloatField()


class LecturerBreakdownItemSerializer(serializers.Serializer):
    lecturer_id = serializers.IntegerField()
    staff_id = serializers.CharField()
    full_name = serializers.CharField()
    total_sessions = serializers.IntegerField()
    held_count = serializers.IntegerField()
    not_held_count = serializers.IntegerField()
    cancelled_count = serializers.IntegerField()
    hold_rate_percentage = serializers.FloatField()


class AnalyticsSummarySerializer(serializers.Serializer):
    total_sessions = serializers.IntegerField()
    held_count = serializers.IntegerField()
    not_held_count = serializers.IntegerField()
    cancelled_count = serializers.IntegerField()
    hold_rate_percentage = serializers.FloatField()


class ClassRepAnalyticsResponseSerializer(serializers.Serializer):
    student_info = serializers.DictField()
    query_range = serializers.DictField()
    summary = AnalyticsSummarySerializer()
    course_breakdown = CourseBreakdownItemSerializer(many=True)


class LecturerAnalyticsResponseSerializer(serializers.Serializer):
    lecturer_info = serializers.DictField()
    query_range = serializers.DictField()
    summary = AnalyticsSummarySerializer()
    course_breakdown = CourseBreakdownItemSerializer(many=True)


class AdminAnalyticsResponseSerializer(serializers.Serializer):
    admin_info = serializers.DictField()
    query_range = serializers.DictField()
    summary = AnalyticsSummarySerializer()
    lecturer_breakdown = LecturerBreakdownItemSerializer(many=True)
