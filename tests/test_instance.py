"""Only one Maodan runs at a time; a second launch wakes the first."""

from __future__ import annotations

import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the project root, for the import below

from instance import WindowsInstance


@unittest.skipUnless(os.name == 'nt', 'Windows single-instance guard')
class WindowsInstanceTests(unittest.TestCase):
    def test_second_instance_wakes_first_and_does_not_take_ownership(self):
        name = f'test-{uuid.uuid4().hex}'
        with WindowsInstance(name) as first, WindowsInstance(name) as second:
            self.assertTrue(first.owner)
            self.assertFalse(second.owner)
            second.wake()
            self.assertTrue(first.consume_wake())
            self.assertFalse(first.consume_wake())
        with WindowsInstance(name) as restarted:
            self.assertTrue(restarted.owner)


class OtherSystemsTests(unittest.TestCase):
    def test_without_windows_every_launch_owns_itself(self):
        with patch.object(os, 'name', 'posix'):
            instance = WindowsInstance('anything')
        self.assertTrue(instance.owner)
        self.assertFalse(instance.consume_wake())
        instance.wake()
        instance.close()


if __name__ == '__main__':
    unittest.main()
