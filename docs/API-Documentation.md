# Timetable, Venue & Discrepancy Management System
## Exhaustive Backend API Documentation (Weeks 1–3)

This document provides a comprehensive, exhaustive technical reference for all API endpoints, data models, authentication mechanisms, scoped permission rules, and the Conflict Detection Engine implemented in the backend.

---

## 1. Global Architecture & Standards

### 1.1 Server & Base URL
* **Development Server**: `http://localhost:8000`
* **API Base Path**: `/api/`
* **Content Type**: `application/json` (All request and response bodies are JSON formatted)

### 1.2 Authentication Scheme
The API uses **JSON Web Token (JWT)** Bearer Authentication (issued via `djangorestframework-simplejwt`).
* **Header Format**: `Authorization: Bearer <access_token>`
* **Access Token Lifetime**: 1 hour
* **Refresh Token Lifetime**: 7 days

### 1.3 First-Login Forced Password Reset
Newly seeded accounts are created with `requires_password_reset = true`.
* **Enforcement Rule**: Any request to a protected endpoint (guarded by `IsPasswordResetDone`) will be rejected with **`403 Forbidden`** until the user calls `/api/auth/password-reset/` to set a new password.

### 1.4 Hierarchical Scope Resolution
Access and querysets are scoped at the database level according to the requesting `AdminOfficer`'s level:
* **Department Admin**: Scoped strictly to their assigned department (`scope_department`).
* **Faculty Admin**: Scoped to their faculty (`scope_faculty`) and **all departments under that faculty** (downward resolution).
* **School Admin**: Scoped to their school (`scope_school`) and **all faculties/departments under that school**.
* **Student / Lecturer**: Scoped to their home department and public schedule information.

---

## 2. Conflict Detection Engine & Routing

The Conflict Detection Engine (`scheduling/conflict_engine.py`) evaluates every proposed timetable entry or exam sitting before it is saved.

### 2.1 Four Core Checks
1. **Interval Overlap Comparison**: Standard interval check (`start1 < end2 AND end1 > start2`). Boundary adjacent slots (e.g., 10:00–11:00 and 11:00–12:00) do **not** clash.
2. **Venue Overlap Detection**: Evaluates proposed room, date, and times against materialized `LectureSession` instances and one-off `TimetableEntry` / `ExamSitting` entries. For recurring entries, it projects and validates **every single occurrence date** across the term.
3. **Student Exam Clash Detection**: Checks if any student registered for a course (via `CourseRegistration`) has another exam sitting at an overlapping time on the same date.
4. **Lecturer Double-Booking Detection**: Checks if assigned teaching staff or exam invigilators have overlapping teaching sessions or invigilation duties on the same date.

### 2.2 Three Routing Outcomes
When a booking attempt is submitted to `POST /api/scheduling/entries/`:

| Outcome | Trigger Condition | HTTP Status | Response Content |
|---|---|---|---|
| **`PROCEED`** | Requester has scope authority over venue **AND** no conflicts exist. | `201 Created` | Created `TimetableEntry` JSON object (auto-materializes sessions if recurring lecture). |
| **`HARD_REJECT`** | Requester has scope authority **BUT** conflicts exist. | `400 Bad Request` | Structured JSON containing `detail` message and `conflicts` array detailing clashing entries, times, and affected users. |
| **`ROUTE_APPROVAL`** | Request touches a venue **outside** the requester's scope (e.g. Dept admin booking a Faculty venue). | `202 Accepted` | Pending status JSON containing `outcome: "ROUTE_APPROVAL"`, `discrepancy_request_id`, and `routed_to_admin_id`. |

---

## 3. Authentication Endpoints (`/api/auth/`)

### 3.1 User Login
Authenticates a student, lecturer, or admin using their unique identifier.

* **URL**: `/api/auth/login/`
* **Method**: `POST`
* **Auth Required**: No (Public)
* **Headers**: `Content-Type: application/json`

#### Request Body
```json
{
  "identifier": "NSUK/CSC/2021/001",
  "password": "Pass#0100"
}
```

