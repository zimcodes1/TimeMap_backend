# Examination Timetable Optimizer — Technical Architecture & Algorithmic Specification

## 1. Executive Summary & Architectural Paradigm

The **Examination Timetable Optimizer** is a decoupled, modular constraint-satisfaction and physical-resource scheduling engine located in `TimeMap_backend/core/scheduling/exam_optimizer/`. It is architecturally separate from the lecture timetable scheduler (`scheduling/optimizer/`).

### 1.1 The Fundamental Scheduling Abstraction

In ordinary lecture scheduling, the problem is modeled as a weekly recurring grid of fixed 2-hour slots where one course occurrence is assigned to one slot and one room:

$$\text{Course Occurrence} \longrightarrow \text{Fixed Day} \longrightarrow \text{Fixed 2-Hour Slot} \longrightarrow \text{Single Room}$$

In contrast, university examinations cannot be modeled with fixed slots or single-room assignments:
1. **The examination period is continuous and policy-driven**: Examinations span a configured calendar date range (e.g., 2–4 weeks), with operating days from Monday through Saturday (08:00 to 18:00), strictly excluding Sunday and respecting a mandatory Friday 12:00–14:00 Jummat prayer blackout.
2. **Written examinations require dynamic room sizing**: Large cohorts (e.g., 500+ students in general courses such as GST111) require simultaneous allocation across multiple halls within a shared examination window, while smaller cohorts require optimal single-room fitting to prevent wasting high-capacity venues.
3. **Computer-Based Tests (CBT) are throughput-driven**: CBT venues process students across multiple sequential **turns** (batches). When multiple CBT centres operate in parallel during a common examination window, students are distributed across centres to minimize total duration.
4. **Course offerings must remain unified**: A single course offered across multiple academic departments or programs must be scheduled on the **same calendar date and common time window**, even if students sit in different physical halls.
5. **Small examinations may be joined**: To optimize venue and supervisory resources, compatible small courses may share an examination session. For CBT sessions, joining is **strictly capped at a maximum of 2 courses** with zero student registration overlap.

Therefore, the fundamental architectural principle of the examination optimizer is:

$$\mathbf{\text{Exam Event}} \neq \mathbf{\text{Venue Allocation}} \neq \mathbf{\text{Student Assignment}}$$

- **Exam Event**: The logical examination of an academic course, carrying the date and time window decision.
- **Venue Allocation**: The physical room or collection of rooms selected to seat the student cohort.
- **Student Assignment**: The distribution of student groups into specific venues or CBT turns.

---

## 2. High-Level System Architecture

The optimizer follows a phased pipeline architecture mirroring the modular design of the lecture timetable optimizer:

```
┌────────────────────────────────────────────────────────┐
│                   1. PREPROCESSING                     │
│  - Validate Semester Exam Period (H1)                  │
│  - Query Scoped Courses & Hierarchy                    │
│  - Precompute Exact Student Conflict Graph (H3)        │
│  - Resolve Exam Durations & Overrides                  │
│  - Filter & Partition Compatible Venues (H4)           │
│  - Generate Policy-Compliant Candidate Windows (H10)   │
└──────────────────────────┬─────────────────────────────┘
                           │ Pure Domain Model
                           ▼
┌────────────────────────────────────────────────────────┐
│             2. PHYSICAL ALLOCATION PLANNER             │
│  - Written Single-Room Fitting (Min Excess)            │
│  - Written Venue Pair Search (Min Excess & Imbalance)  │
│  - Written Multi-Room Greedy Allocation                │
│  - CBT Parallel Centre Throughput & Turn Planner       │
└──────────────────────────┬─────────────────────────────┘
                           │ Allocation Plans
                           ▼
┌────────────────────────────────────────────────────────┐
│             3. CONSTRUCTIVE SOLVER SEARCH              │
│  - Composite Difficulty Ordering Heuristic             │
│  - Greedy Constraint-Directed Placement               │
│  - Temporal & Venue Clash Avoidance                    │
│  - Student Workload Distribution Scoring               │
└──────────────────────────┬─────────────────────────────┘
                           │ Candidate Schedule
                           ▼
┌────────────────────────────────────────────────────────┐
│            4. SESSION JOINING & LOCAL REPAIR           │
│  - Small Exam Joining (Capped at 2 Courses for CBT)   │
│  - Deterministic Collision Repair Pipeline             │
└──────────────────────────┬─────────────────────────────┘
                           │ Final Candidate
                           ▼
┌────────────────────────────────────────────────────────┐
│          5. INDEPENDENT VALIDATION & REPORTING         │
│  - Hard Constraint Verification (H1 - H11)             │
│  - Workload & Diagnostic Metrics Compilation           │
│  - Packaging into ExamGenerationResult                 │
└────────────────────────────────────────────────────────┘
```

