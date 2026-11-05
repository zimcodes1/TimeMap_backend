"""
Management command to seed realistic venues for the Faculty of Engineering (ENG)
and its departments (CVE, EEE, MEE, CHE) at NSUK.

NOTE: Strict restriction — NO CBT Exam Centers or Exam Halls.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, School
from venues.models import Venue
from venues.seeding_utils import ensure_venue


class Command(BaseCommand):
    help = "Seed venues for Faculty of Engineering (ENG) and its departments."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Venues for Faculty of Engineering (ENG) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ENG").first()
            if not faculty:
                self.stderr.write("Faculty ENG not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            cve_dept = depts.get("CVE")
            eee_dept = depts.get("EEE")
            mee_dept = depts.get("MEE")
            che_dept = depts.get("CHE")

            venues_data = [
                # === Faculty-Level Venues ===
                {
                    "name": "Faculty of Engineering Auditorium",
                    "code": "ENG-AUD",
                    "venue_type": Venue.VenueType.AUDITORIUM,
                    "capacity": 400,
                    "exam_capacity": 240,
                    "location": "Faculty of Engineering Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Air Conditioning", "Tiered Lecture Seating"],
                },
                {
                    "name": "Engineering Central Lecture Theatre",
                    "code": "ENG-CLT",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 260,
                    "exam_capacity": 150,
                    "location": "Engineering Central Building",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },
                {
                    "name": "Central Engineering Technical Drawing Studio",
                    "code": "ENG-DRW",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 150,
                    "exam_capacity": 120,
                    "location": "Engineering Central Studio",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Drawing Boards & Desks", "Air Conditioning", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Central Engineering Workshop & Foundry",
                    "code": "ENG-WKP",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 100,
                    "exam_capacity": 80,
                    "location": "Workshop Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets"],
                },

                # === Civil Engineering (CVE) ===
                {
                    "name": "Civil Structures & Concrete Lab",
                    "code": "CVE-STR",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Civil Engineering Labs",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": cve_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets"],
                },
                {
                    "name": "Geotechnical & Soil Mechanics Lab",
                    "code": "CVE-GEO",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Civil Engineering Labs",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": cve_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets"],
                },
                {
                    "name": "Civil Engineering Lecture Hall 1",
                    "code": "CVE-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 130,
                    "exam_capacity": 75,
                    "location": "Civil Engineering Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": cve_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },

                # === Electrical and Electronics Engineering (EEE) ===
                {
                    "name": "Electrical Machines & High Voltage Lab",
                    "code": "EEE-PWR",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "EEE Labs Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": eee_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets", "Air Conditioning"],
                },
                {
                    "name": "Electronics & Embedded Systems Lab",
                    "code": "EEE-ELX",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "EEE Labs Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": eee_dept,
                    "facilities": ["High-Speed Internet", "Laboratory Equipment", "Tables and Sockets", "Air Conditioning"],
                },
                {
                    "name": "EEE Lecture Hall 1",
                    "code": "EEE-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 140,
                    "exam_capacity": 80,
                    "location": "EEE Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": eee_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },

                # === Mechanical Engineering (MEE) ===
                {
                    "name": "Thermodynamics & Heat Transfer Lab",
                    "code": "MEE-THM",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "MEE Labs Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mee_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets"],
                },
                {
                    "name": "Mechanics of Machines & Automotive Lab",
                    "code": "MEE-AUT",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "MEE Labs Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mee_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets"],
                },
                {
                    "name": "Mechanical Engineering Lecture Hall 1",
                    "code": "MEE-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 140,
                    "exam_capacity": 80,
                    "location": "MEE Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mee_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },

                # === Chemical Engineering (CHE) ===
                {
                    "name": "Unit Operations & Chemical Reaction Lab",
                    "code": "CHE-UOP",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "CHE Labs Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": che_dept,
                    "facilities": ["Laboratory Equipment", "Chemical Safety Hood", "Tables and Sockets"],
                },
                {
                    "name": "Process Control & Petrochemicals Lab",
                    "code": "CHE-PRC",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "CHE Labs Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": che_dept,
                    "facilities": ["Laboratory Equipment", "Chemical Safety Hood", "Tables and Sockets", "Air Conditioning"],
                },
                {
                    "name": "Chemical Engineering Lecture Hall 1",
                    "code": "CHE-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "CHE Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": che_dept,
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

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Engineering Venues Seeding Complete! ==="))
            self.stdout.write(f"New venues created: {created_count}, updated: {updated_count}")

