"""
Management command to seed realistic venues for the Faculty of Medical and Health Sciences (FMHS)
and its departments (MED, NUR, MLS, PBH) at NSUK.

NOTE: Strict restriction — NO CBT Exam Centers or Exam Halls.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, School
from venues.models import Venue
from venues.seeding_utils import ensure_venue


class Command(BaseCommand):
    help = "Seed venues for Faculty of Medical and Health Sciences (FMHS) and its departments."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Venues for Faculty of Medical and Health Sciences (FMHS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FMHS").first()
            if not faculty:
                self.stderr.write("Faculty FMHS not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            med_dept = depts.get("MED")
            nur_dept = depts.get("NUR")
            mls_dept = depts.get("MLS")
            pbh_dept = depts.get("PBH")

            venues_data = [
                # === Faculty-Level Venues ===
                {
                    "name": "College of Health Sciences Auditorium",
                    "code": "FMH-AUD",
                    "venue_type": Venue.VenueType.AUDITORIUM,
                    "capacity": 450,
                    "exam_capacity": 250,
                    "location": "College of Health Sciences Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Air Conditioning", "Tiered Lecture Seating"],
                },
                {
                    "name": "Medical Lecture Amphitheatre 1",
                    "code": "FMH-LT1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 250,
                    "exam_capacity": 150,
                    "location": "Basic Medical Sciences Block",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },
                {
                    "name": "Medical Lecture Amphitheatre 2",
                    "code": "FMH-LT2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 200,
                    "exam_capacity": 120,
                    "location": "Basic Medical Sciences Block",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Sound Speakers"],
                },
                {
                    "name": "Human Anatomy Dissection Laboratory",
                    "code": "FMH-DIS",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 100,
                    "exam_capacity": 80,
                    "location": "Anatomy Department Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Laboratory Equipment", "Air Conditioning", "Chemical Safety Hood", "Tables and Sockets"],
                },
                {
                    "name": "Multidisciplinary Physiology & Pharmacology Lab",
                    "code": "FMH-MPL",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 80,
                    "exam_capacity": 65,
                    "location": "Physiology & Pharmacology Wing",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets", "Air Conditioning"],
                },
                {
                    "name": "Histology & Morbid Anatomy Lab",
                    "code": "FMH-PAT",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 70,
                    "exam_capacity": 60,
                    "location": "Pathology Wing",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets", "Air Conditioning"],
                },

                # === Medicine and Surgery (MED) ===
                {
                    "name": "Clinical Skills Simulation & OSCE Suite",
                    "code": "MED-OSC",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Clinical Sciences Building",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": med_dept,
                    "facilities": ["Clinical Simulation Equipment", "Air Conditioning", "Tables and Sockets"],
                },
                {
                    "name": "Medicine Lecture Room 1",
                    "code": "MED-LR1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "Clinical Sciences Building",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": med_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },

                # === Nursing Science (NUR) ===
                {
                    "name": "Nursing Demonstration Clinical Ward",
                    "code": "NUR-WRD",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 60,
                    "exam_capacity": 45,
                    "location": "Nursing Science Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": nur_dept,
                    "facilities": ["Clinical Simulation Equipment", "Air Conditioning", "Tables and Sockets"],
                },
                {
                    "name": "Maternal & Child Health Nursing Lab",
                    "code": "NUR-MCH",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Nursing Science Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": nur_dept,
                    "facilities": ["Clinical Simulation Equipment", "Laboratory Equipment", "Tables and Sockets"],
                },
                {
                    "name": "Nursing Science Lecture Hall 1",
                    "code": "NUR-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 130,
                    "exam_capacity": 75,
                    "location": "Nursing Science Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": nur_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },

                # === Medical Laboratory Science (MLS) ===
                {
                    "name": "Medical Microbiology & Parasitology Lab",
                    "code": "MLS-MIC",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "MLS Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mls_dept,
                    "facilities": ["Laboratory Equipment", "Chemical Safety Hood", "Tables and Sockets"],
                },
                {
                    "name": "Clinical Chemistry & Haematology Lab",
                    "code": "MLS-CHM",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "MLS Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mls_dept,
                    "facilities": ["Laboratory Equipment", "Chemical Safety Hood", "Tables and Sockets", "Air Conditioning"],
                },
                {
                    "name": "Medical Laboratory Science Lecture Hall 1",
                    "code": "MLS-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "MLS Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mls_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },

                # === Public Health (PBH) ===
                {
                    "name": "Epidemiology & Community Health Lab",
                    "code": "PBH-EPI",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Public Health Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pbh_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning"],
                },
                {
                    "name": "Public Health Lecture Hall 1",
                    "code": "PBH-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 130,
                    "exam_capacity": 75,
                    "location": "Public Health Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pbh_dept,
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

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Medical and Health Sciences Venues Seeding Complete! ==="))
            self.stdout.write(f"New venues created: {created_count}, updated: {updated_count}")

