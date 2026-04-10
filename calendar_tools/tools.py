from datetime import datetime, date, time, timedelta
from gcsa.attendee import Attendee
from gcsa.event import Event
from tzlocal import get_localzone

from calendar_tools.client import CalendarClient
from calendar_tools.classify import enrich_event, classify_event
from calendar_tools.config import load_routine_config
from calendar_tools.contacts import resolve_contact_emails


def _ensure_datetime(d):
    """Convert a date to datetime if needed (start of day). Always returns timezone-aware."""
    if isinstance(d, datetime):
        if d.tzinfo is None:
            return d.replace(tzinfo=get_localzone())
        return d
    return datetime.combine(d, time.min, tzinfo=get_localzone())


def _end_of_day(d):
    """Get end-of-day datetime for a date. Always returns timezone-aware."""
    if isinstance(d, datetime):
        d = d.date()
    return datetime.combine(d, time(23, 59, 59), tzinfo=get_localzone())


def _now_local():
    """Current system time in local timezone."""
    return datetime.now(get_localzone())


# ── Read operations ──────────────────────────────────────────────


def get_events(client: CalendarClient, day: date = None, time_min=None, time_max=None):
    """Fetch events for a given day or time range.

    Returns a list of enriched event dicts with routine classification.
    """
    if day and not (time_min or time_max):
        time_min = _ensure_datetime(day)
        time_max = _end_of_day(day)
    elif not time_min:
        time_min = _ensure_datetime(date.today())
        time_max = _end_of_day(date.today())

    events = list(client.calendar.get_events(time_min=time_min, time_max=time_max, order_by="startTime", single_events=True))
    return [enrich_event(e) for e in events]


def get_non_routine_events(client: CalendarClient, day: date = None, **kwargs):
    """Fetch only non-routine events for a day."""
    all_events = get_events(client, day=day, **kwargs)
    return [e for e in all_events if not e["routine"]]


# ── Write operations ─────────────────────────────────────────────


def _resolve_attendees(kwargs: dict):
    attendees = kwargs.get("attendees")
    if not attendees:
        return kwargs

    if not isinstance(attendees, list):
        raise ValueError("attendees must be a list of contact names and/or email addresses")

    resolved = resolve_contact_emails(attendees)
    out = dict(kwargs)
    out["attendees"] = resolved
    return out


def _coerce_attendees_to_objects(value):
    if not isinstance(value, list):
        raise ValueError("attendees must be a list of contact names and/or email addresses")
    return [a if isinstance(a, Attendee) else Attendee(a) for a in value]


def create_event(client: CalendarClient, summary: str, start, end, **kwargs):
    """Create a new calendar event.

    Args:
        summary: Event title
        start: datetime for event start
        end: datetime for event end
        **kwargs: Additional Event fields (location, description, etc.)
    """
    kwargs = _resolve_attendees(kwargs)
    if "attendees" in kwargs:
        kwargs["attendees"] = _coerce_attendees_to_objects(kwargs["attendees"])
    if "reminders" not in kwargs:
        kwargs["reminders"] = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 30}],
        }
    event = Event(summary=summary, start=start, end=end, **kwargs)
    return client.calendar.add_event(event, send_updates="all")


def update_event(client: CalendarClient, event_id: str, **changes):
    """Update an existing event.

    Fetches the event by ID, applies changes, and saves.

    Args:
        event_id: The Google Calendar event ID
        **changes: Fields to update (summary, start, end, location, description, etc.)
    """
    changes = _resolve_attendees(changes)
    if "attendees" in changes:
        changes["attendees"] = _coerce_attendees_to_objects(changes["attendees"])
    event = client.calendar.get_event(event_id)
    for key, value in changes.items():
        setattr(event, key, value)
    return client.calendar.update_event(event, send_updates="all")


def delete_event(client: CalendarClient, event_id: str):
    """Delete an event by ID."""
    client.calendar.delete_event(event_id)


# ── Availability operations ──────────────────────────────────────


def find_open_slots(
    client: CalendarClient,
    day: date = None,
    time_min=None,
    time_max=None,
    min_duration_minutes: int = 30,
    work_hours=(9, 18),
    from_now: bool = False,
):
    """Find open time slots in the calendar.

    Args:
        day: The date to search (defaults to today)
        time_min/time_max: Override for custom range
        min_duration_minutes: Minimum slot length to return
        work_hours: Tuple of (start_hour, end_hour) to constrain search

    Returns:
        List of dicts with 'start' and 'end' datetimes and 'duration_minutes'.
    """
    if day and not (time_min or time_max):
        target_date = day
    elif time_min:
        target_date = time_min.date() if isinstance(time_min, datetime) else time_min
    else:
        target_date = date.today()

    local_tz = get_localzone()
    if not time_min:
        time_min = datetime.combine(target_date, time(work_hours[0], 0), tzinfo=local_tz)
    if not time_max:
        time_max = datetime.combine(target_date, time(work_hours[1], 0), tzinfo=local_tz)

    if from_now and target_date == date.today():
        time_min = max(time_min, _now_local())

    events = list(client.calendar.get_events(time_min=time_min, time_max=time_max, order_by="startTime", single_events=True))

    # Walk through the day and find gaps
    slots = []
    cursor = time_min

    for event in events:
        event_start = _ensure_datetime(event.start)
        event_end = _ensure_datetime(event.end)

        # Clamp to our search window
        event_start = max(event_start, time_min)
        event_end = min(event_end, time_max)

        if event_start > cursor:
            gap_minutes = (event_start - cursor).total_seconds() / 60
            if gap_minutes >= min_duration_minutes:
                slots.append({
                    "start": cursor,
                    "end": event_start,
                    "duration_minutes": int(gap_minutes),
                })

        cursor = max(cursor, event_end)

    # Check for gap after last event
    if cursor < time_max:
        gap_minutes = (time_max - cursor).total_seconds() / 60
        if gap_minutes >= min_duration_minutes:
            slots.append({
                "start": cursor,
                "end": time_max,
                "duration_minutes": int(gap_minutes),
            })

    return slots


# ── High-level wrappers ──────────────────────────────────────────


def daily_briefing(client: CalendarClient, day: date = None):
    """Generate a structured daily briefing.

    Returns a dict with:
        - all_events: all events for the day
        - routine: routine events
        - non_routine: non-routine events that need attention
        - open_slots: available time windows
    """
    day = day or date.today()
    if day == date.today():
        now = _now_local()
        all_events = get_events(client, time_min=now, time_max=_end_of_day(day))
        open_slots = find_open_slots(client, day=day, from_now=True)
    else:
        all_events = get_events(client, day=day)
        open_slots = find_open_slots(client, day=day)

    routine = [e for e in all_events if e["routine"]]
    non_routine = [e for e in all_events if not e["routine"]]

    return {
        "date": day,
        "total_events": len(all_events),
        "all_events": all_events,
        "routine": routine,
        "non_routine": non_routine,
        "open_slots": open_slots,
    }
