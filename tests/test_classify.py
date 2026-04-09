import unittest
from types import SimpleNamespace

from calendar_tools.classify import classify_event


class TestClassifyEvent(unittest.TestCase):
    def _event(self, **kwargs):
        base = {
            "summary": "Untitled",
            "recurring_event_id": None,
            "calendar_id": None,
            "calendar": None,
            "organizer": None,
        }
        base.update(kwargs)
        return SimpleNamespace(**base)

    def test_keyword_match_is_routine(self):
        cfg = {"title_keywords": ["gym"], "routine_calendars": [], "recurring_is_routine": False}
        event = self._event(summary="Evening Gym")
        self.assertTrue(classify_event(event, cfg))

    def test_recurring_flag_is_respected(self):
        cfg = {"title_keywords": [], "routine_calendars": [], "recurring_is_routine": True}
        event = self._event(summary="Weekly Sync", recurring_event_id="abc123")
        self.assertTrue(classify_event(event, cfg))

    def test_routine_calendar_matches_organizer_email_fallback(self):
        organizer = SimpleNamespace(email="owner@example.com")
        cfg = {"title_keywords": [], "routine_calendars": ["owner@example.com"], "recurring_is_routine": False}
        event = self._event(summary="Any title", organizer=organizer)
        self.assertTrue(classify_event(event, cfg))

    def test_non_routine_when_no_signals_match(self):
        cfg = {"title_keywords": ["gym"], "routine_calendars": ["routines@example.com"], "recurring_is_routine": False}
        event = self._event(summary="Client review")
        self.assertFalse(classify_event(event, cfg))


if __name__ == "__main__":
    unittest.main()
