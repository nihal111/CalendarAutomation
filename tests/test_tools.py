import unittest
from datetime import date, datetime, time
from unittest.mock import patch

from tzlocal import get_localzone

from calendar_tools.tools import daily_briefing, _end_of_day


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


if __name__ == "__main__":
    unittest.main()
