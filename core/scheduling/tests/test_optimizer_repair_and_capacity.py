from unittest import TestCase

from scheduling.optimizer.evaluation.evaluator import evaluate
from scheduling.optimizer.genetic.algorithm import OptimizerConfig, run_genetic_algorithm
from scheduling.optimizer.genetic.chromosome import Chromosome
from scheduling.optimizer.genetic.population import create_heuristic_individual
from scheduling.optimizer.genetic.repair import final_repair_pass, repair_chromosome
from scheduling.optimizer.genetic.venue_utils import pick_best_fit_venue
from scheduling.optimizer.models.assignment import Assignment
from scheduling.optimizer.models.course import CourseData
from scheduling.optimizer.models.occurrence import CourseOccurrence
from scheduling.optimizer.models.problem import SchedulingProblem
from scheduling.optimizer.models.slot import Slot
from scheduling.optimizer.models.student_group import StudentGroup
from scheduling.optimizer.models.venue import VenueData
from scheduling.optimizer.preprocessing.conflicts import build_student_conflict_graph
from scheduling.optimizer.preprocessing.occurrences import expand_occurrences
from scheduling.optimizer.preprocessing.slots import build_valid_slots


class OptimizerRepairAndCapacityTests(TestCase):
    def setUp(self):
        self.valid_slots = build_valid_slots()

        self.venue_small = VenueData(id=1, name="Small Room", venue_type="lecture_hall", capacity=50)
        self.venue_medium = VenueData(id=2, name="Medium Hall", venue_type="lecture_hall", capacity=120)
        self.venue_large = VenueData(id=3, name="Grand Auditorium", venue_type="lecture_hall", capacity=500)
        self.venue_lab = VenueData(id=4, name="Computing Lab", venue_type="laboratory", capacity=40)

        self.venues_map = {
            1: self.venue_small,
            2: self.venue_medium,
            3: self.venue_large,
            4: self.venue_lab,
        }

    def test_pick_best_fit_venue_prioritizes_small_room_for_small_cohort(self):
        """
        A course with 45 students should pick Small Room (50) rather than consuming Grand Auditorium (500).
        """
        allowed = [1, 2, 3]  # small, medium, large
        for _ in range(20):
            chosen = pick_best_fit_venue(
                expected_students=45,
                allowed_venue_ids=allowed,
                venues=self.venues_map,
            )
            # Must pick smallest sufficient capacity (Small Room = 1 or Medium = 2), never the 500-seat auditorium
            self.assertIn(chosen, [1, 2], f"Expected small/medium venue, got {chosen}")

    def test_pick_best_fit_venue_allocates_large_auditorium_for_large_cohort(self):
        """
        A large course with 380 students must be allocated the 500-seat Grand Auditorium.
        """
        allowed = [1, 2, 3]  # small, medium, large
        for _ in range(10):
            chosen = pick_best_fit_venue(
                expected_students=380,
                allowed_venue_ids=allowed,
                venues=self.venues_map,
            )
            self.assertEqual(chosen, 3, "Large cohort must receive Grand Auditorium (Venue #3)")

    def test_pick_best_fit_venue_avoids_occupied_venues(self):
        """
        When the smallest venue is already occupied in this slot, it should pick the next best free venue.
        """
        allowed = [1, 2, 3]
        occupied = {1}  # Small room occupied

        chosen = pick_best_fit_venue(
            expected_students=45,
            allowed_venue_ids=allowed,
            venues=self.venues_map,
            occupied_venue_ids=occupied,
        )
        self.assertEqual(chosen, 2, "Should pick Medium Hall (#2) since Small Room (#1) is occupied")

    def test_repair_chromosome_resolves_venue_double_bookings(self):
        """
        Two courses assigned to the exact same slot and venue must be deterministically repaired.
        The larger class should retain the room, and the smaller class should be relocated.
        """
        slot = self.valid_slots[0]
        occ_large = CourseOccurrence(
            occurrence_id="CSC101-1",
            course_id=1,
            course_code="CSC101",
            course_title="Large Class",
            occurrence_index=1,
            total_occurrences=1,
            expected_students=400,
        )
        occ_small = CourseOccurrence(
            occurrence_id="CSC102-1",
            course_id=2,
            course_code="CSC102",
            course_title="Small Class",
            occurrence_index=1,
            total_occurrences=1,
            expected_students=40,
        )

        problem = SchedulingProblem(
            occurrences=[occ_large, occ_small],
            valid_slots=self.valid_slots,
            venues=self.venues_map,
            student_conflict_graph={},
            allowed_venues_by_course={1: [1, 2, 3], 2: [1, 2, 3]},
        )

        # Both assigned to Venue #3 (Auditorium) in the same slot
        a1 = Assignment(occurrence=occ_large, slot=slot, venue_id=3)
        a2 = Assignment(occurrence=occ_small, slot=slot, venue_id=3)
        chrome = Chromosome([a1, a2])

        eval_before = evaluate(chrome.assignments, problem)
        self.assertEqual(eval_before.venue_conflicts, 1)

        repaired = repair_chromosome(chrome, problem)
        eval_after = evaluate(repaired.assignments, problem)

        self.assertEqual(eval_after.venue_conflicts, 0, "Venue double-booking must be resolved")
        # Ensure the large class kept the auditorium (Venue #3)
        for a in repaired.assignments:
            if a.occurrence.course_id == 1:
                self.assertEqual(a.venue_id, 3, "Large cohort must retain the Grand Auditorium")

    def test_repair_chromosome_resolves_student_cohort_conflicts(self):
        """
        Two courses sharing a student group assigned to the exact same slot must be separated.
        """
        grp = StudentGroup(program_id=1, level=100, program_code="CSC")
        slot = self.valid_slots[0]

        occ1 = CourseOccurrence(
            occurrence_id="CSC101-1",
            course_id=1,
            course_code="CSC101",
            course_title="Class 1",
            occurrence_index=1,
            total_occurrences=1,
            student_groups=(grp,),
        )
        occ2 = CourseOccurrence(
            occurrence_id="MTH101-1",
            course_id=2,
            course_code="MTH101",
            course_title="Class 2",
            occurrence_index=1,
            total_occurrences=1,
            student_groups=(grp,),
        )

        problem = SchedulingProblem(
            occurrences=[occ1, occ2],
            valid_slots=self.valid_slots,
            venues=self.venues_map,
            student_conflict_graph={1: {2}, 2: {1}},
            shared_student_groups={(1, 2): [grp], (2, 1): [grp]},
            allowed_venues_by_course={1: [1, 2], 2: [1, 2]},
        )

        # Assigned to same slot, different venues
        a1 = Assignment(occurrence=occ1, slot=slot, venue_id=1)
        a2 = Assignment(occurrence=occ2, slot=slot, venue_id=2)
        chrome = Chromosome([a1, a2])

        eval_before = evaluate(chrome.assignments, problem)
        self.assertEqual(eval_before.student_conflicts, 1)

        repaired = repair_chromosome(chrome, problem)
        eval_after = evaluate(repaired.assignments, problem)

        self.assertEqual(eval_after.student_conflicts, 0, "Student cohort conflict must be resolved")

    def test_final_repair_pass_achieves_zero_hard_conflicts(self):
        """
        Simulate a schedule with multiple venue and student conflicts.
        final_repair_pass must resolve all conflicts to produce a 100% feasible schedule.
        """
        grp = StudentGroup(program_id=1, level=100, program_code="CSC")
        slot1 = self.valid_slots[0]

        courses = [
            CourseData(id=1, code="CSC101", title="A", level=100, department_id=1, required_occurrences=1, student_groups=(grp,), expected_students=45),
            CourseData(id=2, code="CSC102", title="B", level=100, department_id=1, required_occurrences=1, student_groups=(grp,), expected_students=45),
            CourseData(id=3, code="CSC103", title="C", level=100, department_id=1, required_occurrences=1, student_groups=(), expected_students=45),
        ]
        occurrences = expand_occurrences(courses)
        conflict_graph, shared_groups = build_student_conflict_graph(courses)

        problem = SchedulingProblem(
            occurrences=occurrences,
            valid_slots=self.valid_slots,
            venues=self.venues_map,
            student_conflict_graph=conflict_graph,
            shared_student_groups=shared_groups,
            allowed_venues_by_course={1: [1, 2], 2: [1, 2], 3: [1, 2]},
        )

        # Force conflicting assignments (all in slot1, courses 1 and 3 in venue 1)
        a1 = Assignment(occurrences[0], slot1, venue_id=1)
        a2 = Assignment(occurrences[1], slot1, venue_id=2)  # Student clash with a1
        a3 = Assignment(occurrences[2], slot1, venue_id=1)  # Venue clash with a1
        chrome = Chromosome([a1, a2, a3])

        eval_before = evaluate(chrome.assignments, problem)
        self.assertGreater(eval_before.hard_conflicts, 0)

        repaired_chrome = final_repair_pass(chrome, problem)
        eval_after = evaluate(repaired_chrome.assignments, problem)

        self.assertEqual(eval_after.hard_conflicts, 0, f"Expected 0 hard conflicts, got {eval_after.hard_conflicts}")
        self.assertTrue(eval_after.is_feasible)

    def test_heuristic_individual_avoids_immediate_conflicts(self):
        """
        create_heuristic_individual should generate an individual with zero venue clashes
        and zero student clashes for a standard multi-course problem.
        """
        grp1 = StudentGroup(program_id=1, level=100, program_code="CSC")
        grp2 = StudentGroup(program_id=2, level=100, program_code="MTH")

        courses = [
            CourseData(id=1, code="CSC101", title="A", level=100, department_id=1, required_occurrences=2, student_groups=(grp1,), lecturer_ids=(10,), expected_students=45),
            CourseData(id=2, code="CSC102", title="B", level=100, department_id=1, required_occurrences=2, student_groups=(grp1,), lecturer_ids=(11,), expected_students=45),
            CourseData(id=3, code="MTH101", title="C", level=100, department_id=2, required_occurrences=2, student_groups=(grp2,), lecturer_ids=(12,), expected_students=100),
        ]
        occurrences = expand_occurrences(courses)
        conflict_graph, shared_groups = build_student_conflict_graph(courses)

        problem = SchedulingProblem(
            occurrences=occurrences,
            valid_slots=self.valid_slots,
            venues=self.venues_map,
            student_conflict_graph=conflict_graph,
            shared_student_groups=shared_groups,
            lecturers_by_course={1: {10}, 2: {11}, 3: {12}},
            allowed_venues_by_course={1: [1, 2], 2: [1, 2], 3: [2, 3]},
        )

        ind = create_heuristic_individual(problem)
        eval_res = evaluate(ind.assignments, problem)

        self.assertEqual(eval_res.venue_conflicts, 0, "Heuristic should not generate venue conflicts")
        self.assertEqual(eval_res.student_conflicts, 0, "Heuristic should not generate student cohort conflicts")
        self.assertEqual(eval_res.lecturer_conflicts, 0, "Heuristic should not generate lecturer conflicts")
