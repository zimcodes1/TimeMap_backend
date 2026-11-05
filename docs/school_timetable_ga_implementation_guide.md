# Genetic Algorithm School Timetable Optimizer --- Implementation Guide

## 1. Purpose

This document is an implementation guide for a Genetic Algorithm (GA)
that generates a recurring weekly lecture timetable for a university.

The optimizer should produce the **best available timetable**, not
assume that every real-world scheduling problem is always feasible.

The design separates:

1.  **Backend/domain logic** --- retrieves and prepares university data.
2.  **Constraint preprocessing** --- converts raw data into a scheduling
    problem.
3.  **Genetic Algorithm** --- searches for good timetable assignments.
4.  **Constraint/evaluation handlers** --- detect violations and
    calculate penalties.
5.  **Final validation/reporting** --- verifies the returned timetable
    and explains any remaining conflicts.

The GA should not directly understand university ownership hierarchies,
database queries, authentication, permissions, or other application
concerns.

------------------------------------------------------------------------

# 2. Core Scheduling Rules

## 2.1 Weekly timetable

The generated timetable is a recurring weekly pattern:

-   Monday--Friday
-   Each lecture lasts exactly 2 hours.
-   Normal periods:
    -   08:00--10:00
    -   10:00--12:00
    -   12:00--14:00
    -   14:00--16:00
    -   16:00--18:00
-   Friday 12:00--14:00 is unavailable because of Jummat.

Therefore the default weekly timetable contains:

``` text
5 days × 5 periods - 1 unavailable period = 24 valid time slots
```

A generated timetable repeats every week until an administrator
regenerates or modifies it.

------------------------------------------------------------------------

# 3. Domain/Data Model

The exact database schema can differ from the following model. These are
the conceptual objects the optimizer needs.

## 3.1 Course

``` text
Course
├── id
├── code
├── name
├── department_id
├── required_occurrences_per_week
├── course_type
└── lecturer_ids[]
```

`required_occurrences_per_week` is an exact requirement, not a maximum.

Examples:

``` text
MTH101 → 1 occurrence
CSC201 → 2 occurrences
PHY301 → 3 occurrences
```

If a course requires two occurrences, exactly two must be scheduled.

------------------------------------------------------------------------

## 3.2 Student Group

Do not model individual students inside the GA.

Use:

``` text
StudentGroup
├── program_id
└── level
```

Examples:

``` text
Computer Science 100L
Computer Science 200L
Cyber Security 100L
Data Science 100L
Mathematics 100L
```

A course can have multiple student groups.

Example:

``` text
MTH101
student_groups:
    Mathematics 100L
    Computer Science 100L
    Cyber Security 100L
```

------------------------------------------------------------------------

## 3.3 Lecturer

``` text
Lecturer
├── id
└── name
```

A course may have one or multiple lecturers.

If a course has multiple lecturers, the scheduler treats **all assigned
lecturers as unavailable during the course's scheduled lecture time**.

This deliberately avoids trying to model which lecturer teaches which
aspect of the course.

Example:

``` text
CSC201
lecturers:
    Lecturer A
    Lecturer B
```

If CSC201 is scheduled Monday 10:00--12:00, both lecturers are
considered occupied during that period.

------------------------------------------------------------------------

## 3.4 Venue

``` text
Venue
├── id
├── name
├── type
├── capacity
└── ownership/access information
```

Venue types include:

``` text
LECTURE_HALL
LAB
EXAM_HALL
```

Exam halls are outside the current lecture scheduling problem.

The optimizer should receive an already-resolved list of venues that a
course may use.

For example:

``` text
CSC201.allowed_venues =
    Computer Lab 1
    Computer Lab 2
```

The GA should not resolve university/faculty/department ownership
itself.

------------------------------------------------------------------------

## 3.5 Course Type

At minimum, distinguish:

``` text
LECTURE
PRACTICAL
```

A practical/lab course must use a lab.

An ordinary lecture must not use a lab.

This is a hard constraint and should preferably be enforced during
preprocessing rather than merely penalized.

------------------------------------------------------------------------

# 4. Generation Scope

The optimizer should support generation for different scopes.

Potential scopes include:

``` text
University
School
Faculty
Department
Program
Program + Level
```

The exact supported scopes can be decided by the application.

A crucial distinction is:

``` text
scheduled_courses
```

versus:

``` text
external_conflict_information
```

A faculty generation may only schedule courses belonging to that
faculty, while some of those courses may have students from outside the
faculty.

Example:

``` text
MTH101
students:
    Mathematics 100L
    Computer Science 100L
```

