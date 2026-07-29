# Timetable, Venue & Discrepancy Management System
## 2-Month Implementation Roadmap & Guide

This document is both a schedule and a build guide. Each week lists what gets built, why it's sequenced where it is, and what "done" looks like for that week. No code is included — this is the technical plan the code will follow.

**Duration:** 8 weeks
**Structure:** 1 pre-roadmap scaffolding phase + 8 weekly phases
**Sequencing principle:** backend-first, isolated-and-tested before wired-to-UI, conflict detection built and proven before anything depends on it.

---

## Pre-Roadmap: Scaffolding & Project Setup

This phase has no calendar week attached — it's the groundwork that has to exist before Week 1 can start. Rushing this to "get to the real work" is what causes rework in week 4.

### Repository structure

Three separate repositories rather than a single monorepo:

- `timetable-backend` — Django / DRF
- `timetable-web` — React / TypeScript
- `timetable-mobile` — React Native / Expo

**Why separate, not monorepo:** the web and mobile clients have almost no shared code (different component primitives, different navigation models), so a monorepo's main benefit — shared packages — doesn't pay for its setup cost here. Three repos also means each can be deployed and versioned independently, which matters since the mobile app will go through app store review cycles the web app doesn't.

### Backend requirements

| Package | Purpose |
|---|---|
| `django`, `djangorestframework` | Core framework and API layer |
| `djangorestframework-simplejwt` | JWT auth, issuing/refreshing tokens for both clients |
| `psycopg2-binary` | PostgreSQL adapter |
| `django-cors-headers` | Allow the web app (and local mobile dev) to call the API cross-origin |
| `celery`, `redis` | Async tasks and scheduled sweeps (reporting windows, notification dispatch) |
| `django-celery-beat` | Persisted periodic task schedule (so sweep intervals are DB-configurable, not hardcoded) |
| `django-filter` | Query filtering on list endpoints (venues by facility, timetable by department, etc.) |
| `drf-spectacular` | Auto-generated OpenAPI schema — both frontend teams (even if it's just you) need a contract to build against |
| `python-decouple` or `django-environ` | Environment variable management, keeps secrets out of source |
| `firebase-admin` | Server-side push notification dispatch to the mobile app via FCM |
| `django-anymail` | Transactional email sending, provider-agnostic |
| `black`, `ruff` | Formatting and linting |
| `pytest`, `pytest-django`, `factory_boy` | Testing — factory_boy matters specifically for generating realistic timetable/venue test fixtures |

### Web requirements

| Package | Purpose |
|---|---|
| `react`, `typescript`, `vite` | Core app and build tooling |
| `@tanstack/react-router` | Type-safe routing — chosen over React Router for full TypeScript inference on route params, important here since routes are permission-scoped (`/department/:deptId/timetable`) and you want compile-time safety on those params |
| `@tanstack/react-query` | Server state management — caching, refetching, and invalidation for API data. This replaces most manual `useEffect`/`useState` data-fetching, which matters a lot on a data-heavy admin dashboard |
| `tailwindcss` | Utility-first styling |
| `lucide-react` | Icon set |
| `axios` | HTTP client, paired with an interceptor for JWT refresh handling |
| `react-hook-form` | Form state management, especially for the multi-field venue/timetable creation forms |
| `zod` | Schema validation, shared shape between form validation and API response typing |
| `zustand` | Lightweight client-side state (current user, active scope/level) — deliberately not Redux, since most state here is server state already handled by React Query |
| `date-fns` | Date/time manipulation for recurrence display and scheduling calculations |
| `recharts` | Charting library for the analytics dashboard |
| `@tanstack/react-table` | Data tables for admin views (timetable lists, discrepancy queues) |

### Mobile requirements

| Package | Purpose |
|---|---|
| `expo`, `react-native` | Core framework — Expo chosen for faster iteration and OTA update capability, consistent with prior React Native/Expo experience |
| `expo-router` | File-based routing, mirrors the web app's route-based mental model |
| `@tanstack/react-query` | Same server-state library as web — same caching/invalidation behavior on both clients, one less thing to reason about differently |
| `nativewind` | Tailwind syntax for React Native styling — keeps styling conventions consistent with the web app |
| `lucide-react-native` | Icon set matching the web app's icon set, for visual consistency across clients |
| `expo-secure-store` | Secure on-device storage for JWT tokens (not AsyncStorage — tokens shouldn't sit in unencrypted storage) |
| `expo-notifications` + `firebase` (via `@react-native-firebase/app`, `@react-native-firebase/messaging`) | Push notification registration and receipt handling on-device |
| `expo-splash-screen` | Splash screen configuration |
| `expo-application` | App version/build metadata, useful for support and forced-update checks later |
| `react-native-svg` | Required peer dependency for several icon and chart libraries |
| `zod` | Same validation schemas, mirrored from the web app where the shape overlaps |

**App icons and splash assets:** generate a full icon set (iOS/Android adaptive icons, splash screen, favicon-equivalent) early, even as placeholders. Expo's `expo-asset` and `app.json`/`app config` icon fields need these paths defined before the first build, and swapping a placeholder later is trivial — discovering a missing icon config at first store submission is not.

### Environment & shared setup

- Three environment tiers from day one: local, staging, production — even if staging isn't deployed until later, the config split should exist so it isn't retrofitted.
- A single `.env.example` per repo documenting every required variable, committed to source (values excluded).
- Git branching: `main` (deployable), `develop` (integration), feature branches off `develop`. Simple, no need for anything heavier at this scale.

**Definition of done for this phase:** all three repos initialized, dependencies installed, a Django app that returns a 200 on a health-check endpoint, a React app that renders a blank routed page, and an Expo app that runs on a physical device or simulator and shows a blank routed screen. Nothing functional yet — just proof the scaffolding holds weight.

---

## Week 1 — Foundations: Data Model, Auth, Roles

**Goal:** the organizational skeleton and login flow exist and are provably permission-scoped, before any scheduling feature is built on top of them.

**Why first:** every other feature in this system checks "who is asking, and what are they allowed to touch." Building scheduling features before this exists means retrofitting permission checks into code that wasn't designed around them — expensive and error-prone. Get this right once.

### Deliverables

- School / Faculty / Department hierarchy modeled as real relational tables, not string labels.
- User models: `Student` (with `is_class_rep` flag), `LecturerStaff`, `AdminOfficer` (with `level` and `scope` fields pointing to the specific department/faculty/school they administer).
- Self-hosted credential store seeded from a sample student/staff dataset (a CSV import command is sufficient at this stage — not a UI yet).
- First-login forced password reset flow.
- JWT issuing and refresh endpoints.
- Role-based permission classes wired into DRF, enforced at the queryset level (not just endpoint-level) — an admin officer's list endpoints filter automatically to their own scope.
- Basic web login screen and basic mobile login screen, both hitting the same auth endpoints.

### Why the queryset-level enforcement matters here specifically

A permission check that only guards "can this user hit this endpoint" still lets a department admin fetch another department's data if the query itself isn't scoped. The filtering has to happen in the database query, not just at the gate. This is worth getting explicit tests around in Week 1, because every subsequent week's endpoints will inherit this pattern — if it's wrong here, it's wrong everywhere.

**Sub-deliverable checklist:**
- [ ] Org hierarchy tables + admin data seeded
- [ ] User models + credential store + CSV seed import
- [ ] JWT auth endpoints (login, refresh, first-login reset)
- [ ] Scoped permission classes with tests proving cross-scope access is blocked
- [ ] Web login screen functional against real auth endpoints
- [ ] Mobile login screen functional against real auth endpoints

---

## Week 2 — Venue Registry & Timetable CRUD (No Conflict Logic Yet)

**Goal:** venues and timetable entries can be created, read, updated, and viewed — deliberately without conflict detection wired in yet.

**Why separate from conflict detection:** conflict detection is the highest-risk, most logic-heavy part of the system. Building it at the same time as basic CRUD means debugging two unfamiliar systems at once. Building plain CRUD first gives you a known-good baseline to test the conflict engine against in Week 3 — you'll know if a bug is in the conflict logic itself, not in the underlying data layer.

### Deliverables

- Venue model: capacity, facilities (a proper `Facility` table, many-to-many — not a free-text field, since analytics later will need to query "venues with a projector") and owning level/entity.
- `Course` model tied to department.
- `TimetableEntry` model covering lectures, exams, and events with a `recurrence_rule` field for weekly-repeating lectures.
- `ExamSitting` extension: registered-candidate count, invigilator assignment.
- Recurrence materialization logic: expanding a recurring `TimetableEntry` into concrete dated `LectureSession` instances for a given term. This is what the class rep will eventually report against — the abstract recurring rule is never itself reportable, only a materialized instance is.
- Basic admin-facing CRUD screens on web for venues and timetable entries (no conflict warnings yet — that's next week).

### Why materialize recurrence now, not later

If you leave lectures as pure recurrence rules and try to bolt on "did this specific Tuesday's lecture hold" reporting later, you end up needing the materialization logic anyway, except now it has to retrofit around a reporting feature that assumed instances already existed. Building the materialization step now, even before it's consumed by anything, means Week 5's reporting feature has a stable foundation to build on.

**Sub-deliverable checklist:**
- [ ] Venue + Facility models, seeded with real venue data where available
- [ ] Course model tied to department
- [ ] TimetableEntry model (lecture/exam/event) with recurrence rule field
- [ ] ExamSitting extension
- [ ] Recurrence materialization command/service producing LectureSession rows
- [ ] Web CRUD screens for venue and timetable entry creation (admin-only, scoped)

---

## Week 3 — Conflict Detection Engine

**Goal:** the core scheduling logic — venue clash detection, student/lecturer double-booking detection, and hierarchical override routing — built and unit-tested in isolation before it's wired into any UI.

**Why isolated first:** this is the single piece of logic the entire system's credibility depends on. A venue double-booking bug undermines the whole point of the system. Testing it against a UI means every bug report starts with "is this a UI problem or a logic problem" — building and testing it as a standalone service removes that ambiguity entirely.

### Deliverables

- Venue overlap check: interval-based comparison against all existing entries for a venue, expanded across materialized instances rather than raw recurrence rules.
- Student exam clash check: no student sitting two exams at the same time, checked against their registered courses.
- Lecturer double-booking check: no lecturer assigned two sessions at the same time.
- Hierarchical override logic: a booking against a venue outside the requester's own level creates a pending approval request routed to the owning level's admin, rather than being silently accepted or rejected.
- Same-level clashes hard-rejected at the point of booking with a clear error, since there's a single owner to arbitrate — no ambiguity, no approval chain needed.
- A comprehensive test suite covering: overlapping times, adjacent-but-not-overlapping times, same-level clashes, cross-level requests, and the recurrence-expansion edge cases (e.g. a one-off exam colliding with only one instance of a recurring lecture).

### Why hierarchical override is a routing decision, not a permission decision

It would be simpler to just reject any cross-level booking attempt outright. But that pushes coordination back into manual channels (emails, phone calls) that the system is meant to replace. Routing it as a pending request keeps the coordination inside the system, where it's logged and auditable, instead of pushing it back out.

**Sub-deliverable checklist:**
- [ ] Venue overlap detection service, tested against materialized instances
- [ ] Student exam clash detection
- [ ] Lecturer double-booking detection
- [ ] Hierarchical override routing (pending request creation for cross-level bookings)
- [ ] Same-level hard-rejection with clear error response
- [ ] Full test suite covering overlap edge cases

---

## Week 4 — Discrepancy Workflow & Audit Log

**Goal:** shifts, postponements, and cancellations become a proper request-and-approval workflow, and every administrative action is recorded.

**Why now:** the discrepancy workflow depends directly on the conflict engine built in Week 3 — a requested shift has to be checked against the same conflict rules as an original booking. Building this before Week 3 would mean building it against logic that doesn't exist yet; building it after means it can lean on already-tested conflict logic.

### Deliverables

- `DiscrepancyRequest` model: original entry, requested change, initiator, reason, status (pending/approved/rejected).
- Approval chain logic reusing the Week 3 hierarchical override routing — a discrepancy affecting a shared venue routes to that venue's owning level.
- State transitions: proposed → approved/rejected → published, with the conflict engine re-run against the *proposed* change before approval is even possible, so an admin never approves something that creates a new clash.
- `AuditLog` model and a generic logging utility hooked into every create/update/delete on venues, timetable entries, and discrepancy requests — actor, action, target, before/after snapshot, timestamp.
- Web screens: discrepancy request submission, admin approval queue, audit log viewer (admin-only).

### Why audit logging is generic, not per-model

Writing bespoke audit logging into each model individually means every future model added to the system needs its own logging code, and it's easy to forget. A single generic logging utility, hooked in once at the model-signal level, means new models get audit coverage automatically. This is worth the small extra setup cost now rather than discovering gaps in the log later, when gaps are hardest to explain.

**Sub-deliverable checklist:**
- [ ] DiscrepancyRequest model + state machine
- [ ] Approval routing reusing Week 3's hierarchical logic
- [ ] Conflict re-check on proposed changes before approval
- [ ] Generic AuditLog model + logging utility wired to all relevant models
- [ ] Web: discrepancy submission form, approval queue, audit log viewer

---

## Week 5 — Class Rep Reporting & Mobile Schedule Views

**Goal:** the mandatory lecture-hold reporting flow, and the mobile app's first real functional screens (schedule viewing).

**Why paired together:** class rep reporting is a mobile-first interaction — reps will realistically do this from their phone after class, not from a desktop. It makes sense to build the mobile schedule-viewing screens at the same time, since reporting needs a session to report against, and the natural place to trigger that is from the session's entry in the schedule view itself.

### Deliverables

- `ClassRepReport` model: session reference, held/not-held boolean, reason text, reporter, timestamp, reporting-window expiry.
- Reporting window logic: opens automatically at a session's `end_time`, closes after a fixed period (configurable, defaulting to 24 hours).
- Celery Beat scheduled sweep: finds sessions whose window has closed with no report and flags them, escalating visibility to the department admin.
- Lecturer response/dispute field on a submitted report — not a separate workflow, just an optional comment attached to the report, visible to admins.
- Mobile: student/rep schedule view (list and calendar-style view of upcoming sessions), reporting action available only to reps and only within the active window.
- Mobile: lecturer schedule view with the ability to respond to a report filed against their session.

### Why the window is enforced server-side, not just hidden client-side

If the reporting window were only enforced by hiding the button in the app after expiry, a rep could still hit the API directly after the window closes. The window check has to live in the endpoint logic itself — the client-side hiding is a UX convenience, not the actual enforcement.

**Sub-deliverable checklist:**
- [ ] ClassRepReport model + server-side window enforcement
- [ ] Celery Beat sweep for unreported/expired sessions
- [ ] Department admin visibility into flagged unreported sessions
- [ ] Lecturer dispute/response field
- [ ] Mobile schedule view (student/rep)
- [ ] Mobile reporting action, window-gated
- [ ] Mobile lecturer schedule view + response capability

---

## Week 6 — Notifications & Read Access Completion

**Goal:** real-time notification delivery across both clients, and the remaining read-only access points for students and lecturers on web.

**Why notifications land here, not earlier:** notifications are only meaningful once there's something worth notifying about — discrepancies (Week 4) and reports (Week 5) are the events that generate them. Building notification infrastructure before those existed would mean testing against fake trigger events.

### Deliverables

- Firebase Cloud Messaging integration: device token registration on mobile app login, server-side dispatch on relevant events (discrepancy approved, venue shifted, reporting window opened).
- In-app notification inbox on web: `Notification` model, read/unread state, populated by the same trigger events as the push notifications.
- Transactional email dispatch (via django-anymail) for durable-record events — approved postponements, for instance — sent asynchronously via Celery so it never blocks the request/response cycle.
- Web: student and lecturer read-only schedule views (mirroring the mobile versions, for users who prefer or need desktop access).

### Why push, in-app, and email are three separate channels rather than one unified system

Each channel serves a different need: push is for immediate attention on mobile, in-app inbox is for a persistent record accessible on web, and email is for a durable, external-to-the-system record the recipient can search later. Collapsing these into one mechanism would mean picking one channel's tradeoffs for all three use cases — better to trigger all relevant channels from the same event and let each do what it's suited for.

**Sub-deliverable checklist:**
- [ ] FCM device registration + server-side push dispatch
- [ ] In-app notification model + web inbox UI
- [ ] Async email dispatch for durable-record events
- [ ] Web student schedule view (read-only)
- [ ] Web lecturer schedule view (read-only, includes report response)

---

## Week 7 — Analytics Dashboard & Calendar Sync

**Goal:** the administrative analytics dashboard, and the optional Google Calendar sync feature — both lower-risk, additive features that depend on data generated by everything built in Weeks 1–6.

**Why last among the functional features:** analytics has nothing to compute until real scheduling, reporting, and discrepancy data exists. Calendar sync is explicitly optional and additive — building it earlier would mean risking core-path time on a feature the system doesn't depend on functioning.

### Deliverables

- Aggregation queries: lecture-hold rate by course/lecturer/department, venue utilization rate, discrepancy frequency by venue.
- Web analytics dashboard: charts (via Recharts) built on top of these aggregation endpoints, scoped to the viewing admin's level.
- Google Calendar OAuth connect flow (web and/or mobile settings screen) — opt-in only, pushing confirmed schedule entries to a connected user's calendar.
- Explicit fallback behavior: if a user hasn't connected Calendar, or the push fails, nothing else in the system is affected — this is worth testing directly, to prove the earlier architectural decision (Calendar sync as non-load-bearing) actually holds in the implementation.

### Why analytics is read-only and adds no new write paths

The aggregation layer queries existing tables — it doesn't need its own data model beyond perhaps a cache table if query performance becomes a concern. Keeping it strictly read-only limits its blast radius: a bug in analytics can show wrong numbers, but it can't corrupt scheduling data, because it never writes to it.

**Sub-deliverable checklist:**
- [ ] Aggregation endpoints (hold rate, venue utilization, discrepancy frequency)
- [ ] Web analytics dashboard with charts, scoped by admin level
- [ ] Google Calendar OAuth connect flow
- [ ] Calendar push on confirmed schedule entries (opt-in users only)
- [ ] Verified fallback: system functions identically for non-connected users

---

## Week 8 — Integration Testing, Hardening, and Deployment Prep

**Goal:** everything built in Weeks 1–7 tested together as a whole system, not just in isolation — and the system made ready for a real deployment.

**Why this can't be skipped or shortened:** each previous week tested its own feature in isolation. This is the first point where the full flow — a venue conflict triggering a routed approval, triggering a notification, appearing on a mobile schedule, generating a class rep report, feeding into analytics — is tested end to end. Isolated tests passing doesn't guarantee the seams between features work.

### Deliverables

- End-to-end test scenarios covering full user journeys: department admin books a venue → conflict routes to faculty → faculty approves → student sees updated schedule on mobile → notification received → class rep reports after the session → analytics reflect the report.
- Load-check on the conflict detection engine specifically, since it's the piece most likely to be hit concurrently (multiple admins booking near-simultaneously).
- Security pass: confirm scoped permissions hold under direct API calls (not just through the UI), confirm JWT expiry/refresh behaves correctly, confirm no sensitive data leaks through over-fetching in list endpoints.
- Environment finalization: staging and production environment variables set, database migration plan for seeding real institutional data (matric numbers, department structures, venue inventory) at launch.
- Deployment: backend (Django) to a hosting provider, web app to a static/edge host, mobile app built and submitted for internal testing distribution (TestFlight / Android internal track) — full public store release can follow after this internal testing period, and is intentionally outside this 2-month window.
- Documentation: a short operational runbook — how to seed a new term's data, how to run the recurrence materialization command, how to manually trigger the reporting-window sweep if needed.

**Why public store release is explicitly out of scope for this window:** app store review timelines are outside your control and shouldn't gate the internal completion milestone. Internal distribution (TestFlight, Android internal testing track) gets the app into real users' hands for feedback immediately, without the roadmap's success depending on Apple/Google's review queue.

**Sub-deliverable checklist:**
- [ ] End-to-end test scenarios written and passing
- [ ] Conflict engine load-check under concurrent booking attempts
- [ ] Security pass on scoped permissions and JWT handling
- [ ] Staging and production environments finalized
- [ ] Backend and web deployed
- [ ] Mobile app on internal testing distribution
- [ ] Operational runbook written

---

## Summary Timeline

| Week | Focus | Key Risk Being Managed |
|---|---|---|
| Pre-roadmap | Scaffolding, tooling, environment setup | Retrofitting config/tooling later mid-build |
| 1 | Org hierarchy, auth, scoped permissions | Permission logic built in after features assumes it away |
| 2 | Venue & timetable CRUD, recurrence materialization | Conflating conflict logic with basic data-layer bugs |
| 3 | Conflict detection engine (isolated) | Core scheduling logic being undertested |
| 4 | Discrepancy workflow, audit log | Building approvals before conflict logic exists to check against |
| 5 | Class rep reporting, mobile schedule views | Reporting feature built without materialized sessions to report against |
| 6 | Notifications, remaining web read views | Notification infra built before trigger events exist |
| 7 | Analytics dashboard, Calendar sync | Non-critical features risking core-path time if built earlier |
| 8 | Integration testing, hardening, deployment | Isolated feature tests passing while integration seams fail |

Each week's output is a functioning increment, not a disconnected piece — by the end of Week 4 there is already a usable (if notification-less, analytics-less) admin scheduling tool; by Week 6 both clients are fully functional; Weeks 7–8 are about completeness and reliability, not core functionality.
