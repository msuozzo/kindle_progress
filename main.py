"""Define a command line interface for Kindle Progress tracking
"""
from events import AddEvent, SetReadingEvent, SetFinishedEvent, ReadEvent
from store import EventStore
from snapshot import KindleLibrarySnapshot, ReadingStatus
from reader import KindleCloudReaderAPI


STORE_PATH = '.store.txt'
CREDENTIAL_PATH = '.credentials.json'


def _update(snapshot, kcr):
    """Calculate the event diffs between `snapshot` and the current library
    state retrieved from the Cloud Reader API.

    Args:
        snapshot: A ``KindleLibrarySnapshot`` instance representing the
            snapshot against which diff events will be generated.
        kcr: A ``KindleCloudReaderAPI`` instance used to fetch updates
    """
    # Get up-to-date library info
    current_books = kcr.get_library_metadata()
    current_progress = kcr.get_library_progress()

    new_events = []
    for book in current_books:
        try:
            data = snapshot.data[book.asin]
        except KeyError:
            new_events.append(AddEvent(book.asin))
        else:
            if data['status'] == ReadingStatus.CURRENT:
                change = current_progress[book.asin].locs[1] - data['progress']
                if change > 0:
                    new_events.append(ReadEvent(book.asin, change))
    return new_events


def run():
    """Execute the command loop
    """
    store = EventStore(STORE_PATH)
    snapshot = KindleLibrarySnapshot(store.get_events())

    with KindleCloudReaderAPI.get_instance(CREDENTIAL_PATH) as kcr:
        current_books = kcr.get_library_metadata()
        current_progress = kcr.get_library_progress()
        new_events = _update(snapshot, kcr)

    # Events are sorted such that, when applied in order, each event
    # represents a logical change in state. That is, an event never requires
    # future events' data in order to be parsed.
    # e.g. All ADDs must go before START READINGs
    #      All START READINGs before all READs
    print 'Processing updates:'
    for event in sorted(new_events):
        print '  ' + str(event)
        store.record_event(event)
        snapshot.process_event(event)

    cmd = ''
    book_range = range(1, len(current_books) + 1)
    ind_to_book = dict(zip(book_range, current_books))
    while cmd != 'q':
        print 'Books:'
        for i in book_range:
            print '\t%d: %s' % (i, ind_to_book[i])
        print 'Commands:'
        print '| start {#}'
        print '| finish {#}'
        print '| q'
        cmd = raw_input('> ')
        get_book = lambda cmd_str: ind_to_book[int(cmd_str.split()[1])]
        if cmd.startswith('start '):
            book = get_book(cmd)
            initial_progress = current_progress[book.asin].locs[1]
            event = SetReadingEvent(book.asin, initial_progress)
        elif cmd.startswith('finish '):
            event = SetFinishedEvent(get_book(cmd).asin)
        else:
            event = None
        if event is not None:
            print 'REGISTERED EVENT:'
            print '  ' + str(event)
            store.record_event(event)
            snapshot.process_event(event)
        print


if __name__ == '__main__':
    run()
