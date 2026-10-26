"""Windows lock protocol tests; native OS locking remains a platform CI check."""

import errno
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from hyba_services import platform


class WindowsPromotionLockTests(unittest.TestCase):
    def test_waits_through_sustained_contention_before_entering(self):
        for error in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                locking = Mock(side_effect=[OSError(error, "lock busy")] * 12 + [None])
                msvcrt = SimpleNamespace(LK_NBLCK=2, locking=locking)
                with (
                    patch.object(platform, "os", SimpleNamespace(name="nt")),
                    patch.dict(sys.modules, {"msvcrt": msvcrt}),
                    patch.object(platform.time, "sleep") as sleep,
                ):
                    with platform._promotion_lock(base):
                        self.assertEqual(locking.call_count, 13)
                        self.assertEqual(sleep.call_count, 12)
                        descriptor = locking.call_args.args[0]
                        os.fstat(descriptor)
                    for call in locking.call_args_list:
                        self.assertEqual(call.args, (descriptor, msvcrt.LK_NBLCK, 1))
                    sleep.assert_called_with(0.1)
                with self.assertRaises(OSError):
                    os.fstat(descriptor)

    def test_noncontention_error_propagates_without_entering_or_retrying(self):
        failure = OSError(errno.EBADF, "invalid descriptor")
        msvcrt = SimpleNamespace(LK_NBLCK=2, locking=Mock(side_effect=failure))
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with (
                patch.object(platform, "os", SimpleNamespace(name="nt")),
                patch.dict(sys.modules, {"msvcrt": msvcrt}),
                patch.object(platform.time, "sleep") as sleep,
            ):
                with self.assertRaises(OSError) as caught:
                    with platform._promotion_lock(base):
                        self.fail("lock body entered without acquisition")
                self.assertIs(caught.exception, failure)
                msvcrt.locking.assert_called_once()
                sleep.assert_not_called()
            with self.assertRaises(OSError):
                os.fstat(msvcrt.locking.call_args.args[0])
