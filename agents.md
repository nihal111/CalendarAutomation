# CalendarAutomation Agent Contract

Google Calendar automation toolkit with first-class contact resolution and email invitations.

## Core Principles

- **Privacy first**: Contact data lives locally in `.local/contacts.yaml` (gitignored). Never committed to git.
- **Name-first API**: Accept contact names/aliases in write operations; resolve to emails automatically.
- **Auto-save contacts**: New contacts provided via `"Name <email>"` syntax are saved to the address book on-the-fly during event creation.
- **Timezone-safe**: All datetimes must be timezone-aware via `tzlocal.get_localzone()`. Never create naive datetimes.

## Architecture

```
calendar_tools/
  __init__.py          # Public API exports
  client.py            # CalendarClient (wraps gcsa.GoogleCalendar)
  contacts.py          # Contact schema, storage, name-to-email resolution, auto-save
  tools.py             # Calendar operations (read/write/availability)
  classify.py          # Routine vs non-routine classification
  config.py            # YAML config loading
config/
  routine_patterns.yaml  # Classification rules
  contacts.schema.yaml   # Canonical contacts schema
  contacts.example.yaml  # Template for .local/contacts.yaml
.local/
  contacts.yaml          # Personal contact store (gitignored)
tests/
  test_contacts.py       # Contact resolution, auto-save, name<email> parsing
  test_tools.py          # Attendee integration in create/update, reminders
  test_classify.py       # Routine classification
```

## Contacts Feature

### How resolution works

When you pass `attendees=["Pravin", "alice@example.com"]` to `create_event` or `update_event`:

1. **Bare email** (`alice@example.com`) → passed through directly
2. **Known name** (`Pravin`) → looked up in `.local/contacts.yaml`, returns stored email
3. **Name <email> syntax** (`Pravin <pravin@example.com>`) → if Pravin is known, returns stored email; if unknown, returns the inline email **and auto-saves Pravin to the address book**
4. **Unknown name with no email** (`Pravin`) → raises `ValueError` with guidance

The write path (`create_event`, `update_event`) always passes `auto_save=True`, so new contacts introduced via `"Name <email>"` are persisted for future use. Direct calls to `resolve_contact_email()` default to `auto_save=False` for safety.

### Address book schema

**File:** `.local/contacts.yaml`

```yaml
version: 1
contacts:
  - canonical_name: "Contact Person"
    email: "contact@example.com"
    aliases:
      - "contact"
      - "spoken variant"
```

**Rules:**
- `canonical_name` is unique (case-insensitive)
- `email` must be valid
- `aliases` are optional, recommended for nicknames and spelling variants
- Each alias must map to exactly one email across all contacts
- Lookup is case-insensitive and strips non-alphanumeric characters

### Python API

```python
from calendar_tools import (
    upsert_contact,
    resolve_contact_email,
    resolve_contact_emails,
    load_contacts,
)

# Add a contact explicitly
upsert_contact("Pravin", "pravin@example.com", aliases=["prav"])

# Resolve by name, alias, or email
resolve_contact_email("Pravin")          # → "pravin@example.com"
resolve_contact_email("prav")            # → "pravin@example.com"
resolve_contact_email("raw@example.com") # → "raw@example.com" (passthrough)

# Name <email> syntax — resolves and optionally saves
resolve_contact_email("Pravin <pravin@example.com>", auto_save=True)

# Bulk resolve
resolve_contact_emails(["Pravin", "alice@example.com"], auto_save=True)

# Inspect all contacts
contacts = load_contacts()
for c in contacts:
    print(f"{c.canonical_name} ({c.email}) aliases={c.aliases}")
```

### In calendar operations

