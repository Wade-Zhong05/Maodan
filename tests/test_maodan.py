"""Maodan's behaviour: drags, clicks, studying along while typing, settings and the sprite atlas."""

from __future__ import annotations

import contextlib
import json
import os
import re
import struct
import sys
import tempfile
import time
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # the project root, for the import below

import maodan


class DragDirectionTests(unittest.TestCase):
    drag_action = staticmethod(maodan.drag_action)

    def test_up_hops_down_rests_and_sideways_runs(self):
        self.assertEqual(self.drag_action(0, -30, None), 'jump')  # screen y grows downwards
        self.assertEqual(self.drag_action(4, 30, None), 'rest')
        self.assertEqual(self.drag_action(30, 3, None), 'runRight')
        self.assertEqual(self.drag_action(-30, -3, None), 'runLeft')

    def test_a_tiny_or_diagonal_movement_keeps_the_current_animation(self):
        self.assertEqual(self.drag_action(2, -3, 'runLeft'), 'runLeft')
        self.assertEqual(self.drag_action(20, -20, 'jump'), 'jump')
        self.assertIsNone(self.drag_action(2, 3, None))

    def test_a_diagonal_drag_still_gets_a_reaction_when_nothing_plays_yet(self):
        self.assertEqual(self.drag_action(20, 21, None), 'rest')
        self.assertEqual(self.drag_action(-21, -20, None), 'runLeft')


class PointerTests(unittest.TestCase):
    """Maodan._press/_drag/_release with a stand-in window, driven through pointer events."""

    def setUp(self):
        self.played = []
        self.pet = SimpleNamespace(
            press_xy=None, window_xy=None, dragged=False, drag_trail=deque(), action='idle',
            speech='', speech_until=0.0, root=MagicMock(),
            _play_action=lambda action, loop=False: self._play(action, loop),
        )
        self.pet._clicked = lambda: maodan.Maodan._clicked(self.pet)
        self.pet.root.winfo_x.return_value = 500
        self.pet.root.winfo_y.return_value = 500
        self.clock = [100.0]
        tick = patch.object(maodan.time, 'monotonic', side_effect=lambda: self.clock[0])
        tick.start()
        self.addCleanup(tick.stop)

    def _play(self, action, loop):
        self.pet.action = action
        self.played.append((action, loop))

    def _event(self, x, y, after=0.03):
        self.clock[0] += after
        return SimpleNamespace(x_root=x, y_root=y)

    def test_turning_mid_drag_changes_the_animation(self):
        pet = maodan.Maodan
        pet._press(self.pet, self._event(100, 100, after=0))
        for y in (92, 84, 76, 68):  # up
            pet._drag(self.pet, self._event(100, y))
        self.assertEqual(self.played[-1], ('jump', True))
        turned_at = None
        for step, y in enumerate((74, 82, 90, 98, 106, 114, 122), start=1):  # then down
            pet._drag(self.pet, self._event(101, y))
            if turned_at is None and self.pet.action == 'rest':
                turned_at = step
        # Read from the last moment only, Maodan turns while still above where the drag began
        # (y=100); measured from the press it would keep hopping until the pointer passed it.
        self.assertEqual(turned_at, 3)
        for x in (110, 120, 130, 140, 150, 160):  # then right
            pet._drag(self.pet, self._event(x, 122))
        self.assertEqual(self.played[-1], ('runRight', True))
        self.assertEqual([action for action, _loop in self.played], ['jump', 'rest', 'runRight'])
        pet._release(self.pet, self._event(160, 122))
        self.assertEqual(self.played[-1], ('wave', False))  # letting go after a drag says hello

    def test_a_small_wobble_is_still_a_click_not_a_drag(self):
        pet = maodan.Maodan
        pet._press(self.pet, self._event(100, 100, after=0))
        pet._drag(self.pet, self._event(101, 102))
        self.assertFalse(self.pet.dragged)
        self.assertEqual(self.played, [])

    def test_a_click_plays_a_little_trick_and_opens_nothing(self):
        pet = maodan.Maodan
        with patch('os.startfile', create=True) as startfile, patch('subprocess.Popen') as popen:
            pet._press(self.pet, self._event(100, 100, after=0))
            pet._release(self.pet, self._event(100, 100))
        startfile.assert_not_called()
        popen.assert_not_called()
        self.assertEqual(len(self.played), 1)
        action, loop = self.played[0]
        self.assertIn(action, maodan.CLICK_ACTIONS)
        self.assertFalse(loop)
        self.assertEqual(self.pet.speech, 'Meow!')
        self.assertGreater(self.pet.speech_until, self.clock[0])
        self.assertIsNone(self.pet.press_xy)

    def test_nothing_from_promis_is_left(self):
        for path in (ROOT / 'maodan.py', ROOT / 'web' / 'index.html', ROOT / 'web' / 'preview.js'):
            source = path.read_text(encoding='utf-8')
            for leftover in ('urllib', 'PROMIS', 'pairing', 'launch_ticket', 'Milo'):
                self.assertNotIn(leftover, source, path.name)
            # A page opened from disk cannot fetch(); a comment may still say so.
            self.assertIsNone(re.search(r'(?<![\w.])fetch\((?!\))', source), path.name)


