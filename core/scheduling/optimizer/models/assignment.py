from dataclasses import dataclass

from .occurrence import CourseOccurrence
from .slot import Slot


@dataclass(frozen=True)
class Assignment:
    """
    Gene representation: mapping of a CourseOccurrence to a specific (Slot, Venue).
    """

    occurrence: CourseOccurrence
    slot: Slot
    venue_id: int | str

    @property
    def course_id(self) -> int | str:
        return self.occurrence.course_id

    @property
    def course_code(self) -> str:
        return self.occurrence.course_code

    @property
    def day(self) -> str:
        return self.slot.day

    def __str__(self) -> str:
        return f"[{self.occurrence.occurrence_id} -> {self.slot.day_name} {self.slot.start_time}-{self.slot.end_time} @ Venue#{self.venue_id}]"