#### Success Response (`200 OK`)
```json
{
  "user": {
    "id": 1,
    "identifier": "NSUK/CSC/2021/001",
    "role": "student",
    "requires_password_reset": true,
    "is_active": true,
    "last_login_at": "2026-07-31T05:40:00Z",
    "created_at": "2026-07-31T04:20:00Z"
  },
  "tokens": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  },
  "requires_password_reset": true,
  "profile": {
    "id": 1,
    "matric_number": "NSUK/CSC/2021/001",
    "full_name": "Alice Smith",
    "department": 1,
    "level": 300,
    "is_class_rep": true,
    "email": "alice@example.com"
  }
}
```

---

### 3.2 Forced First-Login Password Reset
Updates the user's password and clears the `requires_password_reset` flag.

* **URL**: `/api/auth/password-reset/`
* **Method**: `POST`
* **Auth Required**: Yes (`Authorization: Bearer <access_token>`)
* **Headers**:
  * `Authorization: Bearer <access_token>`
  * `Content-Type: application/json`

#### Request Body
```json
{
  "new_password": "MyNewSecurePassword123"
}
```

#### Success Response (`200 OK`)
```json
{
  "detail": "Password has been successfully updated. You may now access the application."
}
```

---

### 3.3 JWT Refresh Token
Obtains a new access token using a valid refresh token.

* **URL**: `/api/auth/token/refresh/`
* **Method**: `POST`
* **Auth Required**: No
* **Headers**: `Content-Type: application/json`

#### Request Body
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Success Response (`200 OK`)
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

---

### 3.4 Get Current User Profile
Retrieves user profile and role details.

* **URL**: `/api/auth/profile/`
* **Method**: `GET`
* **Auth Required**: Yes (`Authorization: Bearer <access_token>`)

#### Success Response (`200 OK`)
```json
{
  "user": {
    "id": 1,
    "identifier": "NSUK/CSC/2021/001",
    "role": "student",
    "requires_password_reset": false,
    "is_active": true
  },
  "profile": {
    "id": 1,
    "matric_number": "NSUK/CSC/2021/001",
    "full_name": "Alice Smith",
    "department": 1,
    "level": 300,
    "is_class_rep": true,
    "email": "alice@example.com"
  }
}
```

---

### 3.5 Student / Lecturer / Admin User List & Detail
Scoped profile management endpoints.

* **URLs**:
  * `/api/auth/students/`
  * `/api/auth/lecturers/`
  * `/api/auth/admins/`
