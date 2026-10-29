"""
Management command to seed realistic venues for the Faculty of Environmental Science (ENV)
and its departments (ARC, GEO, URP, ESM, QTS) at NSUK.

NOTE: Strict restriction — NO CBT Exam Centers or Exam Halls.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, School
from venues.models import Venue
from venues.seeding_utils import ensure_venue


class Command(BaseCommand):
    help = "Seed venues for Faculty of Environmental Science (ENV) and its departments."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Venues for Faculty of Environmental Science (ENV) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ENV").first()
            if not faculty:
                self.stderr.write("Faculty ENV not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            arc_dept = depts.get("ARC")
            geo_dept = depts.get("GEO")
            urp_dept = depts.get("URP")
            esm_dept = depts.get("ESM")
            qts_dept = depts.get("QTS")

            venues_data = [
                # === Faculty-Level Venues ===
                {
                    "name": "Faculty of Environmental Science Auditorium",
                    "code": "ENV-AUD",
                    "venue_type": Venue.VenueType.AUDITORIUM,
                    "capacity": 350,
                    "exam_capacity": 200,
                    "location": "Environmental Studies Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Air Conditioning", "Tiered Lecture Seating"],
                },
                {
                    "name": "Environmental Lecture Theatre 1",
                    "code": "ENV-LT1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 220,
                    "exam_capacity": 130,
                    "location": "Environmental Block A",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },

                # === Architecture (ARC) ===
                {
                    "name": "Architecture Design Studio 1",
                    "code": "ARC-DS1",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 80,
                    "exam_capacity": 60,
                    "location": "Architecture Studios Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": arc_dept,
                    "facilities": ["Drawing Boards & Desks", "Air Conditioning", "High-Speed Internet", "Tables and Sockets"],
                },
                {
                    "name": "Architecture Design Studio 2",
                    "code": "ARC-DS2",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 80,
                    "exam_capacity": 60,
                    "location": "Architecture Studios First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": arc_dept,
                    "facilities": ["Drawing Boards & Desks", "Air Conditioning", "Tables and Sockets"],
                },
                {
                    "name": "Architecture CAD & 3D Visualization Lab",
                    "code": "ARC-CAD",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Architecture Studios Second Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": arc_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning", "HD Projector"],
                },
                {
                    "name": "Architecture Lecture Room 1",
                    "code": "ARC-LR1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 100,
                    "exam_capacity": 60,
                    "location": "Architecture Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": arc_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },

                # === Geography and Environmental Management (GEO) ===
                {
                    "name": "Geography Lecture Hall 1",
                    "code": "GEO-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 130,
                    "exam_capacity": 75,
                    "location": "Geography Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": geo_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "GIS, Remote Sensing & Spatial Analysis Lab",
                    "code": "GEO-GIS",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Geography Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": geo_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning"],
                },
                {
                    "name": "Physical Geography & Climatology Lab",
                    "code": "GEO-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Geography Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": geo_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets", "Air Conditioning"],
                },

                # === Urban and Regional Planning (URP) ===
                {
                    "name": "Urban Planning Design Studio 1",
                    "code": "URP-DS1",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 75,
                    "exam_capacity": 55,
                    "location": "URP Studio Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": urp_dept,
                    "facilities": ["Drawing Boards & Desks", "Air Conditioning", "Tables and Sockets"],
                },
                {
                    "name": "URP Lecture Hall 1",
                    "code": "URP-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 110,
                    "exam_capacity": 65,
                    "location": "URP Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": urp_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },

                # === Estate Management (ESM) ===
                {
                    "name": "Estate Management Lecture Hall 1",
                    "code": "ESM-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "Estate Management Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": esm_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Real Estate Valuation & Land Economics Lab",
                    "code": "ESM-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Estate Management Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": esm_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning"],
                },

                # === Quantity Surveying (QTS) ===
                {
                    "name": "Quantity Surveying Measurement Studio",
                    "code": "QTS-STU",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 70,
                    "exam_capacity": 50,
                    "location": "QS Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": qts_dept,
                    "facilities": ["Drawing Boards & Desks", "Air Conditioning", "Tables and Sockets"],
                },
                {
                    "name": "Quantity Surveying Lecture Hall 1",
                    "code": "QTS-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 110,
                    "exam_capacity": 65,
                    "location": "QS Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": qts_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
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

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Environmental Science Venues Seeding Complete! ==="))
            self.stdout.write(f"New venues created: {created_count}, updated: {updated_count}")

