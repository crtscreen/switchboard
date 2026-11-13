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