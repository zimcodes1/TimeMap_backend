# Week 3 — Detailed Implementation Roadmap
## Conflict Detection Engine (Built and Tested in Isolation)

Same format as Weeks 1 and 2: a day-by-day build order. This week is the highest-risk week in the whole 8-week plan — it's the piece the system's entire credibility rests on — so the sequencing here is deliberately conservative: each individual check is built and proven correct on its own before the next one is layered on top, and none of it is wired into the admin-facing UI until the logic itself is already trustworthy.

**Week 3 mission:** by the end of this week, the system can correctly answer four separate questions — does this booking clash with another booking at the same venue, does it clash with a student's exam schedule, does it clash with a lecturer's assignments, and if it touches a venue outside the requester's own authority, does it get routed for approval rather than silently accepted or rejected — and every one of those answers is backed by a test proving it, not just a plausible-looking implementation.

---

## Day 1 — Venue Overlap Detection

**Why this is the first and most foundational check:** venue double-booking is the most visible, most damaging failure mode the system exists to prevent — two classes or exams showing up to the same room at the same time is the exact problem this whole project was commissioned to solve. Everything else this week builds on the interval-comparison logic developed today.

### Steps

1. **Build the overlap comparison as a standalone function first** — given two time ranges (`start_time`, `end_time`) on the same date, determine whether they overlap, using the standard interval-overlap check: `existing.start < proposed.end AND existing.end > proposed.start`. Write this as its own small, isolated, heavily-tested unit before wiring it to anything database-related — it's the single piece of logic every other check this week reuses, so it needs to be unambiguously correct on its own first.
2. **Decide explicitly how adjacent-but-not-overlapping slots are handled** — a lecture ending at 10:00 and another starting at 10:00 in the same venue should not be flagged as a conflict. Write a specific test for this exact boundary case before anything else, since off-by-one boundary handling is the most common source of subtle bugs in interval logic, and it's far cheaper to catch here than after it's embedded in three other checks.
3. **Apply the overlap check against materialized instances, not raw recurrence rules.** A venue clash check needs to compare actual dated occurrences — `LectureSession` rows, one-off exam `TimetableEntry` rows, event `TimetableEntry` rows — never two abstract recurring rules against each other. Comparing recurrence rules directly (e.g. "does 'every Tuesday' overlap with 'every other Wednesday'") is a much harder and more error-prone problem than comparing concrete dates, and Week 2 already built the materialization step specifically so this problem never has to be solved.
4. **Build the venue overlap query**: given a proposed `(venue, date, start_time, end_time)`, fetch every existing `LectureSession` and one-off `TimetableEntry`/`ExamSitting` at that venue on that date, and run each through the Day 1 comparison function. Return every conflicting record found, not just the first — an admin resolving a clash benefits from seeing the full picture, not one match at a time.
5. **Write the edge-case test suite for this check specifically**: fully overlapping ranges, partially overlapping ranges (start overlaps only, end overlaps only), one range fully containing another, identical ranges, adjacent-non-overlapping ranges (from step 2), and a proposed booking against a venue with zero existing bookings on that date (the trivial no-conflict case, worth confirming explicitly rather than assuming it "obviously works").

**End of Day 1 checkpoint:** a standalone, thoroughly tested venue overlap detection function exists, correctly comparing a proposed booking against every materialized instance at a venue on a given date, with all boundary cases explicitly covered by tests — not yet wired into any creation endpoint.

---

## Day 2 — Student & Lecturer Double-Booking Detection