---

## 3. Mathematical Formulation & Scheduling Invariants

### 3.1 Decision Sets & Variables

Let:
- $\mathcal{E} = \{e_1, e_2, \dots, e_n\}$ be the set of logical examination events.
- $\mathcal{S}$ be the set of registered students.
- $\mathcal{V}$ be the set of active examination venues.
- $\mathcal{D} = \{d \in \text{Calendar} \mid \text{start\_date} \le d \le \text{end\_date}\}$ be the candidate examination dates.
- $\mathcal{T}$ be the set of discrete candidate start times ($30$-minute intervals between $08:00$ and $18:00$).
- $N_e$ be the total student count for exam event $e$.
- $C_v$ be the examination seating capacity of venue $v \in \mathcal{V}$.
- $d_e$ be the effective duration in minutes of exam event $e$.
- $\text{Students}(e) \subseteq \mathcal{S}$ be the set of registered students taking exam event $e$.

For each exam event $e \in \mathcal{E}$, the primary decision is the assignment of a calendar placement tuple $(date(e), start(e), end(e))$ and a physical venue plan $\mathcal{A}(e) = \{(v, s_v, turns_v) \mid v \in \mathcal{V}_e\}$:

$$end(e) = start(e) + d_e$$

$$\sum_{(v, s_v, \cdot) \in \mathcal{A}(e)} s_v = N_e$$

---

### 3.2 Hard Constraints (H1 – H11)

All generated examination timetables must satisfy the following eleven hard constraints to be considered feasible:

#### H1. Semester Examination Period Boundaries
Every exam must occur strictly within the administrator-configured semester examination dates:
$$\text{exam\_start\_date} \le date(e) \le \text{exam\_end\_date} \quad \forall e \in \mathcal{E}$$

#### H2. Course Single-Date Rule
All departmental or program offerings of a single academic course must share exactly one calendar date and common examination window:
$$date(p_i) = date(p_j) \quad \text{and} \quad start(p_i) = start(p_j) \quad \forall p_i, p_j \in \text{Populations}(e)$$

#### H3. Student Conflict Absence
If two courses share one or more registered students, their examination windows must not overlap:
$$\text{Conflict}(e_1, e_2) = 1 \iff \text{Students}(e_1) \cap \text{Students}(e_2) \neq \emptyset$$
$$\text{Conflict}(e_1, e_2) = 1 \implies [start(e_1), end(e_1)) \cap [start(e_2), end(e_2)) = \emptyset \quad (\text{if } date(e_1) = date(e_2))$$

#### H4. Venue Type Compatibility
An examination event may only be assigned to venues physically compatible with its examination type:
- **WRITTEN**: Classroom, Exam Hall, or Multipurpose Hall ($\text{venue\_type} \neq \text{LABORATORY}$).
- **CBT**: Facilities equipped with computers or designated as CBT centres.
- **LAB\_PRACTICAL**: Designated laboratories ($\text{venue\_type} = \text{LABORATORY}$).

#### H5. Simultaneous Venue Capacity
For written exams, the number of students assigned to venue $v$ cannot exceed its exam seating capacity:
$$s_v \le C_v \quad \forall (v, s_v, 1) \in \mathcal{A}(e)$$
For CBT exams, the number of students seated in any single turn cannot exceed the centre's capacity:
$$\lceil s_v / turns_v \rceil \le C_v \quad \forall (v, s_v, turns_v) \in \mathcal{A}(e)$$

