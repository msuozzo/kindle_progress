#!/usr/bin/env python
"""Define a command line interface for Kindle Progress tracking
"""
from aduro.events import SetReadingEvent, SetFinishedEvent
from aduro.store import EventStore
from aduro.manager import KindleProgressMgr

import json


STORE_PATH = '.store.txt'
CREDENTIAL_PATH = '.credentials.json'


def safe_raw_input(*args, **kwargs):
    """A `raw_input` wrapper with graceful handling of KeyboardInterrupt.

    A wrapper around the normal `raw_input` builtin that, when a
    `KeyboardInterrupt` is raised, the exception is caught and None is
    returned.
    """
    try:
        return raw_input(*args, **kwargs)
    except KeyboardInterrupt:
        return None


def run():  #pylint: disable=too-many-locals
    """Execute the command loop
    """
    store = EventStore(STORE_PATH)
    with open(CREDENTIAL_PATH, 'r') as cred_file:
        creds = json.load(cred_file)
        uname, pword = creds['uname'], creds['pword']
    mgr = KindleProgressMgr(store, uname, pword)

    print 'Detecting updates to Kindle progress:'
    events = mgr.detect_events()
    if events is None:
        print 'Failed to retrieve Kindle progress updates'
        return
    elif not events:
        print '  No updates detected'
    else:
        for event in events:
            print '  ' + str(event)

    print
    print 'Finished updating.'
    print 'Mark new books as \'reading\' or old books as \'read\'? (y/N)'
    if safe_raw_input('> ') == 'y':
        _change_state_prompt(mgr)
    mgr.commit_events()


def _change_state_prompt(mgr):
    """Runs a prompt to change the state of books.

    Registers `Event`s with `mgr` as they are requested.

    Args:
        mgr: A `KindleProgressMgr` object with the `books` and `progress`
            fields populated.
    """
    cmd = ''
    book_range = range(1, len(mgr.books) + 1)
    ind_to_book = dict(zip(book_range, mgr.books))
    get_book = lambda cmd_str: ind_to_book[int(cmd_str.split()[1])]
    while cmd != 'q':
        print 'Books:'
        for i in book_range:
            print '\t%d: %s' % (i, ind_to_book[i])
        print 'Commands:'
        print '| start {#}   | Start reading book with index {#}'
        print '| finish {#}  | Finish reading book with index {#}'
        print '| q           | Quit'
        cmd = safe_raw_input('> ')
        if cmd is None or cmd == 'q':
            break
        elif cmd.startswith('start '):
            book = get_book(cmd)
            initial_progress = mgr.progress[book.asin].locs[1]
            event = SetReadingEvent(book.asin, initial_progress)
        elif cmd.startswith('finish '):
            event = SetFinishedEvent(get_book(cmd).asin)
        else:
            print 'Invalid command'
            event = None
        if event is not None:
            print
            print 'REGISTERED EVENT:'
            print '  ' + str(event)
            mgr.register_events((event))
        print


if __name__ == '__main__':
    run()
