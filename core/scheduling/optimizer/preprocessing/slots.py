from typing import List

from ..models.slot import Slot

DAYS = [
    ("MO", "Monday"),
    ("TU", "Tuesday"),
    ("WE", "Wednesday"),
    ("TH", "Thursday"),
    ("FR", "Friday"),
]

PERIODS = [
    (0, "08:00", "10:00"),
    (1, "10:00", "12:00"),
    (2, "12:00", "14:00"),
    (3, "14:00", "16:00"),
    (4, "16:00", "18:00"),
]


def build_valid_slots() -> List[Slot]:
    """
    Builds the complete set of valid 2-hour lecture slots for a weekly cycle:
      - Monday through Friday
      - 5 standard periods per day
      - EXCLUDING Friday 12:00-14:00 (period 2) for Jummat prayer.
    Total = 5 x 5 - 1 = 24 valid time slots.
    """
    slots: List[Slot] = []

    for day_code, day_name in DAYS:
        for period_idx, start_time, end_time in PERIODS:
            # Jummat exclusion: Friday 12:00 - 14:00 is strictly prohibited
            if day_code == "FR" and period_idx == 2:
                continue

            slots.append(
                Slot(
                    day=day_code,
                    day_name=day_name,
                    period_index=period_idx,
                    start_time=start_time,
                    end_time=end_time,
                )
            )

    return slots

