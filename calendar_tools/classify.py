from calendar_tools.config import load_routine_config

_config = None


def _get_config():
    global _config
    if _config is None:
        _config = load_routine_config()
    return _config


def classify_event(event, config=None):
    """Tag an event as routine or non-routine based on config patterns.

    Returns a dict with event data plus a 'routine' boolean.
    """
    cfg = config or _get_config()
    title = (event.summary or "").lower()
    keywords = [k.lower() for k in cfg.get("title_keywords", [])]
    routine_calendars = {str(c).lower() for c in cfg.get("routine_calendars", [])}
    recurring_is_routine = bool(cfg.get("recurring_is_routine", False))

    # 1) Title keyword match.
    if any(keyword in title for keyword in keywords):
        return True

    # 2) Optionally treat all recurring events as routine.
    if recurring_is_routine and getattr(event, "recurring_event_id", None):
        return True

    # 3) Match routine calendars via any available event calendar identifier.
    event_calendar_ids = _extract_event_calendar_identifiers(event)
    return any(cid in routine_calendars for cid in event_calendar_ids)


def _extract_event_calendar_identifiers(event):
    """Return normalized identifiers that can represent an event's calendar."""
    identifiers = set()

    calendar_id = getattr(event, "calendar_id", None)
    if calendar_id:
        identifiers.add(str(calendar_id).lower())

    calendar = getattr(event, "calendar", None)
    if isinstance(calendar, str):
        identifiers.add(calendar.lower())
    elif calendar is not None:
        for attr in ("id", "email", "name"):
            value = getattr(calendar, attr, None)
            if value:
                identifiers.add(str(value).lower())

    organizer = getattr(event, "organizer", None)
    organizer_email = getattr(organizer, "email", None)
    if organizer_email:
        identifiers.add(str(organizer_email).lower())

    return identifiers


def enrich_event(event, config=None):
    """Return a dict representation of an event with routine classification."""
    return {
        "id": event.event_id,
        "summary": event.summary,
        "start": event.start,
        "end": event.end,
        "location": getattr(event, "location", None),
        "description": getattr(event, "description", None),
        "recurring": event.recurring_event_id is not None if hasattr(event, "recurring_event_id") else False,
        "routine": classify_event(event, config),
        "_raw": event,
    }
