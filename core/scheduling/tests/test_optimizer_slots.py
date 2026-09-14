from unittest import TestCase

from scheduling.optimizer.models.slot import Slot
from scheduling.optimizer.preprocessing.slots import build_valid_slots


class OptimizerSlotsTests(TestCase):
    def test_valid_slots_count_is_24(self):
        """Standard week: 5 days * 5 periods - 1 Jummat = 24 valid slots."""
        slots = build_valid_slots()
        self.assertEqual(len(slots), 24)

    def test_jummat_period_excluded(self):
        """Friday 12:00-14:00 (period 2) must strictly NOT exist in valid slots."""
        slots = build_valid_slots()
        friday_slots = [s for s in slots if s.day == "FR"]
        self.assertEqual(len(friday_slots), 4)

        for s in friday_slots:
            self.assertFalse(
                s.period_index == 2 and s.start_time == "12:00" and s.end_time == "14:00",
                "Friday 12:00-14:00 Jummat period must not be in valid slots!",
            )

    def test_slot_properties(self):
        """Verify slot periods and structure."""
        slots = build_valid_slots()
        mon_first = slots[0]
        self.assertEqual(mon_first.day, "MO")
        self.assertEqual(mon_first.day_name, "Monday")
        self.assertEqual(mon_first.period_index, 0)
        self.assertEqual(mon_first.start_time, "08:00")
        self.assertEqual(mon_first.end_time, "10:00")
        self.assertEqual(mon_first.slot_id, "MO_08:00-10:00")

