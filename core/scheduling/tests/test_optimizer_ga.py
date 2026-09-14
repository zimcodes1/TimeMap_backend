from unittest import TestCase

from scheduling.optimizer.generator import generate_timetable
from scheduling.optimizer.genetic.algorithm import OptimizerConfig
from scheduling.optimizer.models.course import CourseData
from scheduling.optimizer.models.problem import SchedulingProblem
from scheduling.optimizer.models.slot import Slot
from scheduling.optimizer.models.student_group import StudentGroup
from scheduling.optimizer.models.venue import VenueData
from scheduling.optimizer.preprocessing.conflicts import build_student_conflict_graph
from scheduling.optimizer.preprocessing.occurrences import expand_occurrences
from scheduling.optimizer.preprocessing.slots import build_valid_slots
from scheduling.optimizer.preprocessing.venues import build_allowed_venues_map


class OptimizerGATests(TestCase):
    def test_ga_solves_feasible_scheduling_problem(self):
        """
        Benchmark problem: 4 courses across 2 student groups, multiple occurrences, 2 venues.
        The GA should successfully find a feasible schedule with 0 hard conflicts.
        """
        grp_cs = StudentGroup(program_id=1, level=100, program_code="CSC")
        grp_se = StudentGroup(program_id=2, level=100, program_code="SEN")

        venues = [
            VenueData(id=1, name="Lecture Hall 1", venue_type="lecture_hall", capacity=120),
            VenueData(id=2, name="Lecture Hall 2", venue_type="lecture_hall", capacity=100),
            VenueData(id=3, name="Software Lab", venue_type="laboratory", capacity=60),
        ]
        venues_dict = {v.id: v for v in venues}

        courses = [
            # CSC101: 2 occurrences, taken by CS and SE
            CourseData(id=1, code="CSC101", title="Intro to CS", level=100, department_id=1, required_occurrences=2, course_type="lecture", student_groups=(grp_cs, grp_se), lecturer_ids=(10,), expected_students=80),
            # CSC102: 1 practical occurrence (Lab), CS only
            CourseData(id=2, code="CSC102", title="CS Lab", level=100, department_id=1, required_occurrences=1, course_type="practical", student_groups=(grp_cs,), lecturer_ids=(11,), expected_students=40),
            # MTH101: 2 occurrences, CS and SE
            CourseData(id=3, code="MTH101", title="Calculus", level=100, department_id=2, required_occurrences=2, course_type="lecture", student_groups=(grp_cs, grp_se), lecturer_ids=(12,), expected_students=80),
            # SEN101: 1 occurrence, SE only
            CourseData(id=4, code="SEN101", title="Software Process", level=100, department_id=1, required_occurrences=1, course_type="lecture", student_groups=(grp_se,), lecturer_ids=(10,), expected_students=40),
        ]

        valid_slots = build_valid_slots()
        occurrences = expand_occurrences(courses)
        conflict_graph, shared_groups = build_student_conflict_graph(courses)
        allowed_venues = build_allowed_venues_map(courses, venues)

        problem = SchedulingProblem(
            occurrences=occurrences,
            valid_slots=valid_slots,
            venues=venues_dict,
            student_conflict_graph=conflict_graph,
            shared_student_groups=shared_groups,
            lecturers_by_course={c.id: set(c.lecturer_ids) for c in courses},
            allowed_venues_by_course=allowed_venues,
            daily_lecture_limit=3,
        )

        config = OptimizerConfig(
            population_size=40,
            max_generations=80,
            patience=20,
            mutation_rate=0.08,
        )

        result = generate_timetable(problem, config=config)

        self.assertTrue(result.is_feasible, f"Expected feasible timetable, got {result.status} with {result.hard_conflicts_count} hard conflicts: {result.conflict_report['summary']}")
        self.assertEqual(result.hard_conflicts_count, 0)
        self.assertEqual(len(result.assignments), len(occurrences))
        self.assertIn(result.status, ["OPTIMAL", "FEASIBLE"])

        # Practical course CSC102 must use the lab
        for a in result.assignments:
            if a.occurrence.course_code == "CSC102":
                self.assertEqual(a.venue_id, 3, "CSC102 practical course must be assigned to the lab (Venue #3)")

    def test_ga_handles_infeasible_problem_gracefully(self):
        """
        Intentionally overconstrained problem:
        2 courses sharing student cohort and lecturer, but only 1 time slot available.
        Must return BEST_AVAILABLE with conflict diagnostics rather than crashing or claiming success.
        """
        grp = StudentGroup(program_id=1, level=100, program_code="CSC")
        single_slot = Slot(day="MO", day_name="Monday", period_index=0, start_time="08:00", end_time="10:00")
        venue = VenueData(id=1, name="Hall 1", venue_type="lecture_hall", capacity=50)

        courses = [
            CourseData(id=1, code="CSC101", title="A", level=100, department_id=1, required_occurrences=1, student_groups=(grp,), lecturer_ids=(10,)),
            CourseData(id=2, code="CSC102", title="B", level=100, department_id=1, required_occurrences=1, student_groups=(grp,), lecturer_ids=(10,)),
        ]

        occurrences = expand_occurrences(courses)
        conflict_graph, shared_groups = build_student_conflict_graph(courses)

        problem = SchedulingProblem(
            occurrences=occurrences,
            valid_slots=[single_slot],
            venues={1: venue},
            student_conflict_graph=conflict_graph,
            shared_student_groups=shared_groups,
            lecturers_by_course={1: {10}, 2: {10}},
            allowed_venues_by_course={1: [1], 2: [1]},
            daily_lecture_limit=3,
        )

        config = OptimizerConfig(population_size=10, max_generations=15, patience=5)
        result = generate_timetable(problem, config=config)

        self.assertEqual(result.status, "BEST_AVAILABLE")
        self.assertFalse(result.is_feasible)
        self.assertGreater(result.hard_conflicts_count, 0)
        self.assertIn("details", result.conflict_report)

