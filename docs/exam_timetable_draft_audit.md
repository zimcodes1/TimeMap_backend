# Examination Timetable Draft Comprehensive Audit & Discrepancy Report

**Run ID Analyzed:** `2` (Scope: School 1, Semester: 1 — First Semester 2026)  
**Creation Date:** 2026-10-24 10:54:26 UTC  
**Target Architecture & Specs:**
- [`exam_timetable_optimizer_architecture.md`](./exam_timetable_optimizer_architecture.md)
- [`exam_timetable_optimizer_implementation_plan.md`](./exam_timetable_optimizer_implementation_plan.md)
- [`exam_schedule_2025_2026_sample.md`](./exam_schedule_2025_2026_sample.md)

---

## Executive Summary

An in-depth empirical comparison was conducted between the newly generated examination timetable draft (Run ID 2) and the mathematical formulation, architectural requirements, and institutional expectations documented across the codebase.

While the current solver successfully satisfies nominal venue non-collision ($H_6$), campus operating hours ($H_{10}$), and Friday Jummat prayer blackout ($H_{10}$), it exhibits **critical structural bugs and architectural discrepancies**. Most notably, when individual student registrations are not available and enrollment counts rely on departmental cohort quotas, the solver's student conflict checks, workload tracking, and soft constraints **completely collapse into a naive greedy FIFO queue**.

This causes students to be subjected to up to **5 consecutive written exams (10 hours back-to-back) in a single day** and **7 CBT exams in a single morning**, while **43 out of 49 written venues sit completely idle** and **1,000 CBT seats are wasted in parallel halls**.

---

## Summary Matrix of Inconsistencies & Bugs

| ID | Category | Severity | Documented Expectation | Actual Draft Implementation | Root Cause |
|:---|:---|:---:|:---|:---|:---|
| **BUG-01** | **Soft Constraint $S_1$ & $S_2$** | **CRITICAL** | Max 1 exam/day ($S_2$), max 3 exams/week ($S_1$). Smooth spread across calendar. | 400L students have **5 written exams on Day 1** (08:00–18:00 back-to-back); 200L students have **7 CBT exams on Day 2**. | `search.py` evaluates workload strictly by `student_ids.intersection()`. For quota-based cohorts, `student_ids` is empty, causing daily/weekly loads to evaluate to 0. |
| **BUG-02** | **Conflict Detection ($H_3$)** | **CRITICAL** | Courses with shared cohorts must not clash in time ($H_3$). 2,084 pairwise edges precomputed. | `solver/search.py`, `solver/repair.py`, and `validation/validator.py` **never query `student_conflict_graph`**. | Solver only checks `student_ids` sets. If empty, conflict detection evaluates to `False`. |
| **BUG-03** | **Metrics & Diagnostics** | **HIGH** | Workload metrics must report true student stress (`max_daily`, `max_weekly`, `over_3_per_week`). | Reports `max_exams_per_day: 0` and `max_exams_per_week: 0` despite students having 7 exams/day. | `constraints/workload.py` loops over `state["student_ids"]` without falling back to cohort `(program_id, level)`. |
| **BUG-04** | **CBT Venue Parallelism ($S_5$)** | **HIGH** | Multiple CBT centres operate in parallel; turns balanced across centres; concurrent courses allowed. | **Zero concurrent CBT exams.** 182/182 CBT courses assigned to `E-Library`. ICT Hall 1 & 2 idle 88% of the time. | Static pre-allocation binds all courses $\le 500$ students to E-Library. Venue overlap in `search.py` then blocks any parallel CBT scheduling. |
| **BUG-05** | **Written Venue Utilization ($S_4$)** | **HIGH** | Dynamic allocation minimizing capacity waste across all 49 accessible halls. | **Only 6 out of 49 venues used.** 43 venues (including major twin theatres and assembly halls) completely untouched. | `written.py` deterministically picks the same single "best-fit" venue for any cohort of a given size before time placement. |
| **BUG-06** | **Session Joining ($H_9$, $S_6$)** | **MEDIUM** | Small compatible courses merge into shared rooms to economize physical rooms and invigilation. | 7 pairs marked "joined", but courses sit in **completely different buildings** (e.g. MTH401 in BCH Hall 2, ZOO401 in Networking Lab). | `joining.py` requires `venue_ids.intersection() == \emptyset` and merely stamps `joined_courses` on separate room events. |
| **BUG-07** | **Calendar Distribution ($S_3$)** | **MEDIUM** | Balance compression against student rest across approved 4-week window (Nov 16 – Dec 15). | Written exams crammed into 2.5 days. Entire schedule ends on Day 10. **19 operating days completely empty.** | Greedy search score `(0, 0, day, start_time)` forces every exam into the earliest possible calendar slot. |
| **BUG-08** | **Payload Data Loss** | **LOW** | Event payload must preserve `duration_per_student_minutes` for UI turn explanation. | Field omitted from `event_payload` in `search.py`. Serialized as `None`. | Missing field in `search_exam_schedule` event dictionary construction. |