```python
from calendar_tools import CalendarClient, create_event

client = CalendarClient()

# Known contact — resolved from address book
create_event(client, "1:1", start, end, attendees=["Pravin"])

# New contact — auto-saved to address book, then invited
create_event(client, "Intro", start, end, attendees=["NewPerson <new@example.com>"])

# Mix of known names, new contacts, and raw emails
create_event(client, "Team Sync", start, end, attendees=[
    "Pravin",                           # known → resolved
    "NewPerson <new@example.com>",      # unknown → auto-saved + resolved
    "external@example.com",             # raw email → passthrough
])
```

**All write operations automatically:**
1. Resolve contact names to emails via `.local/contacts.yaml`
2. Auto-save new `"Name <email>"` contacts to the address book
3. Coerce emails to `gcsa.attendee.Attendee` objects (required by GCSA serialization)
4. Send invitation/update emails (`send_updates="all"`)

### Error messages

Unknown name without email:
```
ValueError: Unknown contact 'Pravin'. Either:
  1. Use 'Name <email>' syntax to auto-add: "Pravin <their@email.com>"
  2. Add manually to .local/contacts.yaml with canonical_name/email/aliases.
```

### For Claude Code agents

**When the user says "invite Pravin" and Pravin is not in the address book:**
- Ask for their email, then use `"Pravin <email>"` syntax in the attendees list — this resolves and saves in one step
- Or call `upsert_contact("Pravin", "email", aliases=["prav"])` explicitly if the user also provides aliases

**When the user says "add Pravin as a contact with email pravin@example.com":**
- Call `upsert_contact("Pravin", "pravin@example.com")` directly
- Ask if there are aliases/nicknames they use for this person

**When the user says "send an invite to Pravin at pravin@example.com":**
- Use `attendees=["Pravin <pravin@example.com>"]` — this invites AND saves the contact automatically
- No separate upsert step needed

**Adding aliases to an existing contact:**
- Call `upsert_contact("Pravin", "pravin@example.com", aliases=["prav", "pravin"])` — this overwrites the entry with the same canonical_name

## Calendar Operations

### Return types (GCSA)
- `create_event()` and `update_event()` return **GCSA Event objects**, not dicts
- Access attributes directly: `event.summary`, `event.start`, `event.end`
- `get_events()` and `daily_briefing()` return enriched **dicts** with routine classification

### Error handling
- Never suppress stderr with `2>/dev/null` on untested code
- Only suppress known warnings (Python 3.9 deprecation, urllib3 OpenSSL)
- Run new code with full output first, suppress only after verifying correctness

### Reading events
| Function | Returns |
|---|---|
| `get_events(client, day=None, time_min=None, time_max=None)` | List of enriched event dicts |
| `get_non_routine_events(client, day=None)` | List of non-routine event dicts |
| `daily_briefing(client, day=None)` | Briefing dict with events, slots, routine breakdown |

### Writing events
| Function | Returns |
|---|---|
| `create_event(client, summary, start, end, **kwargs)` | GCSA Event object |
| `update_event(client, event_id, **changes)` | GCSA Event object |
| `delete_event(client, event_id)` | None |

### Availability
| Function | Returns |
|---|---|
| `find_open_slots(client, day=None, min_duration_minutes=30, work_hours=(9, 18))` | List of slot dicts with start, end, duration_minutes |

### Classification
Events are classified as **routine** or **non-routine** based on `config/routine_patterns.yaml`. Routine = background noise (commutes, gym, standups). Non-routine = needs attention.

## Authentication

