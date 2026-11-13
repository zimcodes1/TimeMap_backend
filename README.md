# TimeMap Backend API & Automated Timetabling Engines

Production-grade Django REST Framework backend, conflict detection engine, and dual optimization engines (Genetic Algorithm Lecture Scheduler and Combinatorial Examination Timetable Optimizer) for the TimeMap academic administration platform.

---

## Table of Contents

1. [Executive System Overview](#1-executive-system-overview)
2. [Technology Stack & Core Dependencies](#2-technology-stack--core-dependencies)
3. [Architecture & Request Lifecycle](#3-architecture--request-lifecycle)
4. [Monorepo & Directory Structure](#4-monorepo--directory-structure)
5. [Domain Data Models & Database Schema Guide](#5-domain-data-models--database-schema-guide)
   - [5.1 Organizational Hierarchy](#51-organizational-hierarchy)
   - [5.2 Identity, RBAC & Profile Extensions](#52-identity-rbac--profile-extensions)
   - [5.3 Venues & Facilities Registry](#53-venues--facilities-registry)
   - [5.4 Academic Structure, Courses & Access Grants](#54-academic-structure-courses--access-grants)
   - [5.5 Student Population Counts](#55-student-population-counts)
   - [5.6 Sessions, Semesters & Timetable Materialization](#56-sessions-semesters--timetable-materialization)
   - [5.7 Class Representative Reporting & Disputes](#57-class-representative-reporting--disputes)
   - [5.8 Discrepancy Shift & Booking Routing Requests](#58-discrepancy-shift--booking-routing-requests)
   - [5.9 Notifications & Device Push Tokens](#59-notifications--device-push-tokens)
   - [5.10 External Calendar Feeds & Synchronization](#510-external-calendar-feeds--synchronization)
6. [Identity Security, Hierarchical RBAC & Password Reset Gate](#6-identity-security-hierarchical-rbac--password-reset-gate)
7. [Real-Time Conflict Detection Engine & Booking Routing](#7-real-time-conflict-detection-engine--booking-routing)
8. [The Two Schedule Optimizer Engines](#8-dedicated-section-the-two-schedule-optimizer-engines)
   - [8.1 Algorithm 1: Genetic Algorithm Lecture Timetable Scheduler](#81-algorithm-1-genetic-algorithm-lecture-timetable-scheduler)
     - [8.1.1 Decoupled Pure-Python Philosophy](#811-decoupled-pure-python-philosophy)
     - [8.1.2 24-Slot Weekly Academic Grid & Friday Jummat Exclusion](#812-24-slot-weekly-academic-grid--friday-jummat-exclusion)
     - [8.1.3 Occurrence Expansion & Precomputed Conflict Graph](#813-occurrence-expansion--precomputed-conflict-graph)
     - [8.1.4 Venue-Capacity Pre-Feasibility Analysis ($O_k \le T \cdot V_k$)](#814-venue-capacity-pre-feasibility-analysis)
     - [8.1.5 The 6 Independent Constraints & Penalties](#815-the-6-independent-constraints--penalties)
     - [8.1.6 Mathematical Objective Function & Fitness Score](#816-mathematical-objective-function--fitness-score)
     - [8.1.7 Genetic Loop: Selection, Crossover, Mutation & Repair](#817-genetic-loop-selection-crossover-mutation--repair)
     - [8.1.8 School-Level Faculty Decomposition Engine](#818-school-level-faculty-decomposition-engine)
     - [8.1.9 Real-Time Server-Sent Events (SSE) Progress Streaming](#819-real-time-server-sent-events-sse-progress-streaming)
     - [8.1.10 Atomic Publication Service](#8110-atomic-publication-service)
   - [8.2 Algorithm 2: Modular Examination Timetable Optimizer](#82-algorithm-2-modular-examination-timetable-optimizer)
     - [8.2.1 Core Paradigms: Event vs Allocation vs Assignment](#821-core-paradigms-event-vs-allocation-vs-assignment)
     - [8.2.2 Candidate Window Generation & Operating Rules](#822-candidate-window-generation--operating-rules)
     - [8.2.3 The 11 Hard Constraints (H1–H11)](#823-the-11-hard-constraints-h1h11)
     - [8.2.4 The 6 Soft Optimization Objectives (S1–S6)](#824-the-6-soft-optimization-objectives-s1s6)
     - [8.2.5 Physical Allocation Engine: Written Best-Fit, Pairs & Multi-Room](#825-physical-allocation-engine-written-best-fit-pairs--multi-room)
     - [8.2.6 CBT Parallel Centre Throughput & Turn Planning Calculations](#826-cbt-parallel-centre-throughput--turn-planning-calculations)
     - [8.2.7 Small Course Session Joining Engine](#827-small-course-session-joining-engine)
     - [8.2.8 Constructive Search & Difficulty Ordering Heuristics](#828-constructive-search--difficulty-ordering-heuristics)
     - [8.2.9 Deterministic Repair & Workload Distribution](#829-deterministic-repair--workload-distribution)
     - [8.2.10 Approval Lifecycle & Exam Sitting Materialization](#8210-approval-lifecycle--exam-sitting-materialization)
9. [Class Representative Lecture Reporting & 30-Minute Window](#9-class-representative-lecture-reporting--30-minute-window)
10. [Discrepancy Resolution & Real-Time Schedule Shifting](#10-discrepancy-resolution--real-time-schedule-shifting)
11. [Complete REST API Reference](#11-complete-rest-api-reference)
12. [Installation, Environment Setup & Running Guide](#12-installation-environment-setup--running-guide)
13. [Automated Test Suite](#13-automated-test-suite)

---

## 1. Executive System Overview

**TimeMap** is an enterprise-grade academic administration, timetable automation, venue allocation, and attendance auditing platform tailored for higher education institutions.

Key operational capabilities:

- **Hierarchical Governance**: Strict downward permission resolution matching university institutional structures (University $\to$ School $\to$ Faculty $\to$ Department $\to$ Academic Program).
- **Dual Optimization Engines**:
  1. A decoupled **Genetic Algorithm Lecture Scheduler** that evaluates 24 weekly academic slots, respects Friday Jummat prayer hours, solves multi-occurrence courses, balances student cohorts, and performs faculty-level divide-and-conquer decomposition.
  2. A **Combinatorial Examination Optimizer** that dynamically allocates multi-room venues for large written exams, calculates student throughput and turn counts across parallel Computer-Based Test (CBT) centres, groups small sessions, and balances student daily/weekly exam loads.
- **Dynamic Booking & Conflict Detection Engine**: Evaluates room collision, cohort overlap, and lecturer double-booking in real-time, routing clean requests directly to creation while triaging clashes into discrepancy approval workflows.
- **Class Representative Attendance Auditing**: Strict server-enforced 30-minute post-lecture reporting window allowing authorized class representatives to verify lecture holding status, with automatic dispute resolution workflows for lecturers.
- **Real-Time Rescheduling**: Allows lecturers to shift lecture instances with real-time venue availability checks and automated push/in-app notification delivery to affected students, class reps, and faculty members.

---

## 2. Technology Stack & Core Dependencies

| Component              | Technology                      | Version         | Purpose                                                     |
| ---------------------- | ------------------------------- | --------------- | ----------------------------------------------------------- |
| **Language**           | Python                          | `3.13+`         | Runtime environment                                         |
| **Framework**          | Django                          | `6.0+`          | Core web framework, ORM, migrations, and signal dispatcher  |
| **REST Toolkit**       | Django REST Framework (DRF)     | `3.17+`         | Serializers, ViewSets, routers, and request negotiation     |
| **Authentication**     | `djangorestframework-simplejwt` | `5.5+`          | Stateless JWT Bearer token issuance and verification        |
| **API Docs**           | `drf-spectacular`               | `0.28+`         | OpenAPI 3.0 schema generation, Swagger UI, and ReDoc        |
| **Database**           | PostgreSQL / SQLite             | `15+` / `3.40+` | Relational persistence with transactional integrity         |
| **Push Notifications** | `firebase-admin`                | `6.6+`          | Firebase Cloud Messaging (FCM) push token dispatch          |
| **Testing**            | `pytest` + `pytest-django`      | `9.1+`          | Deterministic unit and integration test runner (204 tests)  |
| **Utilities**          | `python-dateutil`, `faker`      | `2.9+`          | Calendar calculations, RRULE parsing, and test data seeding |

---

## 3. Architecture & Request Lifecycle

```
┌────────────────────────────────────────────────────────────────────────┐
│                        HTTP / HTTPS CLIENT REQUEST                     │
│               (Web Admin Portal, Mobile App, Calendar Client)          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     DJANGO REST MIDDLEWARE & AUTH                      │
│  - JWT Bearer Authentication (`simplejwt`)                             │
│  - Forced Password Reset Gate (`IsPasswordResetDone`)                  │
│  - Hierarchical Scope Resolution (`get_user_scope`)                    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     DOMAIN VIEWSETS & API ROUTERS                      │
│  /api/hierarchy/    /api/courses/        /api/venues/                  │
│  /api/scheduling/   /api/reporting/      /api/discrepancies/           │
│  /api/analytics/    /api/notifications/  /api/calendars/               │
└───────────────┬───────────────────────────────┬────────────────────────┘
                │                               │
                ▼                               ▼
┌──────────────────────────────┐ ┌───────────────────────────────────────┐
│   CONFLICT DETECTION ENGINE  │ │         OPTIMIZATION SERVICES         │
│  - 4 Core Interval Checks    │ │ ┌───────────────────────────────────┐ │
│  - Scope Authority Check     │ │ │ Genetic Algorithm Lecture Engine  │ │
│  - Routing Outcomes:         │ │ │ (24 slots, Jummat, 6 constraints) │ │
│    * PROCEED (201 Created)   │ │ └───────────────────────────────────┘ │
│    * ROUTE_APPROVAL (Discrep)│ │ ┌───────────────────────────────────┐ │
│    * HARD_REJECT (400 Bad)   │ │ │ Examination Timetable Optimizer   │ │
│                              │ │ │ (Written pairs, CBT turns, H1-H11)│ │
└───────────────┬──────────────┘ │ └───────────────────────────────────┘ │
                │                └──────────────────┬────────────────────┘
                ▼                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     TRANSACTIONAL PERSISTENCE (ORM)                    │
│      PostgreSQL / SQLite Database with Atomic Commits & Signal Bus     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Monorepo & Directory Structure

```
TimeMap_backend/
├── core/
│   ├── accounts/              # User auth, RBAC, AdminOfficer, LecturerStaff, Student models
│   ├── analytics/             # Administrative metrics, utilization, hold rates, reporting compliance
│   ├── calendars/             # External calendar sync (iCal RFC 5545, Google Calendar exports)
│   ├── courses/               # Course registry, practical flags, exam types, access sharing grants
│   ├── discrepancies/         # Reschedule/cancel requests, approval routing, discrepancy audit log
│   ├── hierarchy/             # Schools, Faculties, Departments, Academic Programs
│   ├── notifications/         # Notification inbox, FCM push token registry, real-time alerts
│   ├── reporting/             # Class representative lecture held/not-held verification & dispute threads
│   ├── scheduling/            # Sessions, semesters, entries, materialized lecture sessions, exam sittings
│   │   ├── optimizer/         # Decoupled Pure-Python Genetic Algorithm Lecture Timetable Engine
│   │   │   ├── models/        # Pure domain dataclasses (Assignment, Slot, Occurrence, Problem)
│   │   │   ├── preprocessing/ # 24 slots, Jummat exclusion, occurrence expansion, DB adapter
│   │   │   ├── constraints/   # 6 independent constraint evaluators (Student, Venue, Lecturer, etc.)
│   │   │   ├── evaluation/    # Lexicographic fitness evaluation & JSON diagnostic report builder
│   │   │   ├── genetic/       # Population generator, crossover, mutation, repair, tournament selection
│   │   │   ├── generator.py   # Top-level pure-Python optimizer facade
│   │   │   ├── decomposed_generator.py # School-level faculty decomposition divide-and-conquer loop
│   │   │   └── publisher.py   # Atomic database publication and session materialization service
│   │   ├── exam_optimizer/    # Decoupled Modular Examination Timetable Optimizer Engine
│   │   │   ├── models/        # Domain dataclasses (ExamEvent, ExamSlot, AllocationPlan)
│   │   │   ├── preprocessing/ # Exam period validation, student conflict graph, candidate windows
│   │   │   ├── allocation/    # Written best-fit, venue pairs, CBT throughput & turn planner, joining
│   │   │   ├── constraints/   # 11 Hard constraint evaluators (H1-H11) & 6 soft penalty functions
│   │   │   ├── solver/        # Difficulty heuristic ordering, constructive placement, local repair
│   │   │   ├── evaluation/    # Workload metrics compiler and exam fitness evaluator
│   │   │   └── generator.py   # Top-level exam optimizer facade
│   │   └── tests/             # Unit and integration test suite (204 tests)
│   ├── student_counts/        # Program-level student population headcounts per level
│   ├── venues/                # Venue registry, lecture halls, laboratories, auditoriums, capacity
│   ├── core/                  # Django project root settings, wsgi, asgi, and root urls
│   └── manage.py              # Django management CLI wrapper
└── docs/                      # Original architecture specifications and audit guides
```

---

## 5. Domain Data Models & Database Schema Guide

Every entity is scoped to support decentralized institutional management.

### 5.1 Organizational Hierarchy

```mermaid
erDiagram
    School ||--o{ Faculty : contains
    Faculty ||--o{ Department : contains
    Department ||--o{ AcademicProgram : offers
```

#### `School` (`hierarchy.School`)

Top-level administrative division (e.g., _School of Computing_, _School of Science_).

- `name` (CharField, unique): Full school name.
- `code` (CharField, max_length=10, unique): Short identifier (e.g., `SC`).
- `created_at` (DateTimeField): Auto-timestamp.

#### `Faculty` (`hierarchy.Faculty`)

Intermediate faculty division belonging to a `School`.

- `school` (ForeignKey $\to$ `School`, `on_delete=CASCADE`): Parent school.
- `name` (CharField): Full faculty name.
- `code` (CharField, max_length=10, unique): Unique identifier (e.g., `FNAS`).

#### `Department` (`hierarchy.Department`)

Academic teaching department hosting lecturers and courses.

- `faculty` (ForeignKey $\to$ `Faculty`, `on_delete=CASCADE`): Parent faculty.
- `name` (CharField): Full department name.
- `code` (CharField, max_length=10, unique): Unique department code (e.g., `CMP`). Code uniqueness is enforced platform-wide to prevent course code ambiguity.
- `max_level` (PositiveIntegerField, default=400): Maximum study level (e.g., 400 for 4-year, 500 for 5-year degrees).

#### `AcademicProgram` (`hierarchy.AcademicProgram`)

Specific degree-awarding program under a department (e.g., _B.Sc. Computer Science_, _B.Sc. Cybersecurity_).

- `department` (ForeignKey $\to$ `Department`, `on_delete=CASCADE`): Owning department.
- `name` (CharField): Full degree title.
- `code` (CharField, max_length=20, unique): Program abbreviation (e.g., `CSC`).
- `max_level` (PositiveIntegerField, default=400): Max level for this degree track.

---

### 5.2 Identity, RBAC & Profile Extensions

Users share a single base `User` record with role-specific 1-to-1 extension profiles.

#### `User` (`accounts.User`)

Custom abstract base user inheriting `AbstractBaseUser` and `PermissionsMixin`.

- `identifier` (CharField, unique): Login username. Matriculation number for students; Staff ID for lecturers and administrators.
- `email` (EmailField, unique): Institutional email address.
- `role` (CharField): One of `admin`, `lecturer`, or `student`.
- `requires_password_reset` (BooleanField, default=True): Security flag enforcing a password change on first login.
- `is_staff`, `is_active`, `is_superuser`: Django standard administrative flags.

#### `AdminOfficer` (`accounts.AdminOfficer`)

Profile for administrative staff managing schedules, hierarchy, and venues.

- `user` (OneToOneField $\to$ `User`, `related_name="admin_profile"`).
- `full_name` (CharField): Full name.
- `staff_id` (CharField, unique): Official staff ID number.
- `level` (CharField): Scope tier — `university` (Superuser), `school`, `faculty`, or `department`.
- `scope_school` (ForeignKey $\to$ `School`, null=True, blank=True).
- `scope_faculty` (ForeignKey $\to$ `Faculty`, null=True, blank=True).
- `scope_department` (ForeignKey $\to$ `Department`, null=True, blank=True).
- `is_dual_role` (BooleanField, default=False): Indicates if this admin officer is concurrently an active lecturer.
- `is_exam_officer` (BooleanField, default=False): Special privilege flag granting exam timetable generation rights within their scope.

#### `LecturerStaff` (`accounts.LecturerStaff`)

Profile for teaching faculty assigned to courses and sessions.

- `user` (OneToOneField $\to$ `User`, `related_name="lecturer_profile"`).
- `full_name` (CharField).
- `staff_id` (CharField, unique).
- `department` (ForeignKey $\to$ `Department`, `on_delete=CASCADE`): Primary academic department.

#### `Student` (`accounts.Student`)

Profile for registered students attending classes and taking exams.

- `user` (OneToOneField $\to$ `User`, `related_name="student_profile"`).
- `full_name` (CharField).
- `matric_number` (CharField, unique).
- `department` (ForeignKey $\to$ `Department`, `on_delete=CASCADE`).
- `program` (ForeignKey $\to$ `AcademicProgram`, `on_delete=CASCADE`).
- `level` (PositiveIntegerField): Current study level (100, 200, 300, 400, 500).
- `is_class_rep` (BooleanField, default=False): Authorizes lecture verification reporting. Strictly capped at **maximum 2 class reps per program + level**.

---

### 5.3 Venues & Facilities Registry

#### `Facility` (`venues.Facility`)

Features present in rooms (e.g., `Projector`, `AC`, `Computers`, `Whiteboard`).

- `name` (CharField, unique), `description` (TextField).

#### `Venue` (`venues.Venue`)

Physical teaching and examination spaces.

- `name` (CharField, max_length=100): Room name (e.g., `CMP Lecture Room 101`).
- `code` (CharField, unique): Short room code.
- `venue_type` (CharField): Room classification — `lecture_hall`, `classroom`, `auditorium`, `multipurpose`, `laboratory`, or `lab`.
- `capacity` (PositiveIntegerField): Seating capacity for standard lecture delivery.
- `exam_capacity` (PositiveIntegerField, null=True, blank=True): Reduced seating capacity enforcing student separation during written/CBT exams (typically 50–70% of standard capacity).
- `owning_level` (CharField): Tier with primary booking sovereignty (`university`, `school`, `faculty`, `department`).
- `owning_department` (ForeignKey $\to$ `Department`, null=True, blank=True).
- `facilities` (ManyToManyField $\to$ `Facility`).
- `is_available` (BooleanField, default=True): Active operational flag.

---

### 5.4 Academic Structure, Courses & Access Grants

#### `Course` (`courses.Course`)

Academic course unit.

- `code` (CharField, unique): Course code (e.g., `CSC301`).
- `title` (CharField): Course title (e.g., `Operating Systems`).
- `level` (PositiveIntegerField): Target level (e.g., 300).
- `owning_department` (ForeignKey $\to$ `Department`, `on_delete=CASCADE`).
- `target_programs` (ManyToManyField $\to$ `AcademicProgram`): Specific programs enrolled in this course.
- `course_type` (CharField): `lecture` (requires classroom/hall) or `practical` (requires laboratory).
- `exam_type` (CharField): `written` (pen-and-paper), `cbt` (computer-based testing), or `lab_practical`.
- `exam_duration_minutes` (PositiveIntegerField, default=120): Duration of the examination.
- `required_occurrences_per_week` (PositiveIntegerField, default=1): Number of distinct weekly lecture sessions.
- `lecturers` (ManyToManyField $\to$ `LecturerStaff`, related_name="courses").

#### `CourseAccessGrant` (`courses.CourseAccessGrant`)

Enables inter-departmental course leasing and service course sharing.

- `course` (ForeignKey $\to$ `Course`, `on_delete=CASCADE`).
- `granted_to_department` (ForeignKey $\to$ `Department`, `on_delete=CASCADE`).
- `grant_scope` (CharField): `general` (all programs in receiving department) or `program` (restricted to `target_program`).
- `target_program` (ForeignKey $\to$ `AcademicProgram`, null=True, blank=True).
- `status` (CharField): `pending`, `approved`, or `rejected`.
- `direction` (CharField): `offered` (owning department pushes to receiver) or `requested` (receiver requests course).

---

### 5.5 Student Population Counts

#### `ProgramStudentCount` (`student_counts.ProgramStudentCount`)

Maintains official student population headcounts per cohort.

- `program` (ForeignKey $\to$ `AcademicProgram`, `on_delete=CASCADE`).
- `level` (PositiveIntegerField): Level (100, 200, 300, etc.).
- `count` (PositiveIntegerField): Student enrollment total.
- **Unique Constraint**: `("program", "level")` — guaranteed 1-to-1 headcount per cohort.

---

### 5.6 Sessions, Semesters & Timetable Materialization

#### `AcademicSession` (`scheduling.AcademicSession`)

Academic calendar year (e.g., `2025/2026`).

- `label` (CharField, unique): Format `YYYY/YYYY`.
- `start_date` (DateField), `end_date` (DateField).
- `is_current` (BooleanField, default=False): Guaranteed singleton active session.

#### `Semester` (`scheduling.Semester`)

Active term within an academic session.

- `session` (ForeignKey $\to$ `AcademicSession`, `on_delete=CASCADE`).
- `name` (CharField): `first` or `second`.
- `start_date` (DateField), `end_date` (DateField): Entire semester duration.
- `lecture_start_date` (DateField), `lecture_end_date` (DateField): Active teaching weeks.
- `exam_start_date` (DateField, null=True), `exam_end_date` (DateField, null=True): Examination period.
- `is_active` (BooleanField, default=False): Singleton active semester across the institution.

#### `TimetableEntry` (`scheduling.TimetableEntry`)

Recurring master schedule pattern (e.g., _CSC301 holds every Monday 08:00–10:00 in Hall A_).

- `entry_type` (CharField): `lecture`, `exam`, or `event`.
- `course` (ForeignKey $\to$ `Course`, null=True, blank=True, `on_delete=SET_NULL`).
- `venue` (ForeignKey $\to$ `Venue`, `on_delete=CASCADE`).
- `start_time` (TimeField), `end_time` (TimeField).
- `recurrence_rule` (CharField): e.g., `weekly:monday`.
- `semester` (ForeignKey $\to$ `Semester`, `on_delete=CASCADE`).
- `status` (CharField): `scheduled`, `cancelled`, or `completed`.

#### `LectureSession` (`scheduling.LectureSession`)

Dated, materialized instance of a `TimetableEntry` for a specific calendar week.

- `timetable_entry` (ForeignKey $\to$ `TimetableEntry`, `on_delete=CASCADE`, related_name="sessions").
- `session_date` (DateField): Specific date (e.g., `2026-10-02`).
- `session_start_time` (TimeField), `session_end_time` (TimeField).
- `venue` (ForeignKey $\to$ `Venue`, `on_delete=CASCADE`).
- `status` (CharField): `scheduled`, `shifted`, `postponed`, `cancelled`, `held`, `not_held`.

#### `ExamSitting` (`scheduling.ExamSitting`)

Physical seating of candidates for an examination event.

- `timetable_entry` (OneToOneField $\to$ `TimetableEntry`, `on_delete=CASCADE`, related_name="exam_sitting").
- `registered_candidates_count` (PositiveIntegerField): Number of students assigned to this room.
- `invigilators` (ManyToManyField $\to$ `LecturerStaff`, related_name="invigilated_exams").

---

### 5.7 Class Representative Reporting & Disputes

#### `LectureReport` (`reporting.LectureReport`)

Audit report submitted by a verified class representative.

- `session` (OneToOneField $\to$ `LectureSession`, `on_delete=CASCADE`, related_name="report").
- `class_rep` (ForeignKey $\to$ `Student`, `on_delete=CASCADE`).
- `held` (BooleanField): Whether the lecture held.
- `reason` (TextField, blank=True): Required explanation if `held=False`.
- `notes` (TextField, blank=True): Optional feedback.
- `submitted_at` (DateTimeField, auto_now_add=True).

#### `ReportDispute` (`reporting.ReportDispute`)

Lecturer response or clarification regarding a class rep report.

- `report` (ForeignKey $\to$ `LectureReport`, `on_delete=CASCADE`, related_name="disputes").
- `lecturer` (ForeignKey $\to$ `LecturerStaff`, `on_delete=CASCADE`).
- `comment` (TextField).
- `created_at` (DateTimeField, auto_now_add=True).

---

### 5.8 Discrepancy Shift & Booking Routing Requests

#### `DiscrepancyRequest` (`discrepancies.DiscrepancyRequest`)

Change request submitted when an action creates a conflict or crosses ownership scope.

- `request_type` (CharField): `shift_lecture`, `cancel_lecture`, `postpone_lecture`, or `create_booking`.
- `session` (ForeignKey $\to$ `LectureSession`, null=True, blank=True).
- `proposed_venue` (ForeignKey $\to$ `Venue`, null=True, blank=True).
- `proposed_date` (DateField, null=True, blank=True).
- `proposed_start_time` (TimeField, null=True, blank=True).
- `proposed_end_time` (TimeField, null=True, blank=True).
- `reason` (TextField).
- `status` (CharField): `pending`, `approved`, or `rejected`.
- `routed_to_admin` (ForeignKey $\to$ `AdminOfficer`, null=True, blank=True).
- `resolved_by` (ForeignKey $\to$ `AdminOfficer`, null=True, blank=True).

---

### 5.9 Notifications & Device Push Tokens

#### `Notification` (`notifications.Notification`)

In-app notification message.

- `user` (ForeignKey $\to$ `User`, `on_delete=CASCADE`, related_name="notifications").
- `title` (CharField), `message` (TextField).
- `notification_type` (CharField): e.g., `SESSION_SHIFTED`, `REPORT_SUBMITTED`, `DISCREPANCY_APPROVAL`.
- `action_url` (CharField, blank=True): Deep link path for mobile or web client.
- `is_read` (BooleanField, default=False).

#### `DeviceToken` (`notifications.DeviceToken`)

Mobile push token for Firebase Cloud Messaging (FCM).

- `user` (ForeignKey $\to$ `User`, `on_delete=CASCADE`, related_name="device_tokens").
- `token` (CharField, unique): FCM device registration token.
- `platform` (CharField): `android` or `ios`.
- `is_active` (BooleanField, default=True).

---

## 6. Identity Security, Hierarchical RBAC & Password Reset Gate

### 6.1 Downward Scope Resolution Algorithm

Administrative sovereignty is resolved downward through foreign keys:

- **`university`**: Unrestricted access to all schools, faculties, departments, venues, and courses.
- **`school`**: Scoped to `scope_school_id`. Access cascades to all faculties and departments where `faculty.school_id == scope_school_id`.
- **`faculty`**: Scoped to `scope_faculty_id`. Access cascades to all departments where `department.faculty_id == scope_faculty_id`.
- **`department`**: Strictly confined to `scope_department_id`. Cannot modify courses, venues, or student records outside their department.

### 6.2 Forced Password Reset Gate (`IsPasswordResetDone`)

Every newly seeded user is assigned `requires_password_reset = True`.

- The custom DRF permission class `IsPasswordResetDone` guards all protected endpoints.
- Any request with a valid JWT will receive `403 Forbidden` (`{"detail": "Password reset required before accessing this resource."}`) until the user completes:
  ```http
  POST /api/auth/password-reset/
  { "old_password": "...", "new_password": "..." }
  ```
- This triggers password hashing and sets `requires_password_reset = False`.

---

## 7. Real-Time Conflict Detection Engine & Booking Routing

The conflict detection engine evaluates proposed booking requests against 4 core invariants:

```mermaid
flowchart TD
    Req[POST /api/scheduling/entries/] --> ScopeCheck{User Owns Venue Scope?}
    ScopeCheck -- No --> RouteAppr[ROUTE_APPROVAL: Create DiscrepancyRequest]
    ScopeCheck -- Yes --> ConflictCheck{Run 4 Conflict Checks}
    ConflictCheck -- Clashes Found --> HardRej[HARD_REJECT: 400 Bad Request with Diagnostics]
    ConflictCheck -- No Clashes --> Proceed[PROCEED: 201 Created & Materialize Sessions]
```

### 7.1 The 4 Core Checks

1. **Interval Overlap Comparison**: Validates $(start_1 < end_2) \land (end_1 > start_2)$. Adjacent slots (e.g., 10:00–12:00 and 12:00–14:00) do not clash.
2. **Venue Overlap Detection**: Evaluates room booking across all dates. For recurring entries (`RRULE`), it checks every single occurrence date throughout the semester.
3. **Student Cohort Clash Detection**: Ensures no two courses sharing a student cohort `(program, level)` are booked concurrently.
4. **Lecturer Double-Booking Detection**: Verifies that assigned instructors are not double-booked across different rooms at the same time.

### 7.2 The 3 Routing Outcomes

- **`PROCEED` (`201 Created`)**: Permitted scope + 0 conflicts. The `TimetableEntry` is saved and weekly `LectureSession` records are immediately materialized.
- **`ROUTE_APPROVAL` (`200 OK`)**: Requester does not own the venue, or the course crosses departments. Generates a `DiscrepancyRequest` routed to the venue's governing admin.
- **`HARD_REJECT` (`400 Bad Request`)**: Unresolvable room, lecturer, or cohort collision. Returns a structured JSON conflict diagnostic report.

---

## 8. The Two Schedule Optimizer Engines

TimeMap features two independent, pure-Python optimization engines located in `core/scheduling/optimizer/` (Lecture Timetabling) and `core/scheduling/exam_optimizer/` (Exam Timetabling).

---

### 8.1 Algorithm 1: Genetic Algorithm Lecture Timetable Scheduler

#### 8.1.1 Decoupled Pure-Python Philosophy

The lecture timetable optimizer contains **zero Django or database imports**. It communicates strictly via lightweight domain dataclasses:

- Input: `SchedulingProblem` (courses, expanded occurrences, valid slots, allowed venues, lecturer assignments, student cohorts).
- Output: `GenerationResult` (assignment list, execution metrics, conflict diagnostics).

#### 8.1.2 24-Slot Weekly Academic Grid & Friday Jummat Exclusion

Teaching operates in fixed 2-hour slots from Monday to Friday:

- Period 0: `08:00 – 10:00`
- Period 1: `10:00 – 12:00`
- Period 2: `12:00 – 14:00`
- Period 3: `14:00 – 16:00`
- Period 4: `16:00 – 18:00`

**Friday Jummat Exclusion**: On Friday, Period 2 (`12:00 – 14:00`, `FR_P2`) is **strictly blacked out** to observe Islamic communal Friday prayers.
$$\text{Total Valid Slots} = (5 \text{ days} \times 5 \text{ periods}) - 1 = \mathbf{24 \text{ slots}}$$

#### 8.1.3 Occurrence Expansion & Precomputed Conflict Graph

- Courses requiring multiple sessions per week (`required_occurrences_per_week = 2`) are expanded into independent genes: `CSC301-1` and `CSC301-2`.
- Cohort conflict graphs are precomputed before GA execution. If Course $A$ and Course $B$ share any `(program, level)` cohort, an edge is added. During the GA loop, cohort clashes are checked in $O(1)$ set lookups.

#### 8.1.4 Venue-Capacity Pre-Feasibility Analysis

Before launching the GA, the system performs a cheap pre-check:
$$\boxed{O_k \le T \cdot V_k}$$
Where $O_k$ is the total required weekly occurrences of type $k$, $T = 24$ is the number of valid slots, and $V_k$ is the number of available venues of type $k$.
$$\text{Capacity Deficit } D_k = O_k - (T \cdot V_k)$$
If $D_k > 0$, the problem is mathematically impossible to solve without collisions. The engine immediately rejects the run with an exact deficit explanation, saving CPU cycles.

#### 8.1.5 The 6 Independent Constraints & Penalties

| Constraint Handler                          | Type | Penalty Weight ($W_i$) | Description                                                                             |
| ------------------------------------------- | ---- | ---------------------- | --------------------------------------------------------------------------------------- |
| **Student Cohort Clash** (`students.py`)    | Hard | $10,000$               | No two courses with overlapping `(program, level)` cohorts in the same slot.            |
| **Lecturer Clash** (`lecturers.py`)         | Hard | $5,000$                | No lecturer scheduled for two courses in the same slot.                                 |
| **Venue Clash** (`venues.py`)               | Hard | $5,000$                | No room booked for two different courses in the same slot.                              |
| **Same-Day Repeats** (`occurrences.py`)     | Hard | $5,000$                | Multi-occurrence courses (e.g. `CSC301-1`, `CSC301-2`) must hold on **different days**. |
| **Daily Lecture Limit** (`daily_limits.py`) | Hard | $2,000$                | A student cohort must not exceed **3 lectures on any single day**.                      |
| **Capacity Deficit** (`capacity.py`)        | Soft | $1$                    | Soft penalty: $\sum \max(0, \text{ExpectedStudents} - \text{VenueCapacity})$.           |

#### 8.1.6 Mathematical Objective Function & Fitness Score

Let $C_{\text{student}}$, $C_{\text{lecturer}}$, $C_{\text{venue}}$, $C_{\text{day\_repeat}}$, and $C_{\text{daily\_limit}}$ represent the hard violation counts, and $P_{\text{capacity}}$ represent the total student capacity deficit.

$$\text{Total Penalty} = 10000 \cdot C_{\text{student}} + 5000 \cdot C_{\text{lecturer}} + 5000 \cdot C_{\text{venue}} + 5000 \cdot C_{\text{day\_repeat}} + 2000 \cdot C_{\text{daily\_limit}} + 1 \cdot P_{\text{capacity}}$$

$$\text{Fitness Score} = \frac{1.0}{1.0 + \text{Total Penalty}}$$

- **Optimal Timetable**: $C_{\text{hard}} = 0 \implies \text{Fitness} \to 1.0$.

#### 8.1.7 Genetic Loop: Selection, Crossover, Mutation & Repair

- **Chromosome Representation**: An array of `Assignment` objects indexed by occurrence gene position:
  $$\text{Chromosome} = [\text{Assignment}_0, \text{Assignment}_1, \dots, \text{Assignment}_{N-1}]$$
- **Heuristic Population Seeding**: 50% of the initial population is generated using heuristic placement (spreading repeat occurrences across days, selecting room sizes that closely match expected student counts). The remaining 50% is randomized for diversity.
- **Tournament Selection**: Candidates compete in groups of $k=3$ with the highest fitness selected for breeding.
- **Uniform Crossover**: Swaps gene assignments between parents with rate $P_{\text{cross}} = 0.85$.
- **Constraint-Aware Mutation**: Mutates conflicted genes with rate $P_{\text{mut}} = 0.08$ to unconflicted slots and rooms.
- **Deterministic Repair Pass**: Scans for same-day duplicates of multi-occurrence courses and shifts duplicate occurrences to alternate weekdays.
- **Termination**: Stops when $C_{\text{hard}} = 0$, or when fitness fails to improve for 40 generations (stagnation patience), or when max generations is reached.

#### 8.1.8 School-Level Faculty Decomposition Engine

For large university problems (e.g. 300+ courses across multiple faculties), solving as a single monolithic GA causes combinatorial explosion. The decomposed engine (`decomposed_generator.py`) solves this via divide-and-conquer:

1. Partitions courses into faculty sub-problems sorted descending by occurrence count.
2. Adaptively tunes population size and generations per faculty.
3. Locks assigned slots and venues from earlier faculties as fixed external obstacles for subsequent faculties.
4. Executes a post-generation repair pass to eliminate any cross-faculty boundary conflicts.

#### 8.1.9 Real-Time Server-Sent Events (SSE) Progress Streaming

The endpoint `GET /api/scheduling/generate/stream/` streams real-time GA generation progress to web clients using standard Server-Sent Events (SSE), emitting generation index, current fitness score, conflict counts, and convergence alerts.

#### 8.1.10 Atomic Publication Service

When an administrator publishes a generated timetable run:

1. Deletes previous scoped `TimetableEntry` records for the semester.
2. Creates recurring master `TimetableEntry` records (`recurrence_rule="weekly:<day>"`).
3. Projects and materializes dated `LectureSession` instances for every week of the teaching calendar.
4. Marks `TimetableGenerationRun.is_published = True` within an atomic database transaction.

---

### 8.2 Algorithm 2: Modular Examination Timetable Optimizer

#### 8.2.1 Core Paradigms: Event vs Allocation vs Assignment

In contrast to regular weekly lectures, university examinations follow a fundamentally different abstraction:
$$\mathbf{\text{Exam Event}} \neq \mathbf{\text{Venue Allocation}} \neq \mathbf{\text{Student Assignment}}$$

- **Exam Event**: The logical examination of a course, defining the calendar date and shared time window.
- **Venue Allocation**: The collection of physical rooms selected to seat the cohort.
- **Student Assignment**: The distribution of students into rooms or sequential CBT turns.

#### 8.2.2 Candidate Window Generation & Operating Rules

- **Date Range**: Continuous calendar period between `exam_start_date` and `exam_end_date`.
- **Operating Days**: Monday through Saturday (Sundays strictly excluded).
- **Daily Operating Window**: `08:00` to `18:00`.
- **Friday Jummat Prayer Blackout**: On Friday, **no examination may cross or overlap with `12:00 – 14:00`**.
- **Discrete Start Intervals**: Candidate windows start at 30-minute intervals (`08:00`, `08:30`, `09:00`, etc.).

#### 8.2.3 The 11 Hard Constraints (H1–H11)

Every valid examination timetable must satisfy all 11 hard constraints:

- **H1 (Period Boundaries)**: $\text{start\_date} \le date(e) \le \text{end\_date}$.
- **H2 (Course Single-Date Rule)**: All offerings of a course across departments must share the same calendar date and common time window.
- **H3 (Student Conflict Absence)**: If two courses share any registered students, their exam windows must not overlap.
- **H4 (Venue Type Compatibility)**:
  - `written`: Classrooms, Lecture Halls, Auditoriums ($\text{venue\_type} \neq \text{laboratory}$).
  - `cbt`: Computer Laboratories and designated CBT centres.
  - `lab_practical`: Science laboratories.
- **H5 (Simultaneous Venue Capacity)**:
  - Written: $\sum \text{Students} \le \text{Capacity}_v$.
  - CBT: Students per turn $\le \text{Capacity}_v$.
- **H6 (Venue Double-Booking Absence)**: No room may host multiple overlapping exams.
- **H7 (Population Conservation)**: $\sum s_v = N_e$ (every student is seated).
- **H8 (Common Examination Window)**: All rooms in a multi-room exam must share identical start and end times.
- **H9 (CBT Session Joining Limit)**: At most **2 courses** may share a joined CBT session.
- **H10 (Operating Calendar & Jummat Blackout)**: Monday–Saturday, 08:00–18:00; Friday 12:00–14:00 completely prohibited.
- **H11 (Maximum Duration)**: Exam duration $d_e \le 360$ minutes (6 hours).

#### 8.2.4 The 6 Soft Optimization Objectives (S1–S6)

- **S1 (Weekly Student Load)**: Penalizes assigning a student $>3$ exams in a calendar week.
- **S2 (Daily Student Load)**: Penalizes assigning a student $>1$ exam on the same day.
- **S3 (Period Compression)**: Prefers schedules that minimize total active exam days without causing cohort workload spikes.
- **S4 (Venue Capacity Fit)**: Minimizes wasted seats in written halls ($C_v - N_e$) and balances 2-room pairs ($|C_{v_1} - C_{v_2}|$).
- **S5 (CBT Throughput Efficiency)**: Minimizes total duration across parallel CBT centres.
- **S6 (Safe Session Joining)**: Consolidates small courses ($\le 60$ written, $\le 100$ CBT) into shared sessions to economize invigilators.

#### 8.2.5 Physical Allocation Engine: Written Best-Fit, Pairs & Multi-Room

For a written cohort of $N$ students:

1. **Single Venue Best-Fit**: If any single room has $C_v \ge N$, select the room minimizing capacity excess:
   $$v^* = \arg\min_{v \in \mathcal{V} \mid C_v \ge N} (C_v - N)$$
2. **Venue Pair Best-Fit**: If no single room accommodates $N$, evaluate all 2-room pairs $(v_1, v_2)$ where $C_{v_1} + C_{v_2} \ge N$, ranking by minimum excess and room balance ($|C_{v_1} - C_{v_2}|$).
3. **Multi-Room Greedy Fallback**: If no pair suffices, sort rooms descending by capacity and allocate until the full population is seated.

#### 8.2.6 CBT Parallel Centre Throughput & Turn Planning Calculations

For a computer-based examination with $N$ students and parallel CBT centres with capacities $C_1, C_2, \dots, C_m$:

- Total simultaneous computer capacity:
  $$C_{\text{total}} = \sum_{i=1}^m C_i$$
- Required turns (batches):
  $$\text{longest\_turns} = \left\lceil \frac{N}{C_{\text{total}}} \right\rceil$$
- Student assignment per centre:
  $$s_i = \min(C_i \times \text{longest\_turns}, \text{remaining})$$
- Actual turns per centre:
  $$turns_i = \left\lceil \frac{s_i}{C_i} \right\rceil$$
- Overall exam event duration:
  $$d_{\text{event}} = \text{longest\_turns} \times d_{\text{student}}$$

#### 8.2.7 Small Course Session Joining Engine

Combines small compatible courses:

- Max 2 courses per joined session.
- Preconditions: identical date, start time, duration, exam type, zero student cohort overlap, and zero venue collision.

#### 8.2.8 Constructive Search & Difficulty Ordering Heuristics

Courses are placed constructively in descending order of difficulty to prevent tight courses from being boxed out:
$$\text{Difficulty}(E) = 1.0 \cdot \text{Population} + 20.0 \cdot \text{ConflictDegree} + 0.5 \cdot \text{Duration} + 50.0 \cdot \text{VenueScarcity}$$
Where $\text{ConflictDegree}$ is the number of neighbors in the student conflict graph, and $\text{VenueScarcity} = \frac{1}{|\text{Eligible Venues}|}$.

#### 8.2.9 Deterministic Repair & Workload Distribution

If candidate placement encounters an edge-case collision, local repair shifts non-conflicting exams to neighboring days to eliminate clashes while minimizing student workload penalties.

#### 8.2.10 Approval Lifecycle & Exam Sitting Materialization

1. **Optimization Run**: Creates an `ExamOptimizerRun` record in `draft` status.
2. **Review & Approval**: Administrators inspect diagnostics and approve the run (`approved_at`, `approved_by`).
3. **Publication**: Atomically materializes `TimetableEntry` records with `entry_type="exam"` and creates corresponding `ExamSitting` instances carrying candidate counts and invigilator rosters.

---

## 9. Class Representative Lecture Reporting & 30-Minute Window

### 9.1 Server-Enforced Reporting Window

Class representatives can only submit lecture audit reports during the official reporting window:
$$\text{Window Start} = \text{session\_date} + \text{session\_start\_time}$$
$$\text{Window Expiry} = \text{session\_date} + \text{session\_end\_time} + \mathbf{30 \text{ minutes}}$$

- If a class rep attempts to submit before the lecture starts or $>30$ minutes after it ends, the backend rejects the request with `400 Bad Request`.

### 9.2 Submission Payload Rules

- `held = true`: The notes field is optional.
- `held = false`: The `reason` field is **strictly required**.
- Upon submission, the parent `LectureSession.status` updates to `held` or `not_held`.

### 9.3 Lecturer Dispute & Resolution Flow

If a lecture is marked as `not_held`, the assigned lecturer receives an automated notification and can submit a `ReportDispute` comment. Administrators review disputes in the web portal to make final attendance determinations.

---

## 10. Discrepancy Resolution & Real-Time Schedule Shifting

Lecturers can shift sessions in real-time through the mobile app or web portal:

1. **Real-Time Verification**: The client checks venue availability for the proposed date and slot via `GET /api/venues/{id}/availability/`.
2. **Single Instance Shift**: Calling `PATCH /api/scheduling/sessions/{id}/` updates the session date, time, and venue, setting `status="shifted"`.
3. **Automated Notification Dispatch**:
   - The initiating lecturer receives a confirmation alert.
   - Assigned co-lecturers receive `SESSION_SHIFTED` alerts.
   - All registered class reps and enrolled students receive high-priority push notifications and in-app inbox items.
4. **Recurring Change Requests**: Recurring schedule shifts generate a `DiscrepancyRequest` routed to the department/faculty administrator for formal approval before updating future sessions.

---

## 11. Complete REST API Reference

### 11.1 Authentication (`/api/auth/`)

| Method | Path                        | Auth   | Description                                                               |
| ------ | --------------------------- | ------ | ------------------------------------------------------------------------- |
| `POST` | `/api/auth/login/`          | Public | Authenticate with identifier/password; returns JWT access/refresh tokens. |
| `POST` | `/api/auth/token/refresh/`  | Public | Exchange refresh token for new access token.                              |
| `POST` | `/api/auth/password-reset/` | JWT    | Forced/voluntary password change. Clears `requires_password_reset`.       |
| `GET`  | `/api/auth/profile/`        | JWT    | Fetch authenticated user identity and role profile.                       |

### 11.2 Organizational Hierarchy (`/api/hierarchy/`)

| Method        | Path                          | Scope      | Description                      |
| ------------- | ----------------------------- | ---------- | -------------------------------- |
| `GET`, `POST` | `/api/hierarchy/schools/`     | University | List / create schools.           |
| `GET`, `POST` | `/api/hierarchy/faculties/`   | School+    | List / create faculties.         |
| `GET`, `POST` | `/api/hierarchy/departments/` | Faculty+   | List / create departments.       |
| `GET`, `POST` | `/api/hierarchy/programs/`    | Dept+      | List / create academic programs. |

### 11.3 Venues & Availability (`/api/venues/`)

| Method        | Path                                    | Scope         | Description                                               |
| ------------- | --------------------------------------- | ------------- | --------------------------------------------------------- |
| `GET`, `POST` | `/api/venues/venues/`                   | Scoped        | List / register venues with capacities and facility tags. |
| `GET`         | `/api/venues/venues/{id}/availability/` | Authenticated | Live availability verification query for date & slot.     |
| `GET`, `POST` | `/api/venues/facilities/`               | Admin         | Manage facility catalog tags.                             |

### 11.4 Courses & Access Sharing (`/api/courses/`)

| Method        | Path                                | Scope  | Description                                            |
| ------------- | ----------------------------------- | ------ | ------------------------------------------------------ |
| `GET`, `POST` | `/api/courses/courses/`             | Scoped | List / create courses, exam types, and durations.      |
| `POST`        | `/api/courses/grants/`              | Dept+  | Request or offer cross-department course access lease. |
| `POST`        | `/api/courses/grants/{id}/approve/` | Admin  | Approve course sharing lease.                          |

### 11.5 Scheduling & Sessions (`/api/scheduling/`)

| Method         | Path                                                | Scope        | Description                                                  |
| -------------- | --------------------------------------------------- | ------------ | ------------------------------------------------------------ |
| `GET`, `POST`  | `/api/scheduling/academic-sessions/`                | School+      | Manage academic years (e.g. 2025/2026).                      |
| `GET`, `POST`  | `/api/scheduling/semesters/`                        | School+      | Manage semesters, lecture dates, and exam periods.           |
| `POST`         | `/api/scheduling/entries/`                          | Scoped       | Create timetable entry (triggers Conflict Detection Engine). |
| `GET`, `PATCH` | `/api/scheduling/sessions/{id}/`                    | Scoped       | Retrieve or shift specific dated lecture session.            |
| `POST`         | `/api/scheduling/generate/`                         | Admin        | Execute Genetic Algorithm lecture timetable scheduler.       |
| `GET`          | `/api/scheduling/generate/stream/`                  | Admin        | SSE real-time streaming progress of active GA run.           |
| `POST`         | `/api/scheduling/generate/runs/{id}/publish/`       | Admin        | Atomically publish timetable run to live schedule.           |
| `POST`         | `/api/scheduling/exam-optimizer/optimize/`          | Exam Officer | Execute Combinatorial Examination Timetable Optimizer.       |
| `POST`         | `/api/scheduling/exam-optimizer/runs/{id}/publish/` | Exam Officer | Atomically publish exam run to live `ExamSitting` records.   |

### 11.6 Reporting, Disputes & Discrepancies

| Method        | Path                                        | Scope     | Description                                         |
| ------------- | ------------------------------------------- | --------- | --------------------------------------------------- |
| `POST`        | `/api/reporting/reports/`                   | Class Rep | Submit lecture held/not-held verification report.   |
| `POST`        | `/api/reporting/disputes/`                  | Lecturer  | Submit dispute/clarification on a class rep report. |
| `GET`, `POST` | `/api/discrepancies/requests/`              | Scoped    | List / submit reschedule discrepancy requests.      |
| `POST`        | `/api/discrepancies/requests/{id}/approve/` | Admin     | Approve discrepancy and materialize changes.        |

### 11.7 Notifications & Device Tokens (`/api/notifications/`)

| Method | Path                                      | Auth | Description                             |
| ------ | ----------------------------------------- | ---- | --------------------------------------- |
| `GET`  | `/api/notifications/inbox/`               | JWT  | Fetch authenticated user notifications. |
| `POST` | `/api/notifications/inbox/mark-all-read/` | JWT  | Mark all in-app notifications as read.  |
| `POST` | `/api/notifications/devices/`             | JWT  | Register mobile FCM push device token.  |

---

## 12. Installation, Environment Setup & Running Guide

### 12.1 Prerequisites

- **Python**: Version `3.13` or higher
- **Virtual Environment Tool**: `venv` or `uv`
- **Database**: PostgreSQL (recommended for production) or SQLite (default for development)

### 12.2 Environment Setup

1. **Clone the repository and enter the backend directory**:

   ```bash
   cd TimeMapper/TimeMap_backend
   ```

2. **Create and activate a Python virtual environment**:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file in `TimeMap_backend/core/` (or set environment variables):

   ```env
   DEBUG=True
   SECRET_KEY=your-secure-django-secret-key-change-in-production
   ALLOWED_HOSTS=localhost,127.0.0.1
   DATABASE_URL=sqlite:///db.sqlite3
   # For PostgreSQL:
   # DATABASE_URL=postgres://user:password@localhost:5432/timemap_db
   CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
   ```

5. **Apply Database Migrations**:

   ```bash
   cd core
   python manage.py migrate
   ```

6. **Seed Initial Demo Data (Optional)**:

   ```bash
   python manage.py seed_data
   ```

7. **Start the Development Server**:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
   The backend API will be available at `http://localhost:8000/api/`.
   - Interactive Swagger documentation: `http://localhost:8000/api/docs/swagger/`
   - ReDoc documentation: `http://localhost:8000/api/docs/redoc/`

### 12.3 Management Commands CLI Reference

- **Generate Lecture Timetable via CLI**:

  ```bash
  python manage.py generate_timetable --semester 1 --scope-type faculty --scope-id 1
  ```

  Add `--publish` to immediately publish the generated timetable to live sessions.

- **Configure Course Exam Settings**:
  ```bash
  python manage.py set_course_exam_settings --semester 1
  ```

---

## 13. Automated Test Suite

The backend includes a comprehensive test suite of **204 tests** built with `pytest` and `pytest-django`.

### 13.1 Running All Tests

```bash
cd TimeMap_backend/core
pytest
```

### 13.2 Running Domain-Specific Tests

- **Scheduling & Optimizer Test Suite**:
  ```bash
  pytest scheduling/tests/
  ```
- **Exam Optimizer Tests**:
  ```bash
  pytest scheduling/tests/test_exam_optimizer_runs.py scheduling/tests/test_exam_optimizer_planning.py
  ```
- **RBAC & Scoped Permission Tests**:
  ```bash
  pytest accounts/tests/test_scoped_rbac.py accounts/tests/test_dual_role_and_exam_officer.py
  ```
- **Reporting & Attendance Verification Tests**:
  ```bash
  pytest reporting/tests/
  ```