#### H6. Venue Double-Booking Absence
A venue cannot be assigned to more than one examination event during overlapping time windows:
$$date(e_1) = date(e_2) \land [start(e_1), end(e_1)) \cap [start(e_2), end(e_2)) \neq \emptyset \implies \mathcal{V}(e_1) \cap \mathcal{V}(e_2) = \emptyset$$

#### H7. Population Conservation
Every student registered or expected for an examination event must be allocated to a physical room:
$$\sum_{(v, s_v, \cdot) \in \mathcal{A}(e)} s_v = N_e \quad \forall e \in \mathcal{E}$$

#### H8. Common Examination Window
All physical allocations for a multi-room examination event must share the same start time and finish time.

#### H9. CBT Session Joining Limit
At most two academic courses may share a joined CBT examination session:
$$|\text{CoursesInJoinedSession}| \le 2$$

#### H10. Operating Calendar & Jummat Prayer Blackout
Every examination must occur between Monday and Saturday within the hours of 08:00 and 18:00. On Friday, no examination window may cross or overlap with the 12:00–14:00 Jummat prayer window:
$$date(e).\text{weekday} \in \{0, 1, 2, 3, 4, 5\}$$
$$08:00 \le start(e) < end(e) \le 18:00$$
$$date(e).\text{weekday} = 4 \implies [start(e), end(e)) \cap [12:00, 14:00) = \emptyset$$

#### H11. Maximum Examination Duration
The effective duration of an examination event cannot exceed the maximum administrative limit (default $360$ minutes / $6$ hours):
$$d_e \le \text{max\_exam\_duration}$$

---

### 3.3 Soft Constraints & Optimization Objectives (S1 – S6)

1. **S1 (Student Weekly Load)**: Penalize assigning a student more than 3 examinations within a single calendar week:
   $$\text{Penalty}_{\text{weekly}}(s, w) = \max(0, \text{weekly\_exams}(s, w) - 3) \times 50.0$$
2. **S2 (Student Daily Load)**: Penalize assigning a student more than 1 examination on the same calendar day:
   $$\text{Penalty}_{\text{daily}}(s, d) = \max(0, \text{daily\_exams}(s, d) - 1) \times 30.0$$
3. **S3 (Examination Period Compression)**: Prefer schedules that minimize total active calendar days without causing student workload spikes.
4. **S4 (Venue Capacity Fit)**: For written exams, minimize capacity waste ($C_v - N_e$). For pairs, minimize excess capacity and capacity imbalance ($|C_{v_1} - C_{v_2}|$).
5. **S5 (CBT Throughput Efficiency)**: Balance turns across parallel CBT centres to minimize overall duration.
6. **S6 (Joining Efficiency)**: Reward safely grouping small compatible examinations to reduce independent supervisory events.

---

## 4. Physical Allocation Engine

### 4.1 Written Venue Allocation Algorithm (`allocation/written.py`)

For a cohort of $N$ students requiring a written examination:

1. **Single Venue Best-Fit**:
   Query all capable rooms where $C_v \ge N$. If any exist, select the room minimizing capacity excess:
   $$v^* = \arg\min_{v \in \mathcal{V} \mid C_v \ge N} (C_v - N, \text{name}_v)$$
2. **Venue Pair Best-Fit**:
   If no single room accommodates $N$, evaluate all 2-room combinations $(v_1, v_2)$ where $C_{v_1} + C_{v_2} \ge N$. Rank pairs by:
   $$\text{Excess}(v_1, v_2) = (C_{v_1} + C_{v_2}) - N$$
   $$\text{Imbalance}(v_1, v_2) = |C_{v_1} - C_{v_2}|$$
   Select the pair minimizing excess first, then imbalance.
3. **Multi-Venue Greedy Fallback**:
   If no pair suffices, sort all eligible rooms descending by capacity and assign students greedily until the full population is seated.

### 4.2 CBT Throughput & Turn Planning (`allocation/cbt.py`)