**Why this follows venue overlap rather than running in parallel:** both of today's checks reuse the exact interval-comparison function built and proven on Day 1 — they're really the same underlying logic applied against a different set of records (a student's registered exams, a lecturer's assigned sessions, instead of a venue's bookings). Building Day 1 first means today is mostly about correctly assembling the right query, not re-deriving the comparison logic.

### Steps

1. **Build the student exam clash check**: given a proposed `ExamSitting` (course, date, start_time, end_time), find every student registered (via `CourseRegistration`) to the course being examined, then check whether any of those students already have another exam scheduled — via a different course's `CourseRegistration` — whose sitting overlaps in time on the same date, using the Day 1 comparison function.
2. **Decide what the check returns when a clash is found**: not just "yes/no," but which students are affected and which other exam they clash with — an admin trying to resolve a scheduling clash needs enough detail to actually act on it (e.g. move one of the two exams, or confirm the affected student count is small enough to handle individually).
3. **Build the lecturer double-booking check**: given a proposed `TimetableEntry` or `ExamSitting` with an assigned lecturer or invigilator, check whether that person already has another session (lecture, exam, or invigilation duty) overlapping in time on the same date.
4. **Test the student check against a realistic scenario**: two courses with overlapping registration (some students registered for both), exams scheduled at overlapping times — confirm only the genuinely overlapping students are flagged, not the entire registration list of either course. This is worth testing explicitly, since a naive implementation might flag "any student registered for either course" rather than correctly narrowing to students registered for *both*.
5. **Test the lecturer check against the multi-role case**: a lecturer who is both teaching a regular lecture and assigned as an invigilator for an exam at an overlapping time — confirm the check catches this correctly, since it involves two different model types (`TimetableEntry.course.lecturers` and `ExamSitting.invigilators`) rather than one.

**End of Day 2 checkpoint:** student exam clash detection and lecturer double-booking detection both exist as standalone, tested functions, correctly identifying affected students/lecturers by name rather than a bare true/false result, and correctly handling the multi-role lecturer case.

---

## Day 3 — Hierarchical Override Routing

**Why this comes after the raw conflict checks, not before:** routing logic decides *what to do* with a detected situation — approve automatically, reject outright, or route for approval — and that decision only makes sense once the system can reliably detect whether a conflict actually exists. Building routing before Days 1–2 existed would mean routing decisions based on conflict information that wasn't trustworthy yet.

### Steps

1. **Reuse the ownership-comparison shape already established** — `Venue.owning_level` / `owning_department` / `owning_faculty` / `owning_school` against `AdminOfficer.level` / `scope_department` / `scope_faculty` / `scope_school`. Write the comparison function once: given a requesting admin and a target venue, determine whether the venue falls within the admin's own scope (including everything beneath it in the hierarchy, per Week 1 Day 5's downward-resolution rule), outside it entirely, or above it.
2. **Define the three routing outcomes explicitly**:
   - **Within scope, no clash detected** (Days 1–2 checks pass) → booking proceeds directly, no approval needed.
   - **Within scope, clash detected** → hard rejection at the point of booking, with a clear error identifying the conflicting record — no approval workflow needed, since there's a single admin with authority to resolve it themselves.
   - **Outside the requester's own scope** (a department admin targeting a faculty-owned or another department's venue) → the booking attempt does not create a `TimetableEntry` directly; instead it becomes a pending request routed to whichever admin owns the target venue, regardless of whether a clash was independently detected — the owning admin's approval step is itself where clash-checking is enforced at decision time.
3. **Confirm the downward-resolution rule holds here specifically**: a department admin booking a venue owned by their *own* department requires no routing at all, even though technically their scope is "beneath" no one — this is the base case and should be the simplest, fastest path through the logic, not something that accidentally falls through to the routing branch by mistake.
4. **Write the routing decision as its own function, separate from the checks it calls** — given a requesting admin and a proposed booking, it should call the ownership-comparison function from step 1, then the Day 1–2 conflict checks as appropriate, and return one of the three outcomes from step 2. Keeping this as a distinct orchestration layer (rather than interleaving ownership logic and conflict logic in one large function) makes each piece independently testable and easier to reason about when something goes wrong later.
5. **Test all three outcomes explicitly**, plus the specific case flagged in Week 1's roadmap: a faculty admin managing an exam timetable that spans several departments beneath their faculty should resolve to the "within scope, no routing needed" path, not incorrectly fall into the "outside scope, requires routing" branch — this was called out before as a case worth testing directly, and this is where it actually gets tested.

**End of Day 3 checkpoint:** a single routing decision function exists, correctly classifying any proposed booking into one of three outcomes (proceed / reject / route for approval) based on the requester's scope relative to the target venue's ownership, with the faculty-admin-cross-department case explicitly verified.

---

## Day 4 — Wiring Into Creation Endpoints

**Why wiring happens after all the logic is independently proven, not alongside it:** every piece built Days 1–3 has been tested as a standalone function so far, deliberately disconnected from the actual `TimetableEntry`/`ExamSitting` creation endpoints built in Week 2. Today is where they get connected — and because each piece is already independently trustworthy, any bug found today is very likely a wiring/integration bug, not a logic bug, which makes it much faster to isolate.

### Steps