If the Computer Science faculty is being scheduled, the optimizer still
needs to know that MTH101 conflicts with courses attended by Computer
Science 100L.

Therefore, do not assume:

> "If a course is outside the generation scope, it is irrelevant."

Its **course event** may be outside the scope while its student-group
participation can still be relevant to conflict detection.

------------------------------------------------------------------------

# 5. Preprocessing Pipeline

Do not send raw database objects directly into the GA.

Create a preprocessing stage.

``` text
Database
   ↓
Retrieve generation scope
   ↓
Resolve course/student/lecturer/venue data
   ↓
Expand course occurrences
   ↓
Create valid time slots
   ↓
Resolve allowed venues
   ↓
Build student conflict information
   ↓
Create SchedulingProblem
   ↓
GA
```

------------------------------------------------------------------------

# 6. Expand Weekly Course Occurrences

Suppose:

``` text
MTH101.required_occurrences = 2
```

Create two scheduling events:

``` text
MTH101-1
MTH101-2
```

They are separate genes in the chromosome, but they reference the same
underlying course.

Each occurrence contains:

``` text
CourseOccurrence
├── occurrence_id
├── course_id
├── occurrence_number
├── student_groups[]
├── lecturer_ids[]
├── allowed_venues[]
└── course_type
```

The important additional constraint is:

``` text
MTH101-1.day != MTH101-2.day
```

Multiple weekly occurrences of the same course may use:

-   the same time on different days,
-   different times,
-   different venues.

They must simply occur on different days.

------------------------------------------------------------------------

# 7. Build Valid Time Slots

Create the valid slots once.

Conceptually:

``` text
Slot
├── day
└── period
```

Example:

``` text
MONDAY    08:00–10:00
MONDAY    10:00–12:00
MONDAY    12:00–14:00
MONDAY    14:00–16:00
MONDAY    16:00–18:00

...

FRIDAY    08:00–10:00
FRIDAY    10:00–12:00
FRIDAY    14:00–16:00
FRIDAY    16:00–18:00
```

Do not include Friday 12:00--14:00.

This means the GA cannot accidentally generate a Jummat-period lecture.

------------------------------------------------------------------------

# 8. Resolve Allowed Venues Before the GA

Create an external function such as:

``` text
get_allowed_venues(course)
```

It should resolve university/faculty/department access rules.

The GA receives the result.

Example:

``` text
CSC101:
    allowed_venues = [Hall A, Hall B, Hall C]

CSC204:
    allowed_venues = [Computer Lab 1, Computer Lab 2]
```

For a practical:

``` text
allowed_venues = labs only
```

For an ordinary lecture:

``` text
allowed_venues = ordinary lecture venues
```

Do not include invalid venue types merely to penalize them later.

This reduces the search space and prevents impossible genes.

------------------------------------------------------------------------

# 9. Student Conflict Matrix / Conflict Graph

Build student conflicts during preprocessing.

For two courses A and B:

``` text
courses_conflict(A, B)
```

is true if their student-group sets intersect.

Example:

``` text
A = {
    Mathematics 100L,
    Computer Science 100L
}

B = {
    Computer Science 100L
}
```

Intersection:

``` text
Computer Science 100L
```

Therefore:

``` text
A conflicts with B
```

Another example:

``` text
A = {
    Mathematics 100L
}

B = {
    Physics 100L
}
```

No intersection:

``` text
A does not conflict with B
```

This can be represented as:

``` text
conflict_graph[A] = {B, C, D}
```

This avoids repeatedly calculating student-group intersections during
every fitness evaluation.

For a larger system, this preprocessing can have a substantial
performance benefit.

------------------------------------------------------------------------

# 10. The Scheduling Problem Object

The GA should receive one prepared object representing the complete
optimization problem.

Conceptually:

``` text
SchedulingProblem
├── occurrences[]
├── valid_slots[]
├── allowed_venues
├── student_conflicts
├── lecturer_assignments
├── daily_lecture_limit
├── timetable_scope
└── soft-constraint configuration
```

The GA should be independent of the database.

This allows you to test it using small artificial problems.

For example:

``` text
GA(test_problem)
```

works without PostgreSQL, Django, Node, or the rest of the application.

------------------------------------------------------------------------

# 11. Chromosome Representation

This is the central modelling decision.

## One gene = one course occurrence

Suppose preprocessing creates:

``` text
CSC101-1
CSC102-1
MTH101-1
MTH101-2
PHY101-1
GST101-1
```

The chromosome contains one gene for each:

``` text
Chromosome
├── Gene 1 → CSC101-1 assignment
├── Gene 2 → CSC102-1 assignment
├── Gene 3 → MTH101-1 assignment
├── Gene 4 → MTH101-2 assignment
├── Gene 5 → PHY101-1 assignment
└── Gene 6 → GST101-1 assignment
```

Each gene represents:

``` text
(day, time_slot, venue)
```

Example:

``` text
MTH101-1
→ Tuesday
→ 14:00–16:00
→ Hall C
```

------------------------------------------------------------------------

# 12. Why This Representation Works

Unlike TSP, this is not fundamentally an ordering problem.

TSP asks:

``` text
What order should I visit the cities?
```

The timetable asks:

``` text
Where should each required course occurrence be placed?
```

Therefore:

``` text
course occurrence → assignment
```

is a better chromosome representation.

It also makes crossover easier because each chromosome position always
represents the same occurrence.

------------------------------------------------------------------------

# 13. Initial Population

Create multiple chromosomes.

For each occurrence:

1.  Select a valid slot.
2.  Select an allowed venue.
3.  Build the assignment.
4.  Repeat until a complete chromosome is created.

Then:

``` text
Population =
[
    chromosome_1,
    chromosome_2,
    chromosome_3,
    ...
]
```

## Random vs heuristic initialization

A purely random population is valid for learning.

Later, improve it with heuristic initialization.

For example, when assigning a difficult course:

-   prefer slots with fewer occupied resources,
-   prefer days that don't already contain that course,
-   prefer times that avoid known student conflicts,
-   prefer suitable-capacity venues.

This is optional for the first implementation.

------------------------------------------------------------------------

# 14. Constraint Categories

Separate constraints into:

## Hard constraints

These represent rules that should normally never be violated.

Examples:

-   Every required occurrence must be scheduled.
-   Repeated occurrences must be on different days.
-   Practical courses must use labs.
-   Ordinary lectures cannot use labs.
-   A venue cannot host two courses simultaneously.
-   A lecturer cannot teach two courses simultaneously.
-   A Program+Level cannot have more than 3 lectures in a day.
-   Courses sharing students should not overlap.

## Soft constraints

These are desirable but can be violated if necessary.

Current example:

-   Venue capacity should preferably accommodate the enrolled students.

Potential future examples:

-   Avoid lecturer back-to-back periods.
-   Prefer certain venues.
-   Prefer balanced daily workloads.
-   Other school-specific preferences.

------------------------------------------------------------------------

# 15. Important Infeasibility Principle

There is a difference between:

``` text
hard constraint
```

and:

``` text
constraint we would like to satisfy but may have to violate when the problem is impossible
```

Because your system must produce the **best available** timetable, the
optimizer should not silently pretend an impossible problem was solved
perfectly.

Instead return:

``` text
BEST_AVAILABLE
```

with a detailed violation report.

Example:

``` text
Status: BEST_AVAILABLE

Student conflicts: 2
Lecturer conflicts: 0
Venue conflicts: 0
Daily-limit violations: 0
Repeated-course-day violations: 0
Capacity penalty: 3
```

The final policy should prioritize student clashes above lower-priority
conflicts.

------------------------------------------------------------------------

# 16. Constraint Handler Architecture

Do not put every constraint directly inside one enormous fitness
function.

Create independent evaluators.

Conceptually:

``` text
constraints/
├── student_conflicts
├── lecturer_conflicts
├── venue_conflicts
├── daily_limits
├── occurrence_days
└── capacity
```

Each handler evaluates a candidate timetable.

For example:

``` text
check_student_conflicts(schedule)
check_lecturer_conflicts(schedule)
check_venue_conflicts(schedule)
check_daily_limits(schedule)
check_occurrence_days(schedule)
calculate_capacity_penalty(schedule)
```

This makes the system easier to test and extend.

------------------------------------------------------------------------

# 17. Student Clash Handler

For every pair of scheduled events:

1.  Determine whether their courses conflict by student group.
2.  Check whether their time slots are equal.
3.  If both are true, record a student conflict.

Conceptually:

``` text
if courses_conflict(A, B) and same_time(A, B):
    student_conflict += 1
```

The report should ideally include details:

``` text
Conflict:
    MTH101
    CSC101

Time:
    Monday 10:00–12:00

Shared group:
    Computer Science 100L
```

This is useful for both debugging and the admin UI.

------------------------------------------------------------------------

# 18. Lecturer Clash Handler

For every pair of events:

1.  Check whether their time slots overlap.
2.  Compare their lecturer sets.
3.  If the lecturer sets intersect, record a conflict.

Example:

``` text
CSC201 → [Lecturer A, Lecturer B]
MTH201 → [Lecturer A]
```

