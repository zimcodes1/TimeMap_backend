from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    """
    Represents a 2-hour lecture time slot on a specific day of the week.
    Standard periods:
      0: 08:00-10:00
      1: 10:00-12:00
      2: 12:00-14:00
      3: 14:00-16:00
      4: 16:00-18:00
    Friday 12:00-14:00 (period 2) is excluded (Jummat prayer).
    """

    day: str  # "MO", "TU", "WE", "TH", "FR"
    day_name: str  # "Monday", "Tuesday", etc.
    period_index: int  # 0..4
    start_time: str  # "08:00"
    end_time: str  # "10:00"

    @property
    def slot_id(self) -> str:
        return f"{self.day}_{self.start_time}-{self.end_time}"

    def __str__(self) -> str:
        return f"{self.day_name} {self.start_time}-{self.end_time}"