CBT capacity is modeled as student processing throughput over time:
- Available centres: $\{v_1, v_2, \dots, v_m\}$ with capacities $C_1, C_2, \dots, C_m$.
- Total simultaneous computer capacity: $C_{\text{total}} = \sum_{i=1}^m C_i$.
- Required turns:
  $$\text{longest\_turns} = \left\lceil \frac{N}{C_{\text{total}}} \right\rceil$$
- Student assignment per centre:
  $$s_i = \min(C_i \times \text{longest\_turns}, \text{remaining})$$
- Turns per centre:
  $$turns_i = \left\lceil \frac{s_i}{C_i} \right\rceil$$
- Total event duration:
  $$d_{\text{event}} = \max(1, \text{longest\_turns} \times d_{\text{student}})$$

### 4.3 Session Joining Engine (`allocation/joining.py`)

Identifies small compatible examinations and groups them into shared administrative sessions:
- Candidate threshold: CBT cohorts $\le 100$ students; Written cohorts $\le 60$ students.
- Hard preconditions:
  1. Identical calendar date, start time, end time, and exam type.
  2. Zero student registration overlap: $\text{Students}(A) \cap \text{Students}(B) = \emptyset$.
  3. Zero venue overlap: $\mathcal{V}(A) \cap \mathcal{V}(B) = \emptyset$.
  4. **Strict upper bound**: at most 2 courses per joined session.

---

## 5. Combinatorial Solver & Search Strategy

### 5.1 Difficulty Ordering Heuristic (`solver/ordering.py`)

To prevent early placement of flexible courses from blocking heavily constrained courses, exams are placed constructively in descending order of difficulty:

$$\text{Difficulty}(E) = 1.0 \times \text{Population} + 20.0 \times \text{ConflictDegree} + 0.5 \times \text{Duration} + 50.0 \times \text{VenueScarcity}$$

where:
- $\text{ConflictDegree} = |\text{Neighbors in Conflict Graph}|$.
- $\text{VenueScarcity} = \frac{1}{|\text{Eligible Venues}|}$.

### 5.2 Constructive Search (`solver/search.py`)

For each sorted exam event $e$:
1. Determine venue allocation plan and required duration $d_e$.
2. Iterate through all policy-compliant candidate windows within the semester.
3. Filter out windows that clash with already placed events (sharing students or venues).
4. Score remaining windows by student workload impact:
   $$\text{Score} = (\text{weekly\_exams\_count}, \text{daily\_exams\_count}, date, start\_time)$$
5. Commit the candidate minimizing the score. If no candidate window is free, record structured failure diagnostic.

### 5.3 Deterministic Repair Pipeline (`solver/repair.py`)

If an edge-case collision occurs (e.g., following joining or override adjustments):
1. Detect colliding pair $(e_1, e_2)$.
2. Unseat the lower-priority event $e_2$.
3. Search for the nearest conflict-free candidate window.
4. Update event timings deterministically without dropping students.

---

## 6. Independent Post-Optimization Validation (`validation/validator.py`)

The validator operates independently of the solver logic, acting as an automated auditor. It iterates over all scheduled events and asserts invariants H1 through H11:
- Asserts all events fall within `[exam_start_date, exam_end_date]`.
- Asserts no events occur on Sundays or during Friday 12:00–14:00.
- Asserts course uniqueness (no course scheduled on multiple dates).
- Asserts population coverage: $\sum s_v = N_e$.
- Asserts venue capacities and CBT turns.
- Asserts zero student clash and zero venue double-booking.

If any invariant fails, `valid` is set to `False` and a structured list of violation descriptors is returned, preventing the timetable from being marked publishable.

---

## 7. Return Type & Data Contracts (`generator.py`)

### 7.1 `ExamGenerationResult` Dataclass

