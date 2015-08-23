"""Defines tools for composing ``KindleEvent``s into coherent state.
"""
from events import AddEvent, SetReadingEvent, SetFinishedEvent, ReadEvent, \
                    KindleEvent


class ReadingStatus(object):
    """An enum representing the three possible progress states of a book
    """
    NOT_STARTED, CURRENT, COMPLETED = xrange(3)


class BookSnapshot(object):
    """A book's state of progress

    Args:
        asin: The ASIN of the book
        status: The book's ReadingStatus value
        progress: An integral value representing the current reading progress.
            This value is meaningless unless `status` is CURRENT as progress
            is untracked for books not currently being read.
    """
    def __init__(self, asin, status=ReadingStatus.NOT_STARTED, progress=None):
        self.asin = asin
        self.status = status
        self.progress = progress


class KindleLibrarySnapshot(object):
    """A snapshot of the state of a Kindle library.

    Args:
        events: An iterable of ``KindleEvent``s which are applied in sequence
            to build the snapshot's state.
    """
    def __init__(self, events=()):
        self._data = {}
        for event in events:
            self.process_event(event)

    def process_event(self, event):
        """Apply an event to the snapshot instance
        """
        if not isinstance(event, KindleEvent):
            pass
        elif isinstance(event, AddEvent):
            self._data[event.asin] = BookSnapshot(event.asin)
        elif isinstance(event, SetReadingEvent):
            self._data[event.asin].status = ReadingStatus.CURRENT
            self._data[event.asin].progress = event.initial_progress
        elif isinstance(event, ReadEvent):
            self._data[event.asin].progress += event.progress
        elif isinstance(event, SetFinishedEvent):
            self._data[event.asin].status = ReadingStatus.COMPLETED
        else:
            raise TypeError

    def get_book(self, asin):
        """Return the `BookSnapshot` object associated with `asin`

        Raises:
            KeyError: If asin not found in current snapshot
        """
        return self._data[asin]

    def calc_update_events(self, asin_to_progress):
        """Calculate and return an iterable of `KindleEvent`s which, when applied to
        the current snapshot, result in the the current snapshot reflecting
        the progress state of the `asin_to_progress` mapping.

        Functionally, this method generates `AddEvent`s and `ReadEvent`s from
        updated Kindle Library state.

        Args:
            asin_to_progress: A map of book asins to the integral
                representation of progress used in the current snapshot.
        """
        new_events = []
        for asin, new_progress in asin_to_progress.iteritems():
            try:
                book_snapshot = self.get_book(asin)
            except KeyError:
                new_events.append(AddEvent(asin))
            else:
                if book_snapshot.status == ReadingStatus.CURRENT:
                    change = new_progress - book_snapshot.progress
                    if change > 0:
                        new_events.append(ReadEvent(asin, change))
        return new_events