---

## Detailed Findings

### 1. Student Workload Explosion & Soft Constraint Bypass (BUG-01, BUG-03)

#### Documented Specification
- **Architecture Doc Section 3.3**:
  $$\text{Penalty}_{\text{weekly}}(s, w) = \max(0, \text{weekly\_exams}(s, w) - 3) \times 50.0$$
  $$\text{Penalty}_{\text{daily}}(s, d) = \max(0, \text{daily\_exams}(s, d) - 1) \times 30.0$$
- An examination timetable is expected to distribute examinations evenly over the active calendar to allow adequate study and rest periods.

#### Observed Empirical Behavior in Run 2
- **400 Level Computer Science Students (Monday 2026-11-16)**:
  - 08:00 – 10:00: `COS401` (Written, 2 hrs)
  - 10:00 – 12:00: `COS403` (Written, 2 hrs)
  - 12:00 – 14:00: `COS405` (Written, 2 hrs)
  - 14:00 – 16:00: `COS407` (Written, 2 hrs)
  - 16:00 – 18:00: `COS409` (Written, 2 hrs)
  - *Result*: **10 continuous hours of written exams without a single minute of break.**
  - On Tuesday morning, the same cohort sits `COS411` (08:00–10:00) and `COS499` (10:00–12:00). All 7 final-year courses are finished in 28 hours.
- **200 Level Computer Science Students (Tuesday 2026-11-17)**:
  - 08:00 – 08:30: `COS203` (CBT)
  - 08:30 – 09:00: `COS205` (CBT)
  - 09:00 – 09:30: `COS207` (CBT)
  - 09:30 – 10:00: `COS209` (CBT)
  - 10:00 – 10:30: `COS211` (CBT)
  - 10:30 – 11:00: `CYB201` (CBT)
  - 11:00 – 11:30: `SWE201` (CBT)
  - *Result*: **7 consecutive CBT exams in 3.5 hours on the same morning.**
- **False Metrics Display**:
  - `metrics.maximum_exams_per_student_per_day` = `0`
  - `metrics.maximum_exams_per_student_per_week` = `0`
  - `metrics.students_over_three_exams_per_week` = `0`
  - The UI displays green checkmarks asserting "Ideal spread ($\le$ 1/day)" and "Zero students overloaded".

#### Root Cause Analysis
In `TimeMap_backend/core/scheduling/exam_optimizer/solver/search.py`:
```python
# Check student workload distribution
if students and students.intersection(old["student_ids"]):
    if old_date.isocalendar().week == day.isocalendar().week:
        weekly_loads.append(old)
    if old["date"] == day.isoformat():
        daily_loads.append(old)
```
When courses are seeded using departmental student quota counts (`DepartmentStudentCount`), individual student rows do not exist in `CourseRegistration`. Consequently:
1. `students` is an empty set: `set()`.
2. `len(weekly_loads)` and `len(daily_loads)` are always `0`.
3. Candidate scoring key `score_key = (0, 0, day, start_time)` degenerates into a pure preference for the earliest calendar date and time.
4. `calculate_student_workload()` in `constraints/workload.py` loops over `state["student_ids"]`, resulting in zero iterations and reporting all workload statistics as `0`.

---

### 2. Disconnect in Conflict Detection ($H_3$) (BUG-02)

#### Documented Specification
- **Architecture Doc Section 3.2 ($H_3$)**:
  $$\text{Conflict}(e_1, e_2) = 1 \implies [start(e_1), end(e_1)) \cap [start(e_2), end(e_2)) = \emptyset$$
