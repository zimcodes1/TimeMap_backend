# Timetable, Venue & Discrepancy Management System
## Data Models Guide

This document describes every data model in the system: its purpose, its fields, its relationships, and the reasoning behind non-obvious design choices. Models are grouped by domain, in the order they were introduced across the roadmap — organizational hierarchy first, since everything else attaches to it.

Field types are described conceptually (text, integer, boolean, date/time, reference) rather than framework-specific, since this guide is meant to hold regardless of the exact ORM syntax used when building it.

---

## 1. Organizational Hierarchy

This is a single-institution system, built for this school's own use — there's no multi-tenant layer, and `School` sits at the top of the hierarchy. Nothing else in the system can be correctly scoped without these three models existing first.

Codes (`code` fields below) are not pre-sourced or seeded from an external document — an admin officer creates school/faculty/department/course records through the platform and sets the abbreviation directly, with the system validating uniqueness in real time and surfacing a conflict immediately if one exists. This is a small but deliberate choice: the system doesn't need to parse or decompose matric numbers to extract a department code from them, so there's no structural reason to source codes from an external convention document — letting the officer in charge manage it directly, with the system catching conflicts, is simpler and correct.

### 1.1 `School`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `name` | Text | Unique, required | Full school name |
| `code` | Text | Unique, required | Short identifier used in dropdowns and references |
| `created_at` | DateTime | Auto-set | Record creation timestamp |

### 1.2 `Faculty`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `school` | Reference → School | Required | The school this faculty belongs to |
| `name` | Text | Required | Full faculty name |
| `code` | Text | Unique, required | Short identifier |
| `created_at` | DateTime | Auto-set | Record creation timestamp |

### 1.3 `Department`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `faculty` | Reference → Faculty | Required | The faculty this department belongs to |
| `name` | Text | Required | Full department name |
| `code` | Text | Unique, required | Short identifier |
| `created_at` | DateTime | Auto-set | Record creation timestamp |

**Why `code` is unique platform-wide rather than just within its immediate parent:** department codes do double duty inside course codes (e.g. `CSC301`), which are referenced standalone without a faculty qualifier attached. If two faculties could both have a `CSC` department, `CSC301` would be ambiguous about which one it belongs to. School and faculty codes carry lower risk of this kind of standalone reuse, but for consistency and simplicity, uniqueness is enforced the same way across all three.

---

## 2. Identity & Access

All authenticated users share a common identity layer, with role-specific profile data attached separately. This split exists because login mechanics (identifier, password, tokens) are identical across roles, but the data describing *who* someone is differs meaningfully by role.

### 2.1 `User` (base identity)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `identifier` | Text | Unique, required | Matric number (students) or staff ID (lecturers/admins) — the login username |
| `password_hash` | Text | Required | Securely hashed password, never stored in plain text |
| `role` | Choice | Required | One of: `student`, `lecturer`, `admin` — determines which profile model applies |
| `requires_password_reset` | Boolean | Default: true | Forces a password change on first login for newly seeded accounts |
| `is_active` | Boolean | Default: true | Deactivation flag — used instead of deleting a record when someone leaves the institution |
| `last_login_at` | DateTime | Nullable | Updated on each successful login |
| `created_at` | DateTime | Auto-set | Record creation timestamp |

**Why `is_active` instead of deletion:** a graduated student or a staff member who leaves still has historical records attached to them (past reports, past bookings). Deleting the user would orphan that history; deactivating preserves the audit trail while blocking further login.

### 2.2 `Student` (profile, one-to-one with User)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `user` | Reference → User | Required, one-to-one | Linked base identity |
| `matric_number` | Text | Unique, required | Also mirrored as `User.identifier`, kept here for domain-specific queries |
| `full_name` | Text | Required | |
| `department` | Reference → Department | Required | Student's home department — faculty is not stored separately, since it's always derivable through `department.faculty` |
| `level` | Integer | Required | Academic level (100, 200, 300, etc.) |
| `is_class_rep` | Boolean | Default: false | Grants access to the mandatory reporting flow |
| `email` | Text | Optional | For email notification delivery |

