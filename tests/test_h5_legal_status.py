"""Check the presence of status fields, not whether a review occurred."""
from pathlib import Path
import unittest

class LegalReviewStatusTests(unittest.TestCase):
    def test_required_status(self):
        text = (Path(__file__).resolve().parents[1] / 'work_orders' / 'H5.0_legal_review_status.md').read_text()
        for required in ('none named', 'IHL', 'ROE', 'not completed',
                         'H5.1 and H5.2', 'BLOCKED pending that review'):
            with self.subTest(required=required):
                self.assertIn(required, text)

if __name__ == '__main__':
    unittest.main()
