from dataclasses import dataclass


@dataclass(frozen=True)
class StudentGroup:
    """
    Represents an academic cohort taking lectures together:
    identified by degree Program + Level (e.g., CSC 100L).
    """

    program_id: int | str
    level: int
    program_code: str = ""
    program_name: str = ""

    @property
    def group_id(self) -> str:
        return f"{self.program_id}_{self.level}"

    @property
    def display_name(self) -> str:
        name = self.program_code or self.program_name or str(self.program_id)
        return f"{name} {self.level}L"

    def __str__(self) -> str:
        return self.display_name