**Why `is_class_rep` is a flag, not a separate model:** a class rep is a student with one additional permission, not a structurally different kind of user. A separate model would duplicate every student field and complicate queries that need to treat all students uniformly (e.g. "everyone in this department at this level").

**Why faculty isn't a separate field on `Student`:** it's fully derivable from `department.faculty`, and storing it redundantly risks the two falling out of sync if a department is ever reassigned to a different faculty. If a genuine secondary affiliation is ever needed (a joint or combined-honours programme spanning two departments), that should be modeled as an explicit `AffiliateDepartment` link rather than a redundant faculty field — flagged here as an open question, not yet built, since it wasn't confirmed as a real case for this system.

### 2.3 `LecturerStaff` (profile, one-to-one with User)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `user` | Reference → User | Required, one-to-one | Linked base identity |
| `staff_id` | Text | Unique, required | |
| `full_name` | Text | Required | |
| `department` | Reference → Department | Required | Home department |
| `email` | Text | Optional | For email notification delivery |

**Note:** the association between a lecturer and the specific courses they teach lives on the `Course` model (Section 4), not here, since a lecturer's teaching load changes term to term and belongs with the course record it applies to.

### 2.4 `AdminOfficer` (profile, one-to-one with User)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `user` | Reference → User | Required, one-to-one | Linked base identity |
| `staff_id` | Text | Unique, required | |
| `full_name` | Text | Required | |
| `level` | Choice | Required | One of: `department`, `faculty`, `school` |
| `scope_department` | Reference → Department | Nullable | Set only if `level = department` |
| `scope_faculty` | Reference → Faculty | Nullable | Set only if `level = faculty` |
| `scope_school` | Reference → School | Nullable | Set only if `level = school` |

**Why three separate nullable scope fields instead of one generic reference:** a single generic foreign key (pointing to "some record in some table") loses referential integrity — the database can no longer enforce that the reference actually points to a valid department/faculty/school. Three explicit, level-matched fields (only one populated at a time, matching `level`) keeps the relationship database-enforced and makes every query explicit about what it's checking, at the small cost of two always-null columns per row.

**Scope always includes everything beneath it in the hierarchy.** A `faculty`-level admin's effective scope is not just the faculty record itself — it extends to every department under that faculty, and everything attached to those departments: their courses, their timetable entries, their exam sittings, and any venue owned at the department level within that faculty. This is deliberate and matters in practice: faculty admin officers are frequently the ones actually managing exam timetables that span multiple departments, so their scope needs to resolve downward through the hierarchy, not just match their own faculty record directly. The same applies one level up — a `school`-level admin's scope extends through every faculty and department beneath their school. The permission-resolution logic (built in Week 1, Day 5) walks the hierarchy downward from an admin's scope field rather than doing a flat equality check, specifically to make this work correctly.

---

## 3. Venue & Facility

### 3.1 `Facility`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `name` | Text | Unique, required | e.g. "Projector", "Air Conditioning", "Exam-style seating", "Whiteboard" |

**Why a real table instead of a text/tag field on Venue:** analytics and search both need to query "venues with X facility" reliably. A free-text field invites inconsistent entries ("projector" vs "Projector" vs "proj."); a proper table with a many-to-many relationship to Venue keeps facility names canonical and queryable.

### 3.2 `Venue`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `name` | Text | Unique, required | e.g. "LT1", "Faculty of Science Auditorium" |
| `venue_type` | Choice | Required | One of: `lecture_hall`, `laboratory`, `exam_hall`, `multipurpose` |
| `capacity` | Integer | Required | Standard seating capacity |
| `exam_capacity` | Integer | Nullable | Reduced capacity under exam-spacing conditions, if different from standard capacity |
| `facilities` | Many-to-many → Facility | Optional | Facilities available in this venue |
| `owning_level` | Choice | Required | One of: `department`, `faculty`, `school` — determines whose approval a cross-level booking needs |
| `owning_department` | Reference → Department | Nullable | Set only if `owning_level = department` |
| `owning_faculty` | Reference → Faculty | Nullable | Set only if `owning_level = faculty` |
| `owning_school` | Reference → School | Nullable | Set only if `owning_level = school` |
| `is_active` | Boolean | Default: true | Set false for venues temporarily or permanently out of use |
| `created_at` | DateTime | Auto-set | |

