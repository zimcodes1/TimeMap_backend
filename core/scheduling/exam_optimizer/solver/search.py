"""Constructive search algorithm for examination scheduling."""

from collections import defaultdict
from datetime import date, time
from typing import Any, Dict, List, Set, Tuple

from ..allocation.planner import allocate_venues
from ..models.problem import ExamSchedulingProblem
from ..preprocessing.calendar import date_windows, is_within_policy
from .ordering import order_exam_events


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _band(m: int) -> int:
    """Classifies minute from midnight into morning (0), midday (1), or afternoon (2) session."""
    if m < 690:
        return 0  # Morning: 08:00 - 11:30
    elif m < 870:
        return 1  # Midday: 11:30 - 14:30
    else:
        return 2  # Afternoon: 14:30 - 18:00


def search_exam_schedule(
    problem: ExamSchedulingProblem,
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    int,
]:
    """Constructs a conflict-free examination schedule using heuristic placement and dynamic venue allocation.

    Returns:
        (events, scheduled_states, unscheduled_diagnostics, candidate_windows_evaluated)
    """
    events: List[Dict[str, Any]] = []
    scheduled_states: List[Dict[str, Any]] = []
    unscheduled: List[Dict[str, Any]] = []
    candidate_windows_evaluated = 0

    ordered = order_exam_events(list(problem.events.values()))
    conflict_graph = problem.student_conflict_graph or {}

    # Fast indexes
    states_by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    course_placed_date: Dict[int, date] = {}
    venue_usage: Dict[int, int] = defaultdict(int)
    campus_date_load: Dict[str, int] = defaultdict(int)
    day_band_load: Dict[Tuple[str, int], int] = defaultdict(int)
    dept_day_band_load: Dict[Tuple[str, Optional[int], int], int] = defaultdict(int)

    for event_data in ordered:
        students = event_data.student_ids
        count = event_data.student_count
        exam_type = event_data.exam_type
        nominal_duration = event_data.duration_minutes
        per_student = event_data.duration_per_student_minutes
        course_id = event_data.course_id
        conflict_course_ids = conflict_graph.get(course_id, set())

        eligible_venues = problem.venues_by_type.get(exam_type, [])
        if not eligible_venues:
            unscheduled.append(
                {
                    "course_id": course_id,
                    "course_code": event_data.course_code,
                    "reason": f"No active venues of compatible type '{exam_type}' available.",
                }
            )
            continue

        # Dates where conflicting courses are already scheduled
        conflict_dates_map: Dict[str, int] = defaultdict(int)
        conflict_dates_list: List[date] = []
        weekly_conflict_counts: Dict[Tuple[int, int], int] = defaultdict(int)

        for cid in conflict_course_ids:
            if cid in course_placed_date:
                d = course_placed_date[cid]
                conflict_dates_map[d.isoformat()] += 1
                conflict_dates_list.append(d)
                iso = d.isocalendar()
                weekly_conflict_counts[(iso.year, iso.week)] += 1

        candidates = []
        rough_finish_m = nominal_duration

        for day, start_time in date_windows(
            problem.start_date, problem.end_date, problem.policy
        ):
            candidate_windows_evaluated += 1
            day_str = day.isoformat()
            iso = day.isocalendar()
            week_key = (iso.year, iso.week)

            # 1. Student conflict & cohort workload check
            same_day_cohort_exams = conflict_dates_map.get(day_str, 0)

            # Check if overlapping in time on this date
            day_states = states_by_date.get(day_str, [])
            has_time_clash = False

            cur_start_m = _minutes(start_time)
            cur_end_m = cur_start_m + rough_finish_m
            band = _band(cur_start_m)

            if day_states:
                for old in day_states:
                    old_start_m = _minutes(old["start_time_val"])
                    old_end_m = _minutes(old["end_time_val"])
                    if cur_start_m < old_end_m and old_start_m < cur_end_m:
                        # Direct student conflict
                        if old["course_id"] in conflict_course_ids or (students and students.intersection(old["student_ids"])):
                            has_time_clash = True
                            break
                        # Program / Department concurrency conflict:
                        # Prevent overlapping exam times for courses in the same department or sharing attributed programs!
                        same_dept = event_data.department_id and old.get("department_id") == event_data.department_id
                        shared_pids = event_data.attributed_program_ids and event_data.attributed_program_ids.intersection(old.get("attributed_pids", set()))
                        if same_dept or shared_pids:
                            has_time_clash = True
                            break

            # Check external pre-existing student commitments
            if not has_time_clash and problem.blocked_student_windows and students:
                for stu_id in students:
                    for ext in problem.blocked_student_windows.get(stu_id, []):
                        if ext["date"] == day:
                            ext_start_m = _minutes(ext["start_time"])
                            ext_end_m = _minutes(ext["end_time"])
                            if cur_start_m < ext_end_m and ext_start_m < cur_end_m:
                                has_time_clash = True
                                break
                    if has_time_clash:
                        break

            # Check external pre-existing cohort commitments
            if not has_time_clash and problem.blocked_cohort_windows and event_data.populations:
                for pop in event_data.populations:
                    for ext in problem.blocked_cohort_windows.get((pop.program_id, pop.level), []):
                        if ext["date"] == day:
                            ext_start_m = _minutes(ext["start_time"])
                            ext_end_m = _minutes(ext["end_time"])
                            if cur_start_m < ext_end_m and ext_start_m < cur_end_m:
                                has_time_clash = True
                                break
                    if has_time_clash:
                        break

            if has_time_clash:
                continue

            # 2. Dynamic Venue Allocation: filter out venues already busy at this time
            busy_venue_ids = set()
            for old in day_states:
                old_start_m = _minutes(old["start_time_val"])
                old_end_m = _minutes(old["end_time_val"])
                if cur_start_m < old_end_m and old_start_m < cur_end_m:
                    busy_venue_ids.update(old["venue_ids"])

            # Filter out venues pre-occupied by external published schedules
            if problem.blocked_venue_windows:
                for vid, ext_list in problem.blocked_venue_windows.items():
                    for ext in ext_list:
                        if ext["date"] == day:
                            ext_start_m = _minutes(ext["start_time"])
                            ext_end_m = _minutes(ext["end_time"])
                            if cur_start_m < ext_end_m and ext_start_m < cur_end_m:
                                busy_venue_ids.add(vid)

            free_venues = [v for v in eligible_venues if v.id not in busy_venue_ids]
            if not free_venues:
                continue

            allocation = allocate_venues(
                free_venues, count, exam_type, nominal_duration, per_student, venue_usage
            )
            if not allocation:
                continue

            actual_duration, venue_allocs = allocation
            venue_ids = {a["venue_id"] for a in venue_allocs}

            if not is_within_policy(day, start_time, actual_duration, problem.policy):
                continue

            finish_minutes = _minutes(start_time) + actual_duration

            # Verify allocated venues with actual_duration do not collide with external commitments
            has_ext_venue_conflict = False
            if problem.blocked_venue_windows:
                for a in venue_allocs:
                    vid = a["venue_id"]
                    for ext in problem.blocked_venue_windows.get(vid, []):
                        if ext["date"] == day:
                            ext_start_m = _minutes(ext["start_time"])
                            ext_end_m = _minutes(ext["end_time"])
                            if cur_start_m < ext_end_m and ext_start_m < finish_minutes:
                                has_ext_venue_conflict = True
                                break
                    if has_ext_venue_conflict:
                        break
            if has_ext_venue_conflict:
                continue
            finish = time(finish_minutes // 60, finish_minutes % 60)

            # 3. Candidate Scoring & Objective Function
            # S2: Heavily penalize multiple exams on the same day for the same cohort
            same_day_penalty = same_day_cohort_exams * 100000.0

            # Gap spacing: encourage >= 1 day off between exams for the same cohort
            min_days_gap = 999
            for prev_d in conflict_dates_list:
                gap = abs((day - prev_d).days)
                if gap < min_days_gap:
                    min_days_gap = gap

            gap_penalty = 0.0
            if min_days_gap == 0:
                gap_penalty = 50000.0
            elif min_days_gap == 1:
                gap_penalty = 500.0  # Consecutive days without rest

            # S1: Penalize > 3 exams per week for this cohort
            weekly_exams = weekly_conflict_counts.get(week_key, 0)
            weekly_penalty = max(0, weekly_exams - 3) * 50.0

            # Campus load balancing: spread exams across days to avoid overcrowding
            campus_day_penalty = campus_date_load[day_str] * 2.0

            # Balance exams across session bands throughout the day (morning, midday, afternoon)
            band_penalty = (
                day_band_load[(day_str, band)] * 30.0
                + dept_day_band_load[(day_str, event_data.department_id, band)] * 100.0
            )

            # Day progress preference (balanced over the multi-week exam period)
            day_pref = ((day - problem.start_date).days) * 0.5

            score = (
                same_day_penalty
                + gap_penalty
                + weekly_penalty
                + campus_day_penalty
                + band_penalty
                + day_pref
            )

            candidates.append((score, (day, start_time, finish, actual_duration, venue_allocs, venue_ids, band)))

            # Evaluate enough candidate windows across the whole day so all sessions are fairly considered
            if same_day_cohort_exams == 0 and min_days_gap >= 2 and len(candidates) >= 120:
                break

        if not candidates:
            unscheduled.append(
                {
                    "course_id": course_id,
                    "course_code": event_data.course_code,
                    "reason": "No conflict-free time window with sufficient venue capacity within the configured exam period.",
                }
            )
            continue

        best_cand = min(candidates, key=lambda c: c[0])[1]
        day, start_time, finish, actual_duration, venue_allocs, venue_ids, band = best_cand
        day_str = day.isoformat()

        event_payload = {
            "course_id": event_data.course_id,
            "course_code": event_data.course_code,
            "course_title": event_data.course_title,
            "course_level": event_data.course_level,
            "department_id": event_data.department_id,
            "department_name": event_data.department_name,
            "program_id": event_data.program_id,
            "program_name": event_data.program_name,
            "exam_type": exam_type,
            "student_count": count,
            "date": day_str,
            "start_time": start_time.isoformat(),
            "end_time": finish.isoformat(),
            "duration_minutes": actual_duration,
            "duration_per_student_minutes": per_student,
            "venues": venue_allocs,
            "joined_courses": [],
            "explanation": "Scheduled by student-conflict, operating-window, and venue-capacity checks.",
        }

        state_payload = {
            "course_id": event_data.course_id,
            "department_id": event_data.department_id,
            "attributed_pids": event_data.attributed_program_ids,
            "date": day_str,
            "start_time": event_payload["start_time"],
            "end_time": event_payload["end_time"],
            "start_time_val": start_time,
            "end_time_val": finish,
            "student_ids": students,
            "venue_ids": venue_ids,
        }

        events.append(event_payload)
        scheduled_states.append(state_payload)
        states_by_date[day_str].append(state_payload)
        course_placed_date[course_id] = day

        campus_date_load[day_str] += 1
        day_band_load[(day_str, band)] += 1
        dept_day_band_load[(day_str, event_data.department_id, band)] += 1
        for vid in venue_ids:
            venue_usage[vid] += 1

    return events, scheduled_states, unscheduled, candidate_windows_evaluated

