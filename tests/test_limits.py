import unittest
from switchboard.limits import Bucket


class BucketTests(unittest.TestCase):
    def test_burst_and_refill(self):
        now = [0.0]
        bucket = Bucket(lambda: now[0])
        self.assertTrue(all(bucket.allow() for _ in range(8)))
        self.assertFalse(bucket.allow())
        now[0] += 0.5
        self.assertTrue(bucket.allow())
        self.assertFalse(bucket.allow())
        now[0] += 100
        self.assertTrue(all(bucket.allow() for _ in range(8)))
        self.assertFalse(bucket.allow())