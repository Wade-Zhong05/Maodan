"""Build Maodan's sprite atlas from the pose art in ``art/``.

The pose art is generated from the selected Maodan portrait. This script only sizes and arranges
those poses into the frame grid that ``maodan.py`` plays, and describes it in
``assets/animation.json``. ``assets/animation.js`` carries the same description for the animation
page in ``web/``: opened straight from disk, a browser refuses to fetch() the JSON.

The desktop window can make only one exact colour see-through, so it cannot show a soft edge. Laid
onto that colour, the semi-transparent pixels round the fur turned into a dark, ragged rim. So each
pet size gets its own sheet in ``assets/desktop/``, drawn at that size straight from the pose art,
where every pixel is either Maodan in its own colour or the see-through colour.

Run with ``pixi run -e art build-atlas`` (the ``art`` environment adds Pillow).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "art"
POSES = ART / "poses"
ASSETS = ROOT / "assets"
FRAME_WIDTH = 192
FRAME_HEIGHT = 208
COLUMNS = 8
ROWS = 11
KEY_COLOR = (1, 2, 3)  # maodan.TRANSPARENT, the colour the desktop window keys out
# maodan.PET_SIZES; a size of p% shows a frame at 1.5 * p / 100 times FRAME_WIDTH x FRAME_HEIGHT.
DESKTOP_SIZES = (25, 50, 75, 100, 125, 150)
# At or above this opacity a pixel is Maodan; below, see-through. Half coverage keeps the drawn
# outline where the soft edge has it, without the faint fur haze beyond it.
ALPHA_THRESHOLD = 128


@dataclass(frozen=True)
class Pose:
    file: Path
    max_width: int
    max_height: int
    bottom: int
    # Optional normalized crop.  It lets one generated contact sheet provide
    # several coherent head-direction keys without baking derived source art.
    crop: tuple[float, float, float, float] | None = None


POSES_BY_NAME = {
    "idle": Pose(ART / "maodan-selected.png", 174, 186, 9),
    "idle_blink": Pose(POSES / "idle-blink.png", 174, 186, 9),
    "run_extend": Pose(POSES / "run-sequence.png", 172, 136, 15, (0, 0, .49, .49)),
    "run_contact": Pose(POSES / "run-sequence.png", 172, 136, 15, (.51, 0, 1, .49)),
    "run_gather": Pose(POSES / "run-sequence.png", 172, 136, 15, (0, .51, .49, 1)),
    "run_push": Pose(POSES / "run-sequence.png", 172, 136, 15, (.51, .51, 1, 1)),
    "wave_low": Pose(POSES / "wave-low.png", 174, 187, 9),
    "wave": Pose(POSES / "wave.png", 174, 187, 9),
    "jump_crouch": Pose(POSES / "jump-crouch.png", 176, 156, 14),
    "jump_takeoff": Pose(POSES / "jump-sequence.png", 176, 166, 17, (0, 0, .49, .49)),
    "jump_apex": Pose(POSES / "jump-sequence.png", 176, 166, 17, (.51, 0, 1, .49)),
    "jump_descent": Pose(POSES / "jump-sequence.png", 176, 166, 17, (0, .51, .49, 1)),
    "jump_land": Pose(POSES / "jump-sequence.png", 176, 158, 14, (.51, .51, 1, 1)),
    "rest_settle": Pose(POSES / "rest-settle.png", 182, 146, 14),
    "rest_wake": Pose(POSES / "rest-wake.png", 182, 137, 14),
    "rest": Pose(POSES / "rest.png", 182, 137, 14),
    "waiting_groom": Pose(POSES / "waiting-groom.png", 174, 187, 9),
    "waiting_paw_low": Pose(POSES / "waiting-paw-low.png", 174, 187, 9),
    "working": Pose(POSES / "working.png", 182, 182, 9),
    "working_tap": Pose(POSES / "working-tap.png", 182, 182, 9),
    "review_work": Pose(POSES / "review-sequence.png", 182, 182, 9, (0, 0, .49, .49)),
    "review_turn": Pose(POSES / "review-sequence.png", 182, 182, 9, (.51, 0, 1, .49)),
    "review_show": Pose(POSES / "review-sequence.png", 182, 182, 9, (0, .51, .49, 1)),
    "review_celebrate": Pose(POSES / "review-sequence.png", 182, 182, 9, (.51, .51, 1, 1)),
    "look_up": Pose(POSES / "look-directions.png", 174, 186, 9, (0, 0, .49, .49)),
    "look_right": Pose(POSES / "look-directions.png", 174, 186, 9, (.51, 0, 1, .49)),
    "look_down": Pose(POSES / "look-directions.png", 174, 186, 9, (0, .51, .49, 1)),
    "look_left": Pose(POSES / "look-directions.png", 174, 186, 9, (.51, .51, 1, 1)),
    "look_up_right": Pose(POSES / "look-diagonals.png", 174, 186, 9, (0, 0, .49, .49)),
    "look_down_right": Pose(POSES / "look-diagonals.png", 174, 186, 9, (.51, 0, 1, .49)),
    "look_down_left": Pose(POSES / "look-diagonals.png", 174, 186, 9, (0, .51, .49, 1)),
    "look_up_left": Pose(POSES / "look-diagonals.png", 174, 186, 9, (.51, .51, 1, 1)),
}


@dataclass(frozen=True)
class Frame:
    pose: str
    dx: int = 0
    dy: int = 0
    stretch_x: float = 1.0
    stretch_y: float = 1.0
    mirrored: bool = False


ACTION_FRAMES = {
    "idle": [
        Frame("idle"), Frame("idle", dy=-1, stretch_y=1.006),
        Frame("idle_blink", dy=-1), Frame("idle", dy=-1, stretch_y=1.008),
        Frame("idle", dx=1), Frame("idle", dy=1, stretch_y=.994),
    ],
    "runRight": [
        Frame("run_extend", dx=-2, dy=-2, stretch_x=1.02),
        Frame("run_contact", dx=-1, dy=1, stretch_y=.99),
        Frame("run_gather", dx=1, dy=2, stretch_x=.99, stretch_y=.98),
        Frame("run_push", dx=2, dy=-1, stretch_x=1.01, stretch_y=1.01),
        Frame("run_extend", dx=-1, dy=-3, stretch_x=1.01, stretch_y=.99),
        Frame("run_contact", dy=1, stretch_x=.99, stretch_y=1.01),
        Frame("run_gather", dx=2, dy=2, stretch_x=1.01, stretch_y=.97),
        Frame("run_push", dx=1, dy=-1, stretch_x=1.02),
    ],
    "wave": [
        Frame("idle"), Frame("wave_low", dy=1, stretch_y=.99),
        Frame("wave", dy=-3, stretch_y=1.015),
        Frame("wave_low", dx=-1, dy=2, stretch_y=.98),
    ],
    "jump": [
        Frame("jump_crouch", dy=4, stretch_x=1.03, stretch_y=.94),
        Frame("jump_takeoff", dy=-3, stretch_y=1.02),
        Frame("jump_apex", dy=-16, stretch_x=1.01, stretch_y=1.01),
        Frame("jump_descent", dx=1, dy=-7),
        Frame("jump_land", dx=1, dy=3, stretch_x=1.02, stretch_y=.96),
    ],
    "rest": [
        Frame("idle"), Frame("rest_settle", dy=1, stretch_y=.98),
        Frame("rest_wake", dy=1, stretch_x=1.01, stretch_y=.985),
        Frame("rest", dy=1, stretch_y=.99),
        Frame("rest", dy=-1, stretch_x=1.006, stretch_y=1.011),
        Frame("rest_wake", dy=1, stretch_x=1.01, stretch_y=.985),
        Frame("rest_settle", dy=1, stretch_y=.98),
        Frame("idle", dy=1, stretch_y=.995),
    ],
    "waiting": [
        Frame("idle"), Frame("idle_blink", dy=-1),
        Frame("waiting_paw_low", dx=-1),
        Frame("waiting_groom", dy=-1),
        Frame("waiting_paw_low", dx=1, dy=1, stretch_y=.99),
        Frame("idle", dx=1),
    ],
    "working": [
        Frame("review_work"), Frame("working", dy=-1),
        Frame("working_tap", dx=1, dy=-2, stretch_y=1.006),
        Frame("working_tap", dx=-1, dy=-1, stretch_x=.995),
        Frame("working_tap", dx=-1, stretch_y=.995),
        Frame("review_work", dy=1),
    ],
    "review": [
        Frame("review_work"), Frame("review_turn", dy=-1),
        Frame("review_show", dy=1, stretch_y=.99),
        Frame("review_celebrate", dy=-2, stretch_y=1.01),
        Frame("review_show", dy=1, stretch_x=.995, stretch_y=.99),
        Frame("review_work"),
    ],
    "look": [
        Frame("look_up", dy=-2), Frame("look_up_right", dx=1, dy=-2),
        Frame("look_up_right", dx=2, dy=-1, stretch_y=.997),
        Frame("look_right", dx=2, dy=-1),
        Frame("look_right", dx=2, dy=1, stretch_y=.995),
        Frame("look_down_right", dx=1, dy=1),
        Frame("look_down_right", dy=2, stretch_y=.995),
        Frame("look_down", dy=2),
        Frame("look_down", dx=-1, dy=2, stretch_y=.995),
        Frame("look_down_left", dx=-1, dy=1),
        Frame("look_down_left", dx=-2, stretch_y=.995),
        Frame("look_left", dx=-2, dy=-1),
        Frame("look_left", dx=-2, dy=-2, stretch_y=1.005),
        Frame("look_up_left", dx=-1, dy=-2),
        Frame("look_up_left", dy=-2, stretch_y=1.005),
        Frame("look_up", dy=-2, stretch_y=.998),
    ],
}
ACTION_FRAMES["runLeft"] = [
    Frame(f.pose, -f.dx, f.dy, f.stretch_x, f.stretch_y, True)
    for f in ACTION_FRAMES["runRight"]
]

ACTION_ROWS = {
    "idle": 0, "runRight": 1, "runLeft": 2, "wave": 3,
    "jump": 4, "rest": 5, "waiting": 6, "working": 7,
    "review": 8, "look": 9,
}

# Milliseconds per frame. "look" has none: maodan.py picks its frame from the pointer direction.
DURATIONS = {
    "idle": [280, 110, 110, 140, 140, 320],
    "runRight": [120, 120, 120, 120, 120, 120, 120, 220],
    "runLeft": [120, 120, 120, 120, 120, 120, 120, 220],
    "wave": [140, 140, 140, 280],
    "jump": [140, 140, 140, 140, 280],
    "rest": [140, 140, 140, 140, 140, 140, 140, 240],
    "waiting": [150, 150, 150, 150, 150, 260],
    "working": [120, 120, 120, 120, 120, 220],
    "review": [150, 150, 150, 150, 150, 280],
}


def isolate_primary_subject(image: Image.Image) -> Image.Image:
    """Remove disconnected neighbours that cross a generated contact-sheet seam."""
    alpha = image.getchannel("A")
    mask = alpha.point(lambda opacity: 255 if opacity > 8 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return image
    center_x = (bbox[0] + bbox[2]) // 2
    center_y = (bbox[1] + bbox[3]) // 2
    pixels = mask.load()
    if not pixels[center_x, center_y]:
        seed = min(
            ((x - center_x) ** 2 + (y - center_y) ** 2, x, y)
            for y in range(bbox[1], bbox[3])
            for x in range(bbox[0], bbox[2])
            if pixels[x, y]
        )[1:]
    else:
        seed = (center_x, center_y)
    selected = mask.copy()
    ImageDraw.floodfill(selected, seed, 128)
    selected = selected.point(lambda value: 255 if value == 128 else 0)
    result = image.copy()
    result.putalpha(ImageChops.multiply(alpha, selected))
    return result


def load_pose(pose: Pose) -> Image.Image:
    image = Image.open(pose.file).convert("RGBA")
    if pose.crop:
        width, height = image.size
        left, top, right, bottom = pose.crop
        image = image.crop((round(left * width), round(top * height),
                            round(right * width), round(bottom * height)))
        image = isolate_primary_subject(image)
    alpha = image.getchannel("A")
    # Discard tiny alpha-compression speckles without trimming real whiskers.
    bbox = alpha.point(lambda opacity: 255 if opacity > 8 else 0).getbbox()
    if bbox is None:
        raise ValueError(f"Pose is empty: {pose.file}")
    return image.crop(bbox)


def render_frame(source: Image.Image, pose: Pose, plan: Frame, scale: float = 1) -> Image.Image:
    """One cell, ``scale`` times FRAME_WIDTH x FRAME_HEIGHT, laid out as at scale 1."""
    width, height = source.size
    ratio = min(pose.max_width / width, pose.max_height / height)
    width = max(1, round(width * ratio * plan.stretch_x))
    height = max(1, round(height * ratio * plan.stretch_y))
    left = round((FRAME_WIDTH - width) / 2) + plan.dx
    top = FRAME_HEIGHT - pose.bottom - height + plan.dy
    if left < 0 or top < 0 or left + width > FRAME_WIDTH or top + height > FRAME_HEIGHT:
        raise ValueError(f"Pose does not fit in cell: {pose.file.name}, {plan}")
    # Resize premultiplied RGBA so invisible source colours cannot create a
    # red/yellow fringe around fur and whiskers after Lanczos interpolation.
    art = source.convert("RGBa").resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        Image.Resampling.LANCZOS).convert("RGBA")
    if plan.mirrored:
        art = art.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    frame = Image.new("RGBA", (round(FRAME_WIDTH * scale), round(FRAME_HEIGHT * scale)))
    frame.alpha_composite(art, (round(left * scale), round(top * scale)))
    return frame


def keyed_sheet(sheet: Image.Image) -> Image.Image:
    """``sheet`` for the desktop window: each pixel Maodan in its own colour, or KEY_COLOR."""
    opaque = sheet.getchannel("A").point(lambda opacity: 255 if opacity >= ALPHA_THRESHOLD else 0)
    colours = sheet.convert("RGB")
    # A pixel of Maodan that happened to be exactly KEY_COLOR would show as a hole.
    red, green, blue = (channel.point(lambda value, wanted=wanted: 255 if value == wanted else 0)
                        for channel, wanted in zip(colours.split(), KEY_COLOR))
    colours.paste((KEY_COLOR[0], KEY_COLOR[1], KEY_COLOR[2] + 1),
                  mask=ImageChops.multiply(ImageChops.multiply(red, green), blue))
    keyed = Image.new("RGB", sheet.size, KEY_COLOR)
    keyed.paste(colours, mask=opaque)
    return keyed


def sheet_at(sources: dict[str, Image.Image], scale: float) -> Image.Image:
    """Every animation's frames in one RGBA sheet, each cell ``scale`` times the normal size."""
    width, height = round(FRAME_WIDTH * scale), round(FRAME_HEIGHT * scale)
    sheet = Image.new("RGBA", (COLUMNS * width, ROWS * height))
    for action, row in ACTION_ROWS.items():
        for index, plan in enumerate(ACTION_FRAMES[action]):
            cell = row * COLUMNS + index
            frame = render_frame(sources[plan.pose], POSES_BY_NAME[plan.pose], plan, scale)
            sheet.alpha_composite(frame, ((cell % COLUMNS) * width, (cell // COLUMNS) * height))
    return sheet


def build(assets: Path = ASSETS) -> None:
    required = {frame.pose for plans in ACTION_FRAMES.values() for frame in plans}
    missing = [str(POSES_BY_NAME[name].file) for name in sorted(required)
               if not POSES_BY_NAME[name].file.is_file()]
    if missing:
        raise FileNotFoundError("Missing Maodan key poses:\n" + "\n".join(missing))

    sources = {name: load_pose(POSES_BY_NAME[name]) for name in required}
    manifest: dict = {
        "frameWidth": FRAME_WIDTH,
        "frameHeight": FRAME_HEIGHT,
        "columns": COLUMNS,
        "spritesheet": "spritesheet.png",
        # One sheet per pet size, each keyed onto the one colour the desktop window hides.
        "desktop": {
            "keyColor": "#{:02x}{:02x}{:02x}".format(*KEY_COLOR),
            "sheets": {str(size): f"desktop/sheet-{size}.png" for size in DESKTOP_SIZES},
        },
        "animations": {},
    }

    for action, row in ACTION_ROWS.items():
        plans = ACTION_FRAMES[action]
        previous_pixels: bytes | None = None
        for index, plan in enumerate(plans):
            frame = render_frame(sources[plan.pose], POSES_BY_NAME[plan.pose], plan)
            alpha_bbox = frame.getchannel("A").getbbox()
            if alpha_bbox is None:
                raise ValueError(f"Empty frame in {action}: {index}")
            if (alpha_bbox[0] == 0 or alpha_bbox[1] == 0
                    or alpha_bbox[2] == FRAME_WIDTH or alpha_bbox[3] == FRAME_HEIGHT):
                raise ValueError(f"Clipped frame in {action}: {index}")
            pixels = frame.tobytes()
            if pixels == previous_pixels:
                raise ValueError(
                    f"Repeated adjacent frames in {action}: {index - 1} and {index}")
            previous_pixels = pixels
        animation = {"row": row, "frames": len(plans), "fps": 8}
        if action in DURATIONS:
            if len(DURATIONS[action]) != len(plans):
                raise ValueError(f"{action} has {len(plans)} frames but "
                                 f"{len(DURATIONS[action])} durations")
            animation["durations"] = DURATIONS[action]
        manifest["animations"][action] = animation

    (assets / "desktop").mkdir(parents=True, exist_ok=True)
    sheet_at(sources, 1).save(assets / "spritesheet.png", optimize=True)
    for size, name in manifest["desktop"]["sheets"].items():
        keyed_sheet(sheet_at(sources, 1.5 * int(size) / 100)).save(assets / name, optimize=True)
    description = json.dumps(manifest, ensure_ascii=False, indent=2)
    (assets / "animation.json").write_text(description + "\n", encoding="utf-8")
    (assets / "animation.js").write_text(
        "// Generated by tools/build_atlas.py; the same data as animation.json, for web/index.html.\n"
        f"window.MAODAN_ANIMATION = {description};\n", encoding="utf-8")
    print(f"Built Maodan's atlas and {len(DESKTOP_SIZES)} desktop sheets in {assets}")


if __name__ == "__main__":
    build()
