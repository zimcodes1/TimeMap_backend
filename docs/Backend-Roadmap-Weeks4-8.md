# Backend Implementation Roadmap — Weeks 4 to 8
## Continuing From Completed Backend Work (Weeks 1–3)

This continues directly from Weeks 1–3, which delivered the organizational hierarchy, auth, scoped permissions, venue/course/timetable CRUD, recurrence materialization, and the conflict-detection engine — all backend, no UI. This document keeps that discipline through to the end of the backend build: every week below produces API endpoints only, tested directly against the API (via automated tests and manual API calls), with no web or mobile screen work included anywhere in this document. The frontend phase — covering both the web portal and mobile app — is a separate document, built once this entire API surface is complete and stable.

**Why finish the whole backend before touching any UI:** a frontend built against an API that's still changing underneath it means UI rework every time a backend decision shifts. Finishing the backend first means the frontend phase has one job — consume a finished, documented contract — rather than two jobs happening at once.

---

# Week 4 — Discrepancy Workflow & Audit Log

**Goal:** shifts, postponements, and cancellations become a real request-and-approval workflow with API endpoints, and every administrative action across the system is logged.

**Why now:** this week directly reuses Week 3's hierarchical routing function — a requested change to an existing booking needs to be checked and routed the same way a new booking is. Building this before Week 3 existed would have meant duplicating routing logic that didn't exist yet to duplicate.

## Day 1 — DiscrepancyRequest Model & Submission Endpoint

