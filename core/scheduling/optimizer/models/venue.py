from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class VenueData:
    """
    Represents an available room/hall that can host lectures or practicals.
    Types:
      - 'laboratory': only allowed for practical courses
      - 'lecture_hall' / 'multipurpose': allowed for standard lectures
    """

    id: int | str
    name: str
    venue_type: str  # "laboratory", "lecture_hall", "multipurpose"
    capacity: int
    owning_level: str = "school"  # "department", "faculty", "school"
    owning_department_id: Optional[int | str] = None
    owning_faculty_id: Optional[int | str] = None
    owning_school_id: Optional[int | str] = None
    owning_scope_id: int | str = ""

    @property
    def is_laboratory(self) -> bool:
        return self.venue_type.lower() == "laboratory"

    def __str__(self) -> str:
        return f"{self.name} [{self.venue_type}, cap={self.capacity}]"