class StudyAlongTests(unittest.TestCase):
    """Maodan._follow_typing with a stand-in pet."""

    def pet(self, **state):
        values = {
            'study_along': SimpleNamespace(get=lambda: True), 'typing_until': 0.0, 'press_xy': None,
            'dragged': False, 'action': 'idle', 'typing_loop': False, 'action_started': 0.0,
            'action_until': 0.0, 'next_idle_action': 0.0, 'idle_trick': False,
        }
        values.update(state)
        return SimpleNamespace(**values)

    def follow(self, pet, now):
        maodan.Maodan._follow_typing(pet, now)
        return pet

    def test_typing_starts_studying_and_stopping_returns_to_idle(self):
        pet = self.follow(self.pet(typing_until=11.0), 10.0)
        self.assertEqual((pet.action, pet.action_until, pet.typing_loop), ('working', 0.0, True))
        self.follow(pet, 10.9)
        self.assertEqual(pet.action, 'working')
        self.follow(pet, 11.1)
        self.assertEqual((pet.action, pet.typing_loop), ('idle', False))
        self.assertGreater(pet.next_idle_action, 11.1)  # no random trick the moment typing stops

    def test_typing_never_interrupts_a_trick_a_drag_or_the_switch_being_off(self):
        for state in (
            {'action': 'jump', 'action_until': 20.0},           # a trick picked from the menu
            {'action': 'review', 'action_until': 20.0},         # a reaction to a click
            {'action': 'rest', 'press_xy': (1, 1), 'dragged': True},  # being dragged downwards
            {'study_along': SimpleNamespace(get=lambda: False)},
        ):
            pet = self.follow(self.pet(typing_until=11.0, **state), 10.0)
            self.assertFalse(pet.typing_loop, state)
            self.assertNotEqual((pet.action, pet.action_until), ('working', 0.0), state)

    def test_a_study_or_wait_picked_from_the_menu_plays_to_its_end(self):
        for picked in ('waiting', 'working'):
            pet = self.follow(self.pet(action=picked, action_until=20.0, typing_until=11.0), 10.0)
            self.assertEqual((pet.action, pet.action_until), (picked, 20.0), picked)
            self.follow(pet, 12.0)  # typing has stopped; the chosen trick is not cut short
            self.assertEqual((pet.action, pet.action_until), (picked, 20.0), picked)

    def test_a_pose_maodan_picked_itself_gives_way_to_typing(self):
        pet = self.follow(self.pet(action='waiting', action_until=20.0, idle_trick=True, typing_until=11.0), 10.0)
        self.assertEqual((pet.action, pet.action_until, pet.typing_loop), ('working', 0.0, True))

    def test_after_a_drag_ends_typing_takes_over_again(self):
        pet = self.follow(self.pet(typing_until=11.0, dragged=True, press_xy=None), 10.0)
        self.assertEqual(pet.action, 'working')


class AnimationFrameTests(unittest.TestCase):
    """The frame Maodan draws: typing has to reach _animation_frame, not just _follow_typing."""

    def test_typing_shows_study_together_and_stopping_shows_idle(self):
        pet = SimpleNamespace(
            reduced_motion=SimpleNamespace(get=lambda: False), study_along=SimpleNamespace(get=lambda: True),
            action='idle', action_started=0.0, action_until=0.0, next_idle_action=1e9, hovered=False,
            typing_until=11.0, typing_loop=False, idle_trick=False, press_xy=None, dragged=False,
            atlas=SimpleNamespace(frame_at=lambda action, elapsed: 0),
        )
        pet._follow_typing = lambda now: maodan.Maodan._follow_typing(pet, now)
        self.assertEqual(maodan.Maodan._animation_frame(pet, 10.0)[0], 'working')
        self.assertEqual(maodan.Maodan._animation_frame(pet, 12.0)[0], 'idle')


