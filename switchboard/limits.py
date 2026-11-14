from collections import deque
import time

class Bucket:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.updated = clock()
        self.tokens = 8.0

    def allow(self):
        now = self.clock()
        self.tokens = min(8.0, self.tokens + (now - self.updated) * 2)
        self.updated = now
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True

class Failures:
    def __init__(self, limit=10, window=600, clock=time.monotonic):
        self.limit = limit
        self.window = window
        self.clock = clock
        self.events = {}

    def _recent(self, source):
        events = self.events.get(source)
        if events is None:
            return None
        cutoff = self.clock() - self.window
        while events and events[0] <= cutoff:
            events.popleft()
        if not events:
            del self.events[source]
            return None
        return events

    def blocked(self, source):
        events = self._recent(source)
        return events is not None and len(events) >= self.limit

    def add(self, source):
        if len(self.events) > 4096:
            for other in list(self.events):
                self._recent(other)
        self.events.setdefault(source, deque()).append(self.clock())