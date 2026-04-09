# CalendarAutomation

Google Calendar automation tools used by the SecondBrain calendar assistant.

## Setup

```bash
pip3 install -r requirements.txt
```

Requires `credentials.json` and `token.pickle` at the project root for Google Calendar OAuth. Run `setup_auth.py` to generate `token.pickle` if missing.

## Usage

```python
from calendar_tools import CalendarClient, daily_briefing, get_events, find_open_slots, create_event

client = CalendarClient()
briefing = daily_briefing(client)
```

## Architecture

- `calendar_tools/client.py` — `CalendarClient` wrapping `gcsa.GoogleCalendar`
- `calendar_tools/tools.py` — All calendar operations (read/write/availability)
- `calendar_tools/classify.py` — Routine vs non-routine event classification
- `calendar_tools/config.py` — Configuration loading
- `config/` — YAML config for routine keywords etc.

## Known constraints

- All datetimes must be timezone-aware. The `_ensure_datetime()` and `_end_of_day()` helpers in `tools.py` enforce this using `tzlocal`. Never create naive datetimes when interacting with Google Calendar — gcsa returns aware datetimes and comparisons will fail.
- Python 3.9 works but shows deprecation warnings from google-auth. Non-blocking.
