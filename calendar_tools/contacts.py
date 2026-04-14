from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import re

import yaml

CONTACTS_VERSION = 1
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTACTS_PATH = PROJECT_ROOT / ".local" / "contacts.yaml"


@dataclass(frozen=True)
class Contact:
    canonical_name: str
    email: str
    aliases: List[str]


def _normalize_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", name.casefold())
    return normalized


def _is_email(value: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value.strip()))


def _default_contacts_payload() -> dict:
    return {
        "version": CONTACTS_VERSION,
        "contacts": [],
    }


def _validate_contact(raw: dict, index: int) -> Contact:
    if not isinstance(raw, dict):
        raise ValueError(f"contacts[{index}] must be an object")

    canonical_name = raw.get("canonical_name")
    email = raw.get("email")
    aliases = raw.get("aliases", [])

    if not isinstance(canonical_name, str) or not canonical_name.strip():
        raise ValueError(f"contacts[{index}].canonical_name must be a non-empty string")
    if not isinstance(email, str) or not _is_email(email):
        raise ValueError(f"contacts[{index}].email must be a valid email")
    if not isinstance(aliases, list) or not all(isinstance(a, str) and a.strip() for a in aliases):
        raise ValueError(f"contacts[{index}].aliases must be a list of non-empty strings")

    return Contact(
        canonical_name=canonical_name.strip(),
        email=email.strip(),
        aliases=[a.strip() for a in aliases],
    )


def _load_contacts_payload(path: Path = DEFAULT_CONTACTS_PATH) -> dict:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(_default_contacts_payload(), f, sort_keys=False)
        return _default_contacts_payload()

    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}

    if not isinstance(payload, dict):
        raise ValueError("contacts file must be a YAML object")

    version = payload.get("version")
    contacts = payload.get("contacts")

    if version != CONTACTS_VERSION:
        raise ValueError(f"Unsupported contacts version: {version}. Expected {CONTACTS_VERSION}")
    if not isinstance(contacts, list):
        raise ValueError("contacts must be a list")

    return payload


def load_contacts(path: Path = DEFAULT_CONTACTS_PATH) -> List[Contact]:
    payload = _load_contacts_payload(path)
    return [_validate_contact(raw, i) for i, raw in enumerate(payload["contacts"])]


def _build_name_index(contacts: Iterable[Contact]) -> Dict[str, Contact]:
    index: Dict[str, Contact] = {}

    for contact in contacts:
        names = [contact.canonical_name, *contact.aliases]
        for name in names:
            key = _normalize_name(name)
            if not key:
                continue
            if key in index and index[key].email != contact.email:
                raise ValueError(
                    f"Duplicate alias conflict for '{name}' between "
                    f"{index[key].canonical_name} and {contact.canonical_name}"
                )
            index[key] = contact

    return index


def _parse_name_email(value: str) -> Optional[tuple]:
    """Parse 'Name <email>' syntax. Returns (name, email) or None."""
    match = re.match(r"^\s*(.+?)\s*<([^>]+)>\s*$", value)
    if match and _is_email(match.group(2)):
        return match.group(1).strip(), match.group(2).strip()
    return None


def resolve_contact_email(
    value: str,
    path: Path = DEFAULT_CONTACTS_PATH,
    auto_save: bool = False,
) -> str:
    """Resolve a contact name, email, or 'Name <email>' to an email address.

    If auto_save is True and value is 'Name <email>' with an unknown name,
    the contact is automatically added to the address book.
    """
    # Direct email — pass through
    if _is_email(value):
        return value.strip()

    # 'Name <email>' syntax — resolve or auto-save
    parsed = _parse_name_email(value)
    if parsed:
        name, email = parsed
        contacts = load_contacts(path)
        index = _build_name_index(contacts)
        normalized = _normalize_name(name)
        if normalized in index:
            return index[normalized].email
        if auto_save:
            upsert_contact(canonical_name=name, email=email, path=path)
        return email

    # Name-only lookup
    contacts = load_contacts(path)
    index = _build_name_index(contacts)
    normalized = _normalize_name(value)

    if normalized in index:
        return index[normalized].email

    raise ValueError(
        f"Unknown contact '{value}'. Either:\n"
        f"  1. Use 'Name <email>' syntax to auto-add: \"{value} <their@email.com>\"\n"
        f"  2. Add manually to {path} with canonical_name/email/aliases."
    )


def resolve_contact_emails(
    values: Iterable[str],
    path: Path = DEFAULT_CONTACTS_PATH,
    auto_save: bool = False,
) -> List[str]:
    """Resolve a list of contact names/emails. See resolve_contact_email."""
    return [resolve_contact_email(v, path=path, auto_save=auto_save) for v in values]


def upsert_contact(canonical_name: str, email: str, aliases: Optional[Iterable[str]] = None, path: Path = DEFAULT_CONTACTS_PATH) -> Contact:
    aliases = [a.strip() for a in (aliases or []) if isinstance(a, str) and a.strip()]

    if not canonical_name or not canonical_name.strip():
        raise ValueError("canonical_name must be a non-empty string")
    if not _is_email(email):
        raise ValueError("email must be valid")

    payload = _load_contacts_payload(path)
    contacts = [_validate_contact(raw, i) for i, raw in enumerate(payload["contacts"])]

    new_contact = Contact(
        canonical_name=canonical_name.strip(),
        email=email.strip(),
        aliases=aliases,
    )

    updated = False
    for idx, existing in enumerate(contacts):
        if existing.canonical_name.casefold() == new_contact.canonical_name.casefold():
            contacts[idx] = new_contact
            updated = True
            break

    if not updated:
        contacts.append(new_contact)

    _build_name_index(contacts)

    out = {
        "version": CONTACTS_VERSION,
        "contacts": [
            {
                "canonical_name": c.canonical_name,
                "email": c.email,
                "aliases": c.aliases,
            }
            for c in sorted(contacts, key=lambda c: c.canonical_name.casefold())
        ],
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(out, f, sort_keys=False)

    return new_contact
