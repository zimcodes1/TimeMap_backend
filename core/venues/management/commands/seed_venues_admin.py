"""
Management command to seed realistic venues for the Faculty of Administration (ADMIN)
and its departments (BAM, ACC, PAD, BFN) at NSUK.

NOTE: Strict restriction — NO CBT Exam Centers or Exam Halls.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, School
from venues.models import Venue
from venues.seeding_utils import ensure_venue


class Command(BaseCommand):
    help = "Seed venues for Faculty of Administration (ADMIN) and its departments."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Venues for Faculty of Administration (ADMIN) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ADMIN").first()
            if not faculty:
                self.stderr.write("Faculty ADMIN not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            bam_dept = depts.get("BAM")
            acc_dept = depts.get("ACC")
            pad_dept = depts.get("PAD")
            bfn_dept = depts.get("BFN")

            # Venues specifications
            venues_data = [
                # === Faculty-Level Venues ===
                {
                    "name": "Faculty of Administration Auditorium",
                    "code": "ADM-AUD",
                    "venue_type": Venue.VenueType.AUDITORIUM,
                    "capacity": 450,
                    "exam_capacity": 250,
                    "location": "Faculty of Admin Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Air Conditioning", "Tiered Lecture Seating"],
                },
                {
                    "name": "Admin Lecture Theatre 1",
                    "code": "ADM-LT1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 300,
                    "exam_capacity": 180,
                    "location": "Faculty of Admin Complex Ground Floor",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },
                {
                    "name": "Admin Lecture Theatre 2",
                    "code": "ADM-LT2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 250,
                    "exam_capacity": 150,
                    "location": "Faculty of Admin Complex First Floor",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Sound Speakers"],
                },

                # === Business Administration (BAM) ===
                {
                    "name": "BAM Lecture Room 101",
                    "code": "BAM-LR101",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 160,
                    "exam_capacity": 95,
                    "location": "Business Admin Wing Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": bam_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "BAM Lecture Room 201",
                    "code": "BAM-LR201",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "Business Admin Wing First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": bam_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "BAM Executive Seminar Hall",
                    "code": "BAM-ESH",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 60,
                    "exam_capacity": 40,
                    "location": "Business Admin Wing Second Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": bam_dept,
                    "facilities": ["Air Conditioning", "HD Projector", "Tables and Sockets", "High-Speed Internet"],
                },

                # === Accounting (ACC) ===
                {
                    "name": "Accounting Lecture Hall 1",
                    "code": "ACC-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 150,
                    "exam_capacity": 90,
                    "location": "Accounting Department Building",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": acc_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Accounting Lecture Hall 2",
                    "code": "ACC-LH2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 110,
                    "exam_capacity": 65,
                    "location": "Accounting Department Building",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": acc_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Accounting Information Systems Lab",
                    "code": "ACC-AIS",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Accounting Department IT Suite",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": acc_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning"],
                },

                # === Public Administration (PAD) ===
                {
                    "name": "Public Administration Lecture Hall 1",
                    "code": "PAD-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 150,
                    "exam_capacity": 90,
                    "location": "PAD Block Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pad_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Public Administration Lecture Room 2",
                    "code": "PAD-LR2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 110,
                    "exam_capacity": 65,
                    "location": "PAD Block First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pad_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Governance & Policy Seminar Room",
                    "code": "PAD-SEM",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 50,
                    "exam_capacity": 35,
                    "location": "PAD Block Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pad_dept,
                    "facilities": ["Air Conditioning", "HD Projector", "Tables and Sockets"],
                },

                # === Banking and Finance (BFN) ===
                {
                    "name": "Banking & Finance Lecture Hall 1",
                    "code": "BFN-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 140,
                    "exam_capacity": 85,
                    "location": "Finance & Banking Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": bfn_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Banking & Finance Lecture Room 2",
                    "code": "BFN-LR2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 100,
                    "exam_capacity": 60,
                    "location": "Finance & Banking Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": bfn_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Financial Markets Simulation Lab",
                    "code": "BFN-SIM",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 45,
                    "exam_capacity": 35,
                    "location": "Finance IT Lab",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": bfn_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning"],
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

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Administration Venues Seeding Complete! ==="))
            self.stdout.write(f"New venues created: {created_count}, updated: {updated_count}")