* **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`
* **Auth Required**: Yes (`Authorization: Bearer <access_token>`)

---

## 4. Organizational Hierarchy Endpoints (`/api/hierarchy/`)

### 4.1 Schools
* **URL**: `/api/hierarchy/schools/`
* **Methods**: `GET` (All users), `POST`, `PUT`, `PATCH`, `DELETE` (Admin only)
* **Auth Required**: Yes

#### Request Body (`POST / PUT`)
```json
{
  "name": "Nasarawa State University",
  "code": "NSUK"
}
```

---

### 4.2 Faculties
* **URL**: `/api/hierarchy/faculties/`
* **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

#### Request Body (`POST / PUT`)
```json
{
  "school": 1,
  "name": "Faculty of Natural & Applied Sciences",
  "code": "FNS"
}
```

---

### 4.3 Departments
* **URL**: `/api/hierarchy/departments/`
* **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

#### Request Body (`POST / PUT`)
```json
{
  "faculty": 1,
  "name": "Computer Science",
  "code": "CSC"
}
```

---

## 5. Venue Registry Endpoints (`/api/venues/`)

### 5.1 Facilities
* **URL**: `/api/venues/facilities/`
* **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

#### Request Body (`POST`)
```json
{
  "name": "HD Projector"
}
```

---

### 5.2 Venues
* **URL**: `/api/venues/venues/`
* **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

#### Request Body (`POST / PUT`)
```json
{
  "name": "Lecture Theatre 1",
  "venue_type": "lecture_hall", // "lecture_hall", "laboratory", "exam_hall", "multipurpose"
  "capacity": 150,
  "exam_capacity": 80,
  "facilities": [1, 2],
  "owning_level": "department", // "department", "faculty", "school"
  "owning_department": 1
}
```

#### Custom Actions:
* **Deactivate Venue**: `POST /api/venues/venues/{id}/deactivate/`
* **Activate Venue**: `POST /api/venues/venues/{id}/activate/`

---

## 6. Academic Structure & Sharing Endpoints (`/api/courses/`)

### 6.1 Courses
* **URL**: `/api/courses/courses/`
* **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

#### Request Body (`POST / PUT`)
```json
{
  "code": "CSC301",
  "title": "Data Structures & Algorithms",
  "level": 300,
  "owning_level": "department", // "department", "faculty", "school", "general"
  "owning_department": 1,
  "lecturers": [1]
}
```

#### Student Visible Course List:
* **URL**: `GET /api/courses/courses/visible-to-me/`
* **Description**: Returns all courses visible to the authenticated student based on default hierarchy rules plus approved course access grants.

---

### 6.2 Course Access Grants (Sharing Workflow)
Allows sharing courses across departments or faculties.

* **URL**: `/api/courses/grants/`
* **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

#### Request Body (`POST`)
```json
{
  "course": 1,
  "granted_to_level": "department",
  "granted_to_department": 2,
  "direction": "offered" // "offered" or "requested"
}
```

#### Custom Actions (Admin Approval):
* **Approve Grant**: `POST /api/courses/grants/{id}/approve/`
* **Reject Grant**: `POST /api/courses/grants/{id}/reject/`

---

### 6.3 Course Registrations
Registers students to courses for an academic session.

* **URL**: `/api/courses/registrations/`
* **Methods**: `GET`, `POST`, `DELETE`

#### Request Body (`POST`)
```json
{
  "course": 1,
  "academic_session": "2025/2026"
}
```

---

## 7. Scheduling & Conflict Detection Endpoints (`/api/scheduling/`)

### 7.1 Timetable Entries
Creates lectures, exams, or events. Automatically triggers Conflict Detection & Hierarchical Routing.

* **URL**: `/api/scheduling/entries/`
* **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

#### Request Body (`POST / PUT`)
```json
{
  "entry_type": "lecture", // "lecture", "exam", "event"
  "title": "CSC301 Weekly Lecture",
  "course": 1,
  "venue": 1,
  "start_time": "09:00:00",
  "end_time": "11:00:00",
  "recurrence_rule": "weekly:tuesday",
  "recurrence_start_date": "2026-08-01",
  "recurrence_end_date": "2026-08-31",
  "academic_session": "2025/2026"
}
```

#### Response Cases:
1. **`201 Created` (PROCEED)**: Live entry created; recurring lectures automatically materialized into dated `LectureSession` rows.
2. **`400 Bad Request` (HARD_REJECT)**:
```json
{
  "detail": "Booking clashes with 1 existing schedule entry/duty.",
  "conflicts": [
    {
      "type": "venue_clash",
      "venue_id": 1,
      "venue_name": "Lecture Theatre 1",
      "date": "2026-08-18",
      "start_time": "09:00:00",
      "end_time": "11:00:00",
      "conflicting_title": "Existing Lecture",
      "conflicting_session_id": 5
    }
  ]
}
```
3. **`202 Accepted` (ROUTE_APPROVAL)**:
```json
{
  "outcome": "ROUTE_APPROVAL",
  "message": "Booking touches a venue outside your scope and has been routed for approval.",
  "discrepancy_request_id": 12,
  "routed_to_admin_id": 3
}
```

#### Custom Actions:
* **Manual Materialization**: `POST /api/scheduling/entries/{id}/materialize/`

---

### 7.2 Lecture Sessions (Materialized Dated Instances)
Provides read and per-instance update access (for one-off date/time/room shifts).

* **URL**: `/api/scheduling/sessions/`
* **Methods**: `GET`, `PUT`, `PATCH`

#### Response Object
```json
{
  "id": 5,
  "timetable_entry": 1,
  "timetable_entry_title": "CSC301 Weekly Lecture",
  "course_code": "CSC301",
  "session_date": "2026-08-18",
  "session_start_time": "09:00:00",
  "session_end_time": "11:00:00",
  "venue": 1,
  "venue_name": "Lecture Theatre 1",
  "status": "scheduled" // "scheduled", "shifted", "postponed", "cancelled", "held", "not_held"
}
```

---

### 7.3 Exam Sittings
Extends a `TimetableEntry` with invigilator assignments and auto-calculated candidate counts.

* **URL**: `/api/scheduling/exam-sittings/`
* **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

#### Request Body (`POST`)
```json
{
  "timetable_entry": 2,
  "invigilators": [1, 2]
}
```
*(If `registered_candidates_count` is omitted, it is automatically calculated from live student `CourseRegistration` records).*

---

## 8. Discrepancy Workflow & Audit Log Endpoints (`/api/discrepancies/`)

### 8.1 Discrepancy Requests
Submits shifts, postponements, cancellations, or cross-level booking requests. Re-validates conflicts at submission time and executes state machine application upon approval.

* **URL**: `/api/discrepancies/requests/`
* **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

#### Request Body (`POST`) - Instance-Level Shift (Single Date Session)
```json
{
  "lecture_session": 5, // Targets a single dated LectureSession instance
  "request_type": "shift_venue", // "shift_venue", "shift_time", "postpone", "cancel", "create_booking"
  "proposed_venue": 2,
  "reason": "Air conditioner maintenance in LT1 on Sept 14"
}
```

#### Request Body (`POST`) - Pattern-Level Shift (All Future Recurrence Dates)
```json
{
  "timetable_entry": 1, // Targets parent TimetableEntry
  "request_type": "shift_time",
  "proposed_start_time": "11:00:00",
  "proposed_end_time": "13:00:00",
  "reason": "Lecturer timetable collision resolved for future sessions"
}
```

#### Custom Actions:
* **Approve Request**: `POST /api/discrepancies/requests/{id}/approve/`
  * Validates conflict safety right at decision time, transitions status `pending` -> `approved` -> `applied`, and updates live schedule records.
* **Reject Request**: `POST /api/discrepancies/requests/{id}/reject/`
  * Body: `{"reason": "Venue already reserved for faculty event"}`
* **Withdraw Request**: `POST /api/discrepancies/requests/{id}/withdraw/`
  * Usable by the original requester while status is `pending`.

---

### 8.2 Generic Audit Logs
Read-only query endpoint for audit trail records captured across core models (`Venue`, `Course`, `CourseAccessGrant`, `TimetableEntry`, `LectureSession`, `ExamSitting`, `DiscrepancyRequest`).

* **URL**: `/api/discrepancies/audit-logs/`
* **Methods**: `GET`
* **Auth Required**: Yes

#### Response Object
```json
{
  "id": 42,
  "actor": 1,
  "actor_identifier": "DEPT1_ADM",
  "action": "create", // "create", "update", "delete", "approve", "reject"
  "target_model": "Venue",
  "target_id": 3,
  "before_snapshot": null,
  "after_snapshot": {
    "id": 3,
    "name": "Audit Test Hall",
    "capacity": 80,
    "owning_level": "department",
    "owning_department": 1
  },
  "timestamp": "2026-08-01T18:07:00Z"
}
```

---

## 9. Class Representative Reporting Endpoints (`/api/reporting/`)

### 9.1 Class Representative Reports
Submits lecture-hold reports for dated `LectureSession` instances. Strictly enforces server-side reporting window expiration (`now <= window_expires_at`).

* **URL**: `/api/reporting/reports/`
* **Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`

