from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True)
class CalendarPolicy:
    """Operating policy governing valid examination days, hours, and blackouts."""

    open_time: time = time(8)
    close_time: time = time(18)
    step_minutes: int = 30
    # Monday (0) through Saturday (5). Sunday (6) is excluded.
    operating_days: tuple[int, ...] = (0, 1, 2, 3, 4, 5)
    # Friday Jummat prayer blackout
    jummat_day: int = 4
    jummat_start_minutes: int = 12 * 60
    jummat_end_minutes: int = 14 * 60

    @property
    def open_minutes(self) -> int:
        return self.open_time.hour * 60 + self.open_time.minute

    @property
    def close_minutes(self) -> int:
        return self.close_time.hour * 60 + self.close_time.minute


@dataclass(frozen=True)
class CandidateWindow:
    """A candidate time window for placing an examination event."""

    date: date
    start_time: time
    end_time: time
    duration_minutes: int

    @property
    def start_minutes(self) -> int:
        return self.start_time.hour * 60 + self.start_time.minute

    @property
    def end_minutes(self) -> int:
        return self.end_time.hour * 60 + self.end_time.minute

    def overlaps_with(self, other: "CandidateWindow") -> bool:
        """Checks if two candidate windows overlap on the same calendar date."""
        if self.date != other.date:
            return False
        return self.start_time < other.end_time and other.start_time < self.end_time

