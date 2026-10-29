"""
Management command to seed and standardize realistic venues for the Faculty of Natural
and Applied Sciences (FNAS) and its departments (CMP, SLT, STA, BCH, MCB, ZOO, MTH, PHY, CHM) at NSUK.

NOTE: Strict restriction — NO CBT Exam Centers or Exam Halls.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, School
from venues.models import Venue
from venues.seeding_utils import ensure_venue


class Command(BaseCommand):
    help = "Seed venues for Faculty of Natural and Applied Sciences (FNAS) and its departments."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Venues for Faculty of Natural & Applied Sciences (FNAS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FNAS").first()
            if not faculty:
                self.stderr.write("Faculty FNAS not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            cmp_dept = depts.get("CMP")
            slt_dept = depts.get("SLT")
            sta_dept = depts.get("STA")
            bch_dept = depts.get("BCH")
            mcb_dept = depts.get("MCB")
            zoo_dept = depts.get("ZOO")
            mth_dept = depts.get("MTH")
            phy_dept = depts.get("PHY")
            chm_dept = depts.get("CHM")

            venues_data = [
                # === Faculty-Level Venues ===
                {
                    "name": "FNAS Twin Lecture Theatre A",
                    "code": "FNA-TLTA",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 500,
                    "exam_capacity": 300,
                    "location": "FNAS Complex Ground Floor",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Whiteboard", "Tiered Lecture Seating"],
                },
                {
                    "name": "FNAS Twin Lecture Theatre B",
                    "code": "FNA-TLTB",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 450,
                    "exam_capacity": 270,
                    "location": "FNAS Complex First Floor",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Whiteboard", "Tiered Lecture Seating"],
                },
                {
                    "name": "Faculty Assembly Hall",
                    "code": "FNA-FAH",
                    "venue_type": Venue.VenueType.AUDITORIUM,
                    "capacity": 400,
                    "exam_capacity": 240,
                    "location": "FNAS Main Complex",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Public Address (PA) System", "HD Projector", "Sound Speakers", "Air Conditioning", "Tiered Lecture Seating"],
                },
                {
                    "name": "Science Lecture Theatre 1 (LT 1)",
                    "code": "FNA-LT1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 300,
                    "exam_capacity": 180,
                    "location": "Science Complex Block A",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },
                {
                    "name": "Science Lecture Theatre 2 (LT 2)",
                    "code": "FNA-LT2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 300,
                    "exam_capacity": 180,
                    "location": "Science Complex Block B",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },
                {
                    "name": "Science Lecture Theatre 3 (LT 3)",
                    "code": "FNA-LT3",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 250,
                    "exam_capacity": 150,
                    "location": "Science Complex Block C",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Sound Speakers"],
                },
                {
                    "name": "ETF Lecture Hall A",
                    "code": "FNA-ETFA",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 300,
                    "exam_capacity": 180,
                    "location": "ETF Building Ground Floor",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Public Address (PA) System", "Tiered Lecture Seating"],
                },
                {
                    "name": "ETF Lecture Hall B",
                    "code": "FNA-ETFB",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 250,
                    "exam_capacity": 150,
                    "location": "ETF Building First Floor",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Sound Speakers"],
                },
                {
                    "name": "PTDF Auditorium",
                    "code": "FNA-PTDF",
                    "venue_type": Venue.VenueType.AUDITORIUM,
                    "capacity": 280,
                    "exam_capacity": 160,
                    "location": "PTDF Center Building",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Air Conditioning", "HD Projector", "Sound Speakers", "High-Speed Internet", "Tiered Lecture Seating"],
                },
                {
                    "name": "FNAS Central Hall 1",
                    "code": "FNA-CH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 220,
                    "exam_capacity": 130,
                    "location": "Science Annex Ground Floor",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["HD Projector", "Whiteboard", "Sound Speakers"],
                },
                {
                    "name": "FNAS Central Hall 2",
                    "code": "FNA-CH2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 200,
                    "exam_capacity": 120,
                    "location": "Science Annex First Floor",
                    "owning_level": Venue.OwningLevel.FACULTY,
                    "faculty": faculty,
                    "department": None,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },

                # === Computer Science (CMP) ===
                {
                    "name": "CMP Lecture Room 101",
                    "code": "CMP-LR101",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 160,
                    "exam_capacity": 95,
                    "location": "Computer Science Wing Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": cmp_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "CMP Lecture Room 201",
                    "code": "CMP-LR201",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 140,
                    "exam_capacity": 80,
                    "location": "Computer Science Wing First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": cmp_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Computer Systems & Software Lab",
                    "code": "CMP-LAB1",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 70,
                    "exam_capacity": 60,
                    "location": "Computer Science Building",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": cmp_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning"],
                },
                {
                    "name": "Computer Networks & Cyber Lab",
                    "code": "CMP-LAB2",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Computer Science Building",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": cmp_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning"],
                },

                # === Science Laboratory Technology (SLT) ===
                {
                    "name": "SLT Lecture Hall A",
                    "code": "SLT-LHA",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 150,
                    "exam_capacity": 90,
                    "location": "SLT Complex",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": slt_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "SLT Lecture Hall B",
                    "code": "SLT-LHB",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "SLT Complex",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": slt_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "SLT Central Physical Sciences Lab",
                    "code": "SLT-LAB1",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 80,
                    "exam_capacity": 65,
                    "location": "SLT Laboratories Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": slt_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets"],
                },
                {
                    "name": "SLT Central Biological Sciences Lab",
                    "code": "SLT-LAB2",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 80,
                    "exam_capacity": 65,
                    "location": "SLT Laboratories First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": slt_dept,
                    "facilities": ["Laboratory Equipment", "Chemical Safety Hood", "Tables and Sockets"],
                },

                # === Mathematics (MTH) ===
                {
                    "name": "MTH Lecture Room 1",
                    "code": "MTH-LR1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 130,
                    "exam_capacity": 75,
                    "location": "Math Building Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mth_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "MTH Lecture Room 2",
                    "code": "MTH-LR2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 100,
                    "exam_capacity": 60,
                    "location": "Math Building First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mth_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },

                # === Physics (PHY) ===
                {
                    "name": "PHY Lecture Hall 1",
                    "code": "PHY-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 140,
                    "exam_capacity": 80,
                    "location": "Physics Block Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": phy_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "PHY Lecture Hall 2",
                    "code": "PHY-LH2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 100,
                    "exam_capacity": 60,
                    "location": "Physics Block First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": phy_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Physics Optics & Mechanics Lab",
                    "code": "PHY-LAB1",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Physics Labs Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": phy_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets"],
                },
                {
                    "name": "Physics Electronics & Modern Lab",
                    "code": "PHY-LAB2",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Physics Labs Block",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": phy_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets", "Air Conditioning"],
                },

                # === Chemistry (CHM) ===
                {
                    "name": "CHM Lecture Hall 1",
                    "code": "CHM-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 150,
                    "exam_capacity": 90,
                    "location": "Chemistry Block Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": chm_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "CHM Lecture Hall 2",
                    "code": "CHM-LH2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "Chemistry Block First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": chm_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Chemistry Organic Synthesis Lab",
                    "code": "CHM-LAB1",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 70,
                    "exam_capacity": 55,
                    "location": "Chemistry Labs Complex",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": chm_dept,
                    "facilities": ["Laboratory Equipment", "Chemical Safety Hood", "Tables and Sockets"],
                },
                {
                    "name": "Chemistry Analytical & Physical Lab",
                    "code": "CHM-LAB2",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 70,
                    "exam_capacity": 55,
                    "location": "Chemistry Labs Complex",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": chm_dept,
                    "facilities": ["Laboratory Equipment", "Chemical Safety Hood", "Tables and Sockets"],
                },

                # === Biochemistry (BCH) ===
                {
                    "name": "BCH Lecture Hall 1",
                    "code": "BCH-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 140,
                    "exam_capacity": 80,
                    "location": "Biochemistry Block Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": bch_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "BCH Lecture Hall 2",
                    "code": "BCH-LH2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 100,
                    "exam_capacity": 60,
                    "location": "Biochemistry Block First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": bch_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Biochemistry Practical Wet Lab",
                    "code": "BCH-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Biochemistry Labs Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": bch_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets", "Air Conditioning"],
                },

                # === Microbiology (MCB) ===
                {
                    "name": "MCB Lecture Room 1",
                    "code": "MCB-LR1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 150,
                    "exam_capacity": 90,
                    "location": "Microbiology Block Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mcb_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "MCB Lecture Room 2",
                    "code": "MCB-LR2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 110,
                    "exam_capacity": 65,
                    "location": "Microbiology Block First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mcb_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Microbiology Culture & Diagnostics Lab",
                    "code": "MCB-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 65,
                    "exam_capacity": 50,
                    "location": "Microbiology Labs Wing",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": mcb_dept,
                    "facilities": ["Laboratory Equipment", "Chemical Safety Hood", "Tables and Sockets", "Air Conditioning"],
                },

                # === Statistics (STA) ===
                {
                    "name": "STA Lecture Hall 1",
                    "code": "STA-LH1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "Statistics Wing Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": sta_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "STA Classroom 2",
                    "code": "STA-CR2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 90,
                    "exam_capacity": 55,
                    "location": "Statistics Wing First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": sta_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Statistics Computing & Analytics Lab",
                    "code": "STA-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Statistics Wing Lab",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": sta_dept,
                    "facilities": ["High-Speed Internet", "Tables and Sockets", "Air Conditioning"],
                },

                # === Zoology (ZOO) ===
                {
                    "name": "ZOO Lecture Room 1",
                    "code": "ZOO-LR1",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 120,
                    "exam_capacity": 70,
                    "location": "Zoology Block Ground Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": zoo_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets", "HD Projector"],
                },
                {
                    "name": "ZOO Classroom 2",
                    "code": "ZOO-CR2",
                    "venue_type": Venue.VenueType.LECTURE_HALL,
                    "capacity": 90,
                    "exam_capacity": 55,
                    "location": "Zoology Block First Floor",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": zoo_dept,
                    "facilities": ["Whiteboard", "Tables and Sockets"],
                },
                {
                    "name": "Zoology Morphology & Museum Lab",
                    "code": "ZOO-LAB",
                    "venue_type": Venue.VenueType.LABORATORY,
                    "capacity": 60,
                    "exam_capacity": 50,
                    "location": "Zoology Laboratories",
                    "owning_level": Venue.OwningLevel.DEPARTMENT,
                    "faculty": faculty,
                    "department": zoo_dept,
                    "facilities": ["Laboratory Equipment", "Tables and Sockets", "Air Conditioning"],
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

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Natural & Applied Sciences Venues Seeding Complete! ==="))
            self.stdout.write(f"New venues created: {created_count}, updated: {updated_count}")

