from datetime import date, time
from types import SimpleNamespace

from courses.models import Course
from scheduling.exam_optimizer import _allocate, _date_windows, _within_policy


def venue(name, capacity):
    return SimpleNamespace(name=name, exam_capacity=capacity, capacity=capacity, id=name)


def test_default_calendar_excludes_sundays_and_friday_prayer_window():
    start, end = date(2026, 10, 9), date(2026, 10, 11)  # Friday through Sunday
    windows = list(_date_windows(start, end))

    assert windows
    assert {day.weekday() for day, _ in windows} == {4, 5}
    assert not any(day.weekday() == 4 and time(12) <= start_time < time(14) for day, start_time in windows)
    assert not _within_policy(date(2026, 10, 9), time(11), 120)
    assert _within_policy(date(2026, 10, 9), time(14), 120)


def test_written_exam_can_split_one_population_across_venues():
    duration, allocations = _allocate(
        [venue("Hall A", 100), venue("Hall B", 80)],
        count=180,
        exam_type=Course.ExamType.WRITTEN,
        duration=120,
        per_student=None,
    )

    assert duration == 120
    assert sum(item["students"] for item in allocations) == 180
    assert all(item["students"] <= item["capacity"] for item in allocations)


def test_cbt_uses_parallel_centres_then_turns_when_needed():
    duration, allocations = _allocate(
        [venue("CBT A", 100), venue("CBT B", 80)],
        count=170,
        exam_type=Course.ExamType.CBT,
        duration=30,
        per_student=30,
    )
    assert duration == 30
    assert sum(item["students"] for item in allocations) == 170
    assert all(item["turns"] == 1 for item in allocations)

    turn_duration, turn_allocations = _allocate(
        [venue("CBT A", 100)],
        count=250,
        exam_type=Course.ExamType.CBT,
        duration=30,
        per_student=30,
    )
    assert turn_duration == 90
    assert turn_allocations[0]["turns"] == 3
