# Timetable Optimizer Engine: Architecture, Pipeline & Integration Guide

## 1. Executive Summary & Architectural Goals

The **Genetic Algorithm (GA) Timetable Optimizer** is an automated scheduling engine built to replace error-prone, manual timetable creation with conflict-free, constraint-satisfying academic schedules for higher education institutions.

### 1.1 Architectural Philosophy: Decoupled Pure-Python Engine

To ensure high computational efficiency, deterministic testability, and clean separation of concerns, the core optimization loop lives in `core/scheduling/optimizer/` and is **strictly decoupled** from Django:

- **Zero Database Imports in Core Optimizer**: The optimizer does not import Django ORM models, querysets, or database connections.
- **Data Transfer via Dataclasses**: Input problems are represented as pure Python dataclasses (`SchedulingProblem`, `CourseOccurrence`, `Slot`, `VenueData`, etc.).
- **Pure-Function Optimization**: The GA optimizer accepts a `SchedulingProblem` and `OptimizerConfig`, executes purely in-memory, and returns a `GenerationResult`.
- **Boundary Adapters**:
  - `preprocessing/pipeline.py`: Translates Django database models into the pure `SchedulingProblem`.
  - `publisher.py`: Translates the optimizer's `GenerationResult` back into Django `TimetableEntry` and `LectureSession` database records.

---

## 2. The Request Pipeline: End-to-End Request Lifecycle

The diagram below illustrates how an HTTP request flows from the frontend client through authentication, permission verification, data extraction, the genetic algorithm, database persistence, and finally to publication and discrepancy management.

sequenceDiagram
autonumber
actor Admin as School / Department Admin
participant Client as Web Frontend (React)
participant API as Django REST API (/api/scheduling/generate/)
participant Perm as CanGenerateTimetable Policy
participant Adapter as Preprocessing Pipeline (DB Adapter)
participant Engine as Genetic Algorithm Engine
participant DB as SQLite / PostgreSQL Database
participant Publisher as Publishing Service

    Admin->>Client: Clicks "Run Generator"
    Client->>API: POST /api/scheduling/generate/ { semester_id, scope_type, scope_id, ... }
    API->>API: Check JWT Authentication & Password Reset Done
    API->>Perm: check_scope_generation_permission(user, semester, scope_type, scope_id)

    alt Permission Denied
        Perm-->>Client: 403 Forbidden (Scope policy restricted)
    end

    API->>API: Validate payload via GenerateTimetableRequestSerializer
    API->>Adapter: build_scheduling_problem_from_db(semester_id, scope_type, scope_id)
    Adapter->>DB: Query Courses, Access Grants, Programs, Student Counts, Venues, Lecturers
    DB-->>Adapter: Raw ORM instances
    Adapter->>Adapter: Precompute conflict graph, expand occurrences, filter valid venues
    Adapter-->>API: Pure-Python SchedulingProblem dataclass
    API->>Engine: generate_timetable(problem, config)

    loop Genetic Algorithm Loop (Generations 1..N)
        Engine->>Engine: Tournament Selection (k=3)
        Engine->>Engine: Uniform & 2-Point Crossover
        Engine->>Engine: Constraint-Aware Mutation & Repair
        Engine->>Engine: Lexicographic Conflict Evaluation
        alt Hard Conflicts == 0 (Optimal)
            Engine->>Engine: Early Termination Triggered
        else Stagnation Limit Reached
            Engine->>Engine: Terminate on Best Available
        end
    end

    Engine-->>API: GenerationResult (Assignments, Metrics, Conflict Diagnostics)
    API->>DB: TimetableGenerationRun.objects.create(...) [Status: Completed, Unpublished]
    DB-->>API: TimetableGenerationRun record (UUID)
    API-->>Client: 200 OK (Run Detail, Metrics & Conflict Diagnostics)

    Admin->>Client: Reviews Diagnostics & Clicks "Publish Timetable"
    Client->>API: POST /api/scheduling/generate/runs/{run_id}/publish/
    API->>Publisher: publish_generation_run(run, created_by_admin)

    critical ATOMIC TRANSACTION
        Publisher->>DB: 1. Delete previous scoped TimetableEntries for semester
        Publisher->>DB: 2. Create recurring TimetableEntry records (RRULE:FREQ=WEEKLY;BYDAY=...)
        Publisher->>DB: 3. Materialize LectureSession instances across semester weeks
        Publisher->>DB: 4. Mark TimetableGenerationRun.is_published = True
    end

    DB-->>Publisher: Transaction Committed
    Publisher-->>Client: 200 OK { status: "published", entries_created, sessions_materialized }

