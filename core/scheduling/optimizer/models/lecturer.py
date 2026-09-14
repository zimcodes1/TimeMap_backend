from dataclasses import dataclass


@dataclass(frozen=True)
class LecturerData:
    """
    Represents an instructor assigned to teach one or more courses.
    """

    id: int | str
    name: str
    staff_id: str = ""

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