#### Request Body (`POST`) - Class Rep Report Submission
```json
{
  "lecture_session": 5,
  "held": true, // true if lecture was held, false if not held
  "reason": "Lecture held successfully on time in LT1."
}
```

#### Custom Actions:
* **Lecturer Dispute Response**: `POST /api/reporting/reports/{id}/respond/`
  * Body: `{"response_text": "Class rep arrived 20 minutes late; lecture was held from 9:30 AM."}`
  * Restricted to assigned course lecturers.

---

### 9.2 Unreported Session Flags
Tracks lecture sessions whose reporting window expired without a report being filed.

* **URL**: `/api/reporting/flags/`
* **Methods**: `GET`
* **Auth Required**: Yes (Department Admins)

#### Response Object
```json
{
  "id": 1,
  "lecture_session": 8,
  "timetable_entry_title": "CSC301 Weekly Lecture",
  "course_code": "CSC301",
  "session_date": "2026-07-28",
  "flagged_at": "2026-07-28T13:00:00Z",
  "acknowledged_by": 1,
  "acknowledged_by_name": "Admin 1",
  "acknowledged_at": "2026-07-28T14:30:00Z"
}
```

#### Custom Actions:
* **Acknowledge Flag**: `POST /api/reporting/flags/{id}/acknowledge/`
* **Manual Sweep Trigger**: `POST /api/reporting/flags/trigger_sweep/`

