import unittest
from collections import deque
from chronus.stratum.rate_limiter import IntegerNanosecondTokenBucket, PriorityShareQueue, ShareCandidate


class TestRateLimiter(unittest.TestCase):
    def test_token_bucket_refill(self):
        bucket = IntegerNanosecondTokenBucket(rate_per_sec=10, capacity=20)
        # Drain all 20 tokens
        for _ in range(20):
            self.assertTrue(bucket.acquire())

        # 21st token should fail
        self.assertFalse(bucket.acquire())

        # Advance time by 500ms (at 10 tokens/sec, this should refill exactly 5 tokens)
        t_refill = bucket.last_refill_ns + 500_000_000
        tokens_available = bucket.refill(now_ns=t_refill)
        self.assertEqual(tokens_available, 5)

        # We should now be able to acquire exactly 5 tokens
        for _ in range(5):
            self.assertTrue(bucket.acquire(now_ns=t_refill))
        self.assertFalse(bucket.acquire(now_ns=t_refill))

    def test_priority_queue_block_bypass(self):
        pq = PriorityShareQueue(maxsize=5)
        c_share = ShareCandidate("j1", "00000001", "60000000", 10, "00000000", 100)
        c_block = ShareCandidate("j2", "00000001", "60000000", 20, "00000000", 50)

        pq.push(c_share, is_block_hit=False)
        pq.push(c_block, is_block_hit=True)

        popped, is_block = pq.pop()
        self.assertTrue(is_block)
        self.assertEqual(popped.job_id, "j2")

    def test_no_float_in_hot_path(self):
        bucket = IntegerNanosecondTokenBucket(rate_per_sec=15)
        # Verify strictly integer types across all state
        self.assertIsInstance(bucket.tokens, int)
        self.assertIsInstance(bucket.ns_per_token, int)
        self.assertIsInstance(bucket.last_refill_ns, int)
        self.assertIsInstance(bucket.remainder_ns, int)
        self.assertIsInstance(bucket.rate_per_sec, int)
        self.assertIsInstance(bucket.capacity, int)

        # Verify hot path acquire remains integer
        t_now = bucket.last_refill_ns + 100_000_000
        acquired = bucket.acquire(now_ns=t_now)
        self.assertTrue(acquired)
        self.assertIsInstance(bucket.tokens, int)
        self.assertIsInstance(bucket.remainder_ns, int)

        # Bounds assertions: rate must be in [10, 20]
        with self.assertRaises(AssertionError):
            IntegerNanosecondTokenBucket(rate_per_sec=5)
        with self.assertRaises(AssertionError):
            IntegerNanosecondTokenBucket(rate_per_sec=25)

        # Capacity assertion: capacity must equal 2 * rate
        with self.assertRaises(AssertionError):
            IntegerNanosecondTokenBucket(rate_per_sec=15, capacity=40)

    def test_block_bypass_preempts_queue(self):
        pq = PriorityShareQueue(maxsize=10)
        self.assertIsInstance(pq.high_priority_blocks, deque)
        self.assertIsInstance(pq.normal_priority_shares, deque)

        share1 = ShareCandidate("j1", "00000001", "60000000", 1, "00000000", 100)
        share2 = ShareCandidate("j2", "00000001", "60000000", 2, "00000000", 200)
        block = ShareCandidate("j_block", "00000001", "60000000", 3, "00000000", 10)

        # Push standard shares first
        pq.push(share1, is_block_hit=False)
        pq.push(share2, is_block_hit=False)

        # Push block solution
        pq.push(block, is_block_hit=True)

        # Block hit MUST be popped first, preempting queued standard shares
        first_item, is_block = pq.pop()
        self.assertTrue(is_block)
        self.assertEqual(first_item.job_id, "j_block")

        # Next items are the original shares in order
        second_item, is_block_2 = pq.pop()
        self.assertFalse(is_block_2)
        self.assertEqual(second_item.job_id, "j1")

        third_item, is_block_3 = pq.pop()
        self.assertFalse(is_block_3)
        self.assertEqual(third_item.job_id, "j2")

        self.assertTrue(pq.empty())


if __name__ == "__main__":
    unittest.main()
