"""
Management command to seed realistic venues for the Faculty of Arts (ARTS)
and its departments (ELS, HIS, TMA, LIN, PRS) at NSUK.

NOTE: Strict restriction — NO CBT Exam Centers or Exam Halls.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, School
from venues.models import Venue
from venues.seeding_utils import ensure_venue


class Command(BaseCommand):
    help = "Seed venues for Faculty of Arts (ARTS) and its departments."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Venues for Faculty of Arts (ARTS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ARTS").first()
            if not faculty:
                self.stderr.write("Faculty ARTS not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            els_dept = depts.get("ELS")
            his_dept = depts.get("HIS")
            tma_dept = depts.get("TMA")
            lin_dept = depts.get("LIN")
            prs_dept = depts.get("PRS")

            venues_data = [
                # === Faculty-Level Venues ===
                {
                    "name": "Faculty of Arts Auditorium",
                    "code": "ART-AUD",
                    "venue_type": Venue.VenueType.AUDITORIUM,
                    "capacity": 400,
                    "exam_capacity": 220,
                    "location": "Arts Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Air Conditioning", "Tiered Lecture Seating"],
                },
                {
                    "name": "Arts Lecture Theatre A",
                    "code": "ART-LTA",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 250,
                    "exam_capacity": 140,
                    "location": "Arts Block Ground Floor",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },
                {
                    "name": "Arts Lecture Theatre B",
                    "code": "ART-LTB",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 200,
                    "exam_capacity": 120,
                    "location": "Arts Block First Floor",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Sound Speakers"],
                },

                # === English and Literary Studies (ELS) ===
                {
                    "name": "English Studies Lecture Hall 1",
                    "code": "ELS-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 130,
                    "exam_capacity": 75,
                    "location": "English Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": els_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Literary Workshop & Seminar Room",
                    "code": "ELS-SEM",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 70,
                    "exam_capacity": 45,
                    "location": "English Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": els_dept,
                    "facilities": ["Air Conditioning", "HD Projector", "Tables and Sockets"],
                },

                # === History and International Studies (HIS) ===
                {
                    "name": "History Lecture Hall 1",
                    "code": "HIS-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "History Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": his_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Diplomatic Studies & Archives Room",
                    "code": "HIS-DIP",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 60,
                    "exam_capacity": 40,
                    "location": "History Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": his_dept,
                    "facilities": ["Air Conditioning", "HD Projector", "Tables and Sockets"],
                },

                # === Theatre and Media Arts (TMA) ===
                {
                    "name": "Theatre Arts Performance Stage & Studio",
                    "code": "TMA-STG",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 180,
                    "exam_capacity": 100,
                    "location": "Arts Cultural Centre",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": tma_dept,
                    "facilities": ["Public Address (PA) System", "Sound Speakers", "Tiered Lecture Seating"],
                },
                {
                    "name": "Media Arts Production Studio",
                    "code": "TMA-STU",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 45,
                    "location": "Arts Media Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": tma_dept,
                    "facilities": ["Air Conditioning", "High-Speed Internet", "Tables and Sockets"],
                },
                {
                    "name": "TMA Lecture Room 1",
                    "code": "TMA-LR1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 100,
                    "exam_capacity": 60,
                    "location": "Arts Cultural Centre",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": tma_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },

                # === Languages and Linguistics (LIN) ===
                {
                    "name": "Phonetics & Language Laboratory",
                    "code": "LIN-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Linguistics Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": lin_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning", "Sound Speakers"],
                },
                {
                    "name": "Linguistics Lecture Room 1",
                    "code": "LIN-LR1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 110,
                    "exam_capacity": 65,
                    "location": "Linguistics Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": lin_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },

                # === Philosophy and Religious Studies (PRS) ===
                {
                    "name": "Philosophy Lecture Hall 1",
                    "code": "PRS-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 110,
                    "exam_capacity": 65,
                    "location": "PRS Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": prs_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Religious Studies Seminar Hall",
                    "code": "PRS-SEM",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 80,
                    "exam_capacity": 50,
                    "location": "PRS Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": prs_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "Air Conditioning"],
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

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Arts Venues Seeding Complete! ==="))
            self.stdout.write(f"New venues created: {created_count}, updated: {updated_count}")

