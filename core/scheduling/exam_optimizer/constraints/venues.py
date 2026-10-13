"""Venue constraint validation: capacity, turns, population coverage, and double-booking."""

from datetime import time
from math import ceil
from typing import Any, Dict, List

from courses.models import Course


def check_venue_constraints(
    events: List[Dict[str, Any]],
    scheduled_states: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Validates physical room capacity, population conservation, and venue double-booking.

    Enforces:
    - H5: Simultaneous venue capacity is not exceeded.
    - H6: Venues are not double-booked during overlapping windows.
    - H7: Venue allocations cover the full student population.
    """
    errors: List[Dict[str, str]] = []

    # 1. Individual event venue allocations check
    for event in events:
        course_code = event["course_code"]
        total_allocated = sum(venue["students"] for venue in event["venues"])
        if total_allocated != event["student_count"]:
            errors.append(
                {
                    "course_code": course_code,
                    "reason": "Venue allocations do not cover the full student population.",
                }
            )

        for venue in event["venues"]:
            cap = venue.get("capacity", 0)
            students = venue.get("students", 0)
            turns = venue.get("turns", 1)

            if not cap:
                errors.append(
                    {
                        "course_code": course_code,
                        "reason": f"Invalid capacity or turn allocation at {venue['venue_name']}.",
                    }
                )
                continue

            required_turns = ceil(students / cap)
            if event["exam_type"] != Course.ExamType.CBT and students > cap:
                errors.append(
                    {
                        "course_code": course_code,
                        "reason": f"Invalid capacity or turn allocation at {venue['venue_name']}.",
                    }
                )
            elif turns < required_turns:
                errors.append(
                    {
                        "course_code": course_code,
                        "reason": f"Invalid capacity or turn allocation at {venue['venue_name']}.",
                    }
                )

    # 2. Pairwise venue collision check across overlapping windows
    for index, first in enumerate(events):
        first_state = scheduled_states[index]
        first_start = time.fromisoformat(first["start_time"])
        first_end = time.fromisoformat(first["end_time"])

        for second_index in range(index + 1, len(events)):
            second = events[second_index]
            if first["date"] != second["date"]:
                continue

            second_start = time.fromisoformat(second["start_time"])
            second_end = time.fromisoformat(second["end_time"])

            overlaps = first_start < second_end and second_start < first_end
            if not overlaps:
                continue

            second_state = scheduled_states[second_index]
            shared_venues = first_state["venue_ids"].intersection(second_state["venue_ids"])
            if shared_venues:
                errors.append(
                    {
                        "course_code": first["course_code"],
                        "reason": f"Venue conflict with {second['course_code']}.",
                    }
                )

    return errors

