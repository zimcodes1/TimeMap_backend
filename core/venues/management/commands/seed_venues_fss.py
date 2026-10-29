"""
Management command to seed realistic venues for the Faculty of Social Sciences (FSS)
and its departments (ECO, POL, SOC, MAC, PSY) at NSUK.

NOTE: Strict restriction — NO CBT Exam Centers or Exam Halls.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, School
from venues.models import Venue
from venues.seeding_utils import ensure_venue


class Command(BaseCommand):
    help = "Seed venues for Faculty of Social Sciences (FSS) and its departments."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Venues for Faculty of Social Sciences (FSS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FSS").first()
            if not faculty:
                self.stderr.write("Faculty FSS not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            eco_dept = depts.get("ECO")
            pol_dept = depts.get("POL")
            soc_dept = depts.get("SOC")
            mac_dept = depts.get("MAC")
            psy_dept = depts.get("PSY")

            venues_data = [
                # === Faculty-Level Venues ===
                {
                    "name": "Social Sciences Auditorium",
                    "code": "FSS-AUD",
                    "venue_type": Venue.VenueType.AUDITORIUM,
                    "capacity": 450,
                    "exam_capacity": 250,
                    "location": "FSS Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Air Conditioning", "Tiered Lecture Seating"],
                },
                {
                    "name": "FSS Twin Lecture Theatre 1",
                    "code": "FSS-LT1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 280,
                    "exam_capacity": 160,
                    "location": "FSS Twin Block",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },
                {
                    "name": "FSS Twin Lecture Theatre 2",
                    "code": "FSS-LT2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 250,
                    "exam_capacity": 140,
                    "location": "FSS Twin Block",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Sound Speakers"],
                },

                # === Economics (ECO) ===
                {
                    "name": "Economics Lecture Hall 1",
                    "code": "ECO-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 160,
                    "exam_capacity": 95,
                    "location": "Economics Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": eco_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Economics Lecture Room 2",
                    "code": "ECO-LR2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "Economics Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": eco_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Econometrics & Quantitative Analysis Lab",
                    "code": "ECO-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Economics Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": eco_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning"],
                },

                # === Political Science (POL) ===
                {
                    "name": "Political Science Lecture Hall 1",
                    "code": "POL-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 150,
                    "exam_capacity": 90,
                    "location": "Political Science Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pol_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Political Science Lecture Room 2",
                    "code": "POL-LR2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 110,
                    "exam_capacity": 65,
                    "location": "Political Science Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pol_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Parliamentary & Debate Chambers",
                    "code": "POL-CHM",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 70,
                    "exam_capacity": 45,
                    "location": "Political Science Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": pol_dept,
                    "facilities": ["Public Address (PA) System", "Air Conditioning", "Tables and Sockets"],
                },

                # === Sociology (SOC) ===
                {
                    "name": "Sociology Lecture Hall 1",
                    "code": "SOC-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 140,
                    "exam_capacity": 80,
                    "location": "Sociology Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": soc_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Sociology Lecture Room 2",
                    "code": "SOC-LR2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 100,
                    "exam_capacity": 60,
                    "location": "Sociology Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": soc_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },

                # === Mass Communication (MAC) ===
                {
                    "name": "Mass Communication Lecture Hall 1",
                    "code": "MAC-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 160,
                    "exam_capacity": 95,
                    "location": "Mass Comm Complex",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mac_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector", "Sound Speakers"],
                },
                {
                    "name": "Campus Broadcast Radio Studio",
                    "code": "MAC-RAD",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 40,
                    "exam_capacity": 30,
                    "location": "Mass Comm Broadcast Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mac_dept,
                    "facilities": ["Sound Speakers", "High-Speed Internet", "Air Conditioning"],
                },
                {
                    "name": "Broadcast Television Studio",
                    "code": "MAC-TV",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 35,
                    "location": "Mass Comm Broadcast Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mac_dept,
                    "facilities": ["HD Projector", "Sound Speakers", "Air Conditioning"],
                },
                {
                    "name": "Print Journalism Newsroom & Layout Lab",
                    "code": "MAC-PRN",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Mass Comm Print Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mac_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning"],
                },

                # === Psychology (PSY) ===
                {
                    "name": "Psychology Lecture Hall 1",
                    "code": "PSY-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 130,
                    "exam_capacity": 75,
                    "location": "Psychology Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": psy_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "Experimental Psychology & Behavioural Lab",
                    "code": "PSY-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 50,
                    "exam_capacity": 40,
                    "location": "Psychology Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": psy_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets", "Air Conditioning"],
                },
                {
                    "name": "Psychological Assessment Suite",
                    "code": "PSY-STE",
                    "venue_type": Venue.VenueType.MULTIPURPOSE,
                    "capacity": 40,
                    "exam_capacity": 30,
                    "location": "Psychology Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": psy_dept,
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

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Social Sciences Venues Seeding Complete! ==="))
            self.stdout.write(f"New venues created: {created_count}, updated: {updated_count}")

