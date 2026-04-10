import unittest
from datetime import date, datetime, time
from unittest.mock import Mock, patch

from gcsa.attendee import Attendee
from tzlocal import get_localzone

from calendar_tools.tools import create_event, daily_briefing, update_event, _end_of_day


class TestDailyBriefing(unittest.TestCase):
    def test_today_briefing_uses_now_as_lower_bound(self):
        client = object()
        today = date.today()
        now = datetime.combine(today, time(11, 0), tzinfo=get_localzone())

        with patch("calendar_tools.tools._now_local", return_value=now), patch(
            "calendar_tools.tools.get_events", return_value=[]
        ) as mock_get_events, patch("calendar_tools.tools.find_open_slots", return_value=[]) as mock_find_open_slots:
            daily_briefing(client, day=today)

        mock_get_events.assert_called_once_with(client, time_min=now, time_max=_end_of_day(today))
        mock_find_open_slots.assert_called_once_with(client, day=today, from_now=True)

    def test_non_today_briefing_keeps_full_day_behavior(self):
        client = object()
        target_day = date(2026, 4, 10)

        with patch("calendar_tools.tools.get_events", return_value=[]) as mock_get_events, patch(
            "calendar_tools.tools.find_open_slots", return_value=[]
        ) as mock_find_open_slots:
            daily_briefing(client, day=target_day)

        mock_get_events.assert_called_once_with(client, day=target_day)
        mock_find_open_slots.assert_called_once_with(client, day=target_day)


class TestAttendeeResolutionInWrites(unittest.TestCase):
    def test_create_event_resolves_attendees(self):
        client = Mock()
        start = datetime(2026, 4, 10, 9, 0, tzinfo=get_localzone())
        end = datetime(2026, 4, 10, 10, 0, tzinfo=get_localzone())

        with patch("calendar_tools.tools.resolve_contact_emails", return_value=["contact@example.com"]) as resolver, patch(
            "calendar_tools.tools.Event"
        ) as event_cls:
            create_event(
                client,
                summary="Game Night",
                start=start,
                end=end,
                attendees=["Contact Person"],
            )

        resolver.assert_called_once_with(["Contact Person"])
        event_cls.assert_called_once()
        _, kwargs = event_cls.call_args
        self.assertEqual(len(kwargs["attendees"]), 1)
        self.assertIsInstance(kwargs["attendees"][0], Attendee)
        self.assertEqual(kwargs["attendees"][0].email, "contact@example.com")
        client.calendar.add_event.assert_called_once()
        _, add_kwargs = client.calendar.add_event.call_args
        self.assertEqual(add_kwargs["send_updates"], "all")

    def test_update_event_resolves_attendees(self):
        event = Mock()
        client = Mock()
        client.calendar.get_event.return_value = event

        with patch("calendar_tools.tools.resolve_contact_emails", return_value=["contact@example.com"]) as resolver:
            update_event(client, "event123", attendees=["Contact Person"])

        resolver.assert_called_once_with(["Contact Person"])
        self.assertEqual(len(event.attendees), 1)
        self.assertIsInstance(event.attendees[0], Attendee)
        self.assertEqual(event.attendees[0].email, "contact@example.com")
        client.calendar.update_event.assert_called_once_with(event, send_updates="all")

    def test_create_event_sets_default_30_minute_popup_reminder(self):
        client = Mock()
        start = datetime(2026, 4, 10, 9, 0, tzinfo=get_localzone())
        end = datetime(2026, 4, 10, 10, 0, tzinfo=get_localzone())

        with patch("calendar_tools.tools.Event") as event_cls:
            create_event(client, summary="Deep Work", start=start, end=end)

        _, kwargs = event_cls.call_args
        self.assertEqual(
            kwargs["reminders"],
            {"useDefault": False, "overrides": [{"method": "popup", "minutes": 30}]},
        )

    def test_create_event_preserves_explicit_reminders(self):
        client = Mock()
        start = datetime(2026, 4, 10, 9, 0, tzinfo=get_localzone())
        end = datetime(2026, 4, 10, 10, 0, tzinfo=get_localzone())
        custom_reminders = {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]}

        with patch("calendar_tools.tools.Event") as event_cls:
            create_event(
                client,
                summary="Deep Work",
                start=start,
                end=end,
                reminders=custom_reminders,
            )

        _, kwargs = event_cls.call_args
        self.assertEqual(kwargs["reminders"], custom_reminders)


if __name__ == "__main__":
    unittest.main()