- `preprocessing/conflicts.py` builds an exact graph where courses sharing attributed program cohorts `(program_id, level)` are connected. In Run 2, this graph contains **2,084 conflict edges**.

#### Observed Empirical Behavior
- The solver (`search.py`) and validator (`validator.py`) never reference `problem.student_conflict_graph`.
- In `search.py`, line 94:
  ```python
  if (students and students.intersection(old["student_ids"])) or venue_ids.intersection(old["venue_ids"]):
      overlaps = True
      break
  ```
- Because `students` is empty, the only check preventing simultaneous exams is `venue_ids.intersection()`.
- Courses from the same department/level avoided overlapping **only by coincidence**, because they were deterministically assigned the same venue. Had they been assigned different rooms, the optimizer would have scheduled them at the exact same hour without flagging any error.

---

### 3. CBT Parallel Venue Under-Utilization & Turn Allocation (BUG-04)

#### Documented Specification
- **Architecture Doc Section 1.1 point 3 & Section 4.2**:
  Throughput model requires multi-centre parallelism:
  $$C_{\text{total}} = \sum_{i=1}^m C_i, \quad \text{longest\_turns} = \left\lceil \frac{N}{C_{\text{total}}} \right\rceil$$
- **Nasarawa State University Historical Schedule (`exam_schedule_2025_2026_sample.md`)**:
  Multiple departmental CBT courses run concurrently in parallel facilities (e.g. `BIO211` at ICT Centre while `NS-BUA213` and `LIS216` run at E-Library).

#### Observed Empirical Behavior in Run 2
- Total CBT courses: **182**
- Total concurrent CBT sessions across different venues: **0**
- Venue distribution for CBT:
  - `Venue 52 (E-Library)`: Assigned to **182 courses (100%)**
  - `Venue 50 (ICT HALL 1)`: Assigned to **21 courses (11.5%)**
  - `Venue 51 (ICT HALL 2)`: Assigned to **7 courses (3.8%)**
- For 161 CBT courses (all courses with $\le 500$ students), **1,000 available CBT seats in ICT Hall 1 and ICT Hall 2 remain completely dark and empty**.
- A small CBT course of 50 students locks out the entire university examination period because its pre-allocated venue is E-Library, and no other CBT course can run at that time.

#### Root Cause Analysis
1. `allocate_cbt_venues()` in `allocation/cbt.py` sorts venues by capacity descending and assigns students greedily:
   ```python
   for venue, cap in capacities:
       assigned = min(cap * longest_turns, remaining)
       allocations.append(...)
       remaining -= assigned
       if remaining == 0:
           break
   ```
2. Because E-Library appears first among 500-seat centres, every course $\le 500$ students receives `allocations = [E-Library]`.
3. In `search.py`, venue allocation is performed **statically before window search**:
   ```python
   allocation = allocate_venues(eligible_venues, count, exam_type, duration, per_student)
   actual_duration, venue_allocs = allocation
   venue_ids = {a["venue_id"] for a in venue_allocs}
   ```
4. During search, every small CBT course carries `venue_ids = {52}`.
5. In `search.py`, `venue_ids.intersection(old["venue_ids"])` triggers for any overlapping time window.
6. The solver serializes all 182 CBT courses end-to-end like a single-lane queue into E-Library.

---

### 4. Written Venue Starvation (BUG-05)

#### Documented Specification
- **Architecture Doc Section 4.1**:
  Written room planner evaluates single-room closest fit ($C_v \ge N$, minimize excess) and room pairs to balance campus room usage.

#### Observed Empirical Behavior in Run 2
- Total available active lecture halls/auditoriums in FNAS: **49**
- Total venues used across all 63 written exams: **6**
- Venues used:
  1. `Venue 8 (NSUK 1000-Seater Auditorium)`: 7 times
  2. `Venue 19 (FNAS Central Hall 2)`: 14 times
  3. `Venue 20 (CMP Lecture Room 101)`: 7 times
  4. `Venue 28 (CHM Lecture Hall 1)`: 14 times
  5. `Venue 31 (BCH Lecture Hall 2)`: 14 times
  6. `Venue 3 (Networking lab)`: 7 times
- **43 active examination venues are never utilized**. High-capacity spaces such as FNAS Twin Lecture Theatres A & B (720 exam seats combined), Faculty Assembly Hall (240 seats), and Science LTs 1–3 remain completely idle throughout the exam season.

