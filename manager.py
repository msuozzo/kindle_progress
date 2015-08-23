"""Define a higher-level interface from which to manage updates to Kindle
progress tracking
"""
from events import UpdateEvent
from snapshot import KindleLibrarySnapshot
from kindle_api.reader import KindleCloudReaderAPI, KindleAPIError

from datetime import datetime


class KindleProgressMgr(object):
    """Manages the Kindle reading progress state held in the the `EventStore`
    instance, `store`

    Args:
        store: An `EventStore` instance containing the past events
        kindle_uname: The email associated with the Kindle account
        kindle_pword: The password associated with the Kindle account
    """
    def __init__(self, store, kindle_uname, kindle_pword):
        self.store = store
        self._snapshot = KindleLibrarySnapshot(store.get_events())
        self._event_buf = []
        self.uname = kindle_uname
        self.pword = kindle_pword
        self.books = None
        self.progress = None

    @property
    def uncommited_events(self):
        """A logically sorted list of `Events` that are have been registered
        to be committed to the current object's state but remain uncommitted.
        """
        return list(sorted(self._event_buf))

    def detect_events(self, max_attempts=3):
        """Returns a list of `Event`s detected from differences in state
        between the current snapshot and the Kindle Library.

        `books` and `progress` attributes will be set with the latest API
        results upon successful completion of the function.

        Returns:
            If failed to retrieve progress, None
            Else, the list of `Event`s
        """
        # Attempt to retrieve current state from KindleAPI
        for _ in xrange(max_attempts):
            try:
                with KindleCloudReaderAPI\
                        .get_instance(self.uname, self.pword) as kcr:
                    self.books = kcr.get_library_metadata()
                    self.progress = kcr.get_library_progress()
            except KindleAPIError:
                continue
            else:
                break
        else:
            return None

        # Calculate diffs from new progress
        progress_map = {book.asin: self.progress[book.asin].locs[1]
                                                for book in self.books}
        new_events = self._snapshot.calc_update_events(progress_map)

        update_event = UpdateEvent(datetime.now().replace(microsecond=0))
        new_events.append(update_event)

        self._event_buf.extend(new_events)
        return new_events

    def register_events(self, events=()):
        """Register `Event` objects in `events` to be committed.

        NOTE: This does not automatically commit the events.
        A separate `commit_updates` call must be made to make the commit.
        """
        self._event_buf.extend(events)

    def commit_events(self):
        """Applies all outstanding `Event`s to the internal state
        """
        # Events are sorted such that, when applied in order, each event
        # represents a logical change in state. That is, an event never requires
        # future events' data in order to be parsed.
        # e.g. All ADDs must go before START READINGs
        #      All START READINGs before all READs
        for event in sorted(self._event_buf):
            self.store.record_event(event)
            self._snapshot.process_event(event)
        self._event_buf = []