If both occur Monday 10:00--12:00:

``` text
Lecturer A is double-booked.
```

Multiple lecturers on the same course are therefore handled naturally.

Back-to-back lectures are legal:

``` text
08:00–10:00
10:00–12:00
```

No penalty is required unless you later decide to make lecturer workload
spacing a soft preference.

------------------------------------------------------------------------

# 19. Venue Clash Handler

Two events conflict if:

``` text
same venue
AND
same time slot
```

Example:

``` text
CSC101 → Hall A → Monday 10–12
MTH101 → Hall A → Monday 10–12
```

Penalty:

``` text
venue_conflict = 1
```

Adjacent use is completely legal:

``` text
CSC101 → Hall A → 08–10
MTH101 → Hall A → 10–12
```

A venue is inanimate; there is no turnaround constraint unless the
school later introduces one.

------------------------------------------------------------------------

# 20. Daily Lecture Limit Handler

The limit is:

``` text
maximum 3 lectures per day
per Program + Level
```

For every Program+Level:

``` text
count its scheduled events by day
```

Example:

``` text
Computer Science 100L

Monday:
    CSC101
    MTH101
    GST101
    PHY101

count = 4
```

Violation:

``` text
4 - 3 = 1
```

The handler should report both the Program+Level and the day.

------------------------------------------------------------------------

# 21. Repeated Occurrence Day Handler

For every course:

``` text
required_occurrences = N
```

collect its assigned days.

For:

``` text
MTH101-1 → Monday
MTH101-2 → Monday
```

there is a violation.

For:

``` text
MTH101-1 → Monday
MTH101-2 → Wednesday
```

there is no violation.

This should ideally be prevented during assignment, but it should still
be checked by the final validator.

------------------------------------------------------------------------

# 22. Capacity Handler

Capacity is soft.

For each event:

``` text
students_required
venue_capacity
```

If:

``` text
students_required <= venue_capacity
```

then:

``` text
capacity_penalty = 0
```

Otherwise calculate a penalty.

The exact formula can be tuned later.

For example, conceptually:

``` text
overflow = students_required - venue_capacity
```

and use some function of `overflow`.

The important rule is:

> Capacity shortage does not make the venue assignment illegal.

If 1000 students must use a 200-seat hall because there is no
alternative, the timetable can still be produced.

------------------------------------------------------------------------

# 23. Fitness Evaluation

A candidate timetable should produce an evaluation object rather than
just a single number.

Conceptually:

``` text
Evaluation
├── total_penalty
├── student_conflicts
├── lecturer_conflicts
├── venue_conflicts
├── daily_limit_violations
├── occurrence_day_violations
└── capacity_penalty
```

Then:

``` text
fitness = function(Evaluation)
```

For a simple first implementation:

``` text
fitness = 1 / (1 + total_penalty)
```

Higher fitness means better timetable.

------------------------------------------------------------------------

# 24. Weighted Penalties

A simple weighted model is:

``` text
total_penalty =
      student_conflicts       × VERY_HIGH_WEIGHT
    + lecturer_conflicts      × HIGH_WEIGHT
    + venue_conflicts         × HIGH_WEIGHT
    + daily_limit_violations  × HIGH_WEIGHT
    + occurrence_day_errors   × VERY_HIGH_WEIGHT
    + capacity_penalty        × LOW_WEIGHT
```

The actual numerical values should be experimentally tuned.

Do not start by obsessing over the perfect weights.

First verify that each constraint handler is correct.

------------------------------------------------------------------------

# 25. Better Than Arbitrary Weights: Lexicographic Fitness

For a more robust implementation, consider comparing solutions
lexicographically.

For example:

``` text
(student_conflicts,
 lecturer_conflicts,
 venue_conflicts,
 daily_limit_violations,
 occurrence_day_violations,
 capacity_penalty)
```

A candidate with fewer student conflicts is always better, even if
another candidate has a lower capacity penalty.

This avoids poorly chosen weights causing the GA to make strange
trade-offs.

You can later decide whether a weighted score or lexicographic ranking
works better for your population.

------------------------------------------------------------------------

# 26. Selection

The GA loop follows the same general structure you learned with TSP.

``` text
Population
    ↓
Evaluate
    ↓
Select parents
```

Possible selection methods:

-   Tournament selection
-   Rank selection
-   Fitness-proportionate selection
-   Top-N selection

Tournament selection is a good future option because it avoids some
issues caused by extreme fitness values.

For your first implementation, your existing top-N approach can work.

------------------------------------------------------------------------

# 27. Elitism

Always preserve the best candidate.

