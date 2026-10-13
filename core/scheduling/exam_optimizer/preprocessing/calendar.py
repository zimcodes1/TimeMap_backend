"""Calendar window and policy generation for the examination scheduler."""

from datetime import date, time, timedelta
from typing import Generator, List, Optional, Tuple

from ..models.time_window import CalendarPolicy, CandidateWindow


def _minutes(t: time) -> int:
    """Converts a time object to minutes from midnight."""
    return t.hour * 60 + t.minute


def is_within_policy(
    day: date,
    start_time: time,
    duration_minutes: int,
    policy: Optional[CalendarPolicy] = None,
) -> bool:
    """Checks whether an exam window complies with institutional policy:

    - Scheduled within daily operating hours (default 08:00 - 18:00).
    - Excludes Friday Jummat prayer window (default 12:00 - 14:00).
    - Operates only on allowed days (default Monday through Saturday).
    """
    pol = policy or CalendarPolicy()
    if day.weekday() not in pol.operating_days:
        return False

    start_m = _minutes(start_time)
    finish_m = start_m + duration_minutes

    # Must finish by closing time
    if finish_m > pol.close_minutes:
        return False

    # Friday Jummat prayer blackout check:
    # Any overlap between [start_m, finish_m] and [jummat_start, jummat_end] is forbidden
    if day.weekday() == pol.jummat_day:
        if start_m < pol.jummat_end_minutes and finish_m > pol.jummat_start_minutes:
            return False

    return True


def date_windows(
    start: date,
    end: date,
    policy: Optional[CalendarPolicy] = None,
) -> Generator[Tuple[date, time], None, None]:
    """Yields candidate (date, start_time) slots within the examination period.

    Iterates in discrete steps (default 30 min) between 08:00 and 18:00.
    Omits slots starting inside the Friday Jummat prayer window.
    """
    pol = policy or CalendarPolicy()
    day = start
    while day <= end:
        if day.weekday() in pol.operating_days:
            minute = pol.open_minutes
            while minute < pol.close_minutes:
                hh, mm = divmod(minute, 60)
                current_time = time(hh, mm)

                # Skip slot if it starts inside the Friday prayer window
                if day.weekday() == pol.jummat_day and (
                    pol.jummat_start_minutes <= minute < pol.jummat_end_minutes
                ):
                    minute += pol.step_minutes
                    continue

                yield day, current_time
                minute += pol.step_minutes
        day += timedelta(days=1)


def build_candidate_windows(
    start: date,
    end: date,
    durations: List[int],
    policy: Optional[CalendarPolicy] = None,
) -> List[CandidateWindow]:
    """Constructs valid CandidateWindow objects for each distinct duration."""
    pol = policy or CalendarPolicy()
    windows = []
    seen = set()

    for day, start_time in date_windows(start, end, pol):
        for dur in durations:
            if is_within_policy(day, start_time, dur, pol):
                finish_m = _minutes(start_time) + dur
                finish_time = time(finish_m // 60, finish_m % 60)
                key = (day, start_time, finish_time, dur)
                if key not in seen:
                    seen.add(key)
                    windows.append(
                        CandidateWindow(
                            date=day,
                            start_time=start_time,
                            end_time=finish_time,
                            duration_minutes=dur,
                        )
                    )
    return windows