---

## 3. Package Structure: `core/scheduling/optimizer/`

```
core/scheduling/optimizer/
├── __init__.py                # Public facade exports
├── generator.py               # Top-level API: generate_timetable()
├── publisher.py               # DB service: publish_generation_run()
├── models/                    # Pure Python domain dataclasses
│   ├── __init__.py
│   ├── assignment.py          # Assignment(occurrence, slot, venue_id)
│   ├── course.py              # CourseData, CourseType ("lecture" | "practical")
│   ├── lecturer.py            # LecturerData(id, name, staff_id)
│   ├── occurrence.py          # CourseOccurrence (gene unit: <CODE>-1, <CODE>-2)
│   ├── problem.py             # SchedulingProblem (complete input spec)
│   ├── slot.py                # Slot(day, period_index, start_time, end_time)
│   ├── student_group.py       # StudentGroup(program_id, level, code, name)
│   └── venue.py               # VenueData(id, name, capacity, venue_type)
├── preprocessing/             # Adapter & data preparation pipeline
│   ├── __init__.py
│   ├── conflicts.py           # build_student_conflict_graph()
│   ├── occurrences.py         # expand_occurrences()
│   ├── pipeline.py            # build_scheduling_problem_from_db() [DB Adapter]
│   ├── slots.py               # build_valid_slots() (24 valid academic slots)
│   └── venues.py              # build_allowed_venues_map() & filter_allowed_venues()
├── constraints/               # 6 Independent constraint handlers
│   ├── __init__.py
│   ├── capacity.py            # calculate_capacity_penalty() [Soft]
│   ├── daily_limits.py        # check_daily_limits() [Hard: max 3/day per cohort]
│   ├── lecturers.py           # check_lecturer_conflicts() [Hard: double booking]
│   ├── occurrences.py         # check_occurrence_days() [Hard: distinct days]
│   ├── students.py            # check_student_conflicts() [Hard: cohort clashes]
│   └── venues.py              # check_venue_conflicts() [Hard: room clashes]
├── evaluation/                # Objective function & diagnostic reporting
│   ├── __init__.py
│   ├── evaluator.py           # evaluate() & EvaluationResult
│   └── report.py              # generate_conflict_report() [JSON diagnostic report]
└── genetic/                   # Genetic algorithm core
    ├── __init__.py
    ├── algorithm.py           # run_genetic_algorithm() & OptimizerConfig
    ├── chromosome.py          # Chromosome gene vector
    ├── crossover.py           # uniform_crossover(), two_point_crossover()
    ├── mutation.py            # constraint_aware_mutation(), slot/venue mutation
    ├── population.py          # create_initial_population() [Heuristic + Random]
    ├── repair.py              # repair_chromosome() [Deterministic fixes]
    └── selection.py           # tournament_selection(k=3)
```

---

## 4. Preprocessing & Input Formulation

Before the genetic algorithm starts, the preprocessing pipeline transforms raw institutional data into indexed, memory-optimized structures:

### 4.1 Academic Time Slots (`preprocessing/slots.py`)

Higher education lecture timetables operate on 2-hour standard periods across 5 days (Monday to Friday):

- **Periods per Day**:
  1. Period 0: `08:00 – 10:00`
  2. Period 1: `10:00 – 12:00`
  3. Period 2: `12:00 – 14:00`
  4. Period 3: `14:00 – 16:00`
  5. Period 4: `16:00 – 18:00`
- **Friday Jummat Exclusion**: The period `12:00 – 14:00` on Friday (`FR_P2`) is **strictly excluded** to observe communal Friday prayers.
- **Total Valid Slots**: Exactly **24 valid lecture slots** per academic week.

### 4.2 Occurrence Expansion (`preprocessing/occurrences.py`)

Each course defines `required_occurrences_per_week` ($\ge 1$, default 1).

- A course with 1 occurrence becomes 1 gene: `CSC301-1`.
- A course with 2 occurrences becomes 2 independent genes: `CSC301-1` and `CSC301-2`.
- Every occurrence gene carries the course's student cohorts, assigned lecturers, allowed venues, and course type.

### 4.3 Student Cohort Conflict Graph (`preprocessing/conflicts.py`)

To avoid evaluating $O(N^2)$ pairwise cohort intersections at runtime:

- Student cohorts are represented as `StudentGroup(program_id, level)`.
- If Course A (taken by B.Sc Computer Science 200L) and Course B (taken by B.Sc Computer Science 200L) share any `(program, level)` cohort, an edge is added between Course A and Course B in the conflict graph.
- During GA evaluation, student conflict checks run in $O(1)$ set-membership lookups.

### 4.4 Venue Filtering by Academic Type (`preprocessing/venues.py`)

- **Practical Courses (`course_type == "practical"`)**: Allowed venues are strictly restricted to laboratories (`venue_type in ["laboratory", "lab"]`).
- **Lecture Courses (`course_type == "lecture"`)**: Allowed venues are restricted to standard academic spaces (`venue_type in ["lecture_hall", "multipurpose", "auditorium", "classroom"]`). Labs are strictly excluded.

---

## 5. Constraint System & Lexicographic Evaluation

The evaluation engine checks 6 independent constraints and computes a fitness score based on strict lexicographic penalties.

### 5.1 The 6 Independent Constraints

| Constraint Handler                           | Type | Weight ($W_i$) | Description                                                                                                                    |
| -------------------------------------------- | ---- | -------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Student Clashes** (`students.py`)          | Hard | $10,000$       | No two courses sharing the same `(program, level)` student cohort may be scheduled in the same time slot.                      |
| **Lecturer Clashes** (`lecturers.py`)        | Hard | $5,000$        | No lecturer may be scheduled to teach two different courses at the same time slot.                                             |
| **Venue Clashes** (`venues.py`)              | Hard | $5,000$        | No venue may host two different occurrences at the same time slot.                                                             |
| **Same-Day Repeats** (`occurrences.py`)      | Hard | $5,000$        | Multiple occurrences of the same course (e.g., `CSC201-1` and `CSC201-2`) must be scheduled on **different days of the week**. |
| **Daily Lecture Limits** (`daily_limits.py`) | Hard | $2,000$        | A student cohort `(program, level)` must not exceed **3 lectures on any single day**.                                          |
| **Venue Capacity Deficit** (`capacity.py`)   | Soft | $1$            | Soft penalty equal to $\sum \max(0, \text{ExpectedStudents} - \text{VenueCapacity})$ to prefer appropriately sized rooms.      |

### 5.2 Mathematical Objective Function

Let $C_{\text{student}}$, $C_{\text{lecturer}}$, $C_{\text{venue}}$, $C_{\text{day\_repeat}}$, and $C_{\text{daily\_limit}}$ be the number of hard violations for each category, and $P_{\text{capacity}}$ be the total student deficit.

$$\text{Total Penalty} = 10000 \cdot C_{\text{student}} + 5000 \cdot C_{\text{lecturer}} + 5000 \cdot C_{\text{venue}} + 5000 \cdot C_{\text{day\_repeat}} + 2000 \cdot C_{\text{daily\_limit}} + 1 \cdot P_{\text{capacity}}$$

$$\text{Fitness Score} = \frac{1.0}{1.0 + \text{Total Penalty}}$$

- **Optimal Timetable**: $C_{\text{hard}} = 0 \implies \text{Total Penalty} = P_{\text{capacity}}$. If capacity also fits, $\text{Fitness} = 1.0$.
- **Hard Conflict Ordering**: Student cohort clashes are penalized higher than lecturer or venue clashes to prevent academic bottlenecks.

---

## 6. Genetic Algorithm Inner Mechanics

```
Initial Population (Heuristic Seeds + Random Fallbacks)
                     │
                     ▼
          Evaluate Fitness & Rank
                     │
         ┌───────────┴───────────┐
         │                       │
Hard Conflicts == 0?      Stagnation Limit?
         │ (Yes)                 │ (Yes)
         ▼                       ▼
Terminated (Optimal)     Terminated (Best Available)
         │ (No)
         ▼
Preserve Elites (Top 2 Chromosomes)
         │
         ▼
Tournament Selection (k=3)
         │
         ▼
Uniform / Two-Point Crossover (Rate = 0.85)
         │
         ▼
Constraint-Aware Mutation (Rate = 0.08)
         │
         ▼
Deterministic Repair (Slot Shifts for Duplicate Days)
         │
         ▼
    Next Generation Loop
```

### 6.1 Chromosome Representation (`genetic/chromosome.py`)

A chromosome is an array of `Assignment` objects indexed by occurrence gene position:
$$\text{Chromosome} = [\text{Assignment}_0, \text{Assignment}_1, \dots, \text{Assignment}_{N-1}]$$
Where $\text{Assignment}_i = (\text{occurrence}_i, \text{slot}_i, \text{venue\_id}_i)$.