class WatchKeyboardTests(unittest.TestCase):
    def setUp(self):
        self.asked = []

    def watch(self, *, study_along=True, window='normal', stopped=False):
        pet = SimpleNamespace(
            stopped=stopped, study_along=SimpleNamespace(get=lambda: study_along),
            root=MagicMock(), typing_until=0.0,
            keyboard=SimpleNamespace(typing=lambda: self.asked.append(True) or True),
        )
        pet.root.state.return_value = window
        pet._watch_keyboard = lambda: None
        maodan.Maodan._watch_keyboard(pet)
        return pet

    def test_typing_is_noticed_while_maodan_is_on_screen(self):
        pet = self.watch()
        self.assertGreater(pet.typing_until, 0)
        self.assertEqual(self.asked, [True])
        pet.root.after.assert_called_once()

    def test_the_keyboard_is_not_read_while_hidden_or_switched_off(self):
        for pet in (self.watch(window='withdrawn'), self.watch(study_along=False)):
            pet.root.after.assert_called_once()  # keeps polling either way
        self.assertEqual(self.asked, [])

    def test_polling_stops_once_maodan_quits(self):
        pet = self.watch(stopped=True)
        pet.root.after.assert_not_called()
        self.assertEqual(self.asked, [])


class KeyboardActivityTests(unittest.TestCase):
    def test_only_a_yes_or_no_comes_out(self):
        activity = maodan.KeyboardActivity()
        pressed = {0x41}
        activity._state = lambda key: -0x8000 if key in pressed else 0  # a SHORT with the top bit set
        self.assertIs(activity.typing(), True)
        pressed.clear()
        self.assertIs(activity.typing(), False)
        pressed.add(0x10)  # Shift alone is not typing
        self.assertIs(activity.typing(), False)

    def test_a_quick_tap_between_polls_counts(self):
        activity = maodan.KeyboardActivity()
        activity._state = lambda key: 0x0001 if key == 0x20 else 0  # pressed and released since last asked
        self.assertTrue(activity.typing())

    def test_every_key_is_asked_each_poll(self):
        # A key skipped this round would keep its pressed-since bit and report typing on a later one.
        activity = maodan.KeyboardActivity()
        asked = []
        activity._state = lambda key: asked.append(key) or (-0x8000 if key == 0x08 else 0)
        self.assertTrue(activity.typing())
        self.assertEqual(asked, list(activity.TYPING_KEYS))

    def test_without_windows_it_never_reports_typing(self):
        activity = maodan.KeyboardActivity()
        activity._state = None
        self.assertFalse(activity.supported)
        self.assertFalse(activity.typing())

    @unittest.skipUnless(os.name == 'nt', 'Windows keyboard state')
    def test_the_real_windows_query_answers(self):
        activity = maodan.KeyboardActivity()
        self.assertTrue(activity.supported)
        self.assertIsInstance(activity.typing(), bool)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.appdata = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.appdata.cleanup)
        env = patch.dict(os.environ, {'APPDATA': self.appdata.name})
        env.start()
        self.addCleanup(env.stop)

    def test_defaults_before_anything_is_saved(self):
        self.assertEqual(maodan.load_pet_size(), 100)
        self.assertTrue(maodan.load_study_along())
        self.assertEqual(maodan.settings_path(), Path(self.appdata.name) / 'Maodan' / 'settings.json')

    def test_size_and_study_along_are_remembered_together(self):
        self.assertTrue(maodan.save_pet_size(75))
        self.assertTrue(maodan.save_study_along(False))
        self.assertTrue(maodan.save_pet_size(125))  # saving one keeps the other
        self.assertFalse(maodan.load_study_along())
        self.assertEqual(maodan.load_pet_size(), 125)
        saved = json.loads(maodan.settings_path().read_text(encoding='utf-8'))
        self.assertEqual(saved, {'size_percent': 125, 'study_along_when_typing': False})

    def test_a_damaged_or_odd_settings_file_falls_back_to_defaults(self):
        path = maodan.settings_path()
        path.parent.mkdir(parents=True)
        for content in ('not json', '[1, 2]', '{"size_percent": 90}', '{"size_percent": true}'):
            path.write_text(content, encoding='utf-8')
            self.assertEqual(maodan.load_pet_size(), 100, content)

    def test_errors_are_appended_to_the_log(self):
        with patch.object(maodan.sys, 'stderr', None):
            maodan.log_error('first')
            maodan.log_error('second')
        log = maodan.log_path().read_text(encoding='utf-8')
        self.assertLess(log.index('first'), log.index('second'))