1. Model `DiscrepancyRequest`: `timetable_entry` (or `lecture_session` for a one-off instance change), `request_type` (shift_venue / shift_time / postpone / cancel), the relevant proposed-value fields (`proposed_venue`, `proposed_start_time`, `proposed_date`), `reason`, `initiated_by`, `status` (pending/approved/rejected), `routed_to`, `decided_by`, `decided_at`.
2. Build the submission endpoint — any admin, or a lecturer proposing a change to their own session, can submit a request. Validate that `request_type` and the populated proposed-value fields are internally consistent (e.g. a `shift_venue` request shouldn't also carry a `proposed_date`).
3. Distinguish a **one-off instance change** (a single Tuesday's lecture shifted, referencing `LectureSession`) from a **recurring-pattern change** (every future occurrence of a weekly lecture moved, referencing `TimetableEntry` itself) at the model level — these are genuinely different operations with different blast radius, and conflating them risks a "shift one date" request accidentally being applied to the whole term.
4. Test: submission correctly rejects an internally inconsistent request (wrong proposed fields for the given `request_type`); submission correctly distinguishes instance-level vs pattern-level requests.

## Day 2 — Approval Routing (Reusing Week 3's Logic)

1. On submission, run the proposed change through Week 3's hierarchical routing function — same-level change with no clash → auto-approved immediately (or fast-tracked to a single-click approval, your call on whether same-level still needs an explicit approve action); same-level change with a clash → hard-rejected immediately with the same clear error messaging Week 3 already produces; cross-level change → routed to `routed_to`, the admin with authority over the affected venue.
2. **Re-run the full Week 3 conflict check against the *proposed* change specifically**, not the original booking — a shift request has to be validated as if it were a brand new booking attempt, checked against everything currently scheduled, before it can even reach the approval stage. This is the step that guarantees an admin can never approve a change that creates a fresh clash.
3. Build the approval/rejection decision endpoints — restricted to the admin identified in `routed_to` (or, for a same-level fast-tracked case, the requester's own scope).
4. Test: a cross-level request correctly routes to the right admin; a proposed change that would itself create a new clash is flagged at submission time, before any human approval step, not after.

## Day 3 — State Transitions & Application

1. Implement the full state machine explicitly: `pending → approved → applied` or `pending → rejected`. "Applied" is a distinct state from "approved" — approval is a decision, application is the actual database change (updating the `TimetableEntry`/`LectureSession` row) that follows it. Keeping these separate means an approval can be logged and notified on before the underlying schedule data changes, which matters once Week 6 wires notifications to these events.
2. On approval, apply the change: update the target `LectureSession` or `TimetableEntry` fields, and set its `status` appropriately (shifted/postponed/cancelled).
3. Build a cancel/withdraw endpoint for the original requester, usable only while `status = pending`.
4. Test: full lifecycle from submission through approval through application produces a correctly updated schedule record; a withdrawn request never reaches application; rejected requests never touch the live schedule data at all.

## Day 4 — Generic Audit Log

1. Model `AuditLog`: `actor`, `action` (create/update/delete/approve/reject), `target_model`, `target_id`, `before_snapshot` (JSON), `after_snapshot` (JSON), `timestamp`.
2. Build a **generic logging utility** hooked in once at the signal/middleware level, covering every create/update/delete across `Venue`, `Course`, `CourseAccessGrant`, `TimetableEntry`, `LectureSession`, `ExamSitting`, and `DiscrepancyRequest` — not bespoke logging code written per model. A model added after this week should get audit coverage automatically, without a developer remembering to wire it in individually.
3. Build a read-only, scope-filtered audit log query endpoint — an admin can see the log for records within their own scope, never platform-wide unless they're at the top of the hierarchy.
4. Test: every write operation this week (Days 1–3) produces a correctly attributed audit entry with accurate before/after snapshots; the query endpoint correctly scopes results.

## Day 5 — Full Test Suite & API Documentation

1. Write end-to-end API tests covering the full discrepancy lifecycle across every routing outcome from Week 3 (same-level auto-resolve, same-level clash-rejected, cross-level routed-and-approved, cross-level routed-and-rejected).
2. Confirm audit entries exist and are accurate for every one of those scenarios.
3. Annotate all new endpoints for the OpenAPI schema (drf-spectacular) — request/response shapes, permission requirements, and possible error responses documented now, not deferred, since the frontend phase will build directly against this schema.
4. Write a short internal note on what's deferred: no notification is sent yet on approval/rejection (that's Week 6); this week's endpoints are silent beyond their direct API response.

**End of Week 4 checkpoint:** discrepancy requests can be submitted, correctly routed by reusing Week 3's logic, re-validated against a full conflict check before approval, approved/rejected/applied through a clean state machine, and every action across the system's core models is captured in a scoped, queryable audit log — all reachable and testable purely through the API.

---

# Week 5 — Class Representative Reporting

**Goal:** the mandatory, time-boxed lecture-hold reporting flow, fully functional at the API level.

**Why now:** this depends on Week 2's materialized `LectureSession` rows existing (there's nothing to report on without them) and benefits from Week 4's audit logging already being in place to capture report submissions and disputes consistently with everything else.

## Day 1 — ClassRepReport Model & Submission Endpoint

1. Model `ClassRepReport`: `lecture_session` (one-to-one), `reported_by`, `held` (boolean), `reason` (required regardless of `held` value), `reported_at`, `window_expires_at`, `lecturer_response`, `lecturer_responded_at`.
2. Build the submission endpoint — restricted to `Student` with `is_class_rep = true`, and only for sessions belonging to their own department/level.
3. **Enforce the reporting window server-side, not just as a UI convenience**: `window_expires_at` is set to the session's `end_time` plus a configurable duration; the submission endpoint rejects any attempt made after that timestamp, regardless of what any client sends. This is the single most important enforcement point in this feature.
4. Test: a report submitted within the window succeeds; a report submitted after `window_expires_at` is rejected even via a direct API call; a non-rep student cannot submit; a rep cannot submit for a session outside their own department.

## Day 2 — Unreported Session Sweep

1. Model `UnreportedSessionFlag`: `lecture_session` (one-to-one), `flagged_at`, `acknowledged_by`, `acknowledged_at`.
2. Build a Celery Beat scheduled task that runs periodically, finds every `LectureSession` whose `window_expires_at` has passed with no associated `ClassRepReport`, and creates an `UnreportedSessionFlag` for each.
3. Build an endpoint for department admins to view and acknowledge flags within their own scope.
4. Test: the sweep correctly flags an expired, unreported session and correctly does *not* flag a session that was reported on time, or one whose window hasn't expired yet; running the sweep twice doesn't create duplicate flags for the same session.

## Day 3 — Lecturer Response

1. Build the lecturer response endpoint — restricted to the `LecturerStaff` actually assigned to the course the reported session belongs to, setting `lecturer_response` and `lecturer_responded_at` on the existing `ClassRepReport` rather than creating a competing record.
2. Decide and enforce whether a response can be edited after submission (a reasonable default: allow one edit within a short window, then lock it).
3. Test: only the correct lecturer can respond to a report on their own session; a lecturer cannot respond to a report on someone else's session.

## Day 4 — Reporting Visibility Endpoints

1. Build scoped read endpoints: a department admin can list all reports and flags within their department; a lecturer can list reports (and any disputes) filed against their own sessions; a student can view their own submission history if they're a rep.
2. Add basic filtering — by date range, by course, by `held`/`not_held`, by acknowledged/unacknowledged flag status — since this data will be consumed by Week 7's analytics work and by admins directly.
3. Test: scoping is correct in every direction (a department admin never sees another department's reports; a lecturer never sees another lecturer's).

## Day 5 — Full Test Suite

1. Write end-to-end tests covering the full lifecycle: session materializes (from Week 2) → window opens at `end_time` → report submitted within window → lecturer response attached → all correctly visible through the Day 4 endpoints.
2. Write the parallel unreported-path test: window expires with no report → sweep flags it → admin acknowledges it.
3. Load-test the sweep task against a realistic volume of sessions (a full term's worth) to confirm it completes in reasonable time as a scheduled background job.
4. Document all endpoints for the OpenAPI schema.

**End of Week 5 checkpoint:** class rep reporting is fully functional at the API level — server-side window enforcement, automatic flagging of unreported sessions via a tested scheduled sweep, a non-one-sided dispute mechanism for lecturers, and correctly scoped visibility for every role — with no UI built yet.

---

# Week 6 — Notifications Infrastructure

**Goal:** real event-driven notification generation and delivery, reachable at the API level, with the actual push/email delivery mechanics fully working even before any client displays them.

**Why now:** notifications are only meaningful once there are real trigger events to notify about — Week 4's discrepancy decisions and Week 5's reporting events are exactly those triggers. Building this infrastructure earlier would have meant testing against fabricated events.

## Day 1 — Notification Model & Trigger Design

1. Model `Notification`: `recipient`, `notification_type`, `title`, `body`, `related_model`, `related_id`, `read_at`, `created_at`.
2. Design the trigger points explicitly as a list, and hook each one into the relevant Week 4/5 event: `discrepancy_approved`, `discrepancy_rejected`, `session_shifted`, `session_cancelled`, `reporting_window_open`, `session_unreported`.
3. Build the in-app inbox endpoints: list (paginated, most recent first), mark-as-read, unread count.
4. Test: each trigger event from Weeks 4–5 correctly produces exactly one `Notification` row for the correct recipient(s) — not zero, not duplicated.

## Day 2 — Push Notification Dispatch

1. Model `DeviceToken`: `user`, `fcm_token`, `platform`, `is_active`, `registered_at`.
2. Build the device registration endpoint (a client will call this once it has a real FCM token — even without a mobile app yet, this can be tested by registering a token manually via the API).
3. Integrate Firebase Admin SDK server-side, and build the dispatch function: given a `Notification`, push it to every active `DeviceToken` belonging to the recipient.
4. Handle dispatch failure correctly — if FCM reports a token as invalid, mark that `DeviceToken.is_active = false` rather than retrying indefinitely against a dead token.
5. Test: dispatch to a valid token succeeds (verifiable against a real test device/emulator even without the full mobile app built); dispatch to a deliberately invalid token correctly deactivates it rather than erroring the whole notification pipeline.

## Day 3 — Async Email Delivery

1. Integrate `django-anymail` (or equivalent) for transactional email.
2. Build the async email dispatch task via Celery — triggered for the subset of notification types that warrant a durable, external record (discrepancy approvals are the clearest case), never run synchronously in the request/response cycle.
3. Test: email dispatch is genuinely asynchronous (the triggering API call returns immediately); a failed email send doesn't fail the underlying operation that triggered it.

## Day 4 — Full Trigger Wiring

1. Go back through every Week 4 and Week 5 endpoint and confirm each correctly fires its corresponding notification trigger from Day 1.
2. Confirm all three channels (in-app, push, email) fire from the same underlying event consistently, rather than three independently-triggered paths that could drift out of sync with each other.
3. Test: triggering a discrepancy approval produces a matching in-app notification, a push dispatch attempt, and an email dispatch task — all three, from one event.

## Day 5 — Full Test Suite & Documentation

1. End-to-end test: full discrepancy and reporting flows from Weeks 4–5, now verified to also produce correct notifications on every channel.
2. Test notification list/read-state endpoints under realistic volume (a user with many historical notifications) for correct pagination and unread-count accuracy.
3. Document all new endpoints for the OpenAPI schema.

**End of Week 6 checkpoint:** every relevant event from Weeks 4–5 reliably produces notifications across in-app, push, and email channels; device token registration and dispatch (including failure handling) work correctly; all of it verified via API and, where applicable, a real test device — no client UI required to prove any of it works.

---

# Week 7 — Analytics & Calendar Sync
# Week 7 — Analytics (Calendar Sync Omitted)

**Goal:** read-only aggregation endpoints for administrative analytics (lecture-hold rate, venue utilization, discrepancy frequency). Note: Google Calendar integration is explicitly excluded from this build phase as in-app inbox and transactional emails are sufficient.

**Why now:** analytics has nothing meaningful to compute until real data exists from every prior week.

## Day 1 — Aggregation Query Design

1. Build the lecture-hold-rate aggregation: held vs. not-held count from `ClassRepReport`, grouped by course, by lecturer, and by department, over a selectable date range (`start_date`, `end_date`).
2. Build the venue utilization aggregation: booked hours vs available hours per venue over a selectable date range.
3. Build the discrepancy-frequency aggregation: count of `DiscrepancyRequest` records per venue and request type, to surface venues or courses that get shifted/cancelled unusually often.
4. Keep these as pure read queries against existing tables — no new write paths, so a bug here can misreport a number but can never corrupt scheduling data.

## Day 2 — Scoped Analytics Endpoints

1. Build the API endpoints exposing Day 1's aggregations under `/api/reporting/analytics/`, each correctly scoped to the requesting admin's level, matching the same downward-resolving scope pattern used everywhere else in the system.
2. Add date-range (`start_date`, `end_date`) and grouping parameters (`group_by`) rather than a single fixed view.
3. Test: aggregation numbers are verified by hand against a known dataset.

## Day 3 & 4 — Optimization & Hierarchical Bounds

1. Verify query efficiency across `ClassRepReport`, `LectureSession`, `Venue`, and `DiscrepancyRequest` aggregations.
2. Ensure strict scope filtering (Department Admin sees department data; Faculty Admin sees faculty & department data under their faculty; School Admin sees school data).

## Day 5 — Full Test Suite & API Documentation

1. Write unit tests covering lecture-hold rate, venue utilization, and discrepancy frequency calculations.
2. Document all new endpoints for the OpenAPI schema and API Documentation guide.

**End of Week 7 checkpoint:** scoped, verified-accurate analytics aggregation endpoints exist for lecture-hold rate, venue utilization, and discrepancy frequency — all reachable purely through the API.

---

# Week 8 — Backend Hardening, Full Documentation & Deployment

**Goal:** the entire backend API — everything built across Weeks 1–7 — tested together as a whole, secured, documented as a complete contract, and deployed, ready for the frontend phase to build against.

**Why this is the final backend week, not skippable:** every prior week tested its own slice in isolation. This is the first point the *entire* backend is exercised end to end as one system, and it's also where the API becomes a finished, trustworthy contract rather than a moving target — which is the precondition for starting frontend work at all.

## Day 1 — End-to-End Integration Testing

1. Write full-journey API test scenarios spanning every week: hierarchy and course setup → venue and course creation with ownership → student registration → recurring lecture creation and materialization → a booking that triggers cross-level routing → approval → notification dispatch → class rep report submission → lecturer dispute → analytics reflecting the report.
2. Confirm each seam between weeks behaves correctly together, not just each week's own isolated tests.

## Day 2 — Security Pass

1. Re-verify scoped permissions hold under direct API calls across *every* endpoint built since Week 1 — a full pass specifically looking for any endpoint where scope filtering might have been missed.
2. Review JWT expiry/refresh behavior for correctness and for any token-leakage risk in logs or error responses.
3. Check every list/detail endpoint for over-fetching — confirm no endpoint returns fields a given role shouldn't see.
4. Confirm encrypted-at-rest handling for `CalendarConnection` tokens is genuinely in place, not just planned.

## Day 3 — Load & Concurrency Check

1. Re-run and extend Week 3's venue-overlap concurrency test at a fuller scale, simulating realistic concurrent load across booking, discrepancy, and reporting endpoints together, not just the conflict engine in isolation.
2. Identify and address any endpoint that becomes a bottleneck under this combined load — most likely the aggregation queries from Week 7 if they're not adequately indexed.

## Day 4 — Complete API Documentation

1. Finalize the OpenAPI schema (drf-spectacular) across every endpoint built since Week 1 — this is the actual contract the frontend phase will build against, so completeness and accuracy here directly determines how smooth that phase goes.
2. Write a short API usage guide covering authentication flow, common error response shapes, and pagination conventions, so the frontend work doesn't have to reverse-engineer these from the schema alone.

## Day 5 — Environment Finalization & Deployment

1. Finalize staging and production environment configuration.
2. Deploy the backend to its hosting provider, with the database seeded with real school data.
3. Write the operational runbook: how to seed a new term's data, how to run the recurrence materialization command, how to manually trigger the reporting-window sweep or the notification dispatch task if needed outside their normal schedule.

**End of Week 8 checkpoint — and end of the backend phase:** the complete backend API is built, tested end to end, secured, documented as a finished OpenAPI contract, and deployed to a real environment. Every feature described across all prior planning documents is reachable and correct via the API alone. The frontend phase that follows has one job: consume this contract.

---

## Why This Sequencing, Summarized

| Week | Focus | Depends On |
|---|---|---|
| 4 | Discrepancy workflow, audit log | Week 3's routing logic, reused rather than rebuilt |
| 5 | Class rep reporting | Week 2's materialized sessions |
| 6 | Notifications infrastructure | Weeks 4–5's trigger events |
| 7 | Analytics, Calendar sync | Real data from every prior week |
| 8 | Hardening, documentation, deployment | Everything — this is the integration point |

No UI work appears anywhere in this document. Every checkpoint above is verified through the API directly. The frontend phase begins only once Week 8 is complete.
