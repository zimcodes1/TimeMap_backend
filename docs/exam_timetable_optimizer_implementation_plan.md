# Exam Timetable Optimizer — Full Implementation Plan

## 1. Purpose

This document defines the implementation plan for the **examination timetable optimizer**, as a separate scheduling engine from the existing lecture timetable optimizer.

The exam optimizer must model the way examinations are actually conducted:

- the examination period is defined by administrators at semester level;
- there is no universal fixed weekly slot grid like the lecture timetable;
- written examinations are primarily constrained by the size and compatibility of available venues;
- CBT examinations are constrained by **throughput over time**, because a CBT venue can process several turns of students;
- one course may be offered by multiple departments/faculties with different student populations;
- all populations writing the same course must share the **same exam day and common exam window**, even when they are physically distributed across multiple venues;
- a single exam may use several venues simultaneously;
- small exams may be deliberately joined into the same examination period to avoid wasting venue/time resources;
- at most two courses should be joined into one CBT period;
- student conflict relationships are derived during preprocessing, rather than relying only on course identity;
- invigilator assignment is outside the optimizer's responsibility.

The fundamental abstraction is:

> **Exam event ≠ venue allocation ≠ student assignment.**

An exam event represents the logical examination of a course. Venue allocations represent where and how the student population is physically processed.

## 2. Core Design Principle

The existing lecture timetable can be thought of as:

```text
Course occurrence
    ↓
fixed day
    ↓
fixed 2-hour slot
    ↓
one compatible venue
```

The exam timetable should instead be modeled as:

```text
Course
    ↓
Exam event
    ↓
student populations / offerings
    ↓
exam type
    ↓
exam date + common exam window
    ↓
one or more venue allocations
    ↓
student groups / CBT turns
```

This is the central architectural difference.

**Do not reuse the lecture optimizer's fixed 2-hour slot assumption.**

## 3. Scope of the Optimizer

The optimizer is responsible for:

1. determining when an exam is held;
2. determining the examination type(though this would be provided from the backend);
3. determining compatible venues;
4. determining whether an exam uses one venue or multiple venues;
5. distributing students across compatible venues where required;
6. calculating/approximating CBT duration and turn requirements;
7. joining compatible small exams when beneficial;
8. preventing student conflicts;
9. enforcing examination-period limits;
10. producing a validated exam timetable;
11. producing enough metadata for the UI to explain how each exam was allocated.

The optimizer is **not** responsible for:

- assigning invigilators;
- deciding invigilator workload;
- marking attendance;
- grading exams;
- generating examination questions;
- determining student registration data;
- manually correcting academic registration errors.

Those are separate systems/services.

## 4. Semester Examination Configuration

An exam timetable must not be generated until the administrator has defined the examination period for the semester.

Conceptually:

```text
Semester
├── academic_session
├── semester
├── ...
├── exam_period_start
└── exam_period_end
```