**Why `owning_level` mirrors the same three-nullable-field pattern as `AdminOfficer.scope`:** this is deliberate consistency — both models answer "who has authority here," and using the identical pattern means the conflict-detection engine can compare an admin's scope against a venue's ownership using the same logic shape in both directions.

**Why `exam_capacity` is separate from `capacity`:** exam seating typically requires spacing between candidates, so the same room holds fewer people under exam conditions than under normal lecture seating. Conflating the two would either overstate exam capacity (a real risk) or understate normal lecture capacity.

---

## 4. Academic Structure

### 4.1 `Course`

Courses are not always department-owned. A course may belong to a single department, be shared across every department in a faculty, span an entire school, or be genuinely general (institution-wide, like a GST course everyone takes). This uses the same ownership pattern already established for `Venue` and `AdminOfficer.scope`, for the same reason: one consistent shape for "who has authority over this," checked the same way everywhere it appears.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `code` | Text | Unique, required | e.g. "CSC301" |
| `title` | Text | Required | Full course title |
| `level` | Integer | Required | Academic level the course is offered at |
| `owning_level` | Choice | Required | One of: `department`, `faculty`, `school`, `general` |
| `owning_department` | Reference → Department | Nullable | Set only if `owning_level = department` |
| `owning_faculty` | Reference → Faculty | Nullable | Set only if `owning_level = faculty` |
| `owning_school` | Reference → School | Nullable | Set only if `owning_level = school` |
| `lecturers` | Many-to-many → LecturerStaff | Optional | Staff assigned to teach this course this term |

**Why `general` has no matching nullable owner field:** a general course (GST-style, visible institution-wide) doesn't belong to any single branch of the hierarchy — it simply has no department/faculty/school populated, and the resolution logic treats an `owning_level = general` course as visible to every student regardless of scope.

**Default visibility, by ownership:** a `department`-owned course is visible only to students in that department; a `faculty`-owned course is visible to every department under that faculty; a `school`-owned course is visible to every department under that school; a `general` course is visible to every student regardless of department, faculty, or school. This default is what a student sees before any explicit sharing is applied — see `CourseAccessGrant` below for the cases that fall outside this default.

### 4.2 `CourseAccessGrant`

Handles every visibility case that doesn't fit the default ownership rule above — most importantly, a course shared with one specific department or faculty that isn't beneath its owner in the hierarchy at all (e.g. a Statistics course owned by the Mathematics department, explicitly shared with Computer Science and Economics, two departments under entirely different faculties).

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `course` | Reference → Course | Required | The course being shared |
| `granted_to_level` | Choice | Required | One of: `department`, `faculty`, `school` |
| `granted_to_department` | Reference → Department | Nullable | Set only if `granted_to_level = department` |
| `granted_to_faculty` | Reference → Faculty | Nullable | Set only if `granted_to_level = faculty` |
| `granted_to_school` | Reference → School | Nullable | Set only if `granted_to_level = school` |
| `direction` | Choice | Required | One of: `offered` (the owning admin proactively shared it outward) or `requested` (a non-owning admin asked for access) |
| `status` | Choice | Default: `pending` | One of: `pending`, `approved`, `rejected` |
| `initiated_by` | Reference → AdminOfficer | Required | Who started the grant, regardless of direction |
| `decided_by` | Reference → AdminOfficer | Nullable | Who approved or rejected it — always an admin with authority over the *owning* side of the course, regardless of which direction initiated it |
| `decided_at` | DateTime | Nullable | |
| `created_at` | DateTime | Auto-set | |

**Why `direction` is tracked separately from `status`:** you described two real workflows — a faculty admin who owns a course proactively extending access to specific departments, and a department admin who doesn't own a course requesting access to it. Both end up as the same kind of record with the same approval outcome, but they start from opposite ends, and knowing which one happened matters for the audit trail (did the owner offer it, or did someone ask). Approval authority sits with whoever owns the course either way — this reuses the same routing concept as the `DiscrepancyRequest` approval workflow (Section 7), so admins aren't learning a second approval pattern for a different kind of object.

