import unittest
from chronus.stratum.rate_limiter import IntegerNanosecondTokenBucket, PriorityShareQueue, ShareCandidate


class TestRateLimiter(unittest.TestCase):
    def test_token_bucket_refill(self):
        bucket = IntegerNanosecondTokenBucket(rate_per_sec=10, capacity=20)
        # Drain all 20 tokens
        for _ in range(20):
            self.assertTrue(bucket.acquire())

        # 21st token should fail
        self.assertFalse(bucket.acquire())

    def test_priority_queue_block_bypass(self):
        pq = PriorityShareQueue(maxsize=5)
        c_share = ShareCandidate("j1", "00000001", "60000000", 10, "00000000", 100)
        c_block = ShareCandidate("j2", "00000001", "60000000", 20, "00000000", 50)

        pq.push(c_share, is_block_hit=False)
        pq.push(c_block, is_block_hit=True)

        popped, is_block = pq.pop()
        self.assertTrue(is_block)
        self.assertEqual(popped.job_id, "j2")


if __name__ == "__main__":
    unittest.main()
