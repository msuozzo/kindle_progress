__version__ = '0.0.1a0'


from .events import EventParseError, Event, KindleEvent, AddEvent,\
        SetReadingEvent, SetFinishedEvent, UpdateEvent, ReadEvent
from .manager import KindleProgressMgr
from .snapshot import ReadingStatus, BookSnapshot, KindleLibrarySnapshot
from .store import EventStore
