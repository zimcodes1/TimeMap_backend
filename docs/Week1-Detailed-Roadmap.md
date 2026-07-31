# Week 1 — Detailed Implementation Roadmap
## Foundations: Data Model, Auth, Roles

This breaks Week 1 down into a day-by-day sequence. The ordering matters: each day's work is a prerequisite for the next, so this isn't a checklist to do in any order — it's a build order. No code here, just the steps, what each produces, and why it's positioned where it is.

**Week 1 mission:** by the end of this week, a real person with a real matric number or staff ID can log in through both the web and mobile app, land in a session scoped to exactly what their role and level permit, and every query they make is provably restricted to their own scope — not just hidden in the UI, but blocked at the data layer.

---

## Day 1 — Organizational Hierarchy

**Why this comes before anything else:** every model built from here forward — venues, courses, timetable entries, admin officers — hangs off department, faculty, or school. Getting this structure wrong on Day 1 means every later model has to be migrated when it's fixed. This is the one piece of the entire system least safe to leave "roughly right for now."

**This is a single-institution system** — built specifically for this school's own use, carrying its name and branding, not a platform meant to onboard other institutions. `School` sits at the top of the hierarchy with no tenant layer above it.

### Steps

1. **Model the hierarchy as three linked tables** — `School`, `Faculty` (foreign key to School), `Department` (foreign key to Faculty). Not as string fields on other models, and not as a single flat table with a `type` column — a proper relational hierarchy is what lets later queries walk up and down it cleanly (e.g. "all departments under this faculty," "the faculty this department belongs to").
2. **Don't pre-source codes from an external convention document.** The system never needs to parse or decompose a matric number to extract a department code from it — matric number is just an opaque unique identifier. Because of that, there's no structural reason to source department/faculty/school abbreviations from an existing registry document before building; it's simpler and just as correct to let the admin officer in charge enter the abbreviation directly when creating each record.
3. **Build admin-facing creation for the hierarchy**, not a one-off import script — an admin officer adds a school, adds a faculty under it, adds a department under that, entering the abbreviation (`code`) directly, with the system validating uniqueness in real time and surfacing a clear conflict message if the code is already taken.
4. **Enforce `code` uniqueness across the whole system**, not just within the immediate parent. Department codes specifically need this since they double up inside course codes referenced standalone (`CSC301` has no faculty qualifier attached) — two departments sharing a code would make those course codes ambiguous. Applying the same rule to school and faculty codes keeps the convention consistent, even though the risk of collision there is lower.
5. **Set format guardrails on the `code` field as input validation**: canonical uppercase storage with case-insensitive lookup, alphanumeric only, and a sensible maximum length — enforced by the form/API layer. This prevents visually inconsistent entries (`Csc` vs `CSC` vs `csc`) without adding any process overhead beyond the form itself.
6. **Write a handful of sanity queries** confirming the hierarchy is walkable in both directions (given a department, get its faculty and school; given a school, get every department under it). This isn't a formal test suite yet, just a confidence check before building on top of it.

**End of Day 1 checkpoint:** the `School` → `Faculty` → `Department` structure exists in the database, admin-creatable through real CRUD with live code-conflict validation, and correctly query-navigable in both directions.

---

## Day 2 — User Models

**Why this follows the hierarchy directly:** every user type built today references the hierarchy from Day 1 — a student belongs to a department, an admin officer is scoped to a department/faculty/school. Building user models before the hierarchy exists would mean either faking the relationship or leaving it as a TODO, both of which cause rework.

### Steps