**How a student's visible course list is resolved:** a course appears for a student if any of the following is true — its `owning_level` covers their department or faculty by the default rule above, or `owning_level = general`, or there exists an `approved` `CourseAccessGrant` covering their department or faculty. This is a single resolution check applied wherever a student's course list is built, rather than logic duplicated across multiple screens.

### 4.3 `CourseRegistration`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `student` | Reference → Student | Required | |
| `course` | Reference → Course | Required | |
| `academic_session` | Text | Required | e.g. "2025/2026" — distinguishes registrations across terms/years |

**Why this model exists at all:** the exam clash-detection logic (Section 5) needs to know which students are registered for which courses, in order to check "does this student have two exams at the same time." Without a registration record, there's no way to know which students an exam sitting actually affects.

---

## 5. Scheduling

This is the core of the system. Lectures, exams, and events share a structure but diverge in specific ways, handled through model extension rather than one flat table trying to serve every case.

### 5.1 `TimetableEntry`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `entry_type` | Choice | Required | One of: `lecture`, `exam`, `event` |
| `title` | Text | Required | Display name — course title for lectures/exams, event name for events |
| `course` | Reference → Course | Nullable | Set for lectures and exams; null for general events |
| `venue` | Reference → Venue | Required | |
| `start_time` | Time | Required | Start of the time slot |
| `end_time` | Time | Required | End of the time slot |
| `recurrence_rule` | Text | Nullable | Encodes weekly repetition (e.g. "every Tuesday") for lectures; null for one-off entries like most exams and events |
| `recurrence_start_date` | Date | Nullable | First date the recurrence applies from |
| `recurrence_end_date` | Date | Nullable | Last date the recurrence applies until (e.g. end of term) |
| `status` | Choice | Default: `scheduled` | One of: `scheduled`, `shifted`, `postponed`, `cancelled` |
| `created_by` | Reference → AdminOfficer | Required | Who originally created this entry |
| `academic_session` | Text | Required | e.g. "2025/2026", for term-based filtering and archiving |
| `created_at` | DateTime | Auto-set | |

**Why `recurrence_rule` is a single text field rather than a set of structured fields:** recurrence patterns (weekly on a given day, biweekly, etc.) are naturally expressed as a compact rule string. Keeping it as one field avoids overengineering the model for recurrence patterns the system doesn't need yet (this system only really needs "weekly, for N weeks," not arbitrary complex recurrence), while leaving room to parse more complex rules later without a schema change.

### 5.2 `LectureSession`

A materialized, dated instance of a recurring `TimetableEntry`. This is the model class reps actually report against — never the abstract recurring entry itself.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `timetable_entry` | Reference → TimetableEntry | Required | The recurring entry this instance was generated from |
| `session_date` | Date | Required | The specific calendar date this instance falls on |
| `session_start_time` | Time | Required | Copied from the parent entry at materialization time, but stored independently — see note below |
| `session_end_time` | Time | Required | Same as above |
| `venue` | Reference → Venue | Required | Copied from parent at materialization time, but can diverge if this specific instance is shifted |
| `status` | Choice | Default: `scheduled` | One of: `scheduled`, `shifted`, `postponed`, `cancelled`, `held`, `not_held` |

**Why time and venue are copied onto the instance rather than always read from the parent:** if a single Tuesday's lecture is shifted to a different room (a one-off change, not a change to the whole recurring pattern), that change needs to live on the specific instance without altering every other week's instance. Copying the values at materialization time, then allowing per-instance overrides, is what makes a one-off shift possible without disturbing the recurring rule.

### 5.3 `ExamSitting` (extension of `TimetableEntry`)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `timetable_entry` | Reference → TimetableEntry | Required, one-to-one | The base entry this extends |
| `registered_candidates_count` | Integer | Required | Number of students expected to sit this exam, drawn from `CourseRegistration` |
| `invigilators` | Many-to-many → LecturerStaff | Optional | Staff assigned to invigilate |

**Why this is a one-to-one extension of `TimetableEntry` rather than a fully separate model:** exams share every field `TimetableEntry` already has (venue, time, status) and only add exam-specific data on top. Extending rather than duplicating avoids maintaining two parallel definitions of the same underlying "a thing happens at a venue at a time" concept.

