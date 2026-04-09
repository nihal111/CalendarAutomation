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
    routine_calendars = cfg.get("routine_calendars", [])

    is_routine = False

    # Check title keywords
    for keyword in keywords:
        if keyword in title:
            is_routine = True
            break

    # Check if the event's calendar is marked as entirely routine
    if hasattr(event, "calendar_id") and event.calendar_id in routine_calendars:
        is_routine = True

    return is_routine


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
