"""Defines tools for storing KindleEvents
"""
from .events import AddEvent, SetReadingEvent, SetFinishedEvent, ReadEvent,\
    EventParseError


class EventStore(object):
    """A simple newline-delimitted file store for events
    """
    def __init__(self, file_path):
        self._path = file_path
        open(file_path, 'a').close()

    def record_event(self, event):
        """Records the ``KindleEvent`` `event` in the store
        """
        with open(self._path, 'a') as file_:
            file_.write(str(event) + '\n')

    def get_events(self):
        """Returns a list of all ``KindleEvent``s held in the store
        """
        with open(self._path, 'r') as file_:
            file_lines = file_.read().splitlines()
            event_lines = [line for line in file_lines if line]
        events = []
        for event_line in event_lines:
            for event_cls in (AddEvent, SetReadingEvent, ReadEvent,
                              SetFinishedEvent):
                try:
                    event = event_cls.from_str(event_line)
                except EventParseError:
                    pass
                else:
                    events.append(event)
        return events
