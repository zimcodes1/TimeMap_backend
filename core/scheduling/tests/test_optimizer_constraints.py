from unittest import TestCase

from scheduling.optimizer.constraints.capacity import calculate_capacity_penalty
from scheduling.optimizer.constraints.daily_limits import check_daily_limits
from scheduling.optimizer.constraints.lecturers import check_lecturer_conflicts
from scheduling.optimizer.constraints.occurrences import check_occurrence_days
from scheduling.optimizer.constraints.students import check_student_conflicts
from scheduling.optimizer.constraints.venues import check_venue_conflicts
from scheduling.optimizer.models.assignment import Assignment
from scheduling.optimizer.models.occurrence import CourseOccurrence
from scheduling.optimizer.models.problem import SchedulingProblem
from scheduling.optimizer.models.slot import Slot
from scheduling.optimizer.models.student_group import StudentGroup
from scheduling.optimizer.models.venue import VenueData


class OptimizerConstraintsTests(TestCase):
    def setUp(self):
        self.slot1 = Slot(day="MO", day_name="Monday", period_index=0, start_time="08:00", end_time="10:00")
        self.slot2 = Slot(day="MO", day_name="Monday", period_index=1, start_time="10:00", end_time="12:00")
        self.slot3 = Slot(day="TU", day_name="Tuesday", period_index=0, start_time="08:00", end_time="10:00")

        self.grp_cs1 = StudentGroup(program_id=1, level=100, program_code="CSC", program_name="Computer Science")
        self.grp_math1 = StudentGroup(program_id=2, level=100, program_code="MTH", program_name="Mathematics")

        self.venue1 = VenueData(id=101, name="Hall A", venue_type="lecture_hall", capacity=100)
        self.venue2 = VenueData(id=102, name="Hall B", venue_type="lecture_hall", capacity=50)

        self.problem = SchedulingProblem(
            occurrences=[],
            valid_slots=[self.slot1, self.slot2, self.slot3],
            venues={101: self.venue1, 102: self.venue2},
            student_conflict_graph={1: {2}, 2: {1}},  # Course 1 conflicts with Course 2
            shared_student_groups={(1, 2): [self.grp_cs1], (2, 1): [self.grp_cs1]},
            lecturers_by_course={1: {10}, 2: {10}},
            daily_lecture_limit=3,
        )

    def test_student_conflict_detected_when_same_slot(self):
        occ1 = CourseOccurrence("CSC101-1", course_id=1, course_code="CSC101", course_title="Intro", occurrence_index=1, total_occurrences=1, student_groups=(self.grp_cs1,))
        occ2 = CourseOccurrence("MTH101-1", course_id=2, course_code="MTH101", course_title="Calc", occurrence_index=1, total_occurrences=1, student_groups=(self.grp_cs1,))

        # Assigned to same slot
        a1 = Assignment(occ1, self.slot1, venue_id=101)
        a2 = Assignment(occ2, self.slot1, venue_id=102)

        count, details = check_student_conflicts([a1, a2], self.problem)
        self.assertEqual(count, 1)
        self.assertEqual(details[0]["course_a"], "CSC101")
        self.assertEqual(details[0]["course_b"], "MTH101")

        # Assigned to different slots: 0 conflicts
        a2_diff = Assignment(occ2, self.slot2, venue_id=102)
        count_diff, _ = check_student_conflicts([a1, a2_diff], self.problem)
        self.assertEqual(count_diff, 0)

    def test_lecturer_conflict_detected_when_same_slot(self):
        occ1 = CourseOccurrence("CSC101-1", course_id=1, course_code="CSC101", course_title="Intro", occurrence_index=1, total_occurrences=1, lecturer_ids=(10,))
        occ2 = CourseOccurrence("MTH101-1", course_id=2, course_code="MTH101", course_title="Calc", occurrence_index=1, total_occurrences=1, lecturer_ids=(10,))

        a1 = Assignment(occ1, self.slot1, venue_id=101)
        a2 = Assignment(occ2, self.slot1, venue_id=102)

        count, details = check_lecturer_conflicts([a1, a2], self.problem)
        self.assertEqual(count, 1)
        self.assertEqual(details[0]["lecturer_id"], "10")

    def test_venue_conflict_detected_when_same_slot_and_venue(self):
        occ1 = CourseOccurrence("CSC101-1", course_id=1, course_code="CSC101", course_title="Intro", occurrence_index=1, total_occurrences=1)
        occ3 = CourseOccurrence("PHY101-1", course_id=3, course_code="PHY101", course_title="Phys", occurrence_index=1, total_occurrences=1)

        # Both use venue 101 at slot 1
        a1 = Assignment(occ1, self.slot1, venue_id=101)
        a3 = Assignment(occ3, self.slot1, venue_id=101)

        count, details = check_venue_conflicts([a1, a3], self.problem)
        self.assertEqual(count, 1)
        self.assertEqual(details[0]["venue_id"], "101")

    def test_daily_limit_violation_when_exceeding_max(self):
        # Create 4 lectures on Monday for CS 100L
        slots_mon = [
            Slot("MO", "Monday", 0, "08:00", "10:00"),
            Slot("MO", "Monday", 1, "10:00", "12:00"),
            Slot("MO", "Monday", 2, "12:00", "14:00"),
            Slot("MO", "Monday", 3, "14:00", "16:00"),
        ]

        assignments = [
            Assignment(CourseOccurrence(f"C{i}-1", i, f"C{i}", f"Course {i}", 1, 1, student_groups=(self.grp_cs1,)), slots_mon[i], venue_id=101)
            for i in range(4)
        ]

        count, details = check_daily_limits(assignments, self.problem)
        self.assertEqual(count, 1)  # 4 - 3 = 1 violation
        self.assertEqual(details[0]["scheduled_count"], 4)

    def test_occurrence_days_violation_when_same_day(self):
        # MTH101 has 2 occurrences; both placed on Monday
        occ1 = CourseOccurrence("MTH101-1", course_id=2, course_code="MTH101", course_title="Calc", occurrence_index=1, total_occurrences=2)
        occ2 = CourseOccurrence("MTH101-2", course_id=2, course_code="MTH101", course_title="Calc", occurrence_index=2, total_occurrences=2)

        a1 = Assignment(occ1, self.slot1, venue_id=101)  # Monday
        a2 = Assignment(occ2, self.slot2, venue_id=101)  # Monday

        count, details = check_occurrence_days([a1, a2], self.problem)
        self.assertEqual(count, 1)
        self.assertEqual(details[0]["course"], "MTH101")

        # Placed on Tuesday: 0 violations
        a2_tue = Assignment(occ2, self.slot3, venue_id=101)  # Tuesday
        count_tue, _ = check_occurrence_days([a1, a2_tue], self.problem)
        self.assertEqual(count_tue, 0)

    def test_capacity_penalty_calculated_when_overflowing(self):
        # 80 students assigned to venue2 (capacity 50) -> overflow 30
        occ = CourseOccurrence("CSC101-1", course_id=1, course_code="CSC101", course_title="Intro", occurrence_index=1, total_occurrences=1, expected_students=80)
        a = Assignment(occ, self.slot1, venue_id=102)

        penalty, details = calculate_capacity_penalty([a], self.problem)
        self.assertEqual(penalty, 30)
        self.assertEqual(details[0]["overflow"], 30)