Conceptually:

``` text
best = best chromosome from current population

new_population = [
    copy(best)
]
```

Then fill the remaining population through selection, crossover, and
mutation.

This prevents the best solution from being accidentally destroyed.

You already encountered this problem in your TSP implementation.

------------------------------------------------------------------------

# 28. Crossover

Because chromosome positions correspond to fixed course occurrences,
crossover is simpler than TSP crossover.

Parent A:

``` text
[A1, A2, A3, A4, A5]
```

Parent B:

``` text
[B1, B2, B3, B4, B5]
```

A simple crossover can produce:

``` text
[A1, A2, A3, B4, B5]
```

Each position still represents the same course occurrence.

The child therefore remains structurally valid.

However, the child can still contain scheduling conflicts.

That is expected.

Crossover creates a candidate solution; the evaluator determines how
good it is.

------------------------------------------------------------------------

# 29. Mutation

A mutation changes the assignment of one or more course occurrences.

For example:

``` text
Before:
MTH101-1 → Monday 08–10 Hall A

After:
MTH101-1 → Thursday 14–16 Hall C
```

Possible mutation types:

### Full reassignment

Change:

``` text
day + time + venue
```

### Day mutation

Change only the day.

### Time mutation

Change only the period.

### Venue mutation

Change only the venue.

For version 1, full reassignment is sufficient.

------------------------------------------------------------------------

# 30. Constraint-Aware Mutation

Once the basic GA works, mutation can become smarter.

Instead of choosing a completely random new assignment:

1.  Find an event involved in conflicts.
2.  Generate several alternative valid assignments.
3.  Evaluate those alternatives.
4.  Prefer one that reduces conflicts.

Example:

``` text
MTH101
    ↓
currently causes:
    2 student conflicts
    1 lecturer conflict
    ↓
try alternative slots
    ↓
Thursday 14–16 removes all 3
```

This turns the GA into a hybrid:

``` text
Genetic Algorithm
+
Local Search
```

Do not implement this in your first version unless you need it.

------------------------------------------------------------------------

# 31. Repair Operators

Repair is another useful technique.

After crossover/mutation:

``` text
candidate
    ↓
detect obvious conflict
    ↓
move offending occurrence
    ↓
candidate becomes better
```

Examples:

-   Move a course out of a student clash.
-   Move a lecturer out of a double booking.
-   Move a course to another available venue.
-   Move an event from a fourth daily lecture for a Program+Level.

Repair can dramatically reduce the number of generations needed.

But it should be added after the basic GA is functioning.

------------------------------------------------------------------------

# 32. Search-Space Reduction

A major performance principle:

> Never make the GA search choices that can be eliminated beforehand.

Examples:

### Don't generate Friday 12--2

Remove it from valid slots.

### Don't generate labs for ordinary lectures

Remove them from allowed venues.

### Don't generate ordinary halls for practical courses

Remove them from allowed venues.

### Don't query database data repeatedly during fitness evaluation

Precompute it.

The smaller the search space, the easier the GA's job becomes.

------------------------------------------------------------------------

# 33. Suggested GA Algorithm

Conceptually:

``` text
function generate_timetable(problem):

    population = create_initial_population(problem)

    best_solution = None

    for generation in range(max_generations):

        evaluations = []

        for chromosome in population:

            evaluation = evaluate(chromosome, problem)

            evaluations.append(evaluation)

        current_best = get_best(evaluations)

        if current_best is better than best_solution:
            best_solution = copy(current_best)

        if termination_condition_met(best_solution):
            break

        elite = copy(best_solution)

        parents = select_parents(population, evaluations)

        new_population = [elite]

        while size(new_population) < population_size:

            parent_a = choose_parent(parents)
            parent_b = choose_parent(parents)

            child = crossover(parent_a, parent_b)

            child = mutate(child)

            child = optional_repair(child)

            new_population.append(child)

        population = new_population

    final_evaluation = evaluate(best_solution, problem)

    return build_result(best_solution, final_evaluation)
```

------------------------------------------------------------------------

# 34. Termination Conditions

Don't rely exclusively on a fixed generation count.

Useful conditions include:

## Maximum generations

``` text
generation >= max_generations
```

## Perfect solution

If every required hard constraint has zero violations:

``` text
student_conflicts = 0
lecturer_conflicts = 0
venue_conflicts = 0
daily_limit_violations = 0
occurrence_day_violations = 0
```

you may stop early.

## Stagnation

If the best score hasn't improved for a certain number of generations:

``` text
no_improvement >= patience
```

you may stop.

This is useful because some problems converge quickly while others
don't.