1. **Insert the Day 3 routing function into the `TimetableEntry` creation endpoint** — every creation attempt (lecture, exam, event) runs through the routing decision before a row is committed, rather than being saved first and checked after.
2. **Insert the same logic into `ExamSitting` creation**, additionally running the Day 2 student-clash check (which doesn't apply to ordinary lectures or events, only exams) as part of the same flow.
3. **Handle the "route for approval" outcome concretely**: rather than the `TimetableEntry` row being created directly, this outcome should produce a distinct pending record capturing the proposed booking details, awaiting the owning admin's decision. (The full `DiscrepancyRequest`/approval-queue model is built out properly in Week 4 — this week only needs the routing outcome to correctly *not* create a live booking, holding the proposal in a minimal pending state sufficient to prove the routing logic works end to end. Week 4 will build the complete workflow around it.)
4. **Return clear, specific error responses on hard rejection** — not a generic "conflict detected" message, but which existing booking it clashes with, at what venue, and at what time, so the requesting admin can immediately understand what to change rather than guessing.
5. **Confirm recurrence-aware conflict checking works correctly**: creating a new recurring lecture should check every one of its materialized `LectureSession` instances against existing bookings, not just the first date — a common mistake would be checking only the recurrence rule's start date and missing a clash that only occurs three weeks into the term. Test this specifically with a recurring lecture whose second or third occurrence (not the first) collides with an existing one-off booking.

**End of Day 4 checkpoint:** venue creation for lectures, exams, and events runs through the full conflict-detection and routing logic built this week, correctly handling recurring entries by checking every materialized occurrence, with clear and specific error messaging on rejection.

---

## Day 5 — Full Test Suite, Load Check & Close-Out

**Why this is a dedicated day rather than folded into Day 4:** the individual pieces have each been tested in isolation as they were built, but today is about proving the *whole* engine behaves correctly together, under realistic and adversarial conditions — including the concurrency scenario this specific piece of logic is most exposed to.

### Steps

1. **Assemble a comprehensive end-to-end test suite** covering every combination the week has built: same-level clash (hard reject), same-level no-clash (proceed), cross-level request within a clash-free slot (routes for approval, no clash flagged), cross-level request that would also clash (routes for approval, with the clash visible to the deciding admin), exam sitting with a genuine student double-booking, exam sitting with a genuine lecturer/invigilator double-booking, and a recurring lecture whose materialized instance three weeks out collides with an existing booking.
2. **Run a concurrency check specifically on venue overlap detection** — simulate two near-simultaneous booking attempts against the same venue and time slot, and confirm the system doesn't allow both to succeed. This is the one part of the system most likely to be hit by genuinely concurrent requests in real use (two admins racing to claim a popular venue), and it's worth deliberately testing under that condition now rather than discovering a race condition later under real usage.
3. **Review every error message produced by the engine** for clarity from a non-technical admin's point of view — a department admin should never see a raw database or stack-trace-style error when a booking is rejected; they should see a plain description of what clashed and with what.
4. **Confirm no partial state is ever created on rejection** — a hard-rejected or routed booking attempt should leave zero trace in the live `TimetableEntry`/`ExamSitting`/`LectureSession` tables; only an actual approval (immediate or via the pending record from Day 4) should ever result in a live, bookable record.
5. **Write a short internal note on what's deferred to Week 4** — the full `DiscrepancyRequest` approval-queue UI, notification on approval/rejection, and audit logging are explicitly not built this week; only the minimal pending-record mechanism needed to prove routing works. This distinction matters so Week 4 isn't mistaken for redundant work — it's building the real workflow around a routing decision that's already proven correct.

**End of Week 3 checkpoint:** the conflict-detection engine — venue overlap, student exam clash, lecturer double-booking, and hierarchical override routing — is fully built, wired into the real creation endpoints, proven correct through a comprehensive test suite including a concurrency check, and produces clear, specific, non-technical error messaging on every rejection path.

---

## Why This Sequencing, Summarized

| Day | Builds On | Because |
|---|---|---|
| 1 — Venue overlap | Week 2's materialized `LectureSession` data | The core interval-comparison logic every other check this week reuses; venue double-booking is the system's central failure mode |
| 2 — Student & lecturer clashes | Day 1's comparison function | Same underlying logic, applied against registration and assignment data instead of venue bookings |
| 3 — Hierarchical routing | Days 1–2 | Routing decides what to do with a detected conflict; needs conflict detection to already be trustworthy before deciding around it |
| 4 — Wiring into endpoints | Days 1–3 | Connecting already-proven standalone logic to real endpoints, so bugs found here are wiring bugs, not logic bugs |
| 5 — Full suite & load check | Days 1–4 | Proves the whole engine together, including the one concurrency scenario most likely to appear in real usage |

Every check built this week stayed a standalone, independently tested function before being wired into anything the admin ever sees. That discipline is what Week 4 depends on — the discrepancy and approval workflow reuses this week's routing logic wholesale rather than re-implementing any part of it, and it can only do that safely because this week's version is already proven correct on its own.