### Files
- `credentials.json` — OAuth client (app identity): Client ID + Secret from Google Cloud Console. Not a true secret for Desktop-type clients per [Google's OAuth docs](https://developers.google.com/identity/protocols/oauth2/native-app), but still gitignored.
- `token.pickle` — Per-user access + refresh token. What actually authenticates API calls. Gitignored.

### Ephemeral-port auth flow
`CalendarClient` passes `authentication_flow_port=0` to `gcsa.GoogleCalendar`, which lets the OS pick a free port for the OAuth redirect server. This avoids collisions with services bound to common ports (e.g. whisper on 8080). `setup_auth.py` does the same. Desktop-type OAuth clients accept any localhost port because the registered redirect is `http://localhost` without a specific port.

### 7-day refresh token expiry (Testing mode)
If `token.pickle` dies with `invalid_grant: Token has been expired or revoked` on a ~weekly cadence, the OAuth consent screen is in **Testing** mode — Google force-expires refresh tokens every 7 days in that state. Fix by clicking **Publish app** on https://console.cloud.google.com/apis/credentials/consent. Single-user apps with sensitive scopes do not require Google verification.

### Recovery paths
- **Token expired/revoked only**: `rm token.pickle && python -c "from calendar_tools import CalendarClient; CalendarClient()"`.
- **Client also missing** (e.g. pruned by Google after long inactivity): create a new OAuth client in the Cloud Console, then `rm credentials.json token.pickle && python setup_auth.py`.

### Claude Code guidance
- If a script fails with `invalid_grant` or `RefreshError`, don't suppress it — surface the error, tell the user to re-auth, and offer to run the re-auth command for them.
- Never write `credentials.json` directly from chat unless the user explicitly asks (the client secret is low-sensitivity but still shouldn't sit in transcripts by default).

## Bulk contact imports

### Gmail frequent recipients

`scripts/import_frequent_recipients.py` scans the Sent folder, counts `To`/`Cc` recipients, and prompts for interactive import into `.local/contacts.yaml`.

- Uses a **separate** OAuth token (`gmail_token.pickle`) with `gmail.readonly` scope so the Calendar token is untouched.
- First run triggers its own browser consent; subsequent runs reuse the token.
- Depends on the Gmail API being enabled in the same Google Cloud project as `credentials.json`.
- Automated addresses (`unsubscribe@`, `bounce@`, transactional senders) surface in the ranked list — skip by not selecting them during the interactive prompt.
- Contacts are added via `upsert_contact` using the Gmail display name as `canonical_name`. First-name aliases are **not** added automatically — call `upsert_contact(name, email, aliases=[first_name])` afterwards if the user refers to someone by first name.

**Agent guidance:**

- When the user asks to "import my frequent contacts" or similar, run with `--dry-run` first, show the ranked list, and confirm which rows to import before writing.
- Before importing, flag ambiguous rows: multiple entries with the same first name, addresses that look like the user's own alternate accounts, and automated/bot addresses.
- After importing, offer to add aliases for people the user refers to by first name.

### Calendar collaborators

`scripts/import_calendar_contacts.py` scans events over a lookback window and ranks attendees + organizers by shared-event count. Drops into the same interactive-selection flow as the Gmail importer.

- Reuses the existing Calendar `token.pickle` — **no extra OAuth consent** needed.
- Each row is tagged with a `roles` set: `organizer`, `attendee`, or both.
- Calendar feeds commonly contain group aliases and bot senders (meeting-room calendars, scheduling tools, shared team inboxes). Flag these during review before importing.
- Default thresholds are looser than the Gmail import (`--months 24`, `--min-count 2`) because calendar events are fewer in volume than emails.

**Agent guidance:**

- Always run `--dry-run` first and surface the ranked list.
- When multiple people map to the same email (rare) or one person maps to multiple emails (common across work/personal addresses), ask the user which to keep as canonical and which to add as aliases.
- If the Gmail-import and calendar-import both find the same person under different display names or emails, merge manually — call `upsert_contact` with the preferred canonical and list the alternate email as a second contact or surface the conflict to the user.

## Testing

```bash
cd ~/Code/CalendarAutomation
python3 -m unittest discover tests/ -v
```

## Security and Privacy

- `.local/contacts.yaml` is gitignored — never committed
- `credentials.json` and `token.pickle` are gitignored
- All documentation uses placeholder names/emails (`Contact Person`, `example.com`)
- Contact emails appear only in error messages, not in logs
