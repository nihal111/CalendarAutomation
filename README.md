# CalendarAutomation

A Python toolkit for reading, writing, and reasoning about your Google Calendar. Built to power a personal calendar assistant — get daily briefings, find open slots, create events, and automatically classify routine vs. important events.

## Features

- **Daily briefings** — Get a structured overview of your day: events, open slots, and what needs your attention.
- **Smart availability** — Find free windows in your schedule, constrained to your working hours.
- **Event management** — Create, update, and delete Google Calendar events programmatically.
- **Routine classification** — Automatically tags events like gym, commute, and standup as routine so you can focus on what matters. Fully configurable via YAML.

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up Google Calendar access

You'll need a Google Cloud project with the [Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com) enabled.

```bash
python setup_auth.py
```

This walks you through pasting your OAuth client ID and secret, then opens a browser for Google sign-in. It generates `credentials.json` and `token.pickle` locally — both are gitignored and never leave your machine.

### 3. Use it

```python
from calendar_tools import CalendarClient, daily_briefing, find_open_slots, create_event

client = CalendarClient()

# What does my day look like?
briefing = daily_briefing(client)

# When am I free?
slots = find_open_slots(client, min_duration_minutes=60)

# Block off focus time
create_event(client, "Deep work", start=slots[0]["start"], end=slots[0]["end"])
```

## API Reference

### Reading events

| Function | Description |
|---|---|
| `get_events(client, day=None, time_min=None, time_max=None)` | Fetch all events for a day or time range. Returns enriched dicts with routine classification. |
| `get_non_routine_events(client, day=None)` | Fetch only non-routine events — filters out commutes, gym, standups, etc. |
| `daily_briefing(client, day=None)` | Structured briefing with all events, routine/non-routine breakdown, and open slots. |

### Writing events

| Function | Description |
|---|---|
| `create_event(client, summary, start, end, **kwargs)` | Create a new event. Supports `location`, `description`, and other Google Calendar fields. |
| `update_event(client, event_id, **changes)` | Update an existing event by ID. |
| `delete_event(client, event_id)` | Delete an event by ID. |

### Availability

| Function | Description |
|---|---|
| `find_open_slots(client, day=None, min_duration_minutes=30, work_hours=(9, 18))` | Find free windows in the calendar within working hours. Returns slots with start, end, and duration. |

### Classification

Events are classified as **routine** or **non-routine** based on configurable patterns in `config/routine_patterns.yaml`. Routine events include things like commutes, gym sessions, and daily standups — they're background noise. Non-routine events are the ones that deserve your attention.

You can customize the classification by editing the YAML config:

```yaml
routine:
  title_keywords:
    - "shuttle"
    - "commute"
    - "gym"
    - "standup"
    # Add your own...

  routine_calendars: []
    # Add calendar IDs that are entirely routine
```

## Project Structure

```
CalendarAutomation/
  calendar_tools/
    __init__.py          # Public API exports
    client.py            # CalendarClient (wraps gcsa)
    tools.py             # All calendar operations
    classify.py          # Routine vs non-routine classification
    config.py            # YAML config loading
  config/
    routine_patterns.yaml  # Classification rules
  setup_auth.py          # Interactive OAuth setup
  requirements.txt
```

## Security

Credentials (`credentials.json`, `token.pickle`) are gitignored and never committed. The `.gitignore` also excludes `.env` files and virtual environments. No secrets are stored in code or git history.
