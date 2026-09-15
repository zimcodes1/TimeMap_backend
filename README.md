# TimeMap Backend API & Automated Timetable Engine

Backend services, REST APIs, and automated scheduling engine for the TimeMap academic timetable, venue allocation, and discrepancy management platform.

---

## 1. Core Architecture & Tech Stack

- **Framework**: Django 6.0 + Django REST Framework (DRF)
- **Authentication**: JWT Bearer Tokens (`djangorestframework-simplejwt`) with forced password reset guard
- **API Documentation**: OpenAPI 3.0 via `drf-spectacular` (Swagger UI at `/api/docs/swagger/`, ReDoc at `/api/docs/redoc/`)
- **Optimization Engine**: Decoupled pure-Python Genetic Algorithm timetable scheduler (`core/scheduling/optimizer/`)
- **Database**: SQLite (Development) / PostgreSQL (Production)
- **Testing**: `pytest` + `pytest-django`

---

## 2. Directory Layout

```
TimeMap_backend/
├── core/
│   ├── accounts/          # User authentication, RBAC, AdminOfficer, LecturerStaff, Student models
│   ├── analytics/         # Utilization, hold rates, reporting, and discrepancy metrics
│   ├── calendars/         # External calendar sync (iCal, Google Calendar exports)
│   ├── courses/           # Course catalog, course types, access grants, credit units
│   ├── discrepancies/     # Post-generation discrepancy shift, cancel, and postpone requests
│   ├── hierarchy/         # Schools, Faculties, Departments, Academic Programs
│   ├── notifications/     # In-app notifications and push token registrations
│   ├── reporting/         # Class representative lecture held/not-held verification reports
│   ├── scheduling/        # Academic sessions, semesters, timetable entries, lecture sessions
│   │   ├── optimizer/     # Decoupled Pure-Python Genetic Algorithm Timetable Engine
│   │   │   ├── models/        # Pure domain dataclasses (Slot, Assignment, Problem, Occurrence)
│   │   │   ├── preprocessing/ # 24 slots, Jummat exclusion, occurrence expansion, DB adapter
│   │   │   ├── constraints/   # 6 independent hard and soft constraint evaluators
│   │   │   ├── evaluation/    # Lexicographic fitness evaluation and conflict reporting
│   │   │   ├── genetic/       # Population, crossover, mutation, repair, selection, loop
│   │   │   ├── generator.py   # Top-level API facade
│   │   │   └── publisher.py   # Atomic publication service to live schedule
│   │   └── tests/         # Unit and integration test suite
│   ├── student_counts/    # Program-level student population headcounts
│   └── venues/            # Lecture halls, laboratories, auditoriums, multipurpose spaces
└── docs/                  # Technical documentation & architectural roadmaps
    ├── API-Documentation.md                                # Complete REST API reference
    ├── Timetable-Optimizer-Architecture-and-Integration.md # GA Scheduler architectural guide
    ├── Data-Models-Guide.md                                # Entity relationship and model guide
    └── Implementation-Roadmap.md                           # Development implementation phases
```

---

## 3. Documentation Reference

- [**Exhaustive API Documentation**](docs/API-Documentation.md): Comprehensive reference covering all endpoints across auth, hierarchy, courses, scheduling, discrepancies, reporting, and analytics.
- [**Timetable Optimizer Architecture & Integration Guide**](docs/Timetable-Optimizer-Architecture-and-Integration.md): In-depth guide detailing the decoupled pure-Python optimizer, the 24 academic slot model, Friday Jummat exclusion, the 6 independent constraints, lexicographic objective function, GA mechanics, request pipeline, and database publishing service.
- [**Data Models Guide**](docs/Data-Models-Guide.md): Detailed explanation of the schema, relationship graphs, and foreign key cascades.

---

## 4. Running the Application

### 4.1 Setup & Virtual Environment

```bash
cd TimeMap_backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4.2 Database Migrations & Running Server

```bash
cd core
python manage.py migrate
python manage.py runserver
```

The API is served at `http://localhost:8000/api/`.

### 4.3 CLI Timetable Generation Command

To run the automated timetable scheduler from the CLI:

```bash
python manage.py generate_timetable --semester 1 --scope-type school --scope-id 1
```

Add `--publish` to immediately publish the generated timetable to live `TimetableEntry` and `LectureSession` records.

---

## 5. Automated Tests

Run test suites using `pytest`:

```bash
cd core
pytest
```

To run specifically the scheduling and optimizer test suite:

```bash
pytest scheduling/tests/
```

All 25 scheduling tests cover slot generation, Jummat exclusion, all 6 independent constraint handlers, genetic algorithm convergence, permission checks, and transactional publishing.