1. **Design the base user structure.** Decide whether `Student`, `LecturerStaff`, and `AdminOfficer` extend a shared custom user base or exist as separate models linked to a common auth identity. A shared base is generally the right call here since all three need to authenticate through the same login mechanism — but the *profile* data (matric number vs staff ID vs admin scope) differs enough to warrant separate profile models attached to that shared base.
2. **Model `Student`**: matric number (unique identifier, doubling as username), name, department (FK), level (100/200/etc.), and an `is_class_rep` flag. Keep the class rep distinction as a flag on `Student`, not a separate table — a rep is a student with one extra permission, not a fundamentally different kind of user.
3. **Model `LecturerStaff`**: staff ID, name, department (FK), and a way to associate them with the courses they teach (this association can be stubbed today and filled in properly once `Course` exists next week — don't force it in now).
4. **Model `AdminOfficer`**: staff ID, name, a `level` field (department / faculty / school), and a `scope` reference — a foreign key that points to the specific department, faculty, or school they administer. This `scope` field is what every permission check in later days and weeks will read from, so get its shape right now: it needs to unambiguously answer "which department/faculty/school does this exact admin control," not just "what level are they at."
5. **Design scope to resolve downward, not just match exactly.** A faculty-level admin's authority isn't limited to the faculty record itself — it extends to every department beneath that faculty, and everything attached to those departments (courses, timetable entries, venues owned at the department level). This matters concretely: faculty admin officers are often the ones actually managing exam timetables that span several departments, so a permission check that only matches an admin's scope against an exact record, rather than walking the hierarchy downward from it, would incorrectly block them from work that's genuinely theirs to do. Get this shape right today — the actual enforcement logic is built on Day 5, but the field structure has to support it from the start.
6. **Decide the identifier convention** per user type — matric number for students, staff ID for lecturers and admins — and confirm neither can collide with the other across types, since the auth layer built tomorrow will need a single lookup path.

**End of Day 2 checkpoint:** `Student`, `LecturerStaff`, and `AdminOfficer` models exist, each correctly linked to the Day 1 hierarchy, with no data loaded yet — that comes next.

---

## Day 3 — Credential Store & Data Seeding

**Why seeding is its own day, not folded into Day 2:** modeling a user and populating it with real, usable credentials are different problems. Today is about the actual mechanics of getting a real dataset of students and staff into the system safely and repeatably — this is infrastructure you'll reuse every new academic term, so it's worth building properly now rather than as a one-off script.

### Steps

1. **Define the password strategy.** Since this is a self-hosted store, decide the first-login default: a deterministic but non-obvious value (e.g. derived from a piece of official record data the student already knows) rather than a static default like `"password123"` for every account, which would leave every unclaimed account trivially guessable in the gap between seeding and first login.
2. **Build a CSV/spreadsheet import command** (a management command, not an admin-panel manual entry flow) that takes a source file of student records (matric number, name, department, level) and staff records (staff ID, name, department), and creates the corresponding user rows with hashed default credentials.
3. **Use the framework's built-in password hashing** (PBKDF2 or Argon2 via the standard auth password hasher) — never store or seed a plaintext password anywhere, including in the import file after processing.
4. **Run the import against a real (or realistically representative) sample dataset** — enough to meaningfully test cross-department, cross-faculty scenarios in the coming days, not just two or three rows.
5. **Flag every seeded account** with a `requires_password_reset` boolean, defaulting to true, so the first-login flow (built tomorrow) knows to force a reset rather than letting a default password persist indefinitely.
6. **Document the import process** in a short internal note — what file format it expects, what happens on a duplicate matric number, how to re-run it safely for a new term's intake — since this command will be reused, not just used once.

**End of Day 3 checkpoint:** a realistic dataset of students, lecturers, and admin officers exists in the database with securely hashed credentials, each flagged for a forced first-login reset.

---

## Day 4 — Authentication Endpoints

**Why authentication comes after the data exists, not before:** there's nothing to authenticate against until Day 3's seeded accounts exist. Building login endpoints against an empty user table means testing against fake data that gets thrown away — better to build auth against the same real dataset that production will eventually use.

### Steps

1. **Set up JWT issuing** — a login endpoint accepting an identifier (matric number or staff ID) and password, returning an access token and a refresh token on success.
2. **Set up the refresh endpoint** — exchanging a valid refresh token for a new access token, without requiring the password again. Decide token lifetimes deliberately here: a short-lived access token (short enough to limit damage if leaked) paired with a longer-lived refresh token (long enough that users, especially on mobile, aren't forced to log in constantly).
3. **Build the forced first-login reset flow**: on a successful login where `requires_password_reset` is true, the response should signal the client to route the user to a password-set screen rather than into the main app — and the underlying endpoint should reject any other authenticated action until the reset is complete.
4. **Handle the three identifier types in one login flow** — matric number, staff ID for lecturers, staff ID for admins — through a single endpoint that resolves which user type it's dealing with internally, rather than three separate login endpoints. One entry point is simpler for both frontend clients to integrate against.
5. **Write explicit tests** for: correct credentials succeed, incorrect password fails cleanly, a nonexistent identifier fails without revealing whether the identifier itself exists (avoid leaking which matric numbers are valid through error message differences), and the forced-reset flag correctly blocks normal access until resolved.

**End of Day 4 checkpoint:** a real student, lecturer, or admin officer from the Day 3 dataset can authenticate via the API, receive tokens, refresh them, and is correctly routed through a forced password reset on first login.

---

## Day 5 — Scoped Permissions

**Why this is the most important day of the week, done last and separately:** this is where "who is logged in" becomes "what are they actually allowed to see and touch" — and it needs the hierarchy (Day 1), the user models with their scope fields (Day 2), and working auth (Day 4) all in place first. This also needs to be done carefully and unrushed, which is why it gets a dedicated day rather than being folded into Day 4.

### Steps

1. **Design permission classes per role** — a `Student` can only read their own data and their department's public schedule information; a `LecturerStaff` can read their own assigned sessions; an `AdminOfficer` can read and write within their own `scope` (the exact department/faculty/school they administer) and nothing outside it.
2. **Enforce scoping at the queryset level, not the endpoint level.** This is the single most important technical decision of the day: a permission class that only decides "can this user call this endpoint" still leaves the door open if the underlying database query isn't itself filtered to the user's scope. Every list/detail endpoint touched by an `AdminOfficer` needs its queryset built by filtering on `request.user`'s scope before any results are returned — not filtered afterward, and not left to the frontend to hide.
3. **Explicitly test cross-scope access attempts** — a department-level admin from Department A directly calling an endpoint scoped to Department B (via direct API call, not through the UI) should be rejected or return an empty result, never Department B's real data. This test matters more than almost any other test written this week, because it's the one that proves the architecture's core promise: administrative authority in the system matches administrative authority in reality.
4. **Extend scoping logic downward through the hierarchy correctly** — a school-level admin's scope should correctly include every faculty and department beneath their school; a faculty-level admin's scope should include every department beneath their faculty, and everything attached to those departments — their courses, timetable entries, and department-owned venues. This requires the permission logic to walk the Day 1/Day 2 hierarchy, not just do a flat equality check against a single ID. This is not an edge case: faculty-level admin officers are frequently the ones actually managing exam timetables that span multiple departments under them, so if this resolution is wrong, a faculty admin doing entirely legitimate work gets incorrectly blocked — test this specific scenario explicitly, not just the reverse (blocking access that should be denied).
5. **Confirm student and lecturer read scopes separately** — a student should only ever see their own personal schedule and their department's relevant public data, never another department's internal admin data; a lecturer should only see sessions they're assigned to. These are narrower and simpler than the admin case, but still need explicit checks, since a mistake here is a real information-exposure issue, not just an inconvenience.

**End of Day 5 checkpoint:** every user type's read/write access is enforced at the query level and proven — through direct API testing, not just UI testing — to correctly include everything within their scope and correctly exclude everything outside it, including at the faculty and school levels where scope spans multiple departments.

---

## Days 6–7 — Client Integration & Week Close-Out

**Why this is the last step, not spread across the week:** the web and mobile login screens are thin clients over what was built Days 1–5. Building them earlier would mean building UI against auth and permission logic that was still changing underneath them. Waiting until the backend is stable means the client work is straightforward wiring, not guesswork.

### Steps

1. **Build the web login screen** — identifier + password fields, calling the Day 4 login endpoint, handling the forced-reset redirect, storing tokens appropriately (not in `localStorage` for anything sensitive — consider the framework's recommended secure storage approach), and wiring the token refresh flow into the API client so expired access tokens are transparently renewed.
2. **Build the mobile login screen** — same flow, but tokens stored via secure on-device storage rather than any unencrypted mechanism, since mobile devices are more likely to be lost or shared than a desktop session.
3. **Confirm both clients hit the same endpoints identically** — this is a deliberate architectural check, not just a convenience: if the mobile app and web app need different backend behavior to authenticate, that's a sign the API contract isn't as unified as the architecture intends, and it should be caught now rather than months in.
4. **Run a full walkthrough per role** — log in as a seeded student, a class rep, a lecturer, a department admin, a faculty admin, and a school admin, on both clients, confirming each lands in an appropriately scoped session and the forced-reset flow works correctly for a fresh account.
5. **Write a short internal note on what's deferred to Week 2** — explicitly listing what Week 1 does *not* cover (venue models, timetable models, course models) so nothing gets assumed to exist prematurely when Week 2 starts.

**End of Week 1 checkpoint:** a real person, using real seeded credentials, can log into either the web or mobile app, complete a forced first-login password reset if required, and land in a session that is provably restricted — at the database query level, verified by direct API testing — to exactly their role and scope within the real NSUK organizational hierarchy.

---

## Why This Sequencing, Summarized

| Day | Builds On | Because |
|---|---|---|
| 1 — Hierarchy | Nothing (first) | Every later model references this structure |
| 2 — User models | Day 1 | Users are scoped against the hierarchy that must already exist |
| 3 — Credential seeding | Day 2 | Can't seed accounts into models that don't exist yet |
| 4 — Auth endpoints | Day 3 | Nothing real to authenticate against until accounts exist |
| 5 — Scoped permissions | Days 1, 2, 4 | Needs hierarchy to walk, user scope fields to check, and working auth to test against |
| 6–7 — Client integration | Day 5 | Building UI against unstable backend logic causes rework; wait for it to settle |

Nothing in this week is replaceable by skipping ahead — Week 2's venue and timetable models will attach directly to the hierarchy and permission system built here, and every week after that inherits Day 5's scoping pattern. A shortcut taken this week reappears as a bug report in Week 6.
