import datetime
from django.core.management.base import BaseCommand, CommandError

from scheduling.models import Semester, TimetableGenerationRun
from scheduling.optimizer.generator import generate_timetable
from scheduling.optimizer.genetic.algorithm import OptimizerConfig
from scheduling.optimizer.preprocessing.pipeline import build_scheduling_problem_from_db
from scheduling.optimizer.publisher import publish_generation_run


class Command(BaseCommand):
    help = "Generates an automated weekly lecture timetable for a semester using the Genetic Algorithm optimizer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--semester",
            type=int,
            required=True,
            help="ID of the Semester to schedule for.",
        )
        parser.add_argument(
            "--scope-type",
            type=str,
            default="school",
            choices=["school", "faculty", "department"],
            help="Target scope type (school, faculty, or department).",
        )
        parser.add_argument(
            "--scope-id",
            type=int,
            required=False,
            help="ID of the target School, Faculty, or Department. Defaults to the semester's school.",
        )
        parser.add_argument(
            "--population-size",
            type=int,
            default=60,
            help="GA population size (default 60).",
        )
        parser.add_argument(
            "--max-generations",
            type=int,
            default=150,
            help="GA maximum generations (default 150).",
        )
        parser.add_argument(
            "--publish",
            action="store_true",
            help="Automatically publish the generated timetable into TimetableEntry and LectureSession rows.",
        )

    def handle(self, *args, **options):
        semester_id = options["semester"]
        scope_type = options["scope_type"]
        scope_id = options.get("scope_id")
        publish = options.get("publish", False)

        semester = Semester.objects.filter(id=semester_id).select_related("session__school").first()
        if not semester:
            raise CommandError(f"Semester with ID {semester_id} not found.")

        if not scope_id:
            if scope_type == "school":
                scope_id = semester.session.school_id
            else:
                raise CommandError(f"--scope-id is required when scope-type is '{scope_type}'.")

        self.stdout.write(self.style.NOTICE(
            f"Preparing timetable generation for {semester} [Scope: {scope_type} #{scope_id}]..."
        ))

        # 1. Preprocessing pipeline
        try:
            problem = build_scheduling_problem_from_db(
                semester_id=semester_id,
                scope_type=scope_type,
                scope_id=scope_id,
            )
        except Exception as e:
            raise CommandError(f"Preprocessing failed: {e}")

        self.stdout.write(
            f"Loaded {len(problem.occurrences)} course occurrences across {len(problem.venues)} venues and {len(problem.valid_slots)} valid slots."
        )

        # 2. Run GA
        config = OptimizerConfig(
            population_size=options["population_size"],
            max_generations=options["max_generations"],
        )

        def progress_cb(gen, max_gen, best_eval):
            if gen % 10 == 0 or gen == 1 or gen == max_gen:
                self.stdout.write(
                    f"Gen {gen}/{max_gen}: Hard conflicts={best_eval.hard_conflicts} (Stu={best_eval.student_conflicts}, Lec={best_eval.lecturer_conflicts}, Ven={best_eval.venue_conflicts}), Fitness={best_eval.fitness:.5f}"
                )

        self.stdout.write(self.style.NOTICE("Running Genetic Algorithm optimization..."))
        result = generate_timetable(problem, config=config, progress_callback=progress_cb)

        self.stdout.write("\n" + "=" * 60)
        status_style = self.style.SUCCESS if result.is_feasible else self.style.WARNING
        self.stdout.write(status_style(f"Result Status: {result.status}"))
        self.stdout.write(f"Hard Conflicts: {result.hard_conflicts_count}")
        self.stdout.write(f"  - Student Clashes: {result.evaluation.student_conflicts}")
        self.stdout.write(f"  - Lecturer Clashes: {result.evaluation.lecturer_conflicts}")
        self.stdout.write(f"  - Venue Clashes: {result.evaluation.venue_conflicts}")
        self.stdout.write(f"  - Daily Limit (Max 3) Violations: {result.evaluation.daily_limit_violations}")
        self.stdout.write(f"  - Occurrence Day Duplicates: {result.evaluation.occurrence_day_violations}")
        self.stdout.write(f"Capacity Penalty: {result.evaluation.capacity_penalty}")
        self.stdout.write(f"Generations Run: {result.generation_count}")
        self.stdout.write(f"Runtime: {result.runtime_seconds}s")
        self.stdout.write("=" * 60 + "\n")

        # 3. Save generation run to database
        now = datetime.datetime.now(datetime.timezone.utc)
        run = TimetableGenerationRun.objects.create(
            semester=semester,
            scope_type=scope_type,
            scope_id=scope_id,
            scope_name=problem.scope_name,
            status=TimetableGenerationRun.Status.COMPLETED,
            result_status=result.status.lower(),
            hard_conflicts_count=result.hard_conflicts_count,
            student_conflicts_count=result.evaluation.student_conflicts,
            lecturer_conflicts_count=result.evaluation.lecturer_conflicts,
            venue_conflicts_count=result.evaluation.venue_conflicts,
            daily_limit_violations_count=result.evaluation.daily_limit_violations,
            occurrence_day_violations_count=result.evaluation.occurrence_day_violations,
            capacity_penalty=result.evaluation.capacity_penalty,
            fitness_score=result.fitness,
            conflict_report=result.conflict_report,
            generation_metrics={
                "generations_run": result.generation_count,
                "runtime_seconds": result.runtime_seconds,
                "occurrences_total": problem.total_occurrences,
            },
            assignments_payload=result.assignments_payload,
            completed_at=now,
        )

        self.stdout.write(self.style.SUCCESS(f"Saved TimetableGenerationRun #{run.id}"))

        # 4. Optional publish
        if publish:
            self.stdout.write(self.style.NOTICE("Publishing generated schedule to live timetable entries..."))
            pub_result = publish_generation_run(run)
            self.stdout.write(self.style.SUCCESS(
                f"Published {pub_result['published_entries_count']} entries and materialized {pub_result['materialized_sessions_count']} lecture sessions!"
            ))