```python
@dataclass
class ExamGenerationResult:
    status: str                         # "OPTIMAL", "FEASIBLE", "BEST_AVAILABLE", "FAILED"
    events: List[Dict[str, Any]]        # Serialized events matching API contract
    diagnostics: Dict[str, Any]         # Detailed diagnostics dictionary
    metrics: Dict[str, Any]             # Pre-calculated summary metrics for ExamOptimizerRun
    fitness: float                      # Normalized quality score (0.0 to 1.0)
    evaluation: ExamEvaluationResult    # Constraint evaluation breakdown
    conflict_report: Dict[str, Any]     # Human-readable conflict diagnostics
    runtime_seconds: float              # Execution time in seconds
    problem: Optional[ExamSchedulingProblem] = None

    def __iter__(self):
        """Allows unpacking as `events, diagnostics = generate_exam_timetable(...)`."""
        return iter((self.events, self.diagnostics))

    def __getitem__(self, index: int):
        return (self.events, self.diagnostics)[index]
```

### 7.2 Backward Compatibility

Callers written for the original prototype:
```python
events, diagnostics = generate_exam_timetable(semester, scope_type, int(scope_id))
```
continue to work without modification because `ExamGenerationResult` implements tuple unpacking via `__iter__`.

Callers desiring rich object access can use:
```python
result = generate_exam_timetable(semester, scope_type, int(scope_id))
if result.is_feasible:
    print(f"Optimal schedule found with fitness {result.fitness} in {result.runtime_seconds}s")
```

---

## 8. Detailed Module-by-Module Specification

