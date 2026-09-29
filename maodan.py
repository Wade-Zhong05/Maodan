"""Maodan, a desktop cat.

Maodan sits in a small borderless window above everything else. Drag it to move it (it runs, hops
or settles in the direction of the drag), click it for a little trick, and right-click it for more
tricks, its size and its settings, or for a web page that plays every animation. While you type
anywhere, Maodan studies along.

Only Python's standard library is used. Start it with ``启动 Maodan.bat`` or ``pixi run start``.
Starting it again while it runs brings the running Maodan back, for example after Hide for now,
instead of opening a second one.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
import tkinter as tk
import traceback
import webbrowser
from collections import deque
from pathlib import Path

from instance import WindowsInstance

TRANSPARENT = '#010203'
NAVY = '#29382f'
TEAL = '#3e7258'
PAPER = '#fffaf0'
NAME = 'Maodan'
ASSET_DIR = Path(__file__).resolve().parent / 'assets'
ANIMATION_PAGE = Path(__file__).resolve().parent / 'web' / 'index.html'
PET_SIZES = (25, 50, 75, 100, 125, 150)
MIN_WINDOW_WIDTH = 216  # Keep speech readable even when the cat is smaller than 75%.
# A drag is read from the last moment of pointer movement, so Maodan turns as soon as the drag does.
DRAG_WINDOW_SECONDS = 0.15
DRAG_MIN_PIXELS = 6
DRAG_ACTIONS = frozenset({'runRight', 'runLeft', 'jump', 'rest'})
CLICK_ACTIONS = ('wave', 'jump', 'review')
TRICKS = (
    ('Say hello', 'wave'), ('Little hop', 'jump'),
    ('Run right', 'runRight'), ('Run left', 'runLeft'),
    ('Quiet moment', 'rest'), ('Wait together', 'waiting'),
    ('Study together', 'working'), ('Celebrate', 'review'),
)
TYPING_POLL_MS = 120
TYPING_LINGER_SECONDS = 1.5  # keep studying through the short pauses between words
SPEECH_HEIGHT = 42


def create_root() -> tk.Tk:
    # Conda/Pixi keeps Tcl under Library/lib on Windows. Starting its pythonw.exe directly, as the
    # launcher does, does not always set these paths.
    if platform.system() == 'Windows':
        library = Path(sys.prefix) / 'Library' / 'lib'
        for key, directory, script in (
            ('TCL_LIBRARY', f'tcl{tk.TclVersion}', 'init.tcl'),
            ('TK_LIBRARY', f'tk{tk.TkVersion}', 'tk.tcl'),
        ):
            candidate = library / directory
            if (candidate / script).is_file():
                os.environ.setdefault(key, str(candidate))
    return tk.Tk()


class SpriteAtlas:
    """Play Maodan's frames, cut from the sprite sheet made for the current size.

    The window hides one exact colour, TRANSPARENT, so it cannot show a soft edge: laid onto that
    colour, the half-transparent fur round the cat became a dark, ragged rim. ``tools/build_atlas.py``
    therefore draws a sheet for every size in PET_SIZES straight from the pose art, each pixel either
    Maodan in its own colour or TRANSPARENT. Scaling one sheet here instead would blow its pixels up
    into jagged steps. The sheets are RGB PNGs: for an RGBA photo Tk also builds a region of its
    visible pixels, which takes seconds on Windows.
    """

    def __init__(self, root: tk.Tk, size_percent: int = 100, asset_dir: Path = ASSET_DIR):
        self.asset_dir = asset_dir
        self.spec = json.loads((asset_dir / 'animation.json').read_text(encoding='utf-8'))
        self.animations = self.spec['animations']
        self.root = root
        self.frames: dict[tuple[str, int], tk.PhotoImage] = {}
        self.set_size(size_percent)

    def sheet_path(self, size_percent: int) -> Path:
        desktop = self.spec['desktop']
        if str(desktop['keyColor']).lower() != TRANSPARENT:
            raise ValueError('The desktop sheets are keyed onto a colour this window does not hide')
        return self.asset_dir / desktop['sheets'][str(size_percent)]

    def set_size(self, size_percent: int) -> None:
        if size_percent not in PET_SIZES:
            raise ValueError('Unsupported pet size')
        scale = 3 * size_percent / 200
        width = round(self.spec['frameWidth'] * scale)
        height = round(self.spec['frameHeight'] * scale)
        # Everything is cut before anything is replaced, so a missing sheet leaves the old size.
        sheet = tk.PhotoImage(master=self.root, file=str(self.sheet_path(size_percent)))
        columns = self.spec['columns']
        frames = {}
        for action, animation in self.animations.items():
            for index in range(animation['frames']):
                cell = animation['row'] * columns + index
                x, y = (cell % columns) * width, (cell // columns) * height
                frame = tk.PhotoImage(master=self.root, width=width, height=height)
                frame.tk.call(frame, 'copy', sheet, '-from', x, y, x + width, y + height)
                frames[action, index] = frame
        # Only the cut frames are kept; holding on to the sheet as well would double the memory.
        self.frames = frames
        self.scale = scale
        self.frame_width, self.frame_height = width, height

    def duration(self, action: str) -> float:
        animation = self.animations[action]
        if animation.get('durations'):
            return sum(animation['durations']) / 1000
        return animation['frames'] / animation['fps']

    def frame_at(self, action: str, elapsed: float) -> int:
        animation = self.animations[action]
        if animation.get('durations'):
            position = max(0, elapsed) * 1000 % sum(animation['durations'])
            for index, duration in enumerate(animation['durations']):
                if position < duration:
                    return index
                position -= duration
            return 0
        return int(max(0, elapsed) * animation['fps']) % animation['frames']

    def image(self, action: str, frame_index: int) -> tk.PhotoImage:
        return self.frames[action, frame_index]

    def draw(
        self, canvas: tk.Canvas, action: str, frame_index: int, *,
        left: int = 0, top: int = SPEECH_HEIGHT,
    ) -> None:
        canvas.create_image(left, top, image=self.image(action, frame_index), anchor='nw')


def settings_path() -> Path:
    root = Path(os.getenv('APPDATA') or (Path.home() / '.config'))
    return root / 'Maodan' / 'settings.json'


def log_path() -> Path:
    return settings_path().with_name('maodan.log')


def _load_settings() -> dict:
    try:
        settings = json.loads(settings_path().read_text(encoding='utf-8'))
        return settings if isinstance(settings, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_settings(**changes) -> bool:
    try:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**_load_settings(), **changes}, indent=2), encoding='utf-8')
        return True
    except OSError:
        return False


def load_pet_size() -> int:
    size = _load_settings().get('size_percent')
    return size if type(size) is int and size in PET_SIZES else 100


def save_pet_size(size_percent: int) -> bool:
    return _save_settings(size_percent=size_percent)


def load_study_along() -> bool:
    return _load_settings().get('study_along_when_typing') is not False


def save_study_along(enabled: bool) -> bool:
    return _save_settings(study_along_when_typing=bool(enabled))


def open_in_browser(url: str) -> None:
    """Open ``url`` in the web browser.

    The animation page is a file: URL, which Windows would hand to whatever opens .html files, often
    an editor on a programmer's computer. So the browser registered for http: links is asked directly,
    and the standard library's choice is the fallback.
    """
    if os.name == 'nt':
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice',
            ) as key:
                prog_id = winreg.QueryValueEx(key, 'ProgId')[0]
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf'{prog_id}\shell\open\command') as key:
                command, kind = winreg.QueryValueEx(key, '')
            if kind == winreg.REG_EXPAND_SZ:
                command = winreg.ExpandEnvironmentStrings(command)
            if '%1' in command:
                # A file: URL from Path.as_uri() has no spaces or quotes, so it is one argument as is.
                subprocess.Popen(command.replace('%1', url))
                return
        except OSError:
            pass
    webbrowser.open(url, new=2)


def drag_action(dx: float, dy: float, current: str | None) -> str | None:
    """The animation for a drag that moved by (dx, dy) just now: run sideways, hop up, settle down.

    Screen y grows downwards, so a negative dy is an upward drag. Movement that is too small, or too
    diagonal to call, keeps ``current``, so a wobbly drag does not flicker between two animations;
    with no drag animation playing yet, the larger of the two directions decides.
    """
    if math.hypot(dx, dy) < DRAG_MIN_PIXELS:
        return current
    vertical = abs(dy) > abs(dx) * 1.2
    horizontal = abs(dx) > abs(dy) * 1.2
    if not vertical and not horizontal:
        if current is not None:
            return current
        vertical = abs(dy) >= abs(dx)  # nothing playing yet: a diagonal drag still gets a reaction
    if vertical:
        return 'jump' if dy < 0 else 'rest'
    return 'runRight' if dx > 0 else 'runLeft'


class KeyboardActivity:
    """Whether you are typing anywhere on this computer, and nothing more.

    Windows reports whether a key is down to any program that asks; this asks about typing keys only
    (letters, digits, punctuation, space, Enter, Backspace, the number pad) and keeps a single yes/no.
    Which key it was is never kept, logged or sent anywhere. Elsewhere it always answers no.
    """

    TYPING_KEYS = (
        0x08, 0x0D, 0x20, *range(0x30, 0x3A), *range(0x41, 0x5B), *range(0x60, 0x70),
        *range(0xBA, 0xC1), *range(0xDB, 0xE0), 0xE2,
    )

    def __init__(self):
        self._state = None
        if os.name == 'nt':
            import ctypes

            user32 = ctypes.WinDLL('user32')
            user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
            user32.GetAsyncKeyState.restype = ctypes.c_short
            self._state = user32.GetAsyncKeyState

    @property
    def supported(self) -> bool:
        return self._state is not None

    def typing(self) -> bool:
        if self._state is None:
            return False
        # 0x8000: down now. 0x0001: pressed since this key was last asked about, which catches quick
        # taps between polls. Every key is asked each time: a key skipped this round would keep its
        # bit and report old typing on a later round.
        states = [self._state(key) for key in self.TYPING_KEYS]
        return any(state & 0x8001 for state in states)


class Maodan:
    def __init__(self, root: tk.Tk, *, still: bool = False, size_percent: int | None = None):
        self.root = root
        self.stopped = False
        initial_size = size_percent if size_percent is not None else load_pet_size()
        self.size_percent = tk.IntVar(master=root, value=initial_size)
        self.atlas = SpriteAtlas(root, initial_size)
        self.width = max(MIN_WINDOW_WIDTH, self.atlas.frame_width)
        self.height = self.atlas.frame_height + SPEECH_HEIGHT
        self.menu_open = False
        self._menu_topmost = True
        self.action = 'idle'
        self.action_started = time.monotonic()
        self.action_until = 0.0
        self.next_idle_action = self.action_started + 12
        self.reduced_motion = tk.BooleanVar(master=root, value=still)
        self.hovered = False
        self.speech = ''
        self.speech_until = 0.0
        self.press_xy: tuple[int, int] | None = None
        self.window_xy: tuple[int, int] | None = None
        self.dragged = False
        self.drag_trail: deque[tuple[float, int, int]] = deque()
        self.keyboard = KeyboardActivity()
        self.study_along = tk.BooleanVar(master=root, value=load_study_along())
        self.typing_until = 0.0
        self.typing_loop = False  # the current 'working' loop is following the keyboard
        self.idle_trick = False  # the current action was picked at random, not by you

        self._build_window()
        if self.keyboard.supported:
            self.root.after(TYPING_POLL_MS, self._watch_keyboard)
        self._play_action('wave')
        self.root.after(40, self._animate)

    def _build_window(self) -> None:
        self.root.title(NAME)
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg=TRANSPARENT)
        if platform.system() == 'Windows':
            self.root.wm_attributes('-transparentcolor', TRANSPARENT)
        else:
            self.root.attributes('-alpha', 0.98)

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(8, screen_width - self.width - 34)
        y = max(8, screen_height - self.height - 74)
        self.root.geometry(f'{self.width}x{self.height}+{x}+{y}')

        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=TRANSPARENT,
            highlightthickness=0,
            cursor='hand2',
        )
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Enter>', lambda _event: self._set_hover(True))
        self.canvas.bind('<Leave>', lambda _event: self._set_hover(False))
        self.canvas.bind('<ButtonPress-1>', self._press)
        self.canvas.bind('<B1-Motion>', self._drag)
        self.canvas.bind('<ButtonRelease-1>', self._release)
        self.canvas.bind('<Button-3>', self._show_menu)

        self.menu = tk.Menu(self.root, tearoff=False)
        tricks = tk.Menu(self.menu, tearoff=False)
        for label, action in TRICKS:
            tricks.add_command(label=label, command=lambda name=action: self._play_action(name))
        self.menu.add_cascade(label=f'Play with {NAME}', menu=tricks)
        sizes = tk.Menu(self.menu, tearoff=False)
        for label, percent in zip(
            ('Tiny', 'Extra small', 'Small', 'Medium', 'Large', 'Extra large'), PET_SIZES,
        ):
            sizes.add_radiobutton(
                label=f'{label} ({percent}%)', value=percent, variable=self.size_percent,
                command=lambda value=percent: self._set_size(value),
            )
        self.menu.add_cascade(label='Size', menu=sizes)
        self.menu.add_checkbutton(label='Reduce motion', variable=self.reduced_motion)
        if self.keyboard.supported:
            self.menu.add_checkbutton(
                label='Study along while I type', variable=self.study_along,
                command=lambda: save_study_along(self.study_along.get()),
            )
        self.menu.add_command(label='See all animations', command=self.open_animation_page)
        self.menu.add_command(label='Hide for now', command=self.root.withdraw)
        self.menu.add_separator()
        self.menu.add_command(label=f'Quit {NAME}', command=self.quit)
        self.menu.bind('<Unmap>', self._menu_unmapped)

    def reveal(self) -> None:
        """A second launch brings this Maodan back, including after Hide for now."""
        if self.root.state() == 'withdrawn':
            self.root.deiconify()
        if not self.menu_open:
            self.root.lift()
        self._play_action('wave')

    def _set_hover(self, hovered: bool) -> None:
        if hovered and not self.hovered and self.action == 'idle':
            self._play_action('wave')
        self.hovered = hovered
        if hovered and not self.speech:
            self.speech = 'Meow~'
        elif not hovered and time.monotonic() >= self.speech_until:
            self.speech = ''

    def _press(self, event: tk.Event) -> None:
        self.press_xy = (event.x_root, event.y_root)
        self.window_xy = (self.root.winfo_x(), self.root.winfo_y())
        self.dragged = False
        self.drag_trail = deque([(time.monotonic(), event.x_root, event.y_root)])

    def _drag(self, event: tk.Event) -> None:
        if not self.press_xy or not self.window_xy:
            return
        dx = event.x_root - self.press_xy[0]
        dy = event.y_root - self.press_xy[1]
        now = time.monotonic()
        self.drag_trail.append((now, event.x_root, event.y_root))
        while len(self.drag_trail) > 2 and self.drag_trail[1][0] <= now - DRAG_WINDOW_SECONDS:
            self.drag_trail.popleft()
        if abs(dx) + abs(dy) > 5:
            self.dragged = True
            _, start_x, start_y = self.drag_trail[0]
            current = self.action if self.action in DRAG_ACTIONS else None
            action = drag_action(event.x_root - start_x, event.y_root - start_y, current)
            if action is not None and action != self.action:
                self._play_action(action, loop=True)
        self.root.geometry(f'+{self.window_xy[0] + dx}+{self.window_xy[1] + dy}')

    def _release(self, _event: tk.Event) -> None:
        if not self.dragged:
            self._clicked()
        else:
            self._play_action('wave')
        self.press_xy = None
        self.window_xy = None

    def _clicked(self) -> None:
        """A click without a drag: Maodan answers with a little trick."""
        self.speech = 'Meow!'
        self.speech_until = time.monotonic() + 2.2
        self._play_action(random.choice(CLICK_ACTIONS))

    def open_animation_page(self) -> None:
        self.speech = 'Opening my animations…'
        self.speech_until = time.monotonic() + 2.2
        self._play_action('review')
        open_in_browser(ANIMATION_PAGE.as_uri())

    def _show_menu(self, event: tk.Event) -> None:
        if self.menu_open:
            return
        self.menu_open = True
        self._menu_topmost = self.root.attributes('-topmost')
        try:
            # A topmost borderless pet can cover Windows' native popup menus.
            # Suspend its topmost status for the whole popup, including submenus.
            self.root.attributes('-topmost', False)
            self.menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            self._restore_after_menu()
            raise
        finally:
            # Win32's native popup is modal; X11 returns while its menu is posted
            # and restores via <Unmap> instead. Quit may already have destroyed Tk.
            try:
                if self.root.tk.call('tk', 'windowingsystem') != 'x11':
                    self._restore_after_menu()
            except tk.TclError:
                self.menu_open = False

    def _menu_unmapped(self, event: tk.Event) -> None:
        if event.widget == self.menu and self.menu_open:
            self.root.after_idle(self._restore_after_menu)

    def _restore_after_menu(self) -> None:
        if not self.menu_open:
            return
        self.menu_open = False
        try:
            self.menu.grab_release()
            self.root.attributes('-topmost', self._menu_topmost)
        except tk.TclError:
            pass  # A menu command can close Maodan before the popup returns.

    def _set_size(self, size_percent: int, *, persist: bool = True) -> None:
        old_width, old_height = self.width, self.height
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self.atlas.set_size(size_percent)
        self.size_percent.set(size_percent)
        self.width = max(MIN_WINDOW_WIDTH, self.atlas.frame_width)
        self.height = self.atlas.frame_height + SPEECH_HEIGHT
        # Keep Maodan's feet and horizontal centre in place when changing size.
        x += (old_width - self.width) // 2
        y += old_height - self.height
        left, top = self.root.winfo_vrootx(), self.root.winfo_vrooty()
        right = left + self.root.winfo_vrootwidth()
        bottom = top + self.root.winfo_vrootheight()
        # Clamp on the reported screen, without pulling a pet on another monitor
        # back to the primary monitor when Tk only reports primary-screen bounds.
        if left <= self.root.winfo_x() < right and top <= self.root.winfo_y() < bottom:
            x = max(left, min(x, right - self.width))
            y = max(top, min(y, bottom - self.height))
        self.canvas.configure(width=self.width, height=self.height)
        self.root.geometry(f'{self.width}x{self.height}+{x}+{y}')
        if persist and not save_pet_size(size_percent):
            self.speech = 'Size changed for this session.'
            self.speech_until = time.monotonic() + 3
        self._draw_frame(time.monotonic())

    def _play_action(self, action: str, *, loop: bool = False) -> None:
        self.typing_loop = False
        self.idle_trick = False
        self.action = action
        self.action_started = time.monotonic()
        # Play the short, original loops twice so an interaction is easy to notice.
        self.action_until = 0.0 if loop else self.action_started + self.atlas.duration(action) * 2
        self.next_idle_action = self.action_started + random.uniform(12, 22)

    def _watch_keyboard(self) -> None:
        if self.stopped:
            return
        # Nothing to follow while Maodan is off screen or told not to.
        if self.study_along.get() and self.root.state() != 'withdrawn':
            try:
                if self.keyboard.typing():
                    self.typing_until = time.monotonic() + TYPING_LINGER_SECONDS
            except OSError:
                pass
        self.root.after(TYPING_POLL_MS, self._watch_keyboard)

    def _follow_typing(self, now: float) -> None:
        """Study together while you type.

        Only takes over from standing idle or from a pose Maodan picked at random itself: a trick
        you chose (even Wait together or Study together) plays to its end.
        """
        typing = self.study_along.get() and now < self.typing_until
        dragging = self.press_xy is not None and self.dragged
        if typing and not dragging and (self.action == 'idle' or self.idle_trick):
            if self.action != 'working':
                self.action_started = now
            self.action = 'working'
            self.action_until = 0.0
            self.typing_loop = True
            self.idle_trick = False
        elif not typing and self.typing_loop:
            self.typing_loop = False
            self.action = 'idle'
            self.action_started = now
            self.next_idle_action = now + random.uniform(12, 22)

    def _animation_frame(self, now: float) -> tuple[str, int]:
        if self.reduced_motion.get():
            return 'idle', 0
        if self.action_until and now >= self.action_until:
            self.action = 'idle'
            self.action_started = now
            self.action_until = 0.0
        self._follow_typing(now)
        if self.action == 'idle' and self.hovered:
            pointer_x, pointer_y = self.root.winfo_pointerxy()
            dx = pointer_x - (self.root.winfo_rootx() + self.width / 2)
            dy = pointer_y - (self.root.winfo_rooty() + SPEECH_HEIGHT + 67 * self.atlas.scale)
            # The atlas look poses begin at up and proceed clockwise.
            direction = round((math.atan2(dy, dx) + math.pi / 2) / (math.pi / 8)) % 16
            return 'look', direction
        if self.action == 'idle' and now >= self.next_idle_action:
            self._play_action(random.choice(('working', 'waiting')))
            self.idle_trick = True
        return self.action, self.atlas.frame_at(self.action, now - self.action_started)

    def _animate(self) -> None:
        if self.stopped:
            return
        if self.root.state() == 'withdrawn' or self.menu_open:
            self.root.after(250, self._animate)
            return
        now = time.monotonic()
        if self.speech_until and now >= self.speech_until and not self.hovered:
            self.speech = ''
            self.speech_until = 0.0
        self._draw_frame(now)
        self.root.after(125 if self.reduced_motion.get() else 40, self._animate)

    def _draw_frame(self, now: float) -> None:
        self.canvas.delete('all')
        action, frame_index = self._animation_frame(now)
        left = (self.width - self.atlas.frame_width) // 2
        self.atlas.draw(self.canvas, action, frame_index, left=left)
        c = self.canvas
        if self.speech:
            c.create_rectangle(18, 4, self.width - 18, 35, fill=PAPER, outline=TEAL, width=1)
            middle = self.width / 2
            c.create_polygon(
                middle - 6, 35, middle + 6, 35, middle, SPEECH_HEIGHT,
                fill=PAPER, outline=TEAL,
            )
            c.create_text(
                self.width / 2, 19, text=self.speech, fill=NAVY, font=('Segoe UI Semibold', 9),
                width=self.width - 48, justify='center',
            )

    def quit(self) -> None:
        self.stopped = True
        self.root.destroy()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run Maodan, the desktop cat')
    parser.add_argument('--still', action='store_true', help='Start with reduced motion')
    parser.add_argument('--size', type=int, choices=PET_SIZES, help='Initial size as a percentage')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    instance = WindowsInstance('pet')
    try:
        if not instance.owner:
            instance.wake()  # the running Maodan comes back instead of a second cat appearing
            return
        root = create_root()
        # Tk reports a failing callback on stderr, which pythonw.exe does not have.
        root.report_callback_exception = lambda *exc: log_error(''.join(traceback.format_exception(*exc)))
        pet = Maodan(root, still=args.still, size_percent=args.size)

        def check_wake():
            if pet.stopped:
                return
            if instance.consume_wake():
                pet.reveal()
            root.after(250, check_wake)

        root.after(250, check_wake)
        root.mainloop()
    finally:
        instance.close()


def log_error(details: str) -> None:
    """Append ``details`` to the log, and print it too when there is a console."""
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as log:
            log.write(f'--- {time.strftime("%Y-%m-%d %H:%M:%S")}\n{details}\n')
    except OSError:
        pass
    if sys.stderr is not None:
        print(details, file=sys.stderr)


def report_crash(details: str) -> None:
    """Keep a fatal error visible: pythonw.exe, which the launcher uses, has no console."""
    log_error(details)
    if sys.stderr is None and os.name == 'nt':
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None, f"Maodan stopped unexpectedly.\n\nDetails were saved to:\n{log_path()}", NAME, 0x10,
        )


if __name__ == '__main__':
    try:
        main()
    except Exception:  # noqa: BLE001 --- whatever it was, it must reach the log and the user
        report_crash(traceback.format_exc())
        sys.exit(1)
