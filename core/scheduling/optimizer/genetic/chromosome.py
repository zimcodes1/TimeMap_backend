from typing import Iterator, List

from ..models.assignment import Assignment


class Chromosome:
    """
    Candidate solution vector.
    Each index corresponds to the exact CourseOccurrence at the same index in problem.occurrences.
    """

    def __init__(self, assignments: List[Assignment]):
        self.assignments: List[Assignment] = list(assignments)

    def __len__(self) -> int:
        return len(self.assignments)

    def __getitem__(self, index: int) -> Assignment:
        return self.assignments[index]

    def __setitem__(self, index: int, value: Assignment) -> None:
        self.assignments[index] = value

    def __iter__(self) -> Iterator[Assignment]:
        return iter(self.assignments)

    def clone(self) -> "Chromosome":
        return Chromosome(self.assignments.copy())

    def __repr__(self) -> str:
        return f"<Chromosome: {len(self.assignments)} genes>"