#### Root Cause Analysis
Because `allocate_written_venues()` is called statically before time placement, every course of a specific cohort size resolves to the exact same room. The solver does not maintain dynamic room availability during search, causing heavy over-subscription of 6 rooms and complete abandonment of the remaining 43.

---

### 5. Inverted "Joined Session" Semantics (BUG-06)

#### Documented Specification
- **Architecture Doc Section 1.1 point 5 & Section 4.3**:
  Small courses ($\le 60$ written, $\le 100$ CBT) are joined to **share an examination session and supervisory resources** (i.e. sitting together in a common room).

#### Observed Empirical Behavior in Run 2
- Run 2 reports `joined_sessions: 7` (14 courses).
- Example: `MTH401` is joined with `ZOO401` on Monday 08:00–10:00:
  - `MTH401` is seated in `BCH Lecture Hall 2` (Capacity 60, Students 60).
  - `ZOO401` is seated in `Networking lab` (Capacity 50, Students 50).
- The two courses are in completely different physical rooms in separate buildings. They share neither physical space nor invigilators.
- In `allocation/joining.py`, line 68:
  ```python
  if state_a["venue_ids"].intersection(state_b["venue_ids"]):
      continue
  ```
  The implementation explicitly enforces that joined courses **cannot share a venue**. The engine merely tags concurrent independent courses as "joined" to fulfill the metric.

---

### 6. Premature Calendar Abandonment (BUG-07)

#### Documented Specification
- Approved semester examination window: **2026-11-16 to 2026-12-15** (4 weeks, 25 operating days).
- Soft constraint $S_3$ seeks period compression without causing student workload spikes.

#### Observed Empirical Behavior in Run 2
- Active exam days utilized: **10 days** (all exams conclude on Thursday 2026-11-26).
- Written exams finish completely on Wednesday 2026-11-18 (Day 3).
- **19 operating days (from Nov 27 to Dec 15) have zero scheduled exams.**
- The schedule is hyper-compressed at the front, creating severe student burnout while leaving 65% of the approved exam calendar empty.

---

### 7. Missing Event Payload Field (BUG-08)

#### Documented Specification
- Course exam settings allow configuring per-student duration (e.g. 30 minutes for CBT).
- The API contract and inspection UI expect `duration_per_student_minutes` to calculate turn distributions.

#### Observed Empirical Behavior in Run 2
- In `solver/search.py`, `event_payload` omits `duration_per_student_minutes`.
- In all 245 event JSON objects, `duration_per_student_minutes` is `None` or absent.

---

## Architectural Remediation Roadmap

To align the optimizer with its documented specifications and real-world institutional standards, the following technical fixes are required:

### Phase 1: Cohort-Aware Conflict & Workload Grounding
1. **Unify `student_ids` with Cohort Identifiers**:
   When individual student registrations are not available, map each course's population to synthetic cohort IDs: `(program_id, level)`.
2. **Direct Solver to Conflict Graph**:
   Update `solver/search.py` and `solver/repair.py` to consult `problem.student_conflict_graph[course_id]`.
3. **Cohort Workload Evaluation**:
   Update `constraints/workload.py` so that daily load ($\le 1$) and weekly load ($\le 3$) are evaluated per cohort `(program_id, level)` when individual student IDs are absent.

### Phase 2: Dynamic Venue Allocation during Search
1. **Decouple Physical Allocation from Pre-Search**:
   Move venue selection inside the candidate window evaluation loop in `search.py`.
2. **Dynamic Room Availability**:
   Maintain a running calendar of room occupancy. When placing course $e$ at $(day, start\_time)$, query available rooms at that specific time window and select the best fit from rooms that are actually free.
3. **Multi-CBT Parallel Stream Support**:
   Allow small CBT courses to occupy single CBT centres (e.g. ICT Hall 1) while another independent course runs in E-Library simultaneously.

### Phase 3: True Session Joining
1. Re-implement `joining.py` so that small courses sharing the same time window merge their student populations into a single shared hall up to the hall's exam capacity.

### Phase 4: Calendar Spreading Objective
1. Refactor candidate window scoring from pure earliest-slot `(0, 0, day, start_time)` to an objective function that penalizes day density and encourages uniform distribution across the full 4-week examination period.