| Module Path | Primary Responsibility | Key Functions / Classes | Inputs & Outputs |
| :--- | :--- | :--- | :--- |
| `models/time_window.py` | Encapsulates candidate time windows and institutional calendar policies. | `CandidateWindow`<br>`CalendarPolicy` | Represents concrete discrete slots (08:00–18:00, Mon–Sat, Friday prayer blackout). |
| `models/event.py` | Encapsulates logical exam demand and offering sub-populations. | `ExamEvent`<br>`ExamPopulation` | Tracks course identity, exam type, durations, headcounts, registered student IDs. |
| `models/allocation.py` | Encapsulates room assignments, CBT batches, and physical plans. | `VenueAllocation`<br>`CBTTurn`<br>`VenuePlan` | Tracks seated student counts, turn breakdowns, capacities, and room IDs. |
| `models/problem.py` | Top-level immutable problem representation decoupled from Django ORM. | `ExamSchedulingProblem` | Holds events, scoped venues, precomputed conflict graph, candidate windows, policy. |
| `preprocessing/calendar.py` | Generates candidate windows and validates operating policy. | `date_windows()`<br>`is_within_policy()`<br>`build_candidate_windows()` | Generates 30-min candidate slots; enforces Jummat blackout (12:00–14:00 Fri). |
| `preprocessing/venues.py` | Resolves hierarchical room access and filters room compatibility. | `resolve_scope_venues()`<br>`filter_venues_by_exam_type()`<br>`get_venue_capacity()` | Scopes rooms across Dept $\to$ Faculty $\to$ School; filters computer labs and practical labs. |
| `preprocessing/durations.py` | Resolves exam duration overrides and default policies. | `resolve_exam_durations()` | Maps course overrides or returns defaults (Written: 120m, CBT: 30m/student, Lab: 120m). |
| `preprocessing/conflicts.py` | Queries registrations and precomputes pairwise conflict graphs. | `build_exam_conflict_graph()` | Returns `(students_by_course, conflict_graph, cohort_overlaps)`. |
| `preprocessing/populations.py`| Aggregates student counts and builds logical `ExamEvent` objects. | `resolve_course_populations()` | Reconciles registration headcounts with estimated counts; instantiates `ExamEvent`. |
| `preprocessing/pipeline.py` | Database adapter orchestrating the complete preprocessing pipeline. | `build_exam_problem_from_db()` | Queries Django models and returns a clean `ExamSchedulingProblem`. |
| `allocation/written.py` | Dynamic room allocation for written and practical examinations. | `allocate_written_venues()` | Implements single-room closest fit, venue-pair search, and multi-venue greedy allocation. |
| `allocation/cbt.py` | Throughput-based CBT turn and parallel centre planning. | `allocate_cbt_venues()` | Distributes students across parallel CBT halls and computes turn duration. |
| `allocation/joining.py` | Identifies small compatible examinations and merges sessions. | `join_compatible_sessions()` | Capped at $\le 2$ courses; checks zero student overlap and distinct room assignments. |
| `allocation/planner.py` | Unified facade dispatching to written or CBT allocation logic. | `allocate_venues()` | Dispatches by `exam_type`; provides exact parity with legacy `_allocate()`. |
| `constraints/calendar.py` | Verifies H1 (period bounds) and H10 (operating hours & Jummat blackout). | `check_calendar_constraints()` | Returns list of calendar policy error dicts. |
| `constraints/conflicts.py` | Verifies H3 (absence of student double-booking). | `check_student_conflicts()` | Checks pairwise student intersection across overlapping windows. |
| `constraints/venues.py` | Verifies H4, H5, H6, and H7 venue constraints. | `check_venue_constraints()` | Validates capacity, CBT turns, population coverage, and room double-booking. |
| `constraints/workload.py` | Calculates student examination distribution metrics. | `calculate_student_workload()`<br>`calculate_workload_penalty()` | Computes weekly exams ($\le 3$) and daily exams ($\le 1$) metrics and penalties. |
| `evaluation/evaluator.py` | Computes comprehensive schedule fitness and lexicographic rank. | `ExamEvaluationResult`<br>`evaluate_exam_schedule()` | Evaluates schedule against all constraints; returns weighted penalties and fitness. |
| `evaluation/report.py` | Formats diagnostic conflict reports for administrator inspection. | `generate_exam_conflict_report()` | Formats structured conflict report matching lecture optimizer format. |
| `solver/ordering.py` | Difficulty heuristic sorting heavily constrained events first. | `compute_exam_difficulty()`<br>`order_exam_events()` | Computes composite difficulty score from population, conflicts, duration, and scarcity. |
| `solver/search.py` | Constructive constraint-directed placement algorithm. | `search_exam_schedule()` | Places events into lowest-cost conflict-free candidate windows. |
| `solver/repair.py` | Deterministic conflict repair pipeline. | `repair_conflicts()` | Re-seats conflicting events into earliest valid alternate windows. |
| `validation/validator.py` | Independent post-optimization validator verifying all hard invariants. | `validate_exam_timetable()` | Validates H1 through H11; returns `{"valid": bool, "errors": List}`. |
| `validation/report.py` | Compiles API diagnostics dictionary and workload statistics. | `build_exam_diagnostics()` | Prepares complete diagnostics payload for `ExamOptimizerRun` persistence. |
| `generator.py` | Top-level facade coordinating the entire optimization workflow. | `generate_exam_timetable()`<br>`ExamGenerationResult` | Orchestrates preprocessing, search, joining, repair, validation, and metrics packaging. |
| `__init__.py` | Package root exporting clean facades and legacy compatibility helpers. | Package exports | Exports `generate_exam_timetable`, `ExamGenerationResult`, `_allocate`, `_date_windows`, `_within_policy`. |

---

## 9. Verification & Quality Assurance

### 9.1 Automated Test Suites

The implementation is verified by three test suites:

1. **`scheduling.tests.test_exam_optimizer_planning`**:
   - Asserts operating calendar excludes Sundays and Friday 12:00–14:00 Jummat blackout.
   - Asserts written exam can split one population across multiple rooms.
   - Asserts CBT uses parallel centres and calculates turns when population exceeds capacity.
2. **`scheduling.tests.test_exam_optimizer_runs`**:
   - Asserts full API workflow: optimize $\to$ inspect $\to$ approve $\to$ publish $\to$ view timetable.
   - Asserts permission boundaries for Department, Faculty, and School exam officers and admins.
3. **`scheduling.tests.test_exam_optimizer_modular`**:
   - Unit tests for written single-room closest fit vs pair allocation.
   - Unit tests for CBT turn throughput calculation.
   - Unit tests enforcing the hard rule of at most 2 courses per joined CBT session.
   - Unit tests verifying the independent validator catches student clashes and room double-booking.
   - Unit tests verifying `ExamGenerationResult` tuple unpacking and attribute access.