### 6.2 Population Initialization (`genetic/population.py`)

- **Heuristic Seeds**: 50% of the initial population is generated with constraint-aware heuristics:
  - Repeated occurrences of the same course are distributed across different days.
  - Venues are selected matching expected student headcounts.
  - Initial slot assignments avoid immediate cohort clashes where possible.
- **Random Fallback**: 50% of the population is randomized across valid slots and allowed venues to maintain genetic diversity.

### 6.3 Selection (`genetic/selection.py`)

- **Tournament Selection ($k=3$)**: 3 candidate chromosomes are randomly drawn; the one with the highest fitness (or lowest hard conflict count) is selected as a parent.

### 6.4 Crossover (`genetic/crossover.py`)

- **Uniform Crossover**: Swaps occurrence assignments between parents with probability $P_{\text{cross}} = 0.85$.
- Because gene positions strictly correspond to specific course occurrences, crossover never duplicates or drops course occurrences.

### 6.5 Mutation & Repair (`genetic/mutation.py`, `genetic/repair.py`)

- **Constraint-Aware Mutation**: Identifies occurrences currently involved in clashes and prioritizes mutating them to unconflicted slots and venues.
- **Deterministic Repair**: Scans for same-day duplicates of multi-occurrence courses and shifts duplicate occurrences to alternate weekdays.

### 6.6 Termination Conditions (`genetic/algorithm.py`)

The algorithm stops when any of the following conditions are met:

1. **Zero Hard Conflicts**: An optimal or feasible solution is found ($C_{\text{hard}} = 0$).
2. **Stagnation Patience**: If the best fitness does not improve for $P$ generations (default $P = 40$), the search terminates to return the **Best Available** schedule.
3. **Max Generations**: Maximum generation ceiling reached (default 150 to 300).

---

## 7. Database Integration & Publishing Engine (`publisher.py`)

Generating a timetable does **not** silently overwrite the institution's live schedule. Instead, generation produces a `TimetableGenerationRun` record that administrators can review. Publishing is an explicit, transactional action:

### 7.1 Atomic Publishing Process

When `publish_generation_run(generation_run, created_by_admin)` is invoked:

1. **Transaction Isolation**: Wrapped in `django.db.transaction.atomic`.
2. **Purging Old Scope Data**: Deletes existing `TimetableEntry` records matching the run's scope (`school`, `faculty`, or `department`) and semester.
3. **Creating Timetable Entries**: For each assigned occurrence:
   - Calculates recurring day of week (e.g. `MO`, `TU`).
   - Writes `TimetableEntry` with:
     - `entry_type = "lecture"`
     - `recurrence_rule = "RRULE:FREQ=WEEKLY;BYDAY=..."`
     - `recurrence_start_date = semester.lecture_start_date`
     - `recurrence_end_date = semester.lecture_end_date`
4. **Materializing Lecture Sessions**: Calls `materialize_timetable_entry()` to generate date-stamped `LectureSession` instances across each calendar week between `lecture_start_date` and `lecture_end_date`.
5. **Marking Published**: Updates `generation_run.is_published = True`.

---

## 8. Post-Generation Discrepancy Management Integration

Once a timetable is published, it becomes the immutable baseline. Any operational adjustments follow the **Discrepancy Workflow** (`core/discrepancies/`):

- **Lecture Shifts**: If a lecturer needs to move a lecture due to illness or departmental clash, a `DiscrepancyRequest` (`request_type="shift_time"` or `"shift_venue"`) is filed.
- **Audit Trails**: Every adjustment is reviewed, approved, or rejected by administrative officers, logging before-and-after snapshots in `AuditLog`.
- **Preserved Stability**: This eliminates spontaneous schedule disruptions and ensures the GA-optimized baseline remains the foundation.

---

## 9. API Reference & Endpoint Specifications

### 9.1 `POST /api/scheduling/generate/`

Triggers the Genetic Algorithm timetable scheduler for a designated scope and semester.

#### Permissions

- Superusers & School Admins: Full generation rights.
- Faculty Admins: Permitted if `allow_faculty_generation == True`.
- Department Admins: Permitted if `allow_department_generation == True`.

#### Request Body

```json
{
	"semester_id": 1,
	"scope_type": "school",
	"scope_id": 1,
	"population_size": 60,
	"max_generations": 150,
	"mutation_rate": 0.08,
	"stagnation_limit": 40,
	"publish_immediately": false
}
```

