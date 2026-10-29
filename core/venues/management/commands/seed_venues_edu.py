"""
Management command to seed realistic venues for the Faculty of Education (EDU)
and its departments (EDF, STM, ASE, GAC) at NSUK.

NOTE: Strict restriction — NO CBT Exam Centers or Exam Halls.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, School
from venues.models import Venue
from venues.seeding_utils import ensure_venue


class Command(BaseCommand):
    help = "Seed venues for Faculty of Education (EDU) and its departments."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Venues for Faculty of Education (EDU) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="EDU").first()
            if not faculty:
                self.stderr.write("Faculty EDU not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            edf_dept = depts.get("EDF")
            stm_dept = depts.get("STM")
            ase_dept = depts.get("ASE")
            gac_dept = depts.get("GAC")

            venues_data = [
                # === Faculty-Level Venues ===
                {
                    "name": "Faculty of Education Auditorium",
                    "code": "EDU-AUD",
                    "venue_type": Venue.VenueType.AUDITORIUM,
                    "capacity": 400,
                    "exam_capacity": 240,
                    "location": "Education Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Air Conditioning", "Tiered Lecture Seating"],
                },
                {
                    "name": "Education Lecture Theatre 1",
                    "code": "EDU-LT1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 250,
                    "exam_capacity": 150,
                    "location": "Education Block A",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },
                {
                    "name": "Education Lecture Theatre 2",
                    "code": "EDU-LT2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 200,
                    "exam_capacity": 120,
                    "location": "Education Block B",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Sound Speakers"],
                },

                # === Educational Foundations (EDF) ===
                {
                    "name": "Educational Foundations Lecture Hall 1",
                    "code": "EDF-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 140,
                    "exam_capacity": 80,
                    "location": "EDF Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": edf_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Educational Foundations Lecture Room 2",
                    "code": "EDF-LR2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 100,
                    "exam_capacity": 60,
                    "location": "EDF Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": edf_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Early Childhood Demonstration Playroom",
                    "code": "EDF-ECD",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 35,
                    "location": "Early Childhood Resource Centre",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": edf_dept,
                    "facilities": ["Air Conditioning", "Tables and Sockets", "Laboratory Equipment"],
                },

                # === Science, Technology and Mathematics Education (STM) ===
                {
                    "name": "STM Education Lecture Hall 1",
                    "code": "STM-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "Science Education Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": stm_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Integrated Science Teaching Lab",
                    "code": "STM-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Science Education Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": stm_dept,
                    "facilities": ["Laboratory Equipment", "Chemical Safety Hood", "Tables and Sockets"],
                },

                # === Arts and Social Science Education (ASE) ===
                {
                    "name": "ASE Lecture Hall 1",
                    "code": "ASE-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 130,
                    "exam_capacity": 75,
                    "location": "Arts Education Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": ase_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Micro-Teaching Demonstration Lab",
                    "code": "ASE-MIC",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 35,
                    "location": "Educational Media Centre",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": ase_dept,
                    "facilities": ["HD Projector", "Sound Speakers", "Air Conditioning", "Tables and Sockets"],
                },

                # === Guidance and Counselling (GAC) ===
                {
                    "name": "Guidance & Counselling Lecture Hall 1",
                    "code": "GAC-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "GAC Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": gac_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Counselling Practicum & Clinic Suite",
                    "code": "GAC-CLN",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 40,
                    "exam_capacity": 30,
                    "location": "Counselling Centre",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": gac_dept,
                    "facilities": ["Air Conditioning", "Tables and Sockets"],
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

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Education Venues Seeding Complete! ==="))
            self.stdout.write(f"New venues created: {created_count}, updated: {updated_count}")