------------------------------------------------------------------------

# 35. Final Validation

Never assume:

> "The GA returned it, therefore it is valid."

Run the complete constraint validator again after optimization.

``` text
best chromosome
      ↓
FINAL VALIDATOR
      ↓
constraint report
```

The final validator should be deterministic and independent enough that
you can trust it.

This also protects against bugs in crossover/mutation/repair.

------------------------------------------------------------------------

# 36. Final Result Model

The generator should return more than a list of timetable entries.

Conceptually:

``` text
GenerationResult
├── status
├── timetable[]
├── fitness
├── evaluation
├── generation_count
└── metadata
```

Possible statuses:

``` text
OPTIMAL
FEASIBLE
BEST_AVAILABLE
FAILED
```

For a GA, `OPTIMAL` should be used carefully because a GA normally does
not mathematically prove global optimality.

A safer vocabulary might be:

``` text
FEASIBLE
BEST_AVAILABLE
FAILED
```

where `FEASIBLE` means all designated hard constraints were satisfied.

------------------------------------------------------------------------

# 37. Example Conflict Report

A useful final result could look like:

``` text
Status: BEST_AVAILABLE

Occurrences scheduled:
    84 / 84

Student conflicts:
    1

Lecturer conflicts:
    0

Venue conflicts:
    0

Daily-limit violations:
    0

Repeated-occurrence-day violations:
    0

Capacity overflow:
    3 events
```

Then the student conflict details:

``` text
Student Conflict #1

Course A:
    MTH101

Course B:
    CSC101

Shared student group:
    Computer Science 100L

Time:
    Wednesday 10:00–12:00
```

This can be passed directly to the admin interface.

------------------------------------------------------------------------

# 38. Why the Conflict Report Matters

The system should not hide an infeasible result.

An administrator might see:

``` text
Timetable generated successfully.

Warning:
1 student conflict could not be eliminated.
```

Then inspect:

``` text
MTH101
CSC101
Computer Science 100L
Wednesday 10–12
```

The administrator can then manually modify the schedule or regenerate
it.

This fits well with a timetable management system where the generated
weekly timetable is a base pattern rather than an immutable artifact.

------------------------------------------------------------------------

# 39. External Functional Handlers

Several operations belong outside the GA.

## Database handlers

``` text
get_courses(scope)
get_student_groups(course)
get_lecturers(course)
get_venues(scope)
```

## Access/venue handlers

``` text
get_allowed_venues(course, scope)
```

## Preprocessing handlers

``` text
expand_occurrences(courses)
build_student_conflict_graph(courses)
build_valid_slots()
```

## Constraint handlers

``` text
check_student_conflicts()
check_lecturer_conflicts()
check_venue_conflicts()
check_daily_limits()
check_occurrence_days()
calculate_capacity_penalty()
```

## GA handlers

``` text
create_population()
evaluate()
select()
crossover()
mutate()
repair()
```

Keeping these responsibilities separate is one of the most important
architectural decisions in the project.

------------------------------------------------------------------------

# 40. Recommended Project Structure

A possible Python implementation:

``` text
timetable_optimizer/
│
├── models/
│   ├── course.py
│   ├── occurrence.py
│   ├── lecturer.py
│   ├── venue.py
│   ├── student_group.py
│   ├── slot.py
│   └── problem.py
│
├── preprocessing/
│   ├── occurrences.py
│   ├── venues.py
│   ├── conflicts.py
│   └── slots.py
│
├── constraints/
│   ├── students.py
│   ├── lecturers.py
│   ├── venues.py
│   ├── daily_limits.py
│   ├── occurrences.py
│   └── capacity.py
│
├── genetic/
│   ├── chromosome.py
│   ├── population.py
│   ├── selection.py
│   ├── crossover.py
│   ├── mutation.py
│   ├── repair.py
│   └── algorithm.py
│
├── evaluation/
│   ├── evaluator.py
│   └── report.py
│
└── generator.py
```

The names are suggestions, not requirements.

------------------------------------------------------------------------

# 41. Database vs Optimizer Models

Do not force your database models to become your GA chromosome.

For example, your Django/SQLAlchemy/etc. model might contain dozens of
fields:

``` text
Course
├── id
├── code
├── title
├── department
├── created_at
├── updated_at
├── status
├── ...
```

The optimizer may only need:

``` text
OptimizedCourse
├── id
├── student_groups
├── lecturers
├── allowed_venues
├── required_occurrences
└── course_type
```

This is called creating a problem-specific representation.

It reduces coupling between the application and optimization engine.

------------------------------------------------------------------------

# 42. Testing Strategy

