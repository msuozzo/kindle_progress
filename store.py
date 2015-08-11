"""Defines tools for storing KindleEvents
"""
from events import AddEvent, SetReadingEvent, SetFinishedEvent, ReadEvent,\
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
            event_strs = file_.read().splitlines()
        events = []
        for event_str in event_strs:
            for event_cls in (AddEvent, SetReadingEvent, ReadEvent,
                    SetFinishedEvent):
                try:
                    event = event_cls.from_str(event_str)
                except EventParseError:
                    pass
                else:
                    events.append(event)