---

## 6. Class Representative Reporting

### 6.1 `ClassRepReport`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `lecture_session` | Reference → LectureSession | Required, one-to-one | The specific session being reported on |
| `reported_by` | Reference → Student | Required | Must have `is_class_rep = true` at submission time |
| `held` | Boolean | Required | Whether the lecture actually took place |
| `reason` | Text | Required | Explanation, required regardless of `held` value — reasons matter for a lecture that held late or under unusual circumstances too |
| `reported_at` | DateTime | Auto-set | |
| `window_expires_at` | DateTime | Required | Set at session-end time plus the configured reporting window duration |
| `lecturer_response` | Text | Nullable | Optional dispute/comment from the lecturer whose session was reported on |
| `lecturer_responded_at` | DateTime | Nullable | |

### 6.2 `UnreportedSessionFlag`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `lecture_session` | Reference → LectureSession | Required, one-to-one | The session whose window closed with no report filed |
| `flagged_at` | DateTime | Auto-set | Set by the scheduled sweep when a window expires unreported |
| `acknowledged_by` | Reference → AdminOfficer | Nullable | Set once a department admin has reviewed the flag |
| `acknowledged_at` | DateTime | Nullable | |

**Why this is its own model rather than a status value on `LectureSession`:** an unreported flag needs its own lifecycle — when it was raised, whether an admin has actually looked at it — that doesn't fit cleanly as a single status enum value. Keeping it separate also means the flag can carry its own audit trail without cluttering the session model with fields that only apply to the unreported case.

---

## 7. Discrepancy & Approval Workflow