_(Note: Both `semester` and `semester_id` are accepted interchangeably)._

#### Response Body (`200 OK`)

```json
{
	"id": "c7a8e291-3b4a-4e2a-89a1-5d98fa6214be",
	"semester": 1,
	"semester_name": "First Semester",
	"scope_type": "school",
	"scope_id": 1,
	"scope_name": "School of Computing",
	"status": "completed",
	"result_status": "optimal",
	"hard_conflicts_count": 0,
	"student_conflicts_count": 0,
	"lecturer_conflicts_count": 0,
	"venue_conflicts_count": 0,
	"daily_limit_violations_count": 0,
	"occurrence_day_violations_count": 0,
	"capacity_penalty": 0,
	"fitness_score": 1.0,
	"is_published": false,
	"conflict_report": {
		"total_hard_conflicts": 0,
		"total_soft_penalties": 0,
		"student_conflicts": [],
		"lecturer_conflicts": [],
		"venue_conflicts": [],
		"daily_limit_violations": [],
		"occurrence_day_violations": [],
		"capacity_violations": []
	},
	"generation_metrics": {
		"generations_run": 24,
		"runtime_seconds": 0.18,
		"occurrences_total": 12
	},
	"assignments_payload": [
		{
			"occurrence_id": "CSC201-1",
			"course_code": "CSC201",
			"slot": {
				"day": "MO",
				"period_idx": 0,
				"start_time": "08:00",
				"end_time": "10:00"
			},
			"venue_id": 4,
			"venue_name": "Lecture Hall 1"
		}
	],
	"created_at": "2026-09-15T02:30:00Z",
	"completed_at": "2026-09-15T02:30:01Z"
}
```

---

### 9.2 `GET /api/scheduling/generate/runs/`

Lists past timetable generation runs.

#### Query Parameters

- `semester`: Filter by semester ID.
- `scope_type`: Filter by `"school"`, `"faculty"`, or `"department"`.
- `scope_id`: Filter by scope ID.

---

### 9.3 `GET /api/scheduling/generate/runs/{id}/`

Returns detailed diagnostic data and full conflict reports for a specific generation run.

---

### 9.4 `POST /api/scheduling/generate/runs/{id}/publish/`

Publishes a generated run into live `TimetableEntry` and `LectureSession` records.

#### Response Body (`200 OK`)

```json
{
	"status": "published",
	"entries_created": 12,
	"sessions_materialized": 180,
	"entries_deleted": 0
}
```

---

### 9.5 `GET & PATCH /api/scheduling/generate/permissions/`

Configures decentralized generation policies for schools.

#### Permissions

- `GET`: Authenticated users.
- `PATCH`: System Superusers only.

#### PATCH Request Body

```json
{
	"school": 1,
	"allow_faculty_generation": true,
	"allow_department_generation": false
}
```

---

## 10. CLI Management Command: `generate_timetable`

Administrators can execute the optimizer directly from the server CLI:

```bash
# Generate school-wide schedule
python manage.py generate_timetable --semester 1 --scope-type school --scope-id 1

# Generate and immediately publish
python manage.py generate_timetable --semester 1 --scope-type school --scope-id 1 --publish

# Adjust hyperparameters
python manage.py generate_timetable --semester 1 --scope-type school --scope-id 1 \
  --population 100 --generations 300 --mutation 0.12 --stagnation 50
```

---

## 11. Automated Test Suite

The optimizer and its integration endpoints are covered by 25 unit and integration tests:

| Test File                                                                                              | Test Scope                                                                                         |
| ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| [`test_optimizer_slots.py`](TimeMap_backend/core/scheduling/tests/test_optimizer_slots.py)             | Verifies the 24 academic slot generation and strict Friday Jummat exclusion (`12:00–14:00`).       |
| [`test_optimizer_constraints.py`](TimeMap_backend/core/scheduling/tests/test_optimizer_constraints.py) | Tests all 6 constraints independently against constructed clash and edge scenarios.                |
| [`test_optimizer_ga.py`](TimeMap_backend/core/scheduling/tests/test_optimizer_ga.py)                   | Tests convergence on solvable instances and graceful fallback on overconstrained instances.        |
| [`test_generation_api.py`](TimeMap_backend/core/scheduling/tests/test_generation_api.py)               | Tests permission enforcement, request payload aliasing, conflict diagnostics, and live publishing. |

Run tests via pytest:

```bash
.venv/bin/pytest core/scheduling/tests/
```