Do not start with your entire university dataset.

Build progressively.

## Test 1 --- Day + Time only

``` text
3 courses
3 days
3 periods
```

Objective:

``` text
avoid student clashes
```

------------------------------------------------------------------------

## Test 2 --- Add lecturers

``` text
A teaches Course 1
A teaches Course 2
```

Verify that they cannot overlap.

------------------------------------------------------------------------

## Test 3 --- Add venues

``` text
Hall A
Hall B
```

Verify that two simultaneous courses cannot use Hall A.

------------------------------------------------------------------------

## Test 4 --- Add practical courses

``` text
Lab 1
Hall A
```

Verify:

``` text
practical → Lab only
lecture → Hall only
```

------------------------------------------------------------------------

## Test 5 --- Add repeated occurrences

``` text
MTH101 → 2 occurrences
```

Verify:

``` text
Monday + Wednesday
```

and reject:

``` text
Monday + Monday
```

------------------------------------------------------------------------

## Test 6 --- Add daily limits

Create enough courses for:

``` text
CS100L Monday = 4
```

Verify the validator detects the violation.

------------------------------------------------------------------------

## Test 7 --- Add soft capacity

Verify that:

``` text
500 students → 200-seat hall
```

is allowed but receives a penalty.

------------------------------------------------------------------------

## Test 8 --- Test infeasibility

Intentionally create an impossible problem.

For example:

``` text
2 courses
same lecturer
same student group
only one available slot
```

The system should return:

``` text
BEST_AVAILABLE
```

rather than falsely claiming a perfect timetable.

------------------------------------------------------------------------

# 43. Debugging Tools You Should Build

During development, add functions that can print a chromosome as a
timetable.

For example:

``` text
Monday
--------------------------------
08–10   CSC101   Hall A
10–12   MTH101   Hall B
12–14   GST101   Hall C
14–16   ---
16–18   PHY101   Hall A
```

Also print evaluation:

``` text
Student conflicts: 2
Lecturer conflicts: 1
Venue conflicts: 0
Daily violations: 1
Capacity penalty: 4
Total penalty: ...
```

This will make debugging the GA dramatically easier.

------------------------------------------------------------------------

# 44. Performance Considerations

The expensive part will likely be **fitness evaluation**, because it
runs repeatedly.

If you have:

``` text
500 course occurrences
1000 population members
500 generations
```

you potentially evaluate hundreds of millions of assignments.

Therefore:

### Precompute

-   student conflict graph
-   lecturer-to-course relationships
-   allowed venues
-   valid slots
-   course metadata

### Avoid

-   database queries inside fitness evaluation
-   repeated student-group intersection calculations
-   repeated venue-access resolution
-   constructing expensive objects unnecessarily

### Consider later

-   incremental fitness evaluation
-   cached conflict information
-   multiprocessing
-   optimized data structures
-   constraint-aware initialization
-   repair/local search

Do not optimize prematurely, but design the interfaces so these
improvements remain possible.

------------------------------------------------------------------------

# 45. The First Implementation You Should Actually Build

Do not implement everything in this document at once.

Your learning implementation should start with:

``` text
CourseOccurrence
    ↓
(day, time, venue)
    ↓
Chromosome
    ↓
Population
    ↓
Fitness
    ↓
Selection
    ↓
Elitism
    ↓
Crossover
    ↓
Mutation
    ↓
Repeat
```

Initially implement only:

``` text
Student conflicts
Venue conflicts
Lecturer conflicts
```

Then add:

``` text
Daily limits
```

Then:

``` text
Repeated occurrence days
```

Then:

``` text
Capacity
```

Then experiment with:

``` text
Repair
Local search
Constraint-aware mutation
```

This progression will keep the project understandable.

------------------------------------------------------------------------

# 46. Recommended Development Phases

## Phase 1 --- Data representation

Implement:

-   CourseOccurrence
-   StudentGroup
-   Lecturer
-   Venue
-   Slot
-   SchedulingProblem
-   Assignment

Do not implement the GA yet.

------------------------------------------------------------------------

## Phase 2 --- Constraint handlers

Implement and independently test:

``` text
check_student_conflicts()
check_lecturer_conflicts()
check_venue_conflicts()
check_daily_limits()
check_occurrence_days()
calculate_capacity_penalty()
```

You should be able to give these functions a manually constructed
timetable and verify their results.

------------------------------------------------------------------------

## Phase 3 --- Basic GA

Implement:

``` text
create_individual()
create_population()
evaluate()
select()
crossover()
mutate()
elitism
```

Get a tiny timetable working.

------------------------------------------------------------------------