class AtlasManifestTests(unittest.TestCase):
    """The shipped assets have every animation maodan.py plays, laid out inside the sheet."""

    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((maodan.ASSET_DIR / 'animation.json').read_text(encoding='utf-8'))

    def test_every_action_the_pet_can_play_exists(self):
        used = {'idle', 'look', 'working', 'waiting', *maodan.DRAG_ACTIONS, *maodan.CLICK_ACTIONS,
                *(action for _label, action in maodan.TRICKS)}
        self.assertLessEqual(used, set(self.spec['animations']))
        self.assertEqual(self.spec['animations']['look']['frames'], 16)  # one per pointer direction

    def test_timings_match_frames_and_cells_fit_the_sheet(self):
        for path in (maodan.ASSET_DIR / self.spec['spritesheet'],
                     maodan.ASSET_DIR / self.spec['desktop']['spritesheet']):
            with path.open('rb') as sheet:
                header = sheet.read(24)
            self.assertEqual(header[:8], b'\x89PNG\r\n\x1a\n', path.name)
            width, height = struct.unpack('>II', header[16:24])
            for action, animation in self.spec['animations'].items():
                if 'durations' in animation:
                    self.assertEqual(len(animation['durations']), animation['frames'], action)
                self.assertLessEqual(animation['frames'], self.spec['columns'] * 2, action)
                last_cell = animation['row'] * self.spec['columns'] + animation['frames'] - 1
                bottom = (last_cell // self.spec['columns'] + 1) * self.spec['frameHeight']
                self.assertLessEqual(bottom, height, (path.name, action))
            self.assertEqual(width, self.spec['columns'] * self.spec['frameWidth'], path.name)

    def test_the_fast_keyed_sheet_is_the_one_loaded(self):
        path = maodan.SpriteAtlas.sheet_path(self.spec)
        self.assertEqual(path.name, 'spritesheet-keyed.png')
        other = {**self.spec, 'desktop': {**self.spec['desktop'], 'keyColor': '#000000'}}
        self.assertEqual(maodan.SpriteAtlas.sheet_path(other).name, 'spritesheet.png')


class AnimationPageTests(unittest.TestCase):
    """web/index.html, which See all animations opens, works from disk and shows every animation."""

    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        cls.spec = json.loads((maodan.ASSET_DIR / 'animation.json').read_text(encoding='utf-8'))

    def test_the_script_copy_of_the_manifest_matches_the_json(self):
        script = (maodan.ASSET_DIR / 'animation.js').read_text(encoding='utf-8')
        prefix = 'window.MAODAN_ANIMATION = '
        self.assertIn(prefix, script)
        body = script.split(prefix, 1)[1].rstrip().removesuffix(';')
        self.assertEqual(json.loads(body), self.spec)

    def test_every_animation_has_a_button_and_every_button_an_animation(self):
        buttons = re.findall(r'data-animation="([^"]+)"', self.page)
        self.assertEqual(len(buttons), len(set(buttons)))
        self.assertEqual(set(buttons), set(self.spec['animations']))
        self.assertEqual(buttons[0], 'idle')  # the one marked as playing when the page opens

    def test_everything_the_page_loads_is_next_to_it(self):
        references = re.findall(r'src="([^"]+)"', self.page) + re.findall(r"url\('([^']+)'\)", self.page)
        self.assertGreaterEqual(len(references), 3)
        for reference in references:
            self.assertTrue((ROOT / 'web' / reference).resolve().is_file(), reference)
        script = (ROOT / 'web' / 'preview.js').read_text(encoding='utf-8')
        self.assertIn("const ASSET_BASE = '../assets/'", script)
        self.assertTrue((ROOT / 'web' / '../assets' / self.spec['spritesheet']).resolve().is_file())

    def test_the_menu_opens_the_page_in_the_browser(self):
        pet = SimpleNamespace(speech='', speech_until=0.0, _play_action=MagicMock())
        with patch.object(maodan, 'open_in_browser') as opened:
            maodan.Maodan.open_animation_page(pet)
        opened.assert_called_once_with(maodan.ANIMATION_PAGE.as_uri())
        self.assertTrue(maodan.ANIMATION_PAGE.is_file())
        self.assertNotIn(' ', maodan.ANIMATION_PAGE.as_uri())  # one command-line argument as it is
        pet._play_action.assert_called_once_with('review')
        self.assertTrue(pet.speech)


class OpenInBrowserTests(unittest.TestCase):
    URL = 'file:///C:/Users/me/Duke%20Fall/maodan/web/index.html'

    def setUp(self):
        self.popen = patch.object(maodan.subprocess, 'Popen').start()
        self.webbrowser = patch.object(maodan.webbrowser, 'open').start()
        self.addCleanup(patch.stopall)

    def registry(self, prog_id, command, kind=None):
        import winreg

        patch('winreg.OpenKey', return_value=MagicMock()).start()
        patch('winreg.QueryValueEx', side_effect=[
            (prog_id, winreg.REG_SZ), (command, winreg.REG_SZ if kind is None else kind),
        ]).start()

    @unittest.skipUnless(os.name == 'nt', 'Windows registry')
    def test_the_browser_registered_for_http_opens_the_page(self):
        self.registry('SLBrowserHTML', '"C:\\Browser\\browser.exe" --single-argument %1')
        maodan.open_in_browser(self.URL)
        self.popen.assert_called_once_with(f'"C:\\Browser\\browser.exe" --single-argument {self.URL}')
        self.webbrowser.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows registry')
    def test_a_command_with_environment_variables_is_expanded(self):
        import winreg

        self.registry('FirefoxURL', '"%ProgramFiles%\\Mozilla Firefox\\firefox.exe" -osint -url "%1"',
                      winreg.REG_EXPAND_SZ)
        maodan.open_in_browser(self.URL)
        (command,), _ = self.popen.call_args
        self.assertTrue(command.startswith(f'"{os.environ["ProgramFiles"]}\\Mozilla Firefox'), command)
        self.assertTrue(command.endswith(f'-url "{self.URL}"'), command)

    @unittest.skipUnless(os.name == 'nt', 'Windows registry')
    def test_anything_unusual_falls_back_to_the_standard_library(self):
        for case in ('no handler', 'no %1', 'browser gone'):
            with self.subTest(case):
                self.popen.reset_mock(side_effect=True)
                self.webbrowser.reset_mock()
                if case == 'no handler':
                    patch('winreg.OpenKey', side_effect=FileNotFoundError).start()
                else:
                    self.registry('SomeHTML', '"C:\\b.exe" %L' if case == 'no %1' else '"C:\\gone.exe" %1')
                if case == 'browser gone':
                    self.popen.side_effect = FileNotFoundError
                maodan.open_in_browser(self.URL)
                self.webbrowser.assert_called_once_with(self.URL, new=2)

    def test_other_systems_use_the_standard_library(self):
        with patch.object(maodan.os, 'name', 'posix'):
            maodan.open_in_browser(self.URL)
        self.webbrowser.assert_called_once_with(self.URL, new=2)
        self.popen.assert_not_called()


class LiveWindowTests(unittest.TestCase):
    """Build the real window once: every frame at every size, the menu and quitting."""

    def setUp(self):
        try:
            self.root = maodan.create_root()
        except maodan.tk.TclError as exc:  # no display, or no Tcl/Tk libraries
            self.skipTest(f'Tk unavailable: {exc}')
        self.appdata = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.appdata.cleanup)
        env = patch.dict(os.environ, {'APPDATA': self.appdata.name})
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self):
        with contextlib.suppress(maodan.tk.TclError):  # the test normally quits Maodan itself
            self.root.destroy()

    def test_the_pet_draws_every_frame_resizes_and_quits(self):
        pet = maodan.Maodan(self.root, size_percent=25)
        self.root.update()
        labels = [pet.menu.entrycget(index, 'label') for index in range(pet.menu.index('end') + 1)
                  if pet.menu.type(index) != 'separator']
        self.assertEqual(labels[:3], ['Play with Maodan', 'Size', 'Reduce motion'])
        self.assertEqual(labels[-3:], ['See all animations', 'Hide for now', 'Quit Maodan'])
        for size in maodan.PET_SIZES:
            pet._set_size(size)
            self.assertEqual(pet.canvas.winfo_reqheight(), pet.height)
            for action, animation in pet.atlas.animations.items():
                for index in range(animation['frames']):
                    image = pet.atlas.image(action, index)
                    self.assertEqual(image.width(), round(192 * pet.atlas.scale), (size, action))
        self.assertEqual(maodan.load_pet_size(), maodan.PET_SIZES[-1])
        pet._clicked()
        pet._draw_frame(time.monotonic())
        self.assertTrue(pet.canvas.find_all())  # the cat and the speech bubble
        self.root.withdraw()
        pet.reveal()
        self.assertEqual(self.root.state(), 'normal')
        pet.quit()
        self.assertTrue(pet.stopped)


if __name__ == '__main__':
    unittest.main()
