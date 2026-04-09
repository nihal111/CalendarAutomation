import os

from gcsa.google_calendar import GoogleCalendar

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_CREDENTIALS = os.path.join(_PROJECT_ROOT, "credentials.json")
_DEFAULT_TOKEN = os.path.join(_PROJECT_ROOT, "token.pickle")


class CalendarClient:
    """Thin wrapper around gcsa's GoogleCalendar for auth and calendar selection."""

    def __init__(self, calendar_id="primary", credentials_path=None, token_path=None):
        self.gc = GoogleCalendar(
            calendar_id,
            credentials_path=credentials_path or _DEFAULT_CREDENTIALS,
            token_path=token_path or _DEFAULT_TOKEN,
        )
        self.calendar_id = calendar_id

    @property
    def calendar(self):
        return self.gc