## Phase 4 --- Full constraints

Add every confirmed school rule.

------------------------------------------------------------------------

## Phase 5 --- Reporting

Return:

``` text
timetable
score
status
violations
statistics
```

------------------------------------------------------------------------

## Phase 6 --- Performance

Only after correctness is established:

-   optimize data structures,
-   cache conflict relationships,
-   profile fitness evaluation,
-   optimize population generation,
-   consider parallel evaluation.

------------------------------------------------------------------------

## Phase 7 --- Hybrid optimization

Only if necessary:

``` text
GA
+
repair
+
local search
```

------------------------------------------------------------------------

# 47. Complete Conceptual Flow

The whole system can now be viewed as:

``` text
┌─────────────────────────────┐
│          DATABASE           │
│                             │
│ Courses                     │
│ Programs                    │
│ Levels                      │
│ Student groups              │
│ Lecturers                   │
│ Venues                      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│       PREPROCESSING         │
│                             │
│ Expand occurrences          │
│ Resolve allowed venues      │
│ Build valid time slots      │
│ Build student conflicts     │
│ Prepare lecturer data       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│    SCHEDULING PROBLEM       │
│                             │
│ Events                      │
│ Slots                       │
│ Allowed venues              │
│ Conflict graph              │
│ Constraints                 │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│      INITIAL POPULATION     │
│                             │
│ Chromosome 1                │
│ Chromosome 2                │
│ ...                         │
│ Chromosome N                │
└──────────────┬──────────────┘
               │
               ▼
       ┌────────────────┐
       │    EVALUATE    │
       └───────┬────────┘
               │
       ┌───────┼──────────┐
       ▼       ▼          ▼
   Students Lecturers   Venues
       │       │          │
       └───────┼──────────┘
               │
          Daily limits
               │
        Occurrence days
               │
           Capacity
               │
               ▼
          FITNESS SCORE
               │
               ▼
          SELECT PARENTS
               │
               ▼
           CROSSOVER
               │
               ▼
            MUTATE
               │
               ▼
       OPTIONAL REPAIR
               │
               ▼
          NEXT GENERATION
               │
               └───────────────┐
                               │
                        repeat until
                         termination
                               │
                               ▼
                     ┌──────────────────┐
                     │  BEST SOLUTION   │
                     └────────┬─────────┘
                              │
                              ▼
                     FINAL VALIDATION
                              │
                              ▼
                     GENERATION RESULT
                              │
                ┌─────────────┴─────────────┐
                │                           │
            TIMETABLE                 CONFLICT REPORT
```

------------------------------------------------------------------------

# 48. Final Design Principles

Keep these principles in mind while implementing.

### 1. The GA is a search engine, not your entire application.

It should not query your database or resolve university permissions.

### 2. Precompute what you can.

Especially student conflicts, allowed venues, and valid slots.

### 3. Prevent impossible choices where practical.

Don't generate invalid venues or unavailable time slots and then punish
them.

### 4. Keep constraints independent.

A `student_conflicts` handler is easier to test than a 300-line
`fitness()` function.

### 5. Fitness should explain itself.

Keep the individual violation counts, not only one mysterious score.

### 6. Preserve the best solution.

Use elitism.

### 7. Validate the final result independently.

Never trust the GA blindly.

### 8. Don't hide infeasibility.

Return `BEST_AVAILABLE` and tell the administrator exactly what remains
wrong.

### 9. Student conflicts have the highest priority.

The optimizer should strongly prefer removing student clashes over
lower-priority improvements.

### 10. Build the simple GA first.

Only introduce repair, local search, constraint-aware mutation, caching,
and parallelism after the basic implementation is correct.

------------------------------------------------------------------------

# 49. The Implementation Mental Model

The most important thing to remember is this:

``` text
              WHAT ARE WE SCHEDULING?
                       │
                       ▼
              Course Occurrences
                       │
                       ▼
              WHERE CAN THEY GO?
                       │
                       ▼
                Valid Assignments
                (day,time,venue)
                       │
                       ▼
              IS THE RESULT GOOD?
                       │
                       ▼
                 Constraints
                       │
                       ▼
                  Evaluation
                       │
                       ▼
                 GA SEARCH
                       │
                       ▼
             Better timetable
                       │
                       ▼
             Repeat until done
```

Your GA is therefore not "creating a timetable" in one magical
operation.

It is repeatedly asking:

> **"Given these course occurrences, how should I assign their day,
> time, and venue so that the resulting schedule has fewer and less
> serious violations?"**

That is the problem your chromosome, fitness function, crossover,
mutation, and constraint handlers collectively solve.
