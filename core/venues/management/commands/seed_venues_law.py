"""
Management command to seed realistic venues for the Faculty of Law (LAW)
and its departments (PIL, PCL) at NSUK.

NOTE: Strict restriction — NO CBT Exam Centers or Exam Halls.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, School
from venues.models import Venue
from venues.seeding_utils import ensure_venue


class Command(BaseCommand):
    help = "Seed venues for Faculty of Law (LAW) and its departments."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Venues for Faculty of Law (LAW) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="LAW").first()
            if not faculty:
                self.stderr.write("Faculty LAW not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            pil_dept = depts.get("PIL")
            pcl_dept = depts.get("PCL")

            venues_data = [
                # === Faculty-Level Venues ===
                {
                    "name": "Faculty of Law Moot Court Auditorium",
                    "code": "LAW-MC1",
                    "venue_type": Venue.VenueType.AUDITORIUM,
                    "capacity": 350,
                    "exam_capacity": 200,
                    "location": "Faculty of Law Main Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Air Conditioning", "Moot Court Bench & Bar", "Tiered Lecture Seating"],
                },
                {
                    "name": "Secondary Moot Court Chamber",
                    "code": "LAW-MC2",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 100,
                    "exam_capacity": 60,
                    "location": "Law Practice Wing",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Moot Court Bench & Bar", "Air Conditioning", "Sound Speakers", "Tables and Sockets"],
                },
                {
                    "name": "Law Lecture Theatre 1",
                    "code": "LAW-LT1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 200,
                    "exam_capacity": 120,
                    "location": "Faculty of Law Block A",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },
                {
                    "name": "Law Lecture Theatre 2",
                    "code": "LAW-LT2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 180,
                    "exam_capacity": 100,
                    "location": "Faculty of Law Block B",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Sound Speakers"],
                },

                # === Public and International Law (PIL) ===
                {
                    "name": "Public Law Lecture Room 1",
                    "code": "PIL-LR1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "Public Law Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pil_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "International Law Seminar Room",
                    "code": "PIL-SR1",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 60,
                    "exam_capacity": 40,
                    "location": "Public Law Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pil_dept,
                    "facilities": ["Air Conditioning", "HD Projector", "Tables and Sockets"],
                },

                # === Private and Commercial Law (PCL) ===
                {
                    "name": "Private Law Lecture Room 1",
                    "code": "PCL-LR1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "Private Law Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pcl_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Commercial Arbitration Suite",
                    "code": "PCL-ARB",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 50,
                    "exam_capacity": 35,
                    "location": "Commercial Law Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pcl_dept,
                    "facilities": ["Air Conditioning", "HD Projector", "Tables and Sockets"],
                },
            ]

            created_count = 0
            updated_count = 0

            for v_data in venues_data:
                _, created = ensure_venue(
                    name=v_data["name"],
                    code=v_data["code"],
                    venue_type=v_data["venue_type"],
                    capacity=v_data["capacity"],
                    exam_capacity=v_data["exam_capacity"],
                    location=v_data["location"],
                    owning_level=v_data["owning_level"],
                    school=school,
                    faculty=v_data["faculty"],
                    department=v_data["department"],
                    facilities=v_data["facilities"],
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Law Venues Seeding Complete! ==="))
            self.stdout.write(f"New venues created: {created_count}, updated: {updated_count}")

