"""tools/build_atlas.py: hard-edged desktop sheets, and shipped assets that match the art.

These need Pillow, which only the art environment has, and are skipped elsewhere:
``pixi run -e art python -m unittest discover -s tests``.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from PIL import Image
except ImportError:
    Image = None


def build_atlas():
    spec = importlib.util.spec_from_file_location('build_atlas', ROOT / 'tools' / 'build_atlas.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['build_atlas'] = module  # dataclasses look their module up while it loads
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(Image is None, 'Pillow is only in the art environment')
class BuildAtlasTests(unittest.TestCase):
    def test_a_pixel_is_maodan_in_its_own_colour_or_see_through(self):
        tools = build_atlas()
        fur = (200, 180, 160)
        sheet = Image.new('RGBA', (4, 1))
        sheet.putdata([(*fur, 255), (*fur, 128), (*fur, 127), (*tools.KEY_COLOR, 255)])
        keyed = tools.keyed_sheet(sheet)
        self.assertEqual(keyed.mode, 'RGB')
        # Half-covered fur keeps its colour instead of fading towards the dark key colour, fainter
        # fur disappears, and a cat pixel that happens to be the key colour does not become a hole.
        self.assertEqual(list(keyed.getdata()),
                         [fur, fur, tools.KEY_COLOR, (*tools.KEY_COLOR[:2], tools.KEY_COLOR[2] + 1)])

    def test_the_shipped_assets_are_what_the_art_builds(self):
        tools = build_atlas()
        shipped = ROOT / 'assets'
        with tempfile.TemporaryDirectory() as out:
            built = Path(out)
            tools.build(built)
            names = sorted(path.relative_to(built).as_posix() for path in built.rglob('*') if path.is_file())
            self.assertEqual(
                names, sorted(path.relative_to(shipped).as_posix() for path in shipped.rglob('*') if path.is_file()),
            )
            for name in names:
                self.assertEqual((built / name).read_bytes(), (shipped / name).read_bytes(), name)


if __name__ == '__main__':
    unittest.main()
