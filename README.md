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

**One-time Google Cloud setup:**

1. **Enable the Calendar API** — https://console.cloud.google.com/apis/library/calendar-json.googleapis.com → **Enable**.
2. **Configure the OAuth consent screen** — https://console.cloud.google.com/apis/credentials/consent
   - User type: **External**.
   - Fill app name + support emails; skip scopes (gcsa requests them at runtime).
   - Click **Publish app** → **Confirm**. This is critical: apps left in "Testing" expire refresh tokens every **7 days**, forcing you to re-auth weekly. Published single-user apps with sensitive scopes don't need Google verification.
3. **Create an OAuth client** — https://console.cloud.google.com/apis/credentials → **Create Credentials** → **OAuth client ID** → **Desktop app**. Copy the Client ID and Client Secret.

**Run the setup script:**

```bash
python setup_auth.py
```

Paste the Client ID and Secret when prompted. A browser tab opens for Google sign-in — if you see an "unverified app" warning, click **Advanced** → **Go to \<app name\> (unsafe)** → **Allow** (safe for your own project). `credentials.json` and `token.pickle` are written locally — both are gitignored.

**Notes:**
- The auth flow uses an ephemeral local port (OS-chosen), so it won't collide with anything already running on 8080 or another common port.
- If `token.pickle` later errors with `invalid_grant: Token has been expired or revoked`, delete it and re-run `python setup_auth.py` (or just `python -c "from calendar_tools import CalendarClient; CalendarClient()"`). If this happens on a ~7-day cadence, your consent screen is still in Testing — go back to step 2 and Publish.
- Google may prune OAuth clients after ~6 months of inactivity. If your Client ID disappears from the console, create a new one and re-run setup.

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

## Importing frequent contacts from Gmail

`scripts/import_frequent_recipients.py` scans your Sent folder over a configurable lookback, counts recipients on `To:`/`Cc:` headers, and lets you interactively pick which to add to `.local/contacts.yaml`.

**One-time setup** (separate from the Calendar auth):

1. Enable the [Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com) in the same Google Cloud project that backs your `credentials.json`.
2. First run will open a browser for a one-time consent (Gmail read-only scope). The token is saved to `gmail_token.pickle` — `*.pickle` is gitignored.

**Run:**

```bash
# Preview only — no writes
python3 scripts/import_frequent_recipients.py --dry-run

# Default: last 12 months, min 3 sends
python3 scripts/import_frequent_recipients.py

# Deeper history, stricter threshold
python3 scripts/import_frequent_recipients.py --months 60 --min-count 5

# Cap the list
python3 scripts/import_frequent_recipients.py --top 50
```

The script prints a ranked table (`#`, count, last-sent date, name, email), marks entries already in your contacts, and prompts for which rows to import. You can enter:

- individual numbers (`1,3,7`)
- ranges (`1-10,15,20-25`)
- `all` or `none`

For each selected row it calls `upsert_contact` with the Gmail display name as the canonical name and the email address. Automated / bounce addresses (unsubscribe links, bank notifications, etc.) will show up in the list — skip those by not including them in your selection. Add first-name aliases afterwards with `upsert_contact` if you want to resolve by first name.

**Flags:**

| Flag | Default | Description |
|---|---|---|
| `--months` | `12` | Lookback window in months |
| `--min-count` | `3` | Minimum sends required to appear in the list |
| `--top` | (none) | Cap the ranked list at top N |
| `--dry-run` | off | Print the table and exit without prompting |

## Importing frequent calendar collaborators

`scripts/import_calendar_contacts.py` is the calendar-side counterpart. It scans your events over a configurable lookback, counts people you share events with (as attendees or organizers), and offers the same interactive-import UX.

**No extra auth** — it reuses the existing Calendar OAuth token (`token.pickle`).

**Run:**

```bash
# Preview only
python3 scripts/import_calendar_contacts.py --dry-run

# Default: last 24 months, min 2 shared events
python3 scripts/import_calendar_contacts.py

# Wider net / stricter threshold
python3 scripts/import_calendar_contacts.py --months 36 --min-count 1
python3 scripts/import_calendar_contacts.py --min-count 5
```

The ranked table adds a `roles` column showing whether the person appeared as `organizer`, `attendee`, or both. Interactive selection uses the same syntax as the Gmail import (`1,3,7`, `1-10`, `all`, `none`).

**Flags:**

| Flag | Default | Description |
|---|---|---|
| `--months` | `24` | Lookback window in months |
| `--min-count` | `2` | Minimum shared events required to appear |
| `--top` | (none) | Cap the ranked list at top N |
| `--dry-run` | off | Print the table and exit without prompting |

Calendar scans commonly surface group aliases (e.g. `team@example.com`) and bot-style addresses alongside real people — review the list before importing.

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
