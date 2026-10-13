from dataclasses import dataclass, field
from datetime import time
from typing import Any, Dict, List, Optional


@dataclass
class VenueAllocation:
    """Represents a physical venue allocation for an exam event."""

    venue_id: int | str
    venue_name: str
    students: int
    turns: int
    capacity: int
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "venue_id": self.venue_id,
            "venue_name": self.venue_name,
            "students": self.students,
            "turns": self.turns,
            "capacity": self.capacity,
        }
        if self.start_time:
            result["start_time"] = self.start_time.isoformat()
        if self.end_time:
            result["end_time"] = self.end_time.isoformat()
        return result


@dataclass
class CBTTurn:
    """Represents a discrete turn/batch of students in a CBT venue."""

    venue_id: int | str
    turn_index: int
    start_time: time
    end_time: time
    student_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "turn_index": self.turn_index,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "student_count": self.student_count,
        }


@dataclass
class VenuePlan:
    """Physical room plan accommodating an exam event's student population."""

    venues: List[VenueAllocation] = field(default_factory=list)
    effective_duration_minutes: int = 120
    turns: List[CBTTurn] = field(default_factory=list)
    explanation: str = ""

    @property
    def total_assigned(self) -> int:
        return sum(v.students for v in self.venues)

    @property
    def total_capacity(self) -> int:
        return sum(v.capacity * max(1, v.turns) for v in self.venues)

    @property
    def excess_capacity(self) -> int:
        return max(0, self.total_capacity - self.total_assigned)

    @property
    def venue_count(self) -> int:
        return len(self.venues)

    @property
    def venue_ids(self) -> set:
        return {v.venue_id for v in self.venues}

    @property
    def average_utilization(self) -> float:
        if self.total_capacity == 0:
            return 0.0
        return round(self.total_assigned / self.total_capacity, 4)

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [v.to_dict() for v in self.venues]

