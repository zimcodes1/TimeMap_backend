from datetime import date, time
from types import SimpleNamespace

from courses.models import Course
from rest_framework.test import APITestCase
from scheduling.exam_optimizer import (
    ExamGenerationResult,
    _allocate,
    _date_windows,
    _within_policy,
)
from scheduling.exam_optimizer.allocation.cbt import allocate_cbt_venues
from scheduling.exam_optimizer.allocation.joining import join_compatible_sessions
from scheduling.exam_optimizer.allocation.written import allocate_written_venues
from scheduling.exam_optimizer.constraints.calendar import check_calendar_constraints
from scheduling.exam_optimizer.constraints.conflicts import check_student_conflicts
from scheduling.exam_optimizer.constraints.venues import check_venue_constraints
from scheduling.exam_optimizer.evaluation.evaluator import (
    ExamEvaluationResult,
    evaluate_exam_schedule,
)
from scheduling.exam_optimizer.evaluation.report import generate_exam_conflict_report
from scheduling.exam_optimizer.models.time_window import CalendarPolicy, CandidateWindow
from scheduling.exam_optimizer.solver.ordering import compute_exam_difficulty, order_exam_events
from scheduling.exam_optimizer.models.event import ExamEvent
from scheduling.exam_optimizer.validation.validator import validate_exam_timetable


def make_venue(name, capacity, exam_capacity=None):
    cap = exam_capacity if exam_capacity is not None else capacity
    return SimpleNamespace(name=name, capacity=capacity, exam_capacity=cap, id=name)


class ExamOptimizerModularUnitTests(APITestCase):
    def test_written_allocation_chooses_closest_fit_single_venue(self):
        venues = [
            make_venue("Huge Hall", 500),
            make_venue("Medium Hall", 150),
            make_venue("Small Room", 50),
        ]
        duration, allocs = allocate_written_venues(venues, student_count=120, base_duration=120)
        self.assertEqual(duration, 120)
        self.assertEqual(len(allocs), 1)
        # Medium Hall (150) is closer to 120 than Huge Hall (500)
        self.assertEqual(allocs[0]["venue_name"], "Medium Hall")
        self.assertEqual(allocs[0]["students"], 120)

    def test_written_allocation_evaluates_venue_pairs(self):
        venues = [
            make_venue("Room A", 70),
            make_venue("Room B", 60),
            make_venue("Room C", 200),
        ]
        # Cohort of 120: Room A + Room B = 130 (excess 10) vs Room C = 200 (excess 80)
        # When no single room works or when pair is better suited
        duration, allocs = allocate_written_venues(venues[:2], student_count=120, base_duration=120)
        self.assertEqual(duration, 120)
        self.assertEqual(len(allocs), 2)
        self.assertEqual(sum(a["students"] for a in allocs), 120)

    def test_cbt_allocation_computes_turns_and_throughput(self):
        venues = [make_venue("CBT Centre", 100)]
        duration, allocs = allocate_cbt_venues(
            venues, student_count=250, per_student_duration=30, base_duration=30
        )
        self.assertEqual(duration, 90)  # ceil(250/100) = 3 turns * 30 min = 90 min
        self.assertEqual(len(allocs), 1)
        self.assertEqual(allocs[0]["turns"], 3)
        self.assertEqual(allocs[0]["students"], 250)

    def test_cbt_joining_respects_max_two_courses_rule(self):
        events = [
            {
                "course_id": 1,
                "course_code": "CSC201",
                "exam_type": Course.ExamType.CBT,
                "student_count": 40,
                "date": "2026-10-12",
                "start_time": "08:00:00",
                "end_time": "09:00:00",
                "duration_minutes": 60,
                "venues": [{"venue_id": "V1", "venue_name": "Lab", "students": 40, "turns": 1, "capacity": 100}],
                "joined_courses": [],
            },
            {
                "course_id": 2,
                "course_code": "MTH201",
                "exam_type": Course.ExamType.CBT,
                "student_count": 50,
                "date": "2026-10-12",
                "start_time": "08:00:00",
                "end_time": "09:00:00",
                "duration_minutes": 60,
                "venues": [{"venue_id": "V2", "venue_name": "Lab 2", "students": 50, "turns": 1, "capacity": 100}],
                "joined_courses": [],
            },
            {
                "course_id": 3,
                "course_code": "PHY201",
                "exam_type": Course.ExamType.CBT,
                "student_count": 30,
                "date": "2026-10-12",
                "start_time": "08:00:00",
                "end_time": "09:00:00",
                "duration_minutes": 60,
                "venues": [{"venue_id": "V3", "venue_name": "Lab 3", "students": 30, "turns": 1, "capacity": 100}],
                "joined_courses": [],
            },
        ]
        scheduled_states = [
            {"student_ids": {1, 2}, "venue_ids": {"V1"}},
            {"student_ids": {3, 4}, "venue_ids": {"V2"}},
            {"student_ids": {5, 6}, "venue_ids": {"V3"}},
        ]

        joined_count = join_compatible_sessions(events, scheduled_states)
        self.assertEqual(joined_count, 1)  # Only 1 pair joined (at most 2 courses per session!)
        self.assertEqual(len(events[0]["joined_courses"]), 1)
        self.assertIn("MTH201", events[0]["joined_courses"])
        self.assertEqual(len(events[2]["joined_courses"]), 0)  # Third course not merged into existing group

    def test_validator_detects_student_conflict(self):
        events = [
            {
                "course_id": 1,
                "course_code": "CSC301",
                "exam_type": Course.ExamType.WRITTEN,
                "student_count": 50,
                "date": "2026-10-12",
                "start_time": "08:00:00",
                "end_time": "10:00:00",
                "duration_minutes": 120,
                "venues": [{"venue_id": "H1", "venue_name": "Hall 1", "students": 50, "turns": 1, "capacity": 100}],
            },
            {
                "course_id": 2,
                "course_code": "CSC302",
                "exam_type": Course.ExamType.WRITTEN,
                "student_count": 50,
                "date": "2026-10-12",
                "start_time": "09:00:00",
                "end_time": "11:00:00",
                "duration_minutes": 120,
                "venues": [{"venue_id": "H2", "venue_name": "Hall 2", "students": 50, "turns": 1, "capacity": 100}],
            },
        ]
        # Overlapping time 09:00-10:00, sharing student ID 999
        scheduled_states = [
            {"student_ids": {101, 999}, "venue_ids": {"H1"}},
            {"student_ids": {202, 999}, "venue_ids": {"H2"}},
        ]

        result = validate_exam_timetable(
            events, scheduled_states, start_date=date(2026, 10, 1), end_date=date(2026, 10, 31)
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("Student conflict" in err["reason"] for err in result["errors"]))

    def test_generation_result_supports_tuple_unpacking(self):
        dummy_eval = ExamEvaluationResult()
        dummy_result = ExamGenerationResult(
            status="FEASIBLE",
            events=[{"course_code": "TEST101"}],
            diagnostics={"scheduled": 1},
            metrics={"runtime_seconds": 0.5},
            fitness=1.0,
            evaluation=dummy_eval,
            conflict_report={},
            runtime_seconds=0.5,
        )

        # Verify tuple unpacking works exactly like a 2-tuple (events, diagnostics)
        events, diagnostics = dummy_result
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["course_code"], "TEST101")
        self.assertEqual(diagnostics["scheduled"], 1)

        # Verify object property access works
        self.assertEqual(dummy_result.status, "FEASIBLE")
        self.assertEqual(dummy_result.fitness, 1.0)
        self.assertTrue(dummy_result.is_feasible)