The exact existing schema should be reused where possible(there's an existing Semseter system).

### Required validation

Before optimization:

```text
exam_period_start != null
exam_period_end != null
exam_period_start < exam_period_end
```

The system should reject timetable generation if the examination period is missing or invalid.

### Configurable examination policy

The semester or exam configuration should also be able to hold:

```text
ExamConfiguration
├── default_written_duration
├── default_cbt_duration_per_student
├── default_lab_practical_duration
├── max_exam_duration
├── max_courses_per_cbt_session
├── max_venues_per_exam
├── maximum_student_exam_load_per_week
├── preferred_minimum_students_per_cbt_session
├── preferred_venue_utilization
└── other institution-specific policies
```

Not every field must exist in exactly this form. The important principle is to keep institution-specific rules configurable rather than hardcoding them inside the solver.

## 5. Exam Types

A course must explicitly resolve to an exam type.

Minimum supported types:

```text
WRITTEN
CBT
LAB_PRACTICAL
```

The design should permit additional types later.

Conceptually:

```text
ExamType
├── code
├── name
├── venue_category
├── duration_model
├── default_duration
├── default_duration_per_student
├── max_duration
├── allows_multiple_venues
├── allows_joining
└── max_courses_per_session
```

### 5.1 Written

Written exams normally use halls/classrooms with a configured `exam_capacity`.

The basic duration is administrator-controlled:

```text
default_written_duration
```

and individual courses may override it:

```text
course_exam_duration
```

Resolution:

```text
course-specific duration
    if present
else
exam-type/default written duration
```

Written exams are generally allocated to the venue or venue pair whose capacity best matches the required student population.

### 5.2 CBT

CBT duration is throughput-based.

Administrators may configure:

```text
average_cbt_exam_duration_per_student
```

For example:

```text
20 minutes
25 minutes
30 minutes
```

An administrator may also override the duration for a particular course when needed.

Resolution:

```text
course-specific CBT duration-per-student
    if present
else
global/default CBT duration-per-student
```

The important point is that CBT capacity is **not** a simple:

```text
students <= venue_capacity
```

constraint over the entire exam period.

A CBT venue can process several turns over time.

### 5.3 Lab Practical

Lab practical examinations should use compatible laboratories.

Unlike CBT, the exact duration model should remain configurable because the institution may later use:

- fixed practical duration;
- per-student duration;
- per-batch duration;
- equipment-dependent duration.

For the first implementation, use the same general architecture as written exams unless the existing academic data model already contains a better practical-specific rule.

## 6. Course vs Course Offering vs Exam Event

This distinction is critical.

Suppose:

```text
CSC301
    Computer Science → 100 students
    Software Engineering → 50 students
```

The logical course is:

```text
CSC301
```

but its populations are:

```text
CSC301 Offering A = 100
CSC301 Offering B = 50
```

The optimizer should create one logical exam event:

```text
ExamEvent(CSC301)
```

containing multiple student populations.

Conceptually:

```text
ExamEvent
├── course
├── exam_type
├── exam_date
├── start_time
├── end_time
├── duration
└── populations[]
```

and:

```text
ExamPopulation
├── course
├── department/faculty/context
├── student_count
└── student_ids / registration reference
```

The actual existing data model may represent this differently. The implementation should adapt the abstraction to the existing models rather than duplicating registration data.

## 7. The Most Important Invariant: Same Course, Same Examination Day

A course must not be scheduled on different days.

For example:

```text
CSC301
    Department A → Monday
    Department B → Tuesday
```

is invalid.

Instead:

```text
CSC301
    Department A → Monday 8:00–10:00 → Venue A
    Department B → Monday 8:00–10:00 → Venue B
```

is valid.

Therefore:

$$
date(p_i)=date(p_j)
$$

for all populations $p_i,p_j$ belonging to the same logical exam event.

Similarly, all allocations for the same exam event must belong to a common examination window.

## 8. Exam Event Creation Pipeline

The preprocessing pipeline should construct the logical exam demand before the optimizer runs.

Recommended sequence:

```text
Raw academic data
    ↓
Validate exam-eligible courses
    ↓
Resolve exam type
    ↓
Build course populations
    ↓
Normalize department/faculty offerings
    ↓
Build student-course registrations
    ↓
Build student conflict graph
    ↓
Build exam events
    ↓
Build venue eligibility
    ↓
Build exam duration metadata
    ↓
Build candidate exam groups
    ↓
Run optimizer
    ↓
Deterministic repairs
    ↓
Final validation
```

The existing preprocessing pipeline should remain the authoritative place for transformations that are already handled by the current system.

Do not duplicate those transformations inside the solver.

## 9. Student Conflict Model

The exam optimizer should reason primarily about **student conflicts**, not only course identity.

For two exam events $A$ and $B$:

$$
Conflict(A,B)=1
$$

when at least one student is required to take both exams and they would overlap.

The strongest exact definition is:

$$
Conflict(A,B)
=
\begin{cases}
1,& Students(A)\cap Students(B)\neq\varnothing\\
0,& otherwise
\end{cases}
$$

The preprocessing pipeline should ideally calculate this before optimization.

### Conflict graph

Represent the result as a graph:

```text
ExamEvent
   ↕
Conflict
   ↕
ExamEvent
```

Each edge means the two exams cannot occupy overlapping examination windows.

### Similar cohorts

A full conflict edge is not the only useful relationship.

For optimization and repair heuristics, store an optional overlap metric:

$$
Overlap(A,B)
=
\frac{|Students(A)\cap Students(B)|}
{|Students(A)\cup Students(B)|}
$$

or another metric consistent with the existing preprocessing pipeline.

This allows the system to distinguish:

```text
very similar cohorts
moderately overlapping cohorts
independent cohorts
```

without redefining hard conflicts.

## 10. Why the 1–3 Exams per Week Rule Is Different

The rule:

```text
students should write roughly 1–3 exams per week
```

is an administrative scheduling preference/rule.

It should not replace the conflict graph.

The conflict graph answers:

> "Can these two exams overlap?"

The weekly-load rule answers:

> "Is this student's exam distribution reasonable?"

Therefore:

### Hard

```text
A student cannot be required to sit two overlapping exams.
```

### Soft/configurable

```text
Do not give a student an excessive number of exams in one week.
```

The exact interpretation can be configured by administrators.

## 11. Exam Period as a Continuous/Configurable Calendar

The examination period is not a fixed five-day weekly grid.

Instead:

```text
ExamPeriod
    start_date
    end_date
```

The optimizer generates candidate dates and time windows within it.

The institution may operate:

```text
Monday–Friday
Monday–Saturday
some Sundays
morning/afternoon/evening sessions
```

Therefore operating days and daily availability should be configurable.

The institution currently permits examinations only from **Monday through Saturday**, within **8:00am–6:00pm**, with the exception of **Friday 12:00pm–2:00pm**, which is blocked for Jummat prayer.

Therefore the base exam-day policy is:

```text
Monday    → enabled
Tuesday   → enabled
Wednesday → enabled
Thursday  → enabled
Friday    → enabled, but 12:00–14:00 unavailable
Saturday  → enabled
Sunday    → disabled
```

The daily operating window is:

```text
08:00–18:00
```

The Friday blackout is a hard constraint and must never be crossed by an exam window. The implementation should still keep operating days/windows configurable in the data model so the institution can support policy changes later, but the current default policy must be the one above.

## 12. Time Representation

Although the final conceptual model is not a fixed-slot timetable, the solver still needs a finite representation.

Recommended implementation:

> Convert the examination period into a configurable set of **candidate start times** and/or **time segments** fine enough for the institution's operating rules.

For example:

```text
08:00
08:15
08:30
08:45
...
17:30
```

or a coarser institution-specific granularity.

This is not the same as saying that exams have fixed slots.

It merely gives the optimizer a finite search space.

## 13. Written Exam Duration

For written exams:

```text
duration =
course-specific duration
or default written exam duration
```

For example:

```text
GST111 → 6 hours
CSC301 → 2 hours
MTH301 → 3 hours
```

The optimizer must preserve the configured duration.

## 14. Written Exam Venue Selection

The written venue model should use:

```text
exam_capacity
```

rather than ordinary lecture timetable capacity.

Example:

```text
Hall A → exam_capacity = 120
Hall B → exam_capacity = 200
Hall C → exam_capacity = 350
```

### Preferred single-venue rule

For a population $N$, find venues satisfying:

$$
capacity_v \ge N
$$

Among them, prefer the closest capacity to the population:

$$
v^* =
\arg\min_v(capacity_v-N)
$$

subject to:

$$
capacity_v\ge N
$$

This prevents a 100-student exam from consuming a 500-seat venue when a 120-seat venue is available.

## 15. Written Multi-Venue Allocation

A large population may require several venues.

For example:

```text
CSC301 = 500 students

Venue A = 300
Venue B = 220
```

Then:

```text
CSC301
    Monday 8:00–10:00
        Venue A → 300
        Venue B → 200
```

The course remains one exam event.

All students take the exam during the common exam window.

### Important

The optimizer should not interpret:

```text
Venue A → 300
Venue B → 200
```

as two separate CSC301 examinations.

It is one exam with two physical allocations.

## 16. Venue Pair Selection

When no single venue can reasonably accommodate $N$, consider venue pairs.

Candidate pair:

$$
(v_1,v_2)
$$

must satisfy:

$$
capacity(v_1)+capacity(v_2)\ge N
$$

The primary goal is to avoid unnecessarily large venues while maintaining a good distribution.

A useful first-stage candidate ranking is:

1. both venues individually eligible;
2. combined capacity covers the population;
3. combined excess capacity is minimized;
4. capacities are reasonably balanced;
5. deterministic tie-breaker.

Define:

$$
excess(v_1,v_2)
=
capacity(v_1)+capacity(v_2)-N
$$

Lower excess is generally better.

For a more balanced split, optionally add:

$$
imbalance(v_1,v_2)
=
\left|
\frac{capacity(v_1)}{capacity(v_1)+capacity(v_2)}
-
\frac{1}{2}
\right|
$$

The exact balancing metric can later be tuned empirically.

### Important note on the "average close to N/2" idea

Your proposed heuristic is reasonable as a starting point, but it should not be the sole objective.

A pair should first be **feasible**, then ranked by:

```text
total excess capacity
+
allocation balance
+
institution-specific venue preferences
```

This is safer than selecting solely by the average of capacities.

## 17. Written Small-Course Joining

A major optimization feature is joining small exams.

The purpose is to reduce the number of separate examination occurrences.

For example:

```text
CSC211 = 40 students
MTH211 = 50 students
```

may be grouped into a common period when:

- their students do not conflict;
- their exam types are compatible;
- their duration rules are compatible;
- their venue requirements are compatible;
- administrative rules permit grouping.

The optimizer should **not** assume that all small exams must be joined.

Joining should be an optimization objective.

## 18. CBT as a Throughput Problem

For CBT, venue capacity is the number of simultaneous computers/seats.

Suppose:

```text
ICT = 100 computers
students = 250
duration/student = 30 minutes
```

Number of required turns:

$$
turns =
\left\lceil
\frac{250}{100}
\right\rceil=3
$$

Approximate processing duration:

$$
duration =
turns\times30=90\text{ minutes}
$$

This is the basic CBT duration model.

## 19. CBT With Multiple Venues

Suppose:

```text
ICT = 100
Library = 80
Students = 250
duration/student = 30 minutes
```

Using both venues:

```text
ICT → 100
Library → 80
```

leaves:

```text
70 students
```

The final turn may therefore use:

```text
ICT → 70
```

The approximate event duration is driven by the slower venue:

$$
duration_{event}
\approx
\max(duration_{ICT},duration_{Library})
$$

subject to the actual turn assignment.

If all venues operate simultaneously, their processing times should be evaluated in parallel rather than summed.

## 20. CBT Student Assignment

The statement:

> students cannot be split across multiple sessions

should be implemented as:

> every student registered for an exam event receives exactly one CBT sitting within that event's common exam window.

A student may not be assigned:

```text
CSC301
    08:00 turn
and
CSC301
    10:00 turn
```

However, the **course population may be distributed among different venue/turn allocations**:

```text
CSC301
    ICT:
        08:00 → Group A
        08:30 → Group B

    Library:
        08:00 → Group C
```

The exact turn-generation method can initially be deterministic.

## 21. CBT Joining

Joining small CBT exams is particularly important because a tiny CBT cohort may otherwise consume an entire venue/time administration period.

Example:

```text
CSC201 = 30
MTH201 = 40
```

Potential joined event:

```text
CSC201 + MTH201
```

with a shared execution window, provided all joining conditions are satisfied.

For the implementation, enforce:

$$
numberOfCoursesInCBTSession\le2
$$

as a hard rule.

No optimizer state should permit:

```text
CSC201 + MTH201 + PHY201
```

in a single CBT session.

## 22. CBT Joining Preconditions

Two CBT exams may be candidates for joining only if:

```text
1. no student conflict exists;
2. both are CBT;
3. venue pools are compatible;
4. their duration assumptions are compatible;
5. the maximum course-per-session rule is not exceeded;
6. administrative restrictions permit grouping.
```

Because conflicts are precomputed, the optimizer does not need to discover these relationships from scratch.

## 23. CBT Joined-Demand Calculation

For two courses $A,B$ with populations $N_A,N_B$:

$$
N_{joined}=N_A+N_B
$$

If the same CBT venue is used, the required turns are approximately:

$$
turns=\left\lceil\frac{N_{joined}}{capacity}\right\rceil
$$

However, if the courses have very different per-student durations, e.g.:

```text
A = 20 min/student
B = 40 min/student
```

do not blindly combine them into a single simple average.

Instead, represent the joined session as distinct student groups and calculate processing demand by turn.

For the first implementation, it is reasonable to require a common/default CBT duration-per-student unless an advanced scheduling mode is introduced.

## 24. Same-Course / Multi-Offering Allocation

Consider:

```text
CSC301
    Department A = 100
    Department B = 50
```

The logical exam event is:

```text
CSC301
```

but its allocations may be:

```text
CSC301
Monday 08:00–10:00

Department A
    Venue A → 100

Department B
    Venue B → 50
```

Do not merge the populations merely because the course code matches if the existing academic model distinguishes their student populations.

The logical exam identity and physical allocation identity must remain separate.

## 25. GST / School-Wide Courses

GST courses are a key test case.

Suppose:

```text
GST111
    Faculty A = 150
    Faculty B = 100
    Faculty C = 80
    Faculty D = 70
```

The optimizer should treat this as one logical exam:

```text
GST111
```

and seek a common exam date/window.

Its physical allocation can be:

```text
Venue A → Faculty A
Venue B → Faculty B
Venue C → Faculty C
Venue D → Faculty D
```

or the populations can be combined differently if the venue/scope rules permit it.

The crucial invariant remains:

$$
date_{GST111,A}
=
date_{GST111,B}
=
date_{GST111,C}
=
date_{GST111,D}
$$

## 26. Venue Model

The existing venue ownership/access model from the lecture scheduler should continue to be respected.

Conceptually:

```text
Venue
├── owner_type
├── owner_id
├── venue_type
├── exam_capacity
├── normal_capacity
├── supports_written
├── supports_cbt
├── supports_lab_practical
├── availability
└── ...
```

The exact schema should match the existing system.

The important separation is:

```text
normal lecture capacity
≠
exam capacity
```

A venue can have different effective capacities for different activities.

## 27. Venue Eligibility

Before the optimizer starts, generate:

```text
EligibleVenues[ExamEvent]
```

This should be resolved using:

```text
exam type
+
scheduling scope
+
venue ownership/access
+
venue compatibility
+
availability
```

The solver should not repeatedly reconstruct venue access rules.

This belongs in preprocessing.

## 28. Important Resource Abstraction

The implementation should distinguish:

```text
Venue eligibility
Venue capacity
Venue throughput
Venue availability
```

For example:

### Written

```text
eligible = supports_written
capacity = exam_capacity
throughput = not usually relevant
```

### CBT

```text
eligible = supports_cbt
capacity = computer capacity
throughput = capacity / duration_per_student
```

### Laboratory

```text
eligible = supports_lab_practical
capacity = practical exam capacity
availability = configured operating availability
```

## 29. Why There Is No Lecture-Style Capacity Precheck

The lecture scheduler can use:

$$
occurrences\le slots\times venues
$$

because the weekly slot system is fixed.

The exam scheduler cannot use the same formula because:

- the examination period is variable;
- exam duration is variable;
- CBT is processed in turns;
- different venues may operate simultaneously;
- an exam may use multiple venues;
- small exams may be joined.

Therefore the equivalent prechecks should be **resource-specific**.

## 30. Useful Examination Feasibility Checks

Before invoking the expensive optimizer, run cheap checks.

### 30.1 Missing exam period

Fail if the semester examination window is undefined.

### 30.2 Missing exam type

Fail or quarantine courses whose exam type cannot be resolved.

### 30.3 No eligible venue

For each exam event:

$$
EligibleVenues(E)\neq\varnothing
$$

For a written exam requiring a single venue, at least one venue should satisfy the population.

If no single venue is sufficient but multi-venue allocation is allowed, verify that an allowed venue combination exists.

### 30.4 CBT time feasibility

For CBT, calculate a theoretical minimum processing time using available throughput.

For a population $N$:

$$
capacity/time =
\sum_v\frac{capacity_v}{durationPerStudent}
$$

approximately, subject to the institution's actual turn model.

This is only a preliminary check.

## 31. Exam Event Candidate Model

Do not immediately create final timetable assignments.

Generate **candidate sessions**.

Conceptually:

```text
CandidateSession
├── exam_event(s)
├── date
├── start_time
├── end_time
├── duration
├── venue_plan
├── student_groups
└── score
```

A candidate session is an option the optimizer can select.

Example:

```text
CSC301
Monday
08:00–10:00
    Hall A = 200
```

versus:

```text
CSC301
Monday
08:00–10:00
    Hall A = 120
    Hall B = 100
```

versus another date/time.

This reduces solver complexity and makes the domain logic easier to test.

## 32. Candidate Generation Should Be Type-Specific

### Written candidates

Generate:

```text
single venue candidates
venue-pair candidates
multi-venue candidates when necessary
```

Rank them by venue fit.

### CBT candidates

Generate:

```text
single CBT venue
multiple CBT venues
joined two-course CBT session
```

and calculate the corresponding approximate processing duration.

### Lab practical

Generate compatible laboratory allocations using the practical duration model.

## 33. Maximum Exam Duration

Introduce:

```text
max_exam_duration
```

as a configurable policy.

For example:

```text
max_exam_duration = 6 hours
```

For CBT, if the calculated processing duration exceeds the maximum, the optimizer should consider splitting the population across more venues.

This is **not** a split into different exam sessions/days.

It is:

```text
same exam event
same date
same common window
more simultaneous venues
```

provided the institution has sufficient eligible venues.

If even all eligible concurrent venues cannot bring the duration under the maximum, the system should report the condition rather than silently violating the rule.

## 34. CBT Venue Splitting Logic

Suppose:

```text
Population = 400

ICT = 100
Library = 80

duration/student = 30 min
max duration = 2 hours
```

With only ICT:

$$
turns=\lceil400/100\rceil=4
$$

$$
duration=4(30)=120\text{ min}
$$

With both:

$$
capacity=180
$$

and simultaneous processing reduces the exam event's completion time significantly.

Candidate plans should therefore be evaluated based on:

```text
number of venues
+
estimated duration
+
utilization
+
administrative preferences
```

rather than simply minimizing venue count.

## 35. Objective Function

Use a lexicographic or weighted objective.

A practical ordering is:

### Priority 1 — eliminate hard violations

No solution with:

- student conflict;
- unavailable venue;
- insufficient venue capacity at a simultaneous allocation;
- incompatible exam type;
- course scheduled on multiple dates;
- missing exam;
- invalid duration.

### Priority 2 — minimize total examination span

Prefer solutions that finish the complete exam timetable earlier within the configured period.

### Priority 3 — minimize unnecessary venue splitting

Prefer one appropriate venue over two or more when one is sufficient.

### Priority 4 — improve venue fit

For written exams:

$$
fit(v)=|capacity_v-N|
$$

For a valid single venue $capacity_v\ge N$, minimize:

$$
capacity_v-N
$$

### Priority 5 — reduce excessive CBT duration

Prefer plans that use additional simultaneous venues when doing so materially reduces processing time.

### Priority 6 — maximize useful joining

Join small exams where safe and beneficial.

### Priority 7 — balance student workload

Prefer a reasonable distribution of exams over weeks/days.

### Priority 8 — improve utilization

Avoid leaving very large venues mostly unused when a better compatible assignment exists.

## 36. Hard Constraint Set

The first implementation should make these hard constraints explicit.

### H1. Examination period

Every exam must occur within:

$$
examPeriodStart\le examStart
$$

and:

$$
examEnd\le examPeriodEnd
$$

### H2. Course single-date rule

For an exam event $E$:

$$
date(E)=one\ unique\ date
$$

All populations of that course must share that date.

### H3. Student conflict

If:

$$
Conflict(A,B)=1
$$

then their examination windows may not overlap.

### H4. Venue compatibility

An allocation must use a venue compatible with the exam type.

### H5. Simultaneous venue capacity

At every relevant time interval:

$$
\sum assignedStudents(v,t)
\le examCapacity(v)
$$

### H6. Venue availability

A venue cannot be used outside its configured availability.

### H7. Population conservation

Every registered student must be allocated exactly once for an exam event.

$$
\sum allocations(student,E)=1
$$

### H8. Same exam window

All venue allocations belonging to the same exam event must use the same common exam window.

### H9. CBT session joining limit

$$
coursesPerCBTSession\le2
$$

### H10. Operating-day and time-window rule

Every exam must be scheduled only on Monday through Saturday, between 08:00 and 18:00, with Friday 12:00–14:00 unavailable.

Equivalently, for an exam interval $I_e=[start_e,end_e)$:

- its date must be Monday–Saturday;
- $08{:}00\le start_e$;
- $end_e\le18{:}00$;
- on Friday, $I_e\cap[12{:}00,14{:}00)=\varnothing$.

### H11. Maximum examination duration

Where configured:

$$
duration(E)\le maxExamDuration
$$

unless a deliberate administrative override exists.

## 37. Soft Constraint Set

These should normally be optimization objectives rather than absolute constraints.

Examples:

```text
student exams per week
student exams on consecutive days
venue utilization
number of venues per course
number of separate exam sessions
CBT throughput efficiency
written venue capacity excess
distribution across examination period
```

A configurable policy can promote some of these to hard constraints later.

## 38. Recommended Solver Architecture

Because the existing lecture optimizer already works well with a preprocessing and repair pipeline, the exam optimizer should follow the same broad architecture:

```text
Input
  ↓
Preprocessing
  ↓
Normalized exam model
  ↓
Conflict graph
  ↓
Candidate generation
  ↓
Optimization
  ↓
Deterministic repair
  ↓
Validation
  ↓
Final timetable
```

Do not force all domain intelligence directly into the solver.

The solver should consume normalized, solver-ready objects produced by preprocessing.

## 39. Preprocessing Pipeline

Recommended exam preprocessing stages:

```text
P1. Validate semester examination period
P2. Resolve exam types
P3. Resolve course populations
P4. Resolve student registrations
P5. Construct exam events
P6. Construct conflict graph
P7. Resolve venue eligibility
P8. Calculate duration metadata
P9. Generate venue candidates
P10. Generate CBT candidate groupings
P11. Generate feasible time candidates
P12. Produce solver-ready structures
```

The existing preprocessing code may already perform several of these tasks.

The new implementation should consume its outputs rather than creating conflicting parallel representations.

## 40. Deterministic Repairs

After each generated candidate solution, run deterministic repairs.

Possible repair order:

```text
1. Repair hard venue-capacity violations
2. Repair student overlaps
3. Repair same-course multi-day violations
4. Repair invalid venue allocations
5. Repair missing populations
6. Repair maximum-duration violations
7. Re-evaluate soft objectives
```

The repair system must never "repair" a hard conflict by silently dropping students or deleting an exam.

If a repair cannot produce a valid state, mark the solution infeasible.

## 41. Conflict Repair Strategy

If two exams overlap and share students:

```text
A ─ conflict ─ B
```

move the exam with the lower placement cost first.

A placement cost can consider:

```text
venue fit
student workload
date scarcity
exam duration
joining opportunities
available alternative sessions
```

This makes repair deterministic if tie-breaking is fixed.

## 42. Course Ordering Heuristic

A useful initial placement order is:

1. exams with the largest student population;
2. exams with the fewest eligible venues;
3. exams with the largest duration;
4. exams with the highest conflict degree;
5. heavily shared GST/general courses;
6. remaining exams.

A combined difficulty score can be:

$$
difficulty(E)
=
w_1population
+w_2conflictDegree
+w_3duration
+w_4venueScarcity
$$

The actual weights should be tuned experimentally.

This gives the most restrictive exams the earliest placement opportunities.

## 43. Venue Scarcity Metric

For an exam event $E$:

$$
venueScarcity(E)=
\frac{1}{|EligibleVenues(E)|}
$$

An exam with:

```text
2 eligible venues
```

should normally receive priority over one with:

```text
15 eligible venues
```

because it has fewer alternatives.

## 44. Candidate Scoring

Each possible placement should have a deterministic score.

For example:

```text
score =
    α * venue_excess
  + β * number_of_venues
  + γ * duration
  + δ * workload_penalty
  + ε * joining_penalty
  + ζ * period_position_penalty
```

Lower is better.

The score must be calculated only after hard feasibility checks.

## 45. Written Venue Allocation Algorithm

Recommended high-level algorithm:

```text
function chooseWrittenVenues(exam):

    N = exam.student_count
    eligible = eligibleWrittenVenues(exam)

    single = venues where capacity >= N

    if single not empty:
        return bestSingleVenue(single, N)

    if exam.allows_multiple_venues:
        pairs = all feasible venue pairs

        if pairs not empty:
            return bestVenuePair(pairs, N)

        largerCombinations = generate feasible combinations
        return bestCombination(largerCombinations, N)

    return infeasible
```

`bestSingleVenue()` should minimize capacity excess first.

`bestVenuePair()` should prioritize:

```text
1. feasibility
2. low combined excess
3. good population balance
4. stable deterministic tie-breaker
```

## 46. CBT Venue Allocation Algorithm

Recommended abstraction:

```text
function estimateCBTPlan(exam, candidateVenues):

    N = exam.student_count
    d = exam.duration_per_student

    determine suitable venue set

    calculate processing turns
    calculate approximate completion time
    calculate utilization
    calculate duration penalty

    return best plan
```

For a single venue:

$$
turns=
\left\lceil\frac N C\right\rceil
$$

$$
duration=turns\times d
$$

For multiple simultaneous venues, calculate the number of students allocated to each venue and evaluate the maximum completion time.

## 47. CBT Allocation Is a Bin-Packing / Scheduling Subproblem

For a large CBT population, the optimizer is effectively solving:

```text
students
    ↓
venue capacities
    ↓
turns
    ↓
time
```

A practical approach is:

1. select the venue set;
2. distribute students across venues;
3. calculate turns per venue;
4. calculate each venue's completion time;
5. use the maximum as the exam event duration;
6. check `max_exam_duration`;
7. increase simultaneous venues if worthwhile.

This can initially be deterministic rather than being an independent optimization problem.

## 48. Student Distribution Across CBT Venues

For a population $N$, venue capacities:

$$
C_1,C_2,\ldots,C_m
$$

we need allocations:

$$
x_1,x_2,\ldots,x_m
$$

such that:

$$
\sum_i x_i=N
$$

and:

$$
0\le x_i\le C_i\times turns_i
$$

Each individual student belongs to exactly one turn.

The first implementation does not need to optimize individual physical seat positions.

The output can initially store:

```text
venue
turn_start
turn_end
student_count
```

and later assign exact students or seating positions.

## 49. CBT Turns and Common Exam Window

A common exam event might look like:

```text
CSC301
Date: Monday

08:00–10:00 common exam window

ICT
    Turn 1: 08:00–08:30
    Turn 2: 08:30–09:00
    Turn 3: 09:00–09:30

Library
    Turn 1: 08:00–08:30
    Turn 2: 08:30–09:00
```

The course is still one exam event.

Students are assigned to exactly one turn.

This allows the physical execution plan to be detailed without creating multiple academic exam dates.

## 50. Joining Written Exams

The same general concept can be extended to written exams where institutionally useful.

However, do not make joining universal.

Joining should only be considered where:

```text
exam types are compatible
student populations do not conflict
duration rules are compatible
venue plan is feasible
the institution allows shared sessions
```

The exact semantics should follow existing institutional practice.

## 51. Exam Group vs Exam Event

To avoid ambiguity in the implementation:

### ExamEvent

One logical course examination:

```text
CSC301
```

### ExamGroup / JoinedSession

A scheduling container that may contain:

```text
CSC201 + MTH201
```

when joining is allowed.

This distinction is especially useful for CBT.

## 52. Proposed Logical Structure

```text
ExamEvent
├── id
├── course_id
├── exam_type
├── duration
├── populations[]
├── conflict_neighbors[]
├── eligible_venues[]
└── placement_metadata

ExamPopulation
├── id
├── exam_event_id
├── department_id / offering_context
├── student_count
└── student references

ExamSession
├── id
├── date
├── start_time
├── end_time
├── exam_events[]
└── allocations[]

VenueAllocation
├── exam_session_id
├── exam_event_id
├── population_id
├── venue_id
├── student_count
├── start_time
├── end_time
└── turns[]

CBTTurn
├── venue_id
├── start_time
├── end_time
├── student_count
└── student references
```

This is a conceptual model. Map it onto the existing project models.

## 53. Persistence Strategy

Do not necessarily persist every solver-internal variable.

Persist:

```text
exam event
exam date
common exam window
exam session
venue allocations
student population allocations
CBT turns where useful
solver metadata / generation version
```

Keep temporary variables such as conflict matrices or candidate scores in preprocessing/solver memory unless the UI or auditing layer needs them.

## 54. Explainability

Every generated exam allocation should be explainable.

Store or derive:

```text
why this venue?
why two venues?
why this date?
why joined?
why multiple CBT turns?
```

For example:

```text
CSC301
Population: 250
Type: CBT
Venue plan:
    ICT (100)
    Library (80)

Estimated processing:
    2 simultaneous venue streams
    90 minutes

Reason:
    No single venue completes the cohort within the configured maximum.
```

This will be extremely useful in the admin UI.

## 55. Candidate Failure Diagnostics

When no valid timetable can be generated, return structured diagnostics.

Examples:

```text
NO_EXAM_PERIOD
NO_ELIGIBLE_VENUE
NO_WRITTEN_VENUE_COMBINATION
CBT_DURATION_TOO_LONG
CONFLICT_DENSITY_TOO_HIGH
VENUE_AVAILABILITY_CONFLICT
COURSE_HAS_INVALID_POPULATION
COURSE_TYPE_UNRESOLVED
```

Also identify the problematic exam events.

Example:

```text
CSC701 cannot be placed because:
- only 1 eligible CBT venue exists;
- calculated duration = 8h 30m;
- configured maximum = 6h;
- no additional compatible venue is available.
```

This is much better than simply returning:

```text
Optimization failed.
```

## 56. Do Not Overuse Global Capacity Checks

The exam period may contain abundant theoretical time even with few CBT venues.

Therefore:

```text
2 CBT halls
```

does not automatically mean the system is infeasible.

Instead calculate:

```text
available processing time
vs
required processing time
```

for the actual candidate schedule.

The strongest capacity measure is temporal:

$$
throughput =
\sum_v
\frac{capacity_v}{durationPerStudent}
$$

within available operating time, subject to simultaneous-use and availability rules.

Because courses conflict with each other, this remains a necessary approximation rather than a proof of full feasibility.

## 57. Approximate CBT Throughput Precheck

For a rough precheck over an examination window of usable duration $H$:

$$
Capacity_{CBT,v}
\approx
capacity_v
\times
\frac{H}{durationPerStudent}
$$

and for several independent venues:

$$
Capacity_{CBT,total}
\approx
\sum_v
capacity_v
\times
\frac{H_v}{durationPerStudent}
$$

This may be used as an early warning.

It must **not** be treated as proof of feasibility because student conflicts, common course windows, venue availability, joined-session rules, and maximum exam-duration constraints still matter.

## 58. Preprocessing vs Solver Responsibility

Use this boundary.

### Preprocessing

Good candidates:

```text
course population aggregation
student registration normalization
course conflict graph
cohort similarity
venue eligibility
duration resolution
course type resolution
venue candidate generation
candidate joined-exam pairs
```

### Solver

Good candidates:

```text
date selection
time selection
exam group selection
venue-plan selection
conflict resolution
period distribution
objective optimization
```

### Deterministic repair

Good candidates:

```text
hard overlap removal
venue capacity corrections
same-course date correction
duration correction
missing-allocation correction
```

This separation will prevent the solver from becoming a giant collection of unrelated business rules.

## 59. Recommended Candidate-Generation Strategy

Do not generate every possible:

```text
exam × date × start_time × venue combination
```

because the search space can become huge.

Instead:

```text
Exam
  ↓
small number of venue plans
  ↓
small number of candidate start times per day
  ↓
small number of viable dates
```

Rank candidates before handing them to the optimizer.

For example, retain:

```text
top 3–10 venue plans
```

per exam depending on system scale.

The exact number should be configurable/tuned.

## 60. Initial Scheduling Heuristic

A good initial deterministic placement order:

```text
sort exams by:

    conflict_degree descending
    population descending
    venue_scarcity descending
    duration descending
```

Then:

```text
for each exam:

    generate feasible candidate sessions

    remove candidates that conflict with already placed exams

    select lowest-cost candidate

    commit placement
```

After the initial construction, run deterministic repair and then an optimization phase.

## 61. Solver Variables

The exact formulation depends on which optimization engine the existing timetable system uses.

For a CP-SAT-style modeling approach, a useful conceptual formulation is:

```text
x[e,c] = 1 if exam e chooses candidate c
```

with:

$$
\sum_c x_{e,c}=1
$$

for every exam event $e$.

Each candidate contains:

```text
date
start
end
venue plan
allocations
```

Conflict constraint:

$$
x_{A,c_A}+x_{B,c_B}\le1
$$

for candidate pairs whose time windows overlap and where $Conflict(A,B)=1$.

This candidate-based formulation can be considerably easier to implement than directly modeling every venue/student/time relationship.

## 62. Alternative Direct Time-Indexed Formulation

If the existing optimizer is already strongly time-indexed, a direct model may be used:

```text
start[e]
end[e]
date[e]
venue allocation[e,v]
```

with interval variables.

For CBT, each venue stream can receive its own interval/turn representation.

However, use direct interval modeling only if it fits the current optimizer architecture cleanly.

Otherwise, candidate-session modeling is simpler.

## 63. Hybrid Approach Recommended

Given that the existing lecture optimizer is already implemented successfully, the safest architecture is:

```text
Preprocessing
     ↓
deterministic candidate generation
     ↓
constraint solver
     ↓
deterministic repairs
     ↓
local improvement / re-optimization
```

The solver handles the difficult combinatorial choices.

The preprocessing and repair layers handle domain-specific transformations.

## 64. Re-Optimization After Repair

Do not stop after a repair if the resulting schedule is valid but poor.

Example:

```text
Repair moved CSC301
    ↓
valid solution
    ↓
but venue utilization became poor
```

Run a limited improvement pass:

```text
try alternative candidates
attempt swaps
attempt date changes
attempt venue-plan changes
attempt valid CBT joining
```

Only accept a change when:

```text
hard constraints remain satisfied
AND
objective score improves
```

## 65. Deterministic Tie-Breaking

To make generated timetables reproducible, all selection steps should have deterministic tie-breaking.

Example:

```text
1. objective score
2. date
3. start time
4. venue capacity
5. venue ID
6. course ID
```

Avoid arbitrary iteration order from hash maps or database sets.

This is especially important for debugging and comparing optimizer generations.

## 66. Example: Written Multi-Department Course

Suppose:

```text
CSC301
CS = 100
SE = 50

Written duration = 2h

Eligible venues:
Hall A = 120
Hall B = 80
Hall C = 200
```

Possible allocation:

```text
CSC301
Monday 08:00–10:00

CS → Hall A = 100
SE → Hall B = 50
```

This is preferable to:

```text
CS + SE → Hall C = 200
```

if preserving offering-specific populations is important and the two smaller venues fit better.

However, if Hall B is unavailable, the optimizer can use Hall C.

The final objective decides between feasible alternatives.

## 67. Example: Large Written Course

```text
GST111
Population = 600

Hall A = 300
Hall B = 250
Hall C = 120
```

No single venue works.

Potential allocation:

```text
Hall A → 300
Hall B → 250
Hall C → 50
```

Total:

$$
300+250+120\ge600
$$

but only:

```text
300 + 250 + 50 = 600
```

students actually occupy seats.

All three allocations use the same exam window.

## 68. Example: CBT Single Venue

```text
CSC401 = 250 students
ICT = 100 computers
duration/student = 30 min
```

Then:

$$
turns=3
$$

and approximately:

$$
duration=90min
$$

Candidate:

```text
Monday 08:00–09:30
ICT
    Turn 1
    Turn 2
    Turn 3
```

Each student appears in one turn.

## 69. Example: CBT Multiple Venues

```text
CSC401 = 250
ICT = 100
Library = 80
duration/student = 30min
```

Possible plan:

```text
Monday 08:00–09:30

ICT
    100
    100
    50

Library
    80
    80
```

The exact allocation should be generated from the student's actual population rather than just counts.

All students still write CSC401 on Monday.

## 70. Example: Joined CBT Session

```text
CSC201 = 40
MTH201 = 50
No student overlap

ICT = 100

CBT duration/student = 30 min
```

Joined candidate:

```text
Monday 08:00–09:00

CSC201
    students allocated

MTH201
    students allocated
```

The institution has reduced the number of independent CBT sessions while obeying:

$$
coursesPerSession=2
$$

## 71. Example: Joined CBT Is Forbidden

```text
CSC201 = 40
MTH201 = 50

Some students take both.
```

Therefore:

$$
Conflict(CSC201,MTH201)=1
$$

They cannot share an overlapping CBT session.

The optimizer must schedule them separately.

## 72. Weekly Student Load Calculation

After a candidate schedule is generated:

```text
student
   ↓
exam dates
   ↓
week buckets
```

Calculate:

$$
weeklyLoad(s,w)
=
\#\{ exams\ of\ student\ s\ in\ week\ w\}
$$

Compare it to the administrative rule.

This should be an optimization penalty initially unless the institution explicitly declares a hard maximum.

Example penalty:

$$
Penalty_{weekly}(s,w)
=
\max(0,weeklyLoad(s,w)-L_{max})^2
$$

## 73. Consecutive Exam Penalty

An optional preference:

$$
Penalty_{consecutive}(s)
=
\#\text{of consecutive exam-day pairs}
$$

This should normally be soft.

The system should not make the entire schedule infeasible merely because some students have two exams on consecutive days unless the institution explicitly requires that restriction.

## 74. Same-Day Multiple Exams

A similar calculation can identify:

```text
student has more than one exam on the same day
```

This may be hard or soft depending on institutional policy.

At minimum, it should be surfaced in the validation report.

## 75. Validation Pipeline

After optimization:

```text
V1. Every exam scheduled
V2. Every exam inside period
V3. Same course never appears on different dates
V4. Student conflicts absent
V5. Venue eligibility valid
V6. Venue capacity valid
V7. Venue availability valid
V8. Every student allocated exactly once
V9. CBT turn durations valid
V10. Operating-day/time-window rule respected
V11. Maximum exam duration respected
V12. CBT joined-session limit respected
V13. Written venue allocations feasible
V14. Lab requirements satisfied
```

Only then should the result become publishable.

## 76. Validation Should Be Independent

The final validator should not simply trust the optimizer.

The architecture should be:

```text
optimizer output
     ↓
independent validator
     ↓
PASS → publishable
FAIL → repair/re-optimize/error
```

This protects against modeling bugs.

## 77. Audit Report

Generate a machine-readable report containing:

```text
total exams
total students
total sessions
written exams
CBT exams
lab practicals
multi-venue exams
joined sessions
average venue utilization
maximum student weekly load
conflicts detected
repair count
optimization score
unresolved violations
```

This can later feed the admin dashboard.

## 78. UI Representation

The admin UI should not show CBT as if it were a normal lecture slot.

For a written exam:

```text
CSC301
Monday, 8:00–10:00

Hall A — 100
Hall B — 50
```

For CBT:

```text
CSC401
Monday, 8:00–9:30

ICT Centre
Turn 1: 8:00–8:30
Turn 2: 8:30–9:00
Turn 3: 9:00–9:30
```

For a joined CBT session:

```text
08:00–09:00
CSC201 + MTH201

ICT Centre
```

The UI can optionally expose the student/department allocation details.

## 79. Data Returned by the Optimizer

Recommended result shape:

```text
ExamTimetableResult
├── timetable_id
├── semester_id
├── exam_period
├── sessions[]
├── metrics
├── warnings[]
├── violations[]
└── generation_metadata
```

Each session:

```text
ExamSession
├── date
├── start_time
├── end_time
├── exams[]
└── allocations[]
```

Each allocation:

```text
ExamVenueAllocation
├── exam_id
├── population_id
├── venue_id
├── student_count
├── start_time
├── end_time
└── turns[]
```

## 80. Suggested Database-Level Concepts

If the existing schema does not already cover these concepts, the following logical entities are useful:

```text
exam_type
exam_configuration
exam_event
exam_population
exam_session
exam_venue_allocation
cbt_turn
exam_conflict
```

Not all need to become database tables.

For example, `exam_conflict` could be generated into memory if the number of students/exams permits it.

## 81. Course Exam-Type Configuration

Provide administrative configuration at multiple levels.

Recommended priority:

```text
course-specific override
       ↓
department/faculty default
       ↓
exam-type default
       ↓
semester default
```

Example:

```text
default CBT duration = 25 min/student

CSC301 override = 30 min/student
```

Similarly:

```text
default written duration = 2h

GST111 override = 6h
```

This accommodates the reality that general papers may require unusually long examination windows.

## 82. Data Validation Before Scheduling

Reject or quarantine malformed records such as:

```text
course has negative student count
exam type missing
duration <= 0
venue exam_capacity <= 0
student registered for same course twice
course population cannot be mapped to offering
exam period invalid
```

Do this before invoking the solver.

## 83. Important Deduplication Rules

Because courses may be listed across several departments/faculties, preprocessing should carefully distinguish:

```text
same logical course
same course offering
duplicate registration
duplicate course code
```

For example:

```text
GST111
GST-111
GST111
```

may need canonicalization if the existing system stores aliases.

Do not assume string equality is enough.

Use the existing course identity where possible.

## 84. Course Identity Should Be Stable

The optimizer should use a canonical internal ID:

```text
course_id
```

rather than relying only on:

```text
course_code
```

because course codes can have formatting variations.

This is particularly important for school-wide GST courses.

## 85. Handling Course Populations Without Student IDs

If the current preprocessing pipeline only provides counts:

```text
CSC301 → 100
CSC301 → 50
```

the optimizer can still schedule populations.

However, exact student conflict resolution requires actual student-course registration membership or an equivalent precomputed conflict representation.

Therefore:

```text
population counts
```

are sufficient for venue planning,

but:

```text
student membership / conflict graph
```

is required for exact conflict enforcement.

## 86. Handling Similar Cohorts

Do not replace exact conflicts with a similarity threshold.

For example:

```text
80% overlap
```

is useful for optimization ordering, but the hard rule should remain exact registration overlap.

Use:

```text
exact overlap → hard conflict
similarity → soft scheduling preference / heuristic
```

## 87. Joining Logic Should Be Conservative

Joining is an efficiency feature, not a relaxation of conflict rules.

Before joining:

```text
check exact student conflict
check type compatibility
check duration compatibility
check venue compatibility
check max 2 courses
check administrative rules
```

Only then create a joined candidate.

## 88. Venue Reservation Semantics

For written exams, the allocation may reserve a venue for the entire exam window.

For CBT, the venue may be used by several turns within the same exam event.

If joined CBT exams use the same physical venue sequentially or concurrently, the underlying reservation model must distinguish:

```text
venue occupancy interval
```

from:

```text
logical exam event
```

This prevents false venue clashes.

## 89. Venue Capacity Constraint for CBT Turns

At any instant:

$$
\sum_{e,t}
students_{e,v,t}
\le capacity_v
$$

This is the actual CBT venue-capacity constraint.

If a venue has:

```text
100 computers
```

the system should never create:

```text
CSC301 = 70
MTH301 = 50
```

on the same CBT turn in that venue because:

$$
70+50=120>100
$$

unless the two populations are assigned to different time portions.

## 90. Multi-Course CBT Reservation

A CBT venue can therefore have:

```text
ICT

08:00–08:30
    CSC301 → 70

08:30–09:00
    CSC301 → 70

09:00–09:30
    MTH301 → 80
```

This is valid provided:

```text
students belong to one sitting
venue capacity is respected
exam windows allow it
student conflicts remain impossible
```

This is fundamentally different from the lecture scheduler's one-resource-one-slot model.

## 91. Maximum Two Courses Per CBT Period

Interpret the policy carefully.

Recommended implementation:

```text
JoinedSession
    max logical exams = 2
```

It should not mean:

```text
maximum 2 courses per entire day
```

or:

```text
maximum 2 courses per venue per day
```

unless a separate administrative rule exists.

## 92. Course Duration Overrides

For CBT:

```text
course.duration_per_student
```

should override:

```text
examConfig.default_cbt_duration_per_student
```

For written:

```text
course.exam_duration
```

should override:

```text
examConfig.default_written_duration
```

For practical:

```text
course.practical_exam_duration
```

can override:

```text
examConfig.default_practical_duration
```

This should be resolved during preprocessing.

## 93. Candidate Session Creation Example

For:

```text
CSC301
Population = 150
Written
Duration = 2h
```

the generator might produce:

```text
Candidate A
Monday 08:00–10:00
Hall 200

Candidate B
Tuesday 08:00–10:00
Hall 200

Candidate C
Wednesday 10:00–12:00
Hall 200
```

For:

```text
CSC401
Population = 250
CBT
Duration = 30 min/student
```

candidate plans might be:

```text
Candidate A
ICT only
3 turns
90 min

Candidate B
ICT + Library
2 simultaneous streams
60 min

Candidate C
ICT + Library + Lab
shorter duration
```

depending on eligibility.

The solver selects among these candidates.

## 94. Exam Period Compression

A useful objective is to reduce the number of active examination days.

For example:

```text
Solution A:
20 active days

Solution B:
16 active days
```

Prefer B when all other major constraints are satisfied.

Possible objective:

$$
minimize\ activeExamDays
$$

This can coexist with student workload objectives.

## 95. Do Not Optimize Only for Minimum Days

Minimum days can produce:

```text
students having 3 exams on one day
```

Therefore:

$$
minimize(activeDays)
$$

must be balanced against:

$$
minimize(studentWorkloadPenalty)
$$

and conflict constraints.

The objective should prefer compact schedules without creating unreasonable student distributions.

## 96. Suggested Objective Hierarchy in Practice

A practical lexicographic order:

```text
Level 0
    hard feasibility

Level 1
    minimize unresolved violations

Level 2
    minimize extreme student workload

Level 3
    minimize examination period span

Level 4
    minimize venue waste

Level 5
    minimize unnecessary venue count

Level 6
    maximize useful exam joining

Level 7
    improve CBT duration / throughput

Level 8
    cosmetic preferences
```

The exact weighting should be tuned using real timetable data.

## 97. Performance Strategy

The biggest performance risk is student-level modeling.

Avoid creating every possible:

```text
student × venue × time × exam
```

variable if it can be avoided.

Prefer:

```text
student conflicts
+
course populations
+
candidate exam sessions
```

and assign individual students to venue/turns after the logical schedule is determined where possible.

Use exact student assignment only where required for conflict or execution output.

## 98. Two-Phase Exam Scheduling

A particularly practical architecture is:

### Phase A — logical timetable

Determine:

```text
course/exam event
    → date
    → common exam window
    → joined session
```

using:

```text
student conflicts
student workloads
course identity
duration
```

### Phase B — physical allocation

Determine:

```text
exam event
    → venue(s)
    → population distribution
    → CBT turns
```

Then verify that the physical allocation is compatible with Phase A.

This separation dramatically simplifies the model.

## 99. When Phase B Fails

A logical schedule can be mathematically valid but physically awkward.

Example:

```text
CSC301
Monday 08:00–10:00
```

but no feasible venue combination can process all 600 students within 2 hours.

Then:

```text
try alternate venue plan
```

If that fails:

```text
try alternate duration/window
```

If that still fails:

```text
try another candidate session
```

This can be implemented either before the solver by candidate filtering or through repair/re-optimization.

## 100. Recommended Final Pipeline

The complete production flow should look like:

```text
                 SEMESTER
                    │
                    ▼
           Validate exam period
                    │
                    ▼
             Load exam courses
                    │
                    ▼
        Resolve exam type/duration
                    │
                    ▼
         Build exam populations
                    │
                    ▼
       Build student registration map
                    │
                    ▼
          Build conflict graph
                    │
                    ▼
        Resolve eligible venues
                    │
                    ▼
       Generate venue allocation plans
                    │
                    ▼
       Generate CBT joining candidates
                    │
                    ▼
        Generate time/date candidates
                    │
                    ▼
              OPTIMIZER
                    │
                    ▼
         Initial valid candidate
                    │
                    ▼
       Deterministic repair pipeline
                    │
                    ▼
          Objective improvement
                    │
                    ▼
          Independent validator
                    │
              ┌─────┴─────┐
              │           │
            VALID       INVALID
              │           │
              ▼           ▼
           Publish     Repair /
                       re-optimize
```

## 101. Minimum Viable Implementation

The first production implementation should support:

```text
✓ semester exam period
✓ WRITTEN / CBT / LAB_PRACTICAL
✓ course-specific duration overrides
✓ global/default duration configuration
✓ student population per course offering
✓ exact student conflict graph
✓ same-course same-day invariant
✓ compatible venue filtering
✓ written single-venue selection
✓ written multi-venue selection
✓ CBT turn calculation
✓ CBT multi-venue allocation
✓ CBT two-course joining
✓ maximum exam duration
✓ student weekly workload scoring
✓ deterministic repair
✓ final independent validation
```

Do not add advanced seat-number optimization yet.

## 102. Later Enhancements

After the basic optimizer is stable, possible improvements include:

```text
student-level seat assignment
seat numbering
special-needs accommodations
invigilator allocation
room-specific desk layouts
automatic invigilator balancing
exam material logistics
venue setup/reset time
equipment setup time
different CBT question batches
anti-collusion constraints
per-faculty exam policies
special examination sessions
carry-over student scheduling
```

These should be layered on top rather than embedded into the first optimizer.

## 103. Recommended Implementation Modules

A clean code organization could be:

```text
exam_optimizer/
├── preprocessing/
│   ├── exam_period.py
│   ├── exam_types.py
│   ├── populations.py
│   ├── conflicts.py
│   ├── venues.py
│   ├── durations.py
│   └── candidates.py
│
├── models/
│   ├── exam_event.py
│   ├── exam_population.py
│   ├── exam_session.py
│   ├── venue_plan.py
│   └── cbt_turn.py
│
├── solver/
│   ├── model.py
│   ├── constraints.py
│   ├── objectives.py
│   └── search.py
│
├── heuristics/
│   ├── ordering.py
│   ├── joining.py
│   ├── venue_selection.py
│   └── workload.py
│
├── repair/
│   ├── conflicts.py
│   ├── venues.py
│   ├── duration.py
│   └── course_date.py
│
├── validation/
│   ├── conflicts.py
│   ├── capacity.py
│   ├── period.py
│   ├── allocations.py
│   └── report.py
│
└── service/
    └── generate_exam_timetable.py
```

Adapt the naming to the current project structure.

## 104. Testing Strategy

The exam optimizer needs a dedicated test suite because the constraints are substantially different from the lecture scheduler.

### Unit tests

Test:

```text
duration resolution
venue eligibility
single venue selection
venue-pair selection
CBT turn calculation
CBT multi-venue calculation
student conflict detection
same-course grouping
CBT join eligibility
weekly workload calculation
```

### Scenario tests

#### Scenario A

One small written exam.

Expected:

```text
one venue
```

#### Scenario B

One large written exam.

Expected:

```text
multiple venues
same exam window
```

#### Scenario C

Multi-department course.

Expected:

```text
one course exam event
multiple populations
same date
```

#### Scenario D

GST-style course.

Expected:

```text
one logical exam
multiple faculty populations
possibly multiple venues
```

#### Scenario E

Small compatible CBT exams.

Expected:

```text
joined session
max 2 courses
```

#### Scenario F

CBT exams with student overlap.

Expected:

```text
not joined
not simultaneous
```

#### Scenario G

Large CBT exam.

Expected:

```text
multiple turns
or multiple simultaneous venues
```

#### Scenario H

No feasible venue configuration.

Expected:

```text
structured failure diagnostic
```

## 105. Regression Testing Against Real Examination Data

The uploaded 2025/2026 examination schedule is useful as a **domain reference** because it shows the institution's real scheduling behavior.

The source demonstrates general courses assigned simultaneously to ICT & Library, and other courses distributed between ICT and Library. It also demonstrates that examination periods can use different time structures across different weeks. For example, Week 5 uses an 8:00am–4:00pm period plus a 4:00–6:00pm slot, while Week 6 uses three shorter daily periods.

The optimizer should therefore be tested against real cases such as:

```text
GST / general courses
ICT + Library simultaneous assignments
single-venue departmental exams
multi-venue large-population exams
multiple exams in one broad time period
```

The source also contains an explicit note about `NS-STA316` appearing twice, illustrating why the preprocessing layer must distinguish legitimate repeated/contextual records from true duplicate scheduling demands.

## 106. Critical Engineering Rule: Do Not Trust Course Count Alone

Do not calculate exam demand as:

```text
number of unique courses
```

The relevant objects are:

```text
logical exam events
+
student populations
+
physical execution requirements
```

A course offered by several departments may represent multiple physical populations but only one logical examination event.

## 107. Critical Engineering Rule: Do Not Treat Venue Choice as Binary

Avoid a simplistic:

```text
venue = occupied/free
```

model.

Written:

```text
venue
    → population allocation
```

CBT:

```text
venue
    → turns
    → student throughput
```

This distinction is essential.

## 108. Critical Engineering Rule: Don't Make CBT Capacity a Global Hard Limit

Do not reject:

```text
250 students
100-seat CBT centre
```

simply because:

$$
250>100
$$

Instead calculate:

$$
turns=
\left\lceil\frac{250}{100}\right\rceil
$$

and the resulting duration.

The hard constraints are temporal and operational, not merely population-vs-capacity.

## 109. Critical Engineering Rule: Same Course Must Remain Unified

Never allow:

```text
CSC301 → Monday
CSC301 → Wednesday
```

merely because its populations were modeled separately.

The logical `ExamEvent` should be the object carrying the date/window decision.

The populations inherit that common event window.

## 110. Critical Engineering Rule: Joining Is Optimization, Not Identity

Joining:

```text
CSC201 + MTH201
```

does not mean the courses become one course.

They remain separate exam events contained within one joined session.

This distinction is important for:

```text
grades
attendance
student registration
results
reporting
course statistics
```

## 111. Summary Mathematical Model

Let:

- $E$ = set of logical exam events;
- $S$ = set of students;
- $V$ = set of venues;
- $D$ = available examination dates;
- $T$ = candidate start times;
- $N_e$ = number of students in exam event $e$;
- $C_v$ = exam capacity of venue $v$;
- $d_e$ = duration of exam $e$;
- $Conf(e_1,e_2)$ = student conflict indicator.

The primary logical scheduling decision is:

$$
date(e), start(e), end(e)
$$

with:

$$
end(e)=start(e)+d_e
$$

subject to:

$$
date(e)\in D
$$

and:

$$
examPeriodStart\le start(e)
$$

$$
end(e)\le examPeriodEnd
$$

For conflicting exams:

$$
Conf(e_1,e_2)=1
\Rightarrow
[time(e_1)\cap time(e_2)=\varnothing]
$$

For venue allocations:

$$
\sum_{e} assignedStudents(e,v,t)
\le C_v
$$

at every relevant time.

For each exam event:

$$
\sum_v assignedStudents(e,v)=N_e
$$

For same-course populations:

$$
date(population_i)=date(population_j)
$$

For CBT turns:

$$
turns_{e,v}
=
\left\lceil
\frac{students_{e,v}}
{C_v}
\right\rceil
$$

and approximately:

$$
duration_{e,v}
=
turns_{e,v}\times d_{perStudent}
$$

with the event's required physical processing duration approximately:

$$
duration_e
=
\max_v(duration_{e,v})
$$

for simultaneously operated venues.

## 112. Final Recommended Architecture

The final exam scheduler should be treated as a **hybrid constraint-scheduling and resource-allocation system**, not as a modified lecture timetable.

The clean conceptual model is:

```text
                    COURSE
                       │
                       ▼
                 EXAM EVENT
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      Population A  Population B  Population C
          │            │            │
          └────────────┼────────────┘
                       │
                       ▼
                 COMMON WINDOW
                       │
          ┌────────────┴─────────────┐
          ▼                          ▼
    Venue allocation             Venue allocation
          │                          │
          ▼                          ▼
       Students                   Students
          │
          ▼
     CBT turns / written seating
```

The optimizer should therefore answer four different questions:

```text
1. WHEN is the logical exam held?
2. WHICH exams may share a session?
3. WHERE is each population physically allocated?
4. HOW is CBT population processed through the available venues?
```

Those questions are related, but they should not be collapsed into one simplistic variable.

## 113. Implementation Order

Build in this order to reduce complexity:

### Phase 1 — normalization

Implement:

```text
exam period validation
exam type resolution
duration resolution
course population construction
venue eligibility
```

### Phase 2 — conflict preprocessing

Implement:

```text
student-course normalization
exam conflict graph
cohort overlap metrics
```

### Phase 3 — physical planning

Implement:

```text
written venue selection
written multi-venue allocation
CBT turn estimation
CBT multi-venue planning
```

### Phase 4 — candidate generation

Implement:

```text
exam session candidates
venue-plan candidates
CBT joined candidates
```

### Phase 5 — logical scheduling

Implement:

```text
date/time selection
same-course invariants
student conflicts
weekly workload objectives
```

### Phase 6 — physical allocation

Implement:

```text
venue assignment
CBT turn allocation
multi-venue assignment
```

### Phase 7 — repair

Implement:

```text
hard conflict repairs
venue repairs
duration repairs
same-course repairs
```

### Phase 8 — optimization

Implement:

```text
venue fit
period compression
joining
CBT efficiency
student workload
```

### Phase 9 — validation and reporting

Implement:

```text
independent validator
diagnostics
metrics
audit trail
admin-facing explanation
```

## 114. Final Design Decision

The most important design decision from this specification is:

> **The exam optimizer should schedule logical exam events in a configurable calendar and then allocate their student populations to physical resources, rather than treating the examination period as a fixed grid of equivalent slots.**

For written examinations, the primary physical consideration is:

$$
\text{population}\leftrightarrow\text{venue exam capacity}
$$

For CBT examinations, it is:

$$
\text{population}
\leftrightarrow
\text{venue capacity}
\leftrightarrow
\text{turns}
\leftrightarrow
\text{time}
$$

For student conflicts, it is:

$$
\text{student registrations}
\rightarrow
\text{conflict graph}
\rightarrow
\text{non-overlapping exam windows}
$$

For multi-department courses:

$$
\text{one logical course exam}
\rightarrow
\text{multiple populations}
\rightarrow
\text{common exam window}
\rightarrow
\text{multiple physical allocations}
$$

And for efficiency:

$$
\text{small compatible exams}
\rightarrow
\text{joined session candidates}
$$

subject to all hard constraints.

This structure should fit cleanly beside the existing lecture optimizer while allowing the examination scheduler to reflect the institution's actual operational model.
