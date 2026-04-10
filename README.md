# CalendarAutomation

A Python toolkit for reading, writing, and reasoning about your Google Calendar. Built to power a personal calendar assistant — get daily briefings, find open slots, create events, and automatically classify routine vs. important events.

> Note: Documentation examples must use placeholder names/emails only (no real personal identifiers).

## Features

- **Daily briefings** — Get a structured overview of your day: events, open slots, and what needs your attention.
- **Smart availability** — Find free windows in your schedule, constrained to your working hours.
- **Event management** — Create, update, and delete Google Calendar events programmatically.
- **Contact resolution** — Use attendee names or aliases in write operations; names resolve to emails via local contacts.
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

# Names resolve through .local/contacts.yaml
create_event(
    client,
    "Game Night",
    start=slots[0]["start"],
    end=slots[0]["end"],
    attendees=["Contact Person"],  # resolves to contact@example.com
)
```

## API Reference

### Reading events

| Function | Description |
|---|---|
| `get_events(client, day=None, time_min=None, time_max=None)` | Fetch all events for a day or time range. Returns enriched dicts with routine classification. |
| `get_non_routine_events(client, day=None)` | Fetch only non-routine events — filters out commutes, gym, standups, etc. |
| `daily_briefing(client, day=None)` | Structured briefing with all events, routine/non-routine breakdown, and open slots. For `day=today`, includes only ongoing/upcoming events. |

### Writing events

| Function | Description |
|---|---|
| `create_event(client, summary, start, end, **kwargs)` | Create a new event. Supports `location`, `description`, and other Google Calendar fields. `attendees` can be emails or contact names/aliases. Invite emails are sent (`send_updates="all"`). |
| `update_event(client, event_id, **changes)` | Update an existing event by ID. `attendees` can be emails or contact names/aliases. Invite/update emails are sent (`send_updates="all"`). |
| `delete_event(client, event_id)` | Delete an event by ID. |

### Contacts

Contact handling is first-class in code, while private contact data stays local.

- Logic and schema are in-repo:
  - `calendar_tools/contacts.py`
  - `config/contacts.schema.yaml`
  - `config/contacts.example.yaml`
- Personal contacts are local-only:
  - `.local/contacts.yaml` (gitignored)

Schema:

```yaml
version: 1
contacts:
  - canonical_name: "Contact Person"
    email: "contact@example.com"
    aliases:
      - "contact"
```

Public API:

- `upsert_contact(canonical_name, email, aliases=None)` to add/update contacts.
- `resolve_contact_email(name_or_email)` and `resolve_contact_emails([...])` for name lookup.
- `load_contacts()` to inspect configured contacts.

Write-path details:

- Contact names are resolved to emails via `.local/contacts.yaml`.
- Resolved attendee emails are converted to `gcsa.attendee.Attendee` objects before writes.
- This conversion is required for `update_event(...)` because GCSA update serialization expects attendee objects, not raw email strings.

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
    contacts.py          # Contact schema, storage, and name-to-email resolution
    tools.py             # All calendar operations
    classify.py          # Routine vs non-routine classification
    config.py            # YAML config loading
  config/
    routine_patterns.yaml  # Classification rules
    contacts.schema.yaml   # Canonical contacts schema
    contacts.example.yaml  # Example contacts file
  setup_auth.py          # Interactive OAuth setup
  requirements.txt
```

## Security

Credentials (`credentials.json`, `token.pickle`) are gitignored and never committed. The `.gitignore` also excludes `.env` files and virtual environments. No secrets are stored in code or git history.