---

## 10. Notifications Infrastructure Endpoints (`/api/notifications/`)

### 10.1 In-App Inbox
Manages recipient notifications, read states, and unread counters.

* **URL**: `/api/notifications/inbox/`
* **Methods**: `GET`
* **Auth Required**: Yes

#### Response Object
```json
{
  "id": 15,
  "recipient": 2,
  "notification_type": "discrepancy_approved", // "discrepancy_approved", "discrepancy_rejected", "session_shifted", "session_cancelled", "session_unreported"
  "title": "Discrepancy Request Approved",
  "body": "Your shift_venue request #12 has been approved and applied.",
  "related_model": "DiscrepancyRequest",
  "related_id": 12,
  "read_at": null,
  "is_read": false,
  "created_at": "2026-08-02T12:00:00Z"
}
```

#### Custom Actions:
* **Mark Single Read**: `POST /api/notifications/inbox/{id}/read/`
* **Mark All Read**: `POST /api/notifications/inbox/mark-all-read/`
* **Unread Count**: `GET /api/notifications/inbox/unread-count/`

---

### 10.2 FCM Device Token Registration
Registers and deactivates Firebase Cloud Messaging (FCM) device push tokens for push notification delivery.

* **URL**: `/api/notifications/devices/`
* **Methods**: `GET`, `POST`
* **Auth Required**: Yes

#### Request Body (`POST`) - Register Device Token
```json
{
  "fcm_token": "fcm_device_token_string_here",
  "platform": "android" // "android", "ios", "web"
}
```

#### Custom Actions:
* **Deactivate Token**: `POST /api/notifications/devices/deactivate/`
  * Body: `{"fcm_token": "fcm_device_token_string_here"}`

---

## 11. Administrative Analytics Endpoints (`/api/reporting/analytics/`)

Read-only aggregation endpoints for administrative metrics, scoped strictly to the requesting admin officer's level (Department, Faculty, or School).

### 11.1 Lecture-Hold Rate Analytics
* **URL**: `/api/reporting/analytics/lecture-hold-rate/`
* **Methods**: `GET`
* **Query Parameters**: `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD), `department_id`, `course_id`, `group_by` ("course", "lecturer", "department")

#### Response Object
```json
{
  "summary": {
    "total_reports": 24,
    "held_count": 20,
    "not_held_count": 4,
    "hold_rate_percentage": 83.33
  },
  "breakdown": [
    {
      "course_id": 1,
      "course_code": "CSC301",
      "course_title": "Data Structures",
      "total_reports": 10,
      "held_count": 9,
      "not_held_count": 1,
      "hold_rate_percentage": 90.0
    }
  ]
}
```

---

### 11.2 Venue Utilization Analytics
* **URL**: `/api/reporting/analytics/venue-utilization/`
* **Methods**: `GET`
* **Query Parameters**: `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD), `venue_id`, `group_by` ("venue")

#### Response Object
```json
{
  "summary": {
    "total_venues": 5,
    "total_booked_hours": 120.5
  },
  "breakdown": [
    {
      "venue_id": 1,
      "venue_name": "LT1",
      "total_booked_hours": 32.0,
      "total_sessions": 16
    }
  ]
}
```

---

