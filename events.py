"""Defines Kindle Events
"""
import re


POSITION_MEASURE = 'LOCATION'


class EventParseError(Exception):
    """Indicate an error in parsing an event from a string
    """
    pass


class KindleEvent(object):
    """A base event.

    Establishes sortability of Events based on the `weight` property
    """
    _WEIGHT = None
    asin = None

    @property
    def weight(self):
        """Define the sorting order of events
        """
        return self._WEIGHT

    @staticmethod
    def from_str(string):
        """Generate a `KindleEvent`-type object from a string
        """
        raise NotImplementedError

    def __eq__(self, other):
        return self.weight == other.weight and self.asin == other.asin

    def __lt__(self, other):
        return self.weight < other.weight and self.asin < other.asin

    def __gt__(self, other):
        return self.weight > other.weight and self.asin > other.asin

    def __ne__(self, other):
        return not self == other


class AddEvent(KindleEvent):
    """Represent the addition of a book to the Kindle Library
    """
    _WEIGHT = 0

    def __init__(self, asin):
        super(AddEvent, self).__init__()
        self.asin = asin

    def __str__(self):
        return 'ADD %s' % (self.asin,)

    @staticmethod
    def from_str(string):
        """Generate a `AddEvent` object from a string
        """
        match = re.match(r'^ADD (\w+)$', string)
        if match:
            return AddEvent(match.group(1))
        else:
            raise EventParseError


class SetReadingEvent(KindleEvent):
    """Represents the user's desire to record progress of a book
    """
    _WEIGHT = 1

    def __init__(self, asin, initial_progress):
        super(SetReadingEvent, self).__init__()
        self.asin = asin
        self.initial_position = initial_progress

    def __str__(self):
        return 'START READING %s FROM %s %d' % (self.asin, POSITION_MEASURE,
                self.initial_position)

    @staticmethod
    def from_str(string):
        """Generate a `SetReadingEvent` object from a string
        """
        match = re.match(r'^START READING (\w+) FROM \w+ (\d+)$', string)
        if match:
            return SetReadingEvent(match.group(1), int(match.group(2)))
        else:
            raise EventParseError


class ReadEvent(KindleEvent):
    """Represents the advance of a user's progress in a book
    """
    _WEIGHT = 2

    def __init__(self, asin, progress):
        super(ReadEvent, self).__init__()
        self.asin = asin
        self.progress = progress
        if progress <= 0:
            raise ValueError('Progress field must be positive')

    def __str__(self):
        return 'READ %s FOR %d %sS' % (self.asin, self.progress,
                POSITION_MEASURE)

    @staticmethod
    def from_str(string):
        """Generate a `SetFinishedEvent` object from a string
        """
        match = re.match(r'^FINISHED READING (\w+)$', string)
        if match:
            return SetFinishedEvent(match.group(1))
        else:
            raise EventParseError


class SetFinishedEvent(KindleEvent):
    """Represents a user's completion of a book
    """
    _WEIGHT = 3

    def __init__(self, asin):
        super(SetFinishedEvent, self).__init__()
        self.asin = asin

    def __str__(self):
        return 'FINISHED READING %s' % (self.asin)

    @staticmethod
    def from_str(string):
        """Generate a `SetFinishedEvent` object from a string
        """
        match = re.match(r'^FINISHED READING (\w+)$', string)
        if match:
            return SetFinishedEvent(match.group(1))
        else:
            raise EventParseError