### 7.1 `DiscrepancyRequest`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `timetable_entry` | Reference → TimetableEntry | Required | The entry being changed (for a one-off lecture instance change, this references `LectureSession` instead — see note) |
| `request_type` | Choice | Required | One of: `shift_venue`, `shift_time`, `postpone`, `cancel` |
| `proposed_venue` | Reference → Venue | Nullable | Set if `request_type = shift_venue` |
| `proposed_start_time` | Time | Nullable | Set if `request_type = shift_time` or `postpone` |
| `proposed_date` | Date | Nullable | Set if postponing to a specific new date |
| `reason` | Text | Required | |
| `initiated_by` | Reference → User | Required | Could be a lecturer, department admin, faculty admin, or school admin |
| `status` | Choice | Default: `pending` | One of: `pending`, `approved`, `rejected` |
| `routed_to` | Reference → AdminOfficer | Nullable | Set if this request required cross-level approval (per the venue's owning level) |
| `decided_by` | Reference → AdminOfficer | Nullable | Who approved or rejected it |
| `decided_at` | DateTime | Nullable | |
| `created_at` | DateTime | Auto-set | |

**Why `routed_to` is nullable:** a same-level request (a department admin changing something they already fully own) doesn't need cross-level routing at all — it can be approved by the same admin who submitted it, or auto-applied. `routed_to` is only populated when the conflict engine determines the affected venue is owned by a different level.

### 7.2 `AuditLog`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `actor` | Reference → User | Required | Who performed the action |
| `action` | Choice | Required | One of: `create`, `update`, `delete`, `approve`, `reject` |
| `target_model` | Text | Required | Name of the model affected (e.g. "TimetableEntry") |
| `target_id` | Integer | Required | Primary key of the affected record |
| `before_snapshot` | Text (JSON) | Nullable | Serialized state of the record before the change |
| `after_snapshot` | Text (JSON) | Nullable | Serialized state of the record after the change |
| `timestamp` | DateTime | Auto-set | |

**Why `target_model` and `target_id` instead of a direct reference:** the audit log needs to point at records across many different models (venues, timetable entries, discrepancy requests, and anything added later). A direct foreign key would require a separate audit log table per model; a generic model/ID pair, paired with a generic logging hook, keeps this as one table covering the whole system, including models added after this guide is written.

---

## 8. Notifications & Device Registration

### 8.1 `Notification`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `recipient` | Reference → User | Required | |
| `notification_type` | Choice | Required | One of: `discrepancy_approved`, `discrepancy_rejected`, `session_shifted`, `session_cancelled`, `reporting_window_open`, `session_unreported` |
| `title` | Text | Required | Short display title |
| `body` | Text | Required | Full message content |
| `related_model` | Text | Nullable | Same generic pattern as AuditLog, points to the record this notification concerns |
| `related_id` | Integer | Nullable | |
| `read_at` | DateTime | Nullable | Null until the recipient views it in the in-app inbox |
| `created_at` | DateTime | Auto-set | |

### 8.2 `DeviceToken`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `user` | Reference → User | Required | |
| `fcm_token` | Text | Unique, required | Firebase Cloud Messaging device token |
| `platform` | Choice | Required | One of: `ios`, `android` |
| `is_active` | Boolean | Default: true | Set false when a token is found invalid on send (app uninstalled, token rotated) |
| `registered_at` | DateTime | Auto-set | |

**Why device tokens are their own model, not a field on `User`:** a single user may log in on more than one device (a new phone, a reinstall), and a stale token from an old device shouldn't silently overwrite the current one. A separate table lets multiple tokens exist per user, each independently marked inactive when it stops working, without losing track of the others.

---

## 9. Optional Calendar Sync

### 9.1 `CalendarConnection`

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer (PK) | Auto | Primary key |
| `user` | Reference → User | Required, one-to-one | |
| `provider` | Choice | Default: `google` | Reserved for future providers beyond Google Calendar |
| `access_token` | Text | Required | OAuth access token, encrypted at rest |
| `refresh_token` | Text | Required | OAuth refresh token, encrypted at rest |
| `token_expires_at` | DateTime | Required | |
| `connected_at` | DateTime | Auto-set | |
| `is_active` | Boolean | Default: true | Set false if the user disconnects or a token becomes permanently invalid |

**Why this model is fully optional and isolated:** per the system's architecture, nothing else depends on `CalendarConnection` existing. A user with no row in this table simply never receives calendar pushes — every other feature (notifications, reporting, scheduling) functions identically with or without it. Keeping this isolated is what makes the "additive, not load-bearing" design decision actually true in the data layer, not just in principle.

---

## Model Relationship Overview

```
School
  └── Faculty
        └── Department
              ├── Student (faculty derived via department.faculty)
              ├── LecturerStaff
              └── AdminOfficer (scope_department; scope_faculty and
                    scope_school set at their respective levels instead,
                    and each resolves downward through the hierarchy)

Course (owning_level: department / faculty / school / general)
  ├── CourseAccessGrant (explicit sharing outside the default ownership rule)
  ├── CourseRegistration → Student
  └── TimetableEntry
        ├── LectureSession (materialized dated instances)
        ├── ExamSitting (extension)
        └── DiscrepancyRequest

Venue (owning_level: department / faculty / school, same pattern as Course)

User (base identity)
  ├── Student
  ├── LecturerStaff
  ├── AdminOfficer
  ├── Notification
  ├── DeviceToken
  └── CalendarConnection

LectureSession
  ├── ClassRepReport
  └── UnreportedSessionFlag

AuditLog → any model, via generic (target_model, target_id) reference
```

---

## Design Principles Applied Throughout

1. **Ownership and scope always follow the same three-nullable-field pattern** (`AdminOfficer.scope_*`, `Venue.owning_*`, `Course.owning_*`, `CourseAccessGrant.granted_to_*`) so the conflict-detection and permission logic can compare "who has authority" using one consistent shape everywhere it's checked — and admin scope always resolves downward through the hierarchy (a faculty admin's authority includes every department beneath their faculty), not as a flat equality check against a single record.
2. **Recurring structure and dated instance are always separate** (`TimetableEntry` vs `LectureSession`) so a one-off change to a single date never disturbs the recurring pattern, and reporting always attaches to something concrete and dated.
3. **Generic references are used only where genuinely generic** (`AuditLog`, `Notification.related_model`) — everywhere else, explicit foreign keys are preferred to keep referential integrity enforced by the database rather than by application code.
4. **Deactivation over deletion** for any model with historical significance (`User.is_active`, `Venue.is_active`, `DeviceToken.is_active`) — preserving history is treated as more important than tidiness.
5. **Additive features are isolated** (`CalendarConnection`) so their absence never breaks a feature that doesn't need them.
