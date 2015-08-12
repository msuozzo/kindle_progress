"""Defines tools for composing ``KindleEvent``s into coherent state.
"""
from events import AddEvent, SetReadingEvent, SetFinishedEvent, ReadEvent


class ReadingStatus(object):
    """An enum representing the three possible progress states of a book
    """
    COMPLETED, CURRENT, NOT_STARTED = xrange(3)


class KindleLibrarySnapshot(object):
    """A snapshot of the state of a Kindle library.

    Args:
        events: An iterable of ``KindleEvent``s which are applied in sequence
            to build the snapshot's state.
    """
    def __init__(self, events=()):
        self.data = {}
        for event in events:
            self.process_event(event)

    def process_event(self, event):
        """Apply an event to the snapshot instance
        """
        if isinstance(event, AddEvent):
            self.data[event.asin] = {
                    'status': ReadingStatus.NOT_STARTED,
                    'progress': None
                }
        elif isinstance(event, SetReadingEvent):
            self.data[event.asin]['status'] = ReadingStatus.CURRENT
            self.data[event.asin]['progress'] = event.initial_progress
        elif isinstance(event, ReadEvent):
            self.data[event.asin]['progress'] += event.progress
        elif isinstance(event, SetFinishedEvent):
            self.data[event.asin]['status'] = ReadingStatus.COMPLETED
        else:
            raise TypeError