### 11.3 Discrepancy Frequency Analytics
* **URL**: `/api/reporting/analytics/discrepancy-frequency/`
* **Methods**: `GET`
* **Query Parameters**: `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD), `venue_id`, `request_type` ("shift_venue", "shift_time", "cancel", etc.)

#### Response Object
```json
{
  "summary": {
    "total_discrepancies": 8,
    "by_status": {
      "approved": 5,
      "rejected": 2,
      "pending": 1
    },
    "by_request_type": {
      "shift_venue": 4,
      "cancel": 2,
      "shift_time": 2
    }
  }
}
```

---

## 12. Dedicated Role-Based Analytics Endpoints (`/api/analytics/`)

Delivers role-constrained lecture hold analytics for Class Representatives, Lecturers, and Admins.

### 12.1 Class Representative Analytics
* **URL**: `/api/analytics/class-rep/`
* **Methods**: `GET`
* **Auth Required**: Yes (`is_class_rep = true`)
* **Query Parameters**: `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD)

#### Response Object
```json
{
  "student_info": {
    "full_name": "Rep Alice",
    "department": "Computer Science",
    "level": 300
  },
  "query_range": {
    "start_date": "2026-08-01",
    "end_date": "2026-08-31"
  },
  "summary": {
    "total_sessions": 12,
    "held_count": 10,
    "not_held_count": 2,
    "cancelled_count": 0,
    "hold_rate_percentage": 83.33
  },
  "course_breakdown": [
    {
      "course_id": 1,
      "course_code": "CSC301",
      "course_title": "Data Structures",
      "total_sessions": 6,
      "held_count": 5,
      "not_held_count": 1,
      "cancelled_count": 0,
      "hold_rate_percentage": 83.33
    }
  ]
}
```

---

### 12.2 Lecturer Analytics
* **URL**: `/api/analytics/lecturer/`
* **Methods**: `GET`
* **Auth Required**: Yes (Lecturer)
* **Query Parameters**: `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD), `course_id` (optional; must be assigned to lecturer)

#### Response Object
```json
{
  "lecturer_info": {
    "full_name": "Dr. Smith",
    "staff_id": "LEC1",
    "department": "Computer Science"
  },
  "query_range": {
    "start_date": "2026-08-01",
    "end_date": "2026-08-31",
    "filtered_course": "CSC301"
  },
  "summary": {
    "total_sessions": 15,
    "held_count": 14,
    "not_held_count": 1,
    "cancelled_count": 0,
    "hold_rate_percentage": 93.33
  },
  "course_breakdown": [
    {
      "course_id": 1,
      "course_code": "CSC301",
      "course_title": "Data Structures",
      "total_sessions": 15,
      "held_count": 14,
      "not_held_count": 1,
      "cancelled_count": 0,
      "hold_rate_percentage": 93.33
    }
  ]
}
```

---

### 12.3 Admin Lecturer & Scope Analytics
* **URL**: `/api/analytics/admin/`
* **Methods**: `GET`
* **Auth Required**: Yes (Admin)
* **Query Parameters**: `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD), `lecturer_id` (optional), `course_id` (optional)

#### Response Object
```json
{
  "admin_info": {
    "full_name": "Admin 1",
    "level": "department"
  },
  "query_range": {
    "start_date": "2026-08-01",
    "end_date": "2026-08-31",
    "filtered_lecturer": "Dr. Smith",
    "filtered_course": null
  },
  "summary": {
    "total_sessions": 20,
    "held_count": 18,
    "not_held_count": 2,
    "cancelled_count": 0,
    "hold_rate_percentage": 90.0
  },
  "lecturer_breakdown": [
    {
      "lecturer_id": 1,
      "staff_id": "LEC1",
      "full_name": "Dr. Smith",
      "total_sessions": 20,
      "held_count": 18,
      "not_held_count": 2,
      "cancelled_count": 0,
      "hold_rate_percentage": 90.0
    }
  ]
}
```

---

## 13. Interactive Documentation & Schema

* **Swagger UI**: `http://localhost:8000/api/docs/swagger/`
* **ReDoc UI**: `http://localhost:8000/api/docs/redoc/`
* **OpenAPI 3.0 Schema (JSON)**: `http://localhost:8000/api/schema/`





