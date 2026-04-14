import tempfile
import unittest
from pathlib import Path

import yaml

from calendar_tools.contacts import (
    load_contacts,
    resolve_contact_email,
    resolve_contact_emails,
    upsert_contact,
)


class TestContacts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.contacts_path = Path(self.tmp.name) / "contacts.yaml"
        payload = {
            "version": 1,
            "contacts": [
                {
                    "canonical_name": "Lavanya",
                    "email": "lavanya@example.com",
                    "aliases": ["lav"],
                }
            ],
        }
        with self.contacts_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, sort_keys=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_alias(self):
        self.assertEqual(
            resolve_contact_email("Lavanya", path=self.contacts_path),
            "lavanya@example.com",
        )

    def test_resolve_case_insensitive(self):
        self.assertEqual(
            resolve_contact_email("lavanya", path=self.contacts_path),
            "lavanya@example.com",
        )

    def test_resolve_alias_shortname(self):
        self.assertEqual(
            resolve_contact_email("lav", path=self.contacts_path),
            "lavanya@example.com",
        )

    def test_resolve_bare_email_passthrough(self):
        self.assertEqual(
            resolve_contact_email("someone@example.com", path=self.contacts_path),
            "someone@example.com",
        )

    def test_unknown_name_raises(self):
        with self.assertRaises(ValueError):
            resolve_contact_email("Unknown Person", path=self.contacts_path)

    def test_upsert_contact_updates_existing(self):
        upsert_contact(
            canonical_name="Lavanya",
            email="lavanya@example.com",
            aliases=["lav"],
            path=self.contacts_path,
        )
        contacts = load_contacts(path=self.contacts_path)
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0].aliases, ["lav"])


class TestNameEmailSyntax(unittest.TestCase):
    """Tests for 'Name <email>' parsing and auto-save behavior."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.contacts_path = Path(self.tmp.name) / "contacts.yaml"
        payload = {
            "version": 1,
            "contacts": [
                {
                    "canonical_name": "Lavanya",
                    "email": "lavanya@example.com",
                    "aliases": ["lav"],
                }
            ],
        }
        with self.contacts_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, sort_keys=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_name_email_syntax_resolves(self):
        email = resolve_contact_email(
            "Pravin <pravin@example.com>", path=self.contacts_path
        )
        self.assertEqual(email, "pravin@example.com")

    def test_name_email_syntax_no_auto_save_by_default(self):
        resolve_contact_email(
            "Pravin <pravin@example.com>", path=self.contacts_path
        )
        contacts = load_contacts(path=self.contacts_path)
        self.assertEqual(len(contacts), 1)  # only Lavanya

    def test_name_email_syntax_auto_save(self):
        resolve_contact_email(
            "Pravin <pravin@example.com>",
            path=self.contacts_path,
            auto_save=True,
        )
        contacts = load_contacts(path=self.contacts_path)
        self.assertEqual(len(contacts), 2)
        names = {c.canonical_name for c in contacts}
        self.assertIn("Pravin", names)

    def test_name_email_syntax_existing_contact_uses_stored_email(self):
        """If 'Lavanya <newemail@example.com>' is passed but Lavanya is already
        known, return the stored email (not the inline one)."""
        email = resolve_contact_email(
            "Lavanya <newemail@example.com>", path=self.contacts_path
        )
        self.assertEqual(email, "lavanya@example.com")

    def test_auto_save_persists_for_future_lookups(self):
        resolve_contact_email(
            "Pravin <pravin@example.com>",
            path=self.contacts_path,
            auto_save=True,
        )
        # Now resolve by name only — should work
        email = resolve_contact_email("Pravin", path=self.contacts_path)
        self.assertEqual(email, "pravin@example.com")

    def test_resolve_multiple_with_mixed_formats(self):
        emails = resolve_contact_emails(
            ["Lavanya", "Pravin <pravin@example.com>", "raw@example.com"],
            path=self.contacts_path,
            auto_save=True,
        )
        self.assertEqual(emails, [
            "lavanya@example.com",
            "pravin@example.com",
            "raw@example.com",
        ])
        # Pravin should now be saved
        contacts = load_contacts(path=self.contacts_path)
        self.assertEqual(len(contacts), 2)


if __name__ == "__main__":
    unittest.main()
