import unittest

from yacht_app.infra.rate_limit import SlidingWindowRateLimiter


class SlidingWindowRateLimiterTests(unittest.TestCase):
    def test_limit_is_scoped_to_key_and_recovers_after_window(self):
        limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)

        self.assertEqual(limiter.allow("127.0.0.1", now=100), (True, 0))
        self.assertEqual(limiter.allow("127.0.0.1", now=101), (True, 0))
        allowed, retry_after = limiter.allow("127.0.0.1", now=102)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)
        self.assertEqual(limiter.allow("127.0.0.2", now=102), (True, 0))
        self.assertEqual(limiter.allow("127.0.0.1", now=111), (True, 0))


if __name__ == "__main__":
    unittest.main()
