# Week 2 — Detailed Implementation Roadmap
## Venue Registry, Course Structure & Timetable CRUD (No Conflict Logic Yet)

Same format as Week 1: a day-by-day build order, not a checklist to tackle in any order. Each day produces something the next day depends on. No conflict-detection logic is built this week — that's deliberately isolated to Week 3, so this week's job is to get every underlying model correct and provably CRUD-able first.

**Week 2 mission:** by the end of this week, an admin officer can create venues (with correct ownership), create courses (with correct ownership and sharing), register students to courses, and create timetable entries — including recurring lectures materialized into dated sessions — all through real, permission-scoped CRUD screens on the web app. None of it checks for conflicts yet; that's next week, deliberately.

---

## Day 1 — Facility & Venue Models

**Why this comes first:** venues are referenced by every timetable entry built later this week, so they need to exist, correctly structured, before anything else. This also reuses the ownership pattern from `AdminOfficer.scope` (Week 1, Day 5) — building it here reinforces that pattern in a second context before Week 3's conflict engine has to lean on it in a third.

### Steps

1. **Model `Facility`** — a proper table (name, unique), not a free-text or tag field on `Venue`. This matters for later querying ("find every venue with a projector") and for keeping facility names canonical, since free text invites duplicate-looking entries ("Projector" vs "projector" vs "proj.").
2. **Seed a small starter set of common facilities** — projector, whiteboard, air conditioning, exam-style seating, public address system — through the same admin-facing creation pattern as everything else this week, not a hardcoded fixture. An admin should be able to add a facility type that isn't in the starter set without a code change.
3. **Model `Venue`** — name, `venue_type` (lecture hall / laboratory / exam hall / multipurpose), `capacity`, `exam_capacity` (nullable, only populated when exam seating reduces the room's usable capacity), a many-to-many link to `Facility`, and an `is_active` flag for venues temporarily or permanently out of use.
4. **Add the ownership fields** — `owning_level` (department / faculty / school) plus the three matching nullable reference fields (`owning_department`, `owning_faculty`, `owning_school`), only one of which is populated depending on `owning_level`. This is the same three-nullable-field shape used for `AdminOfficer.scope` — deliberately, so the conflict engine built in Week 3 can compare "who administers this" against "who owns this venue" using one consistent comparison, not two different data shapes.
5. **Decide who can set ownership at creation time.** A department admin creating a venue should only be able to set `owning_level = department` with `owning_department` fixed to their own department — they shouldn't be able to declare a venue faculty-owned themselves. A faculty admin can set `department` (for any department under their faculty) or `faculty`. A school admin can set any level. This rule belongs in the permission/serializer layer now, even though nothing yet checks venue conflicts — it's about who's allowed to claim ownership of a shared resource, which is a permissions question, not a conflict-detection question.
6. **Build admin-facing venue CRUD** — create, edit, deactivate. No booking or scheduling logic yet, just managing the venue registry itself: name, type, capacity, facilities, ownership.

**End of Day 1 checkpoint:** `Facility` and `Venue` exist, correctly structured with the ownership pattern, and an admin officer can create and manage venues through the web app — with ownership-setting correctly restricted by the creating admin's own level and scope.

---

## Day 2 — Course Model & Sharing Workflow

**Why this follows venues, not the other way around:** courses and venues don't depend on each other directly, but course ownership uses the exact same pattern just built for venues on Day 1 — doing it immediately after means the pattern is fresh and consistently applied, rather than re-derived from scratch.

### Steps

1. **Model `Course`** — `code` (unique), `title`, `level` (academic year the course is offered at), and a many-to-many link to `LecturerStaff` for the term's assigned teaching staff.
2. **Add the ownership fields** — `owning_level` (department / faculty / school / **general**), plus the three matching nullable reference fields. `general` is the one case with no reference field populated at all, since a general course (a GST-style course every student takes) doesn't belong to any single branch of the hierarchy.
3. **Define the default visibility rule** in the service layer now, even before anything renders it to a student: a department-owned course is visible to that department only; a faculty-owned course is visible to every department under that faculty; a school-owned course is visible to every department under that school; a general course is visible to everyone. Write this as a single resolution function from the start — it'll be called from multiple places later (student course lists, registration screens, analytics), and having one canonical implementation avoids the default rule quietly drifting out of sync between two hand-written copies.
4. **Model `CourseAccessGrant`** — handles sharing outside the default rule (e.g. a Mathematics-owned Statistics course explicitly shared with Computer Science, a department under a different faculty entirely). Fields: `course`, `granted_to_level` plus matching nullable references, `direction` (`offered` if the owning admin proactively shared it, `requested` if a non-owning admin asked for it), `status` (pending/approved/rejected), `initiated_by`, `decided_by`, `decided_at`.
5. **Build the two-directional grant flow**: an admin who owns a course can offer access to a specific department/faculty/school directly; an admin who doesn't own a course can submit an access request, which routes to whichever admin has authority over the owning level. Approval always sits with the owning side, regardless of which direction started it — this is the same routing shape the discrepancy workflow will use in Week 4, so it's worth getting the pattern right here first, since it's simpler in this context (no conflict-checking involved yet, just an approval toggle).
6. **Extend the visibility resolution function from step 3** to also check for an `approved` `CourseAccessGrant` covering the student's department or faculty, alongside the default ownership rule. One function, two conditions checked together — not two separate visibility systems a caller has to remember to combine correctly.
7. **Build admin-facing course CRUD**, including the create-with-ownership flow (mirroring the same creation-time restriction from Day 1 — a department admin can only create department-owned courses for their own department) and a simple grant-management screen (offer access, view/approve incoming requests).

**End of Day 2 checkpoint:** `Course` and `CourseAccessGrant` exist, an admin can create courses at the correct ownership level, offer or request sharing across departments/faculties/schools, and the visibility resolution function correctly reflects both default ownership and approved grants.

---

## Day 3 — Course Registration & Timetable Entry Model

**Why registration comes before the timetable entry model:** the exam clash-detection logic being planned for Week 3 depends on knowing which students are registered for which courses. If `CourseRegistration` doesn't exist by the time timetable entries (specifically exams) are built, there's no way to test even the shape of that dependency this week — better to have it in place now, even though the clash-check logic itself isn't built until next week.

### Steps

1. **Model `CourseRegistration`** — `student`, `course`, `academic_session` (a text field like "2025/2026" distinguishing the same course across different years/terms). No status field needed yet at this stage — a registration is just a fact, not a workflow.
2. **Build a simple registration flow** — a student can register for any course visible to them (per Day 2's resolution function), and an admin can view/manage registrations for their scope. This doesn't need to be elaborate this week; it needs to exist and produce real data other features can query against.
3. **Model `TimetableEntry`** — the shared structure behind lectures, exams, and events: `entry_type` (lecture/exam/event), `title`, `course` (nullable — null for general events with no course attached), `venue`, `start_time`, `end_time`, `recurrence_rule` (nullable, for weekly-repeating lectures), `recurrence_start_date`, `recurrence_end_date`, `status` (scheduled/shifted/postponed/cancelled), `created_by`, `academic_session`.
4. **Decide the recurrence rule format now** — a compact rule string describing the repetition pattern (e.g. "weekly on Tuesday"), rather than a set of fully structured fields. This system only needs to express simple weekly recurrence for lectures, not arbitrary complex patterns, so keep the field simple — this avoids overengineering a recurrence system the system doesn't need, while leaving room to parse more complex rules later without a schema change.
5. **Apply the same creation-time ownership restriction as venues and courses**: who can create a `TimetableEntry` against a given venue should be governed by whether the creating admin's scope matches or is permitted to request the venue's owning level — even though the actual conflict/approval logic isn't built until Weeks 3–4, the basic "can this admin even attempt to book here" gate belongs in the permission layer from the start.
6. **Build a bare-bones admin CRUD for `TimetableEntry`** — create, edit, view — without any conflict warning yet. This is intentionally the simplest possible version: no recurrence expansion, no venue clash checking, just a form that creates a valid row.

**End of Day 3 checkpoint:** `CourseRegistration` exists and is populated with real registration data; `TimetableEntry` exists and can be created through a basic admin form, with no conflict checking wired in yet.

---

## Day 4 — Recurrence Materialization & Exam Extension

**Why this is its own day, not folded into Day 3:** turning an abstract recurring rule into concrete dated sessions is a distinct piece of logic from simply storing the rule — and it's the piece that everything from Week 5 onward (class rep reporting) depends on. Getting it right in isolation, before anything else consumes its output, makes it much easier to verify correctness.

### Steps

1. **Build the recurrence materialization service** — given a `TimetableEntry` with a `recurrence_rule`, `recurrence_start_date`, and `recurrence_end_date`, generate one `LectureSession` row per actual calendar date the recurrence applies to, for the current term.
2. **Model `LectureSession`** — `timetable_entry` (reference to the parent recurring entry), `session_date`, `session_start_time`, `session_end_time`, `venue`, and `status` (scheduled/shifted/postponed/cancelled/held/not_held). Time and venue are copied from the parent at materialization time rather than always read live from it.
3. **Explain and enforce why time/venue are copied, not referenced live**: if a single Tuesday's lecture is shifted to a different room — a one-off change affecting only that date, not the whole weekly pattern — that change has to live on the specific `LectureSession` instance without altering every other week's instance. If the instance always read its venue live from the parent `TimetableEntry`, a one-off shift would be impossible to express without either changing the recurring rule for every week or building an override mechanism that duplicates what copying already gives for free.
4. **Run materialization against real registered courses** from Day 3, for a realistic date range (a full term), and manually spot-check a sample of the generated sessions against the expected calendar dates — this is worth doing by hand once, not just trusting the logic, since an off-by-one error in date generation here quietly corrupts every downstream feature that depends on session dates being correct.
5. **Model `ExamSitting`** as a one-to-one extension of `TimetableEntry` — `registered_candidates_count` (derived from `CourseRegistration` counts for the linked course and session) and `invigilators` (many-to-many to `LecturerStaff`). Extending rather than duplicating the base fields avoids maintaining two parallel definitions of "a thing happens at a venue at a time."
6. **Build a basic admin flow for creating an exam sitting** — selecting the course, venue, and time, with `registered_candidates_count` auto-populated from real registration data rather than manually entered, since manual entry here is exactly the kind of value that drifts out of sync with reality over time.

**End of Day 4 checkpoint:** recurring lecture entries correctly materialize into dated `LectureSession` rows for a full term, spot-checked for date accuracy; `ExamSitting` exists and can be created with an auto-populated candidate count drawn from real registration data.

---

## Day 5 — Web CRUD Completion & Week Close-Out

**Why this is last:** by Day 5, every model this week depends on already exists and has been tested in isolation. Today is about making sure the actual admin-facing web screens are complete and usable end to end — not introducing new logic, just finishing the interface layer on top of what's already correct underneath.

### Steps

1. **Complete the venue management screen** — list, filter (by type, facility, owning level), create, edit, deactivate — scoped correctly so a department admin only sees and manages their own department's venues by default, while still being able to view (not edit) venues above their level for booking-request purposes later.
2. **Complete the course management screen** — list, filter (by department, level, ownership), create, edit, and the grant-management sub-screen (offer/request/approve sharing) from Day 2.
3. **Complete the timetable entry creation screen** — supporting all three entry types (lecture, exam, event) through one form with type-specific fields shown conditionally, rather than three separate disconnected forms. Lecture creation should trigger the Day 4 materialization service automatically once saved.
4. **Run a full walkthrough per role**: as a department admin, create a department-owned venue and course, register a student to it, create a recurring lecture and confirm sessions materialize correctly; as a faculty admin, confirm visibility into (and correct edit permissions over) everything beneath their faculty, including approving a course access grant requested by one of their departments.
5. **Write a short internal note on what's deferred to Week 3** — explicitly stating that no conflict detection exists yet, so double-booking a venue or double-scheduling a student across two exams is currently possible and expected to be possible until next week's work closes that gap. This matters so nobody mistakes this week's lack of conflict warnings for a bug rather than a deliberate sequencing choice.

**End of Week 2 checkpoint:** an admin officer, scoped correctly to their level, can create venues, courses (with correct ownership and sharing), register students, and create lecture/exam/event timetable entries — including recurring lectures that correctly materialize into dated sessions — entirely through the web app, with no conflict checking yet in place by design.

---

## Why This Sequencing, Summarized

| Day | Builds On | Because |
|---|---|---|
| 1 — Facility & Venue | Week 1's ownership pattern | Reuses the exact scope-comparison shape already proven for AdminOfficer, applied to a second model before Week 3 needs it in a third |
| 2 — Course & sharing | Day 1's ownership pattern | Course ownership/sharing needs the same shape; doing it right after Venue keeps the pattern fresh and consistent |
| 3 — Registration & TimetableEntry | Day 2 | Exam clash-detection (Week 3) needs registration data to exist; timetable entries need courses and venues to reference |
| 4 — Materialization & ExamSitting | Day 3 | Reporting (Week 5) needs dated instances, not abstract recurring rules; materialization needs the entry model to exist first |
| 5 — Web CRUD completion | Days 1–4 | Every underlying model is stable by now; this day is interface work, not new logic |

Nothing built this week checks for conflicts — that's deliberate. Week 3 builds the conflict engine against this week's now-stable, already-tested data layer, so any bug found in Week 3 can be confidently attributed to the conflict logic itself, not to something shaky underneath it.
