# Agents Notes

This repository supports contact name resolution for calendar attendees.

Privacy note: any examples in docs should use placeholder names/emails only.

## Where to look

- Contact logic and schema handling: `calendar_tools/contacts.py`
- Attendee resolution in write wrappers: `calendar_tools/tools.py`
- Canonical schema/example: `config/contacts.schema.yaml`, `config/contacts.example.yaml`
- Private contact data (local only): `.local/contacts.yaml` (gitignored)

## Behavior contract

- `create_event(...)` and `update_event(...)` accept `attendees` as either raw emails or names.
- Names are normalized (case/punctuation-insensitive) and matched against `canonical_name` + `aliases`.
- Unknown names raise a `ValueError` so the assistant can request clarification.
- Resolved attendee emails are coerced to `gcsa.attendee.Attendee` objects before write calls.
- `create_event(...)` and `update_event(...)` both call Google Calendar with `send_updates="all"` so invite/update emails are dispatched.

## Managing contacts

Use `upsert_contact(canonical_name, email, aliases=None)` from `calendar_tools` to add/update entries.
