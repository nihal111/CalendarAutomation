#!/usr/bin/env python3
"""Import frequent calendar collaborators into .local/contacts.yaml.

Scans events over the last N months, counts who you invite (attendees on
events you organized) and who invites you (organizers of events you
attend), then lets you interactively pick which to add as contacts.

Reuses the existing Calendar OAuth token — no extra consent needed.

Usage:
  python3 scripts/import_calendar_contacts.py --dry-run
  python3 scripts/import_calendar_contacts.py --months 24 --min-count 2
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from tzlocal import get_localzone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from calendar_tools import CalendarClient  # noqa: E402
from calendar_tools.contacts import load_contacts, upsert_contact  # noqa: E402


def _attr(obj, *names, default=None):
    for n in names:
        v = getattr(obj, n, None)
        if v:
            return v
    return default


def _event_date(event):
    s = getattr(event, "start", None)
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    return None


def _extract_people(event, skip_email: str):
    """Yield (email, display_name, role) tuples from an event."""
    organizer = getattr(event, "organizer", None)
    if organizer:
        email = _attr(organizer, "email", default="")
        if email:
            email = email.strip().lower()
            if email and email != skip_email:
                yield email, _attr(organizer, "display_name", default="") or "", "organizer"

    attendees = getattr(event, "attendees", None) or []
    for a in attendees:
        email = _attr(a, "email", default="")
        if not email:
            continue
        email = email.strip().lower()
        if not email or email == skip_email:
            continue
        yield email, _attr(a, "display_name", default="") or "", "attendee"


def scan_events(client: CalendarClient, months: int, skip_email: str):
    tz = get_localzone()
    time_max = datetime.now(tz)
    time_min = time_max - timedelta(days=30 * months)

    counts: Counter = Counter()
    names: dict = {}
    last_seen: dict = {}
    roles: dict = {}

    total = 0
    print(f"Scanning events from {time_min.date()} to {time_max.date()} …", file=sys.stderr)
    for event in client.calendar.get_events(
        time_min=time_min,
        time_max=time_max,
        single_events=True,
        order_by="startTime",
    ):
        total += 1
        if total % 200 == 0:
            print(f"  scanned {total} events", file=sys.stderr)
        ev_date = _event_date(event) or date.today()
        for email, display_name, role in _extract_people(event, skip_email):
            counts[email] += 1
            display_name = display_name.strip()
            if display_name and ev_date >= last_seen.get(email, date.min):
                names[email] = display_name
            if ev_date > last_seen.get(email, date.min):
                last_seen[email] = ev_date
            roles.setdefault(email, set()).add(role)
    print(f"  scanned {total} events total", file=sys.stderr)
    return counts, names, last_seen, roles


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--months", type=int, default=24,
                        help="Lookback window in months (default 24)")
    parser.add_argument("--min-count", type=int, default=2,
                        help="Minimum events shared to appear (default 2)")
    parser.add_argument("--top", type=int, default=None,
                        help="Cap ranked list at top N (default: no cap)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the ranked list and exit without writing")
    args = parser.parse_args()

    client = CalendarClient()
    user_email = getattr(client.calendar, "default_calendar", None) or "primary"
    # gcsa exposes the authenticated email via calendar.get_calendar("primary")
    try:
        primary = client.calendar.get_calendar("primary")
        user_email = getattr(primary, "calendar_id", None) or user_email
    except Exception:
        pass
    skip_email = (user_email or "").strip().lower()
    print(f"Authenticated calendar: {skip_email or '(unknown)'}")

    counts, names, last_seen, roles = scan_events(client, args.months, skip_email)

    ranked = [
        (email, counts[email], names.get(email, ""), last_seen.get(email), roles.get(email, set()))
        for email in counts
        if counts[email] >= args.min_count
    ]
    ranked.sort(key=lambda t: (-t[1], t[0]))
    if args.top:
        ranked = ranked[: args.top]

    if not ranked:
        print("No calendar collaborators met the min-count threshold.")
        return

    existing_emails = {c.email.lower() for c in load_contacts()}

    print(
        f"\nTop {len(ranked)} calendar collaborators over the last {args.months} months "
        f"(min {args.min_count} shared events):\n"
    )
    print(f"{'#':>3}  {'count':>5}  {'last':>10}  {'roles':<18}  {'name':<28}  email")
    print("-" * 110)
    for i, (email, count, name, last, role_set) in enumerate(ranked, 1):
        marker = " *" if email in existing_emails else ""
        display_name = name or "(no name)"
        last_str = last.isoformat() if last else "?"
        roles_str = ",".join(sorted(role_set))
        print(
            f"{i:>3}  {count:>5}  {last_str}  {roles_str:<18}  "
            f"{display_name[:28]:<28}  {email}{marker}"
        )
    print("\n* = email already in contacts.yaml (will be skipped)")

    if args.dry_run:
        return

    raw = input(
        "\nImport which? Enter comma-separated #s, ranges (e.g. 1-5,8,12), "
        "'all', or 'none': "
    ).strip().lower()
    if not raw or raw == "none":
        print("Nothing imported.")
        return

    chosen: set = set()
    if raw == "all":
        chosen = set(range(1, len(ranked) + 1))
    else:
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            if "-" in token:
                try:
                    a, b = token.split("-", 1)
                    for x in range(int(a), int(b) + 1):
                        chosen.add(x)
                except ValueError:
                    print(f"  ignoring invalid range '{token}'")
            else:
                try:
                    chosen.add(int(token))
                except ValueError:
                    print(f"  ignoring invalid '{token}'")

    added = 0
    skipped = 0
    for idx in sorted(chosen):
        if idx < 1 or idx > len(ranked):
            continue
        email, _, name, _, _ = ranked[idx - 1]
        if email in existing_emails:
            skipped += 1
            continue
        canonical = name.strip() or email.split("@")[0]
        try:
            upsert_contact(canonical_name=canonical, email=email)
            print(f"  added {canonical} <{email}>")
            added += 1
        except ValueError as e:
            print(f"  skip {email}: {e}")
            skipped += 1
    print(f"\nDone. added={added} skipped={skipped}")


if __name__ == "__main__":
    main()
