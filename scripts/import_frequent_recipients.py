#!/usr/bin/env python3
"""Import frequent Gmail recipients into .local/contacts.yaml.

Scans your Sent folder over the last N months, counts recipients on the
To:/Cc: lines, and lets you interactively pick which to add as contacts.

Auth is kept separate from the Calendar auth — the Gmail token lives at
gmail_token.pickle so the calendar flow is untouched.

Usage:
  python3 scripts/import_frequent_recipients.py
  python3 scripts/import_frequent_recipients.py --months 6 --min-count 5
  python3 scripts/import_frequent_recipients.py --top 50 --dry-run
"""

from __future__ import annotations

import argparse
import pickle
import sys
from collections import Counter
from datetime import date, timedelta
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "gmail_token.pickle"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

sys.path.insert(0, str(PROJECT_ROOT))
from calendar_tools.contacts import load_contacts, upsert_contact  # noqa: E402


def get_service():
    creds = None
    if TOKEN_PATH.exists():
        with TOKEN_PATH.open("rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(host="localhost", port=0, open_browser=True)
        with TOKEN_PATH.open("wb") as f:
            pickle.dump(creds, f)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def list_sent_message_ids(service, after_date: date):
    ids = []
    q = f"after:{after_date.strftime('%Y/%m/%d')}"
    req = service.users().messages().list(
        userId="me", labelIds=["SENT"], q=q, maxResults=500
    )
    while req is not None:
        resp = req.execute()
        for m in resp.get("messages", []):
            ids.append(m["id"])
        req = service.users().messages().list_next(req, resp)
    return ids


def _header_date(headers) -> date:
    raw = next((h["value"] for h in headers if h["name"].lower() == "date"), None)
    if not raw:
        return date.today()
    try:
        return parsedate_to_datetime(raw).date()
    except Exception:
        return date.today()


def _accumulate(headers, counts, names, last_sent, send_date):
    combined = []
    for h in headers:
        if h["name"].lower() in ("to", "cc"):
            combined.append(h.get("value", ""))
    if not combined:
        return
    for display_name, email in getaddresses(combined):
        email = email.strip().lower()
        if not email or "@" not in email:
            continue
        counts[email] += 1
        display_name = (display_name or "").strip()
        if display_name and send_date >= last_sent.get(email, date.min):
            names[email] = display_name
        if send_date > last_sent.get(email, date.min):
            last_sent[email] = send_date


def fetch_recipients(service, message_ids, user_email: str):
    counts: Counter = Counter()
    names: dict = {}
    last_sent: dict = {}
    total = len(message_ids)
    for i, mid in enumerate(message_ids, 1):
        if i == 1 or i % 100 == 0 or i == total:
            print(f"  fetched {i}/{total}", file=sys.stderr)
        msg = service.users().messages().get(
            userId="me",
            id=mid,
            format="metadata",
            metadataHeaders=["To", "Cc", "Date"],
        ).execute()
        headers = msg.get("payload", {}).get("headers", [])
        _accumulate(headers, counts, names, last_sent, _header_date(headers))
    counts.pop(user_email.lower(), None)
    names.pop(user_email.lower(), None)
    last_sent.pop(user_email.lower(), None)
    return counts, names, last_sent


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--months", type=int, default=12,
                        help="Lookback window in months (default 12)")
    parser.add_argument("--min-count", type=int, default=3,
                        help="Minimum sends to be eligible (default 3)")
    parser.add_argument("--top", type=int, default=None,
                        help="Cap ranked list at top N (default: no cap)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the ranked list and exit without writing")
    args = parser.parse_args()

    service = get_service()
    user_email = service.users().getProfile(userId="me").execute()["emailAddress"]
    print(f"Authenticated as {user_email}")

    after = date.today() - timedelta(days=30 * args.months)
    print(f"Scanning Sent mail since {after} …")
    ids = list_sent_message_ids(service, after)
    print(f"Found {len(ids)} sent messages")

    if not ids:
        return

    counts, names, last_sent = fetch_recipients(service, ids, user_email)

    ranked = [
        (email, counts[email], names.get(email, ""), last_sent.get(email))
        for email in counts
        if counts[email] >= args.min_count
    ]
    ranked.sort(key=lambda t: (-t[1], t[0]))
    if args.top:
        ranked = ranked[: args.top]

    if not ranked:
        print("No recipients met the min-count threshold.")
        return

    existing_emails = {c.email.lower() for c in load_contacts()}

    print(
        f"\nTop {len(ranked)} recipients over the last {args.months} months "
        f"(min {args.min_count} sends):\n"
    )
    print(f"{'#':>3}  {'count':>5}  {'last':>10}  {'name':<30}  email")
    print("-" * 90)
    for i, (email, count, name, last) in enumerate(ranked, 1):
        marker = " *" if email in existing_emails else ""
        display_name = name or "(no name)"
        last_str = last.isoformat() if last else "?"
        print(f"{i:>3}  {count:>5}  {last_str}  {display_name[:30]:<30}  {email}{marker}")
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
        email, _, name, _ = ranked[idx - 1]
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
