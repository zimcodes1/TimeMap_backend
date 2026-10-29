"""
Management command to seed realistic venues for the Faculty of Agriculture (AGRIC)
and its departments (AGR, ANS, AEE, FAQ, FOR) at NSUK.

NOTE: Strict restriction — NO CBT Exam Centers or Exam Halls.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, School
from venues.models import Venue
from venues.seeding_utils import ensure_venue


class Command(BaseCommand):
    help = "Seed venues for Faculty of Agriculture (AGRIC) and its departments."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Venues for Faculty of Agriculture (AGRIC) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="AGRIC").first()
            if not faculty:
                self.stderr.write("Faculty AGRIC not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            agr_dept = depts.get("AGR")
            ans_dept = depts.get("ANS")
            aee_dept = depts.get("AEE")
            faq_dept = depts.get("FAQ")
            for_dept = depts.get("FOR")

            venues_data = [
                # === Faculty-Level Venues ===
                {
                    "name": "Faculty of Agriculture Auditorium",
                    "code": "AGR-AUD",
                    "venue_type": Venue.VenueType.AUDITORIUM,
                    "capacity": 350,
                    "exam_capacity": 200,
                    "location": "Faculty of Agriculture Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Air Conditioning", "Tiered Lecture Seating"],
                },
                {
                    "name": "Agric Lecture Theatre 1",
                    "code": "AGR-LT1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 220,
                    "exam_capacity": 130,
                    "location": "Agric Building Block A",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },
                {
                    "name": "Agric Lecture Theatre 2",
                    "code": "AGR-LT2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 180,
                    "exam_capacity": 100,
                    "location": "Agric Building Block B",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Sound Speakers"],
                },

                # === Agronomy (AGR) ===
                {
                    "name": "Agronomy Lecture Hall 1",
                    "code": "AGR-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 110,
                    "exam_capacity": 65,
                    "location": "Agronomy Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": agr_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Crop & Soil Science Teaching Lab",
                    "code": "AGR-SOIL",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Agric Central Labs",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": agr_dept,
                    "facilities": ["Laboratory Equipment", "Chemical Safety Hood", "Tables and Sockets"],
                },

                # === Animal Science (ANS) ===
                {
                    "name": "Animal Science Lecture Hall 1",
                    "code": "ANS-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 100,
                    "exam_capacity": 60,
                    "location": "Animal Science Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": ans_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Animal Nutrition & Physiology Lab",
                    "code": "ANS-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Agric Central Labs",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": ans_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets", "Air Conditioning"],
                },

                # === Agricultural Economics and Extension (AEE) ===
                {
                    "name": "Agricultural Extension Lecture Hall 1",
                    "code": "AEE-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 110,
                    "exam_capacity": 65,
                    "location": "Agric Extension Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": aee_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Rural Sociology & Extension Media Lab",
                    "code": "AEE-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Agric Extension Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": aee_dept,
                    "facilities": ["HD Projector", "High-Speed Internet", "Tables and Sockets"],
                },

                # === Fisheries and Aquaculture (FAQ) ===
                {
                    "name": "Fisheries Lecture Room 1",
                    "code": "FAQ-LR1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 80,
                    "exam_capacity": 50,
                    "location": "Fisheries & Aqua Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": faq_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Aquaculture & Hatchery Wet Lab",
                    "code": "FAQ-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Fish Hatchery Complex",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": faq_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets"],
                },

                # === Forestry and Wildlife Management (FOR) ===
                {
                    "name": "Forestry Lecture Room 1",
                    "code": "FOR-LR1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 80,
                    "exam_capacity": 50,
                    "location": "Forestry Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": for_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Wildlife Museum & Herbarium Lab",
                    "code": "FOR-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Forestry & Wildlife Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": for_dept,
                    "facilities": ["Laboratory Equipment", "Air Conditioning", "Tables and Sockets"],
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

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Agriculture Venues Seeding Complete! ==="))
            self.stdout.write(f"New venues created: {created_count}, updated: {updated_count}")

