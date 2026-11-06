"""Fixer 3D: a cozy keyboard repair bench, in 3D.

Pick a keyboard and take it all apart: every keycap and every switch one by one, the stabilisers, the plate, the
foam, the circuit board, down to the bare case, with a screwdriver for the screws underneath. Brush out the crumbs
(and find what was lost in there), build it back up in your own colours and switches, then type on it to test
every key. fixer.py is the 2D game; this borrows its keyboard layouts. It needs the Ursina engine
(pip install ursina), which brings Pillow with it; the sounds are made by fixer3d_sounds.py.

Mouse: drag to turn it round (right button anywhere, or left on an empty spot), scroll to zoom. Click to use the
tool in your hand: one click, one part, whether it's a keycap, a switch or a screw. The brush is the one you hold
down: drag it over the crumbs. Right-click puts back what you're holding. Point at the sound or music button for
its volume: scroll, or click the slider.
Keys: 1 hand, 2 screwdriver, 3 keycap puller, 4 switch puller, 5 brush. F flip it over, R set it level, H help,
M music, F3 frame rate, F11 full screen or a window, Esc back.
It starts full screen; run with --windowed for a window, --fps N to change the frame cap (120 by default, 0 for
none), or --vsync to match the monitor instead.

Every part is drawn as one mesh (with a colour for each corner), and so are all the keycaps together and all the
switches together: a keycap comes off by rewriting just its own corners in that mesh. That keeps the number of
things drawn small, so it runs fast with lots of detail.
"""
import colorsys
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from array import array
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")  # fixer.py imports pygame
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fixer import KEY_LEGENDS, KEYBOARD_MODELS, keyboard_layout, shade  # noqa: E402

import fixer3d_sounds  # noqa: E402
import ursina  # noqa: E402
from panda3d.core import (BitMask32, CardMaker, CollisionBox, CollisionHandlerQueue, CollisionNode,  # noqa: E402
                          CollisionRay, CollisionTraverser, Filename, Geom, GeomNode, GeomTriangles,
                          GeomVertexArrayFormat, GeomVertexData, GeomVertexFormat, InternalName, LVector3f,
                          OmniBoundingVolume, Point2, Point3, Quat, TransparencyAttrib)
from ursina import (Button, Entity, Text, Texture, Ursina, Vec3, application, camera, color, curve,  # noqa: E402
                    destroy, held_keys, mouse, window)
from ursina.audio import _audio_manager  # noqa: E402
from ursina.lights import DirectionalLight  # noqa: E402
from ursina.models.procedural.quad import Quad  # noqa: E402
from ursina.shader import Shader  # noqa: E402

CACHE = os.path.join(tempfile.gettempdir(), "fixer3d")  # made sounds, the window icon, fonts
SOUNDS = os.path.join(CACHE, f"sounds{fixer3d_sounds.VERSION}")
SAVE_FILE = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Fixer3D", "save.json")

# Sizes are in key widths: one key is 1 unit across (19 mm in real life). y is up; the front of the keyboard is -z.
MARGIN = 0.55  # how far the case reaches past the keys
WALL, WALL_H, FLOOR = 0.3, 1.3, 0.25  # the bottom case's walls and floor
FOAM_Y = 0.32  # the middle of the case foam on the floor
PCB_Y = 0.56  # the middle of the circuit board
PLATE_FOAM_Y = 0.78  # the foam between the board and the plate
PLATE_Y = 0.99  # the middle of the steel plate
SWITCH_Y = 1.03  # the top of the plate, where the switch housings stand
CAP_Y, CAP_H, DISH = 1.36, 0.5, 0.035  # the keycaps' bottom edge, how tall they are, how deep their tops dip
FRAME_Y = (1.3, 1.75)  # the top frame, from the top of the walls up
HOLE = 0.74  # the square cut-out in the plate for a switch (14 mm)
LIFT = 7  # how far a big part flies when it comes off
TURN_TIME = 0.5  # seconds a screw takes to turn out (or in) once you click it
PRESS = 0.13  # how far a key goes down when it's pressed
DESK_Y = -2.6  # the top of the desk
PIVOT_Y = 1.4  # the height the keyboard turns about, when it's level (it's lifted as it turns, to clear the desk)
CLEARANCE = 0.12  # how near the desk its lowest corner may come
VOLUME_TRACK = (0.262, 0.392)  # the volume sliders' bottom and top, in the screen's units
TRAY_SCALE = 0.34  # the trays hold the keycaps and switches laid out like the keyboard, this much smaller
BRUSH_REACH = 0.7  # how near the brush has to pass to sweep a speck away
BRUSH_STROKE = 0.8  # how far the brush moves (in key widths) between one swish and the next
PICK_MASK = BitMask32.bit(8)  # what the mouse ray hits: the parts' click shapes, nothing else
SHADOW_MASK = BitMask32.bit(0)  # the light's camera, for shadows

# The parts' own colours
PCB_GREEN, STEEL, RUBBER = (34, 100, 64), (150, 154, 162), (30, 30, 34)
GOLDEN, SILVER, BLACK, WHITE = (212, 176, 90), (196, 198, 206), (24, 24, 28), (240, 240, 236)
FOAM, PLATE_FOAM = (206, 204, 196), (226, 210, 204)
HOUSING, HOUSING_TOP, CLIP, LIGHT_WINDOW = (52, 54, 62), (84, 86, 96), (40, 42, 50), (226, 230, 236)
WIRES = [(205, 60, 55), (44, 44, 48), (60, 170, 80), (236, 236, 230)]  # USB's four: power, ground, data, data

# Colours you can build in. "Original" is the keyboard's own; the rest go on any keycap or case part.
PAINTS = [("Original", None), ("Cream", (244, 236, 218)), ("Latte", (214, 186, 150)), ("Cocoa", (122, 88, 66)),
          ("Sage", (168, 190, 160)), ("Matcha", (120, 160, 100)), ("Sky", (150, 190, 222)),
          ("Ocean", (70, 112, 160)), ("Lavender", (186, 168, 220)), ("Peach", (246, 180, 150)),
          ("Rose", (232, 140, 150)), ("Butter", (246, 218, 130)), ("Charcoal", (58, 58, 64))]
# Switches you can build with: (colour name, kind, what it feels like, the stem's colour)
SWITCH_KINDS = [("red", "Linear", "smooth and quiet", (214, 60, 56)),
                ("brown", "Tactile", "a soft bump on the way down", (140, 92, 58)),
                ("blue", "Clicky", "a crisp click with every press", (64, 120, 220)),
                ("pink", "Silent", "dampened: hardly a sound", (232, 150, 176))]
TOOLS = [("hand", "Hand"), ("driver", "Screwdriver"), ("puller", "Keycap puller"), ("switcher", "Switch puller"),
         ("brush", "Brush"), ("lube", "Lube")]
TRINKETS = ["lucky coin", "paperclip", "guitar pick", "tiny die", "star sticker", "toy brick"]
KEY_NAMES = {"Back": "Backspace", "Caps": "Caps Lock", "Ent": "numpad Enter", "Num": "Num Lock",
             "PrtSc": "Print Screen", "ScrLk": "Scroll Lock", "PgUp": "Page Up", "PgDn": "Page Down",
             "Ins": "Insert", "Del": "Delete", "Win": "Windows", "Space": "space bar"}
# What the engine calls each key when you press it on a real keyboard (for testing it at the end)
INPUT_NAMES = {"Esc": ["escape"], "Back": ["backspace"], "Tab": ["tab"], "Caps": ["caps_lock", "caps lock"],
               "Enter": ["enter"], "Ent": ["enter"], "Space": ["space"], "Ins": ["insert"], "Home": ["home"],
               "PgUp": ["page up"], "Del": ["delete"], "End": ["end"], "PgDn": ["page down"], "Up": ["up arrow"],
               "Down": ["down arrow"], "Left": ["left arrow"], "Right": ["right arrow"],
               "PrtSc": ["print_screen", "print screen"], "ScrLk": ["scroll_lock", "scroll lock"],
               "Pause": ["pause"], "Num": ["num_lock", "num lock"], "Menu": ["menu"],
               "Win": ["lmeta", "left meta", "lwin", "left windows"], "Fn": []}
SIDED = {"Shift": "shift", "Ctrl": "control", "Alt": "alt"}

# The cozy look: warm wood, cream paper, cocoa ink
BACKDROP, CREAM, PAPER, PAPER_DARK = (40, 30, 26), (250, 244, 232), (236, 226, 208), (214, 200, 178)
COCOA, MUTED, HONEY, HONEY_DARK = (74, 54, 44), (150, 128, 112), (238, 172, 84), (196, 120, 44)
SAGE, ROSE, INK_LIGHT = (126, 170, 120), (222, 118, 108), (255, 252, 246)
SUN = (206, 186, 160)  # the lamp's light
GLOW = (255, 214, 120)  # a tested key's legend
GRIME = (150, 124, 78)  # years of fingers: keycaps go yellow and a little greasy
WASH_TIME = 1.4  # seconds the keycaps spend in the bowl

# More keyboards, here in 3D (the first three are the 2D game's too). Each is a real kind, with something of its own:
# grime is how many of its keycaps are grubby (1 for all of them), dirt how much more crumbs and dust it has.
MORE_KEYBOARDS = [
    dict(key="numpad", name="Number pad", size="numpad", switch="pink", grime=0.25,
         case=(206, 222, 212), cap=(250, 248, 240), mod=(168, 198, 182), legend=(60, 80, 70), accent=(236, 146, 116),
         cable=(206, 222, 212),
         intro="A little number pad, for sums and spreadsheets: a quick, cozy job."),
    dict(key="knob75", name="75% keyboard", size="75", switch="red", knob=(15.5, 0.5), grime=0.15,
         case=(192, 182, 218), cap=(248, 244, 236), mod=(146, 132, 190), legend=(66, 58, 92), accent=(246, 192, 116),
         cable=(146, 132, 190),
         intro="A 75% with a volume knob: lift the knob off by hand, and turn it to test it at the end."),
    dict(key="wireless65", name="Wireless 65% keyboard", size="65", switch="brown", wireless=True, grime=0.15,
         case=(146, 174, 148), cap=(244, 240, 228), mod=(106, 138, 110), legend=(50, 66, 52), accent=(236, 174, 94),
         cable=(244, 240, 228),
         intro="A wireless one, with a battery inside: unplug its lead before you lift the circuit board out."),
    dict(key="gasket96", name="Gasket 96% keyboard", size="96", switch="red", gaskets=True, weight=True, grime=0.1,
         case=(64, 70, 88), cap=(230, 222, 204), mod=(94, 108, 140), legend=(46, 50, 62), accent=(222, 120, 96),
         cable=(222, 120, 96),
         intro="A hobbyist's board: its plate floats on rubber gaskets, and a brass weight sits inside."),
    dict(key="vintage", name="Vintage keyboard", size="full", switch="blue", grime=1.0, dirt=2.0,
         case=(214, 204, 178), cap=(234, 226, 204), mod=(190, 178, 152), legend=(74, 64, 54), accent=(196, 98, 70),
         cable=(214, 204, 178),
         intro="An old office keyboard, yellowed and dusty: wash its keycaps in the bowl before they go back on."),
]
# Computer mice: the 2D game's three kinds, with their insides. size is (width, length, height) in key widths (an
# office mouse is about 65 x 120 x 38 mm); feet is how many skates are on the bottom, each over a screw.
MICE = [
    dict(kind="mouse", key="mouse_office", name="Office mouse", size=(3.4, 6.3, 1.95), feet=2,
         case=(198, 200, 208), bottom=(70, 72, 80), accent=(80, 140, 200), cable=(40, 40, 44), skate=(236, 236, 232),
         intro="A plain wired office mouse. Its screws hide under the feet: flip it over (F) and peel them off."),
    dict(kind="mouse", key="mouse_gaming", name="Gaming mouse", size=(3.6, 6.6, 2.1), feet=4, side=True, rgb=True,
         weight=True, case=(38, 40, 48), bottom=(28, 30, 34), accent=(90, 220, 160), cable=(30, 30, 34),
         skate=(226, 226, 222),
         intro="A gaming mouse: side buttons, a light-up logo, and a weight inside. Four screws, under four feet."),
    dict(kind="mouse", key="mouse_travel", name="Travel mouse", size=(3.05, 5.4, 1.75), feet=3, wireless=True,
         case=(214, 92, 84), bottom=(64, 60, 66), accent=(250, 236, 220), cable=(230, 230, 226),
         skate=(236, 236, 232),
         intro="A wireless travel mouse, with a battery under a cover underneath: take that out before you open it."),
]
for _m in MICE:  # (what the screen's colour picker and the switch card expect of any product)
    _m.setdefault("cap", _m["case"])
    _m.setdefault("switch", "blue")
_BY_KEY = {m["key"]: m for m in KEYBOARD_MODELS + MORE_KEYBOARDS + MICE}
# On the menu, smallest first
MODELS = [_BY_KEY[k] for k in ("numpad", "compact", "wireless65", "knob75", "tkl", "gasket96", "full", "vintage")]
ALL_MODELS = MODELS + MICE
KINDS = [("keyboard", "Keyboards"), ("mouse", "Mice")]


def kind_of(spec):
    return spec.get("kind", "keyboard")


def rgb(c, a=255):
    return color.rgba32(int(c[0]), int(c[1]), int(c[2]), a)


def smooth(s):
    return s * s * (3 - 2 * s)


def out_quad(s):
    return 1 - (1 - s) * (1 - s)


def mix(a, b, s):
    return tuple(x + (y - x) * s for x, y in zip(a, b))


def hue(h, sat=0.55, val=1.0):
    return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h % 1.0, sat, val))


def short_name(spec):
    return spec["name"].replace(" keyboard", "")


def nice_label(label):
    return KEY_NAMES.get(label, label)


def legend_for(cap):
    """Ink that shows up on a keycap of this colour."""
    return (58, 50, 46) if 0.3 * cap[0] + 0.59 * cap[1] + 0.11 * cap[2] > 150 else (246, 240, 230)


def keycap_tint(label):
    """Which of a keyboard's colours a keycap is: the accent for Esc and Enter, the main colour for letters,
    numbers and the space bar, the second colour for the rest."""
    if label in ("Esc", "Enter"):
        return "accent"
    return "cap" if len(label) == 1 or label == "Space" else "mod"


def part_colours(spec, paint):
    """The colours of a keyboard's case parts, in its own colours or in a paint."""
    case = paint or spec["case"]
    inside = shade(case, 0.82)
    if "bottom" in spec:  # a mouse's base is its own colour
        inside = spec["bottom"] if paint is None else shade(paint, 0.62)
    return {"case": case, "frame": shade(case, 1.12 if sum(case) < 300 else 0.94), "legs": shade(case, 0.8),
            "inside": inside, "cable": paint or spec["cable"]}


def footprint(spec):
    """How much room a product takes on the desk: its width and depth."""
    if kind_of(spec) == "mouse":
        return spec["size"][0], spec["size"][1]
    _, wu, hu = layout_for(spec["size"])
    return wu + 2 * MARGIN, hu + 2 * MARGIN


def cap_colours(spec, label, paint):
    """A keycap's body and its legend, in the keyboard's own colours or in a paint."""
    if paint is None:
        return spec[keycap_tint(label)], spec["legend"]
    return paint, legend_for(paint)


def grubby(body, legend):
    """A keycap that's been typed on for years: yellowed, and its legend a little worn."""
    return mix(body, GRIME, 0.34), mix(legend, body, 0.35)


def layout_for(size):
    """Every key on a keyboard of this size, in key widths: (label, x, y, w, h), and the layout's width and height.
    The full-size, tenkeyless and 60% layouts are the 2D game's; these are the rest:
    "numpad", the number pad on its own; "65", a 60% with a column of keys down the right and the arrows tucked in
    under it; "75", the same with a tight row of F keys on top; "96", the 75% with a number pad beside it."""
    if size in ("full", "tkl", "60"):
        return keyboard_layout(size)
    keys = []
    pad = [("Num", 0, 0), ("/", 1, 0), ("*", 2, 0), ("-", 3, 0), ("7", 0, 1), ("8", 1, 1), ("9", 2, 1), ("4", 0, 2),
           ("5", 1, 2), ("6", 2, 2), ("1", 0, 3), ("2", 1, 3), ("3", 2, 3), (".", 2, 4)]
    tall = [("+", 3, 1, 1, 2), ("Ent", 3, 3, 1, 2), ("0", 0, 4, 2, 1)]

    def number_pad(x0, y0):
        keys.extend((label, x0 + x, y0 + y, 1, 1) for label, x, y in pad)
        keys.extend((label, x0 + x, y0 + y, w, h) for label, x, y, w, h in tall)

    if size == "numpad":
        number_pad(0, 0)
        return keys, 4.0, 5.0
    top = 1.25 if size in ("75", "96") else 0.0
    if top:  # the F row, packed tight
        keys.append(("Esc", 0, 0, 1, 1))
        for i in range(12):
            keys.append((f"F{i + 1}", 1.25 + i + (i // 4) * 0.25, 0, 1, 1))
        keys.append(("Del", 14.0, 0, 1, 1))
        if size == "96":
            keys.append(("Ins", 15.0, 0, 1, 1))
    rows = [[("Esc" if not top else "`", 1)] + [(c, 1) for c in "1234567890-="] + [("Back", 2), ("Home", 1)],
            [("Tab", 1.5)] + [(c, 1) for c in "QWERTYUIOP[]"] + [("\\", 1.5), ("PgUp", 1)],
            [("Caps", 1.75)] + [(c, 1) for c in "ASDFGHJKL;'"] + [("Enter", 2.25), ("PgDn", 1)],
            [("Shift", 2.25)] + [(c, 1) for c in "ZXCVBNM,./"] + [("Shift", 1.75), ("Up", 1), ("End", 1)],
            [("Ctrl", 1.25), ("Win", 1.25), ("Alt", 1.25), ("Space", 6.25), ("Alt", 1), ("Fn", 1), ("Ctrl", 1),
             ("Left", 1), ("Down", 1), ("Right", 1)]]
    for r, row in enumerate(rows):
        x = 0.0
        for label, w in row:
            keys.append((label, x, top + r, w, 1))
            x += w
    width = 16.0
    if size == "96":  # and the number pad, just beside it
        for i, label in enumerate(("PrtSc", "ScrLk", "Pause", "Menu")):
            keys.append((label, 16.25 + i, 0, 1, 1))
        number_pad(16.25, top)
        width = 20.25
    return keys, width, top + 5


def look(cap):
    """How a keycap looks now: its colours, under any grime."""
    return grubby(cap.body, cap.legend) if cap.grimy else (cap.body, cap.legend)


def rects_minus_holes(x0, x1, z0, z1, holes):
    """The pieces of a rectangle that aren't in any of the holes, all of them lined up with the axes: how the plate
    and the foam get their cut-outs. Holes are (x0, x1, z0, z1)."""
    edges = sorted({z0, z1} | {v for h in holes for v in (h[2], h[3]) if z0 < v < z1})
    pieces = []
    for za, zb in zip(edges, edges[1:]):
        zm = (za + zb) / 2
        x = x0
        for ha, hb in sorted((h[0], h[1]) for h in holes if h[2] <= zm <= h[3]):
            if ha > x:
                pieces.append((x, min(ha, x1), za, zb))
            x = max(x, hb)
        if x < x1:
            pieces.append((x, x1, za, zb))
    return pieces


# ---- meshes ----

class Shapes:
    """Triangles to draw, each corner with its own colour: everything of one part goes in one of these, and comes
    out as one mesh. Pieces can be grouped into items (a keycap, a switch, a crumb) that the mesh can move, hide
    or recolour on their own, and tagged ("case", "cap") so a colour can be painted onto just them."""

    def __init__(self):
        self.v, self.n, self.c, self.uv = [], [], [], []
        self.paint, self.tag, self.item = (1.0, 1.0, 1.0, 1.0), None, 0
        self.items, self.ranges = {}, {}  # item -> [start, end] rows; (item, tag) -> list of [start, end]
        self.cached = None

    def use(self, colour, tag=None):
        self.paint = (colour[0] / 255, colour[1] / 255, colour[2] / 255, 1.0)
        self.tag = tag
        return self

    def begin(self, item):
        self.item = item
        return self

    def _added(self, start):
        end = len(self.v)
        span = self.items.get(self.item)
        if span is None:
            self.items[self.item] = [start, end]
        else:
            span[1] = end
        if self.tag:
            spans = self.ranges.setdefault((self.item, self.tag), [])
            if spans and spans[-1][1] == start:
                spans[-1][1] = end
            else:
                spans.append([start, end])

    def quad(self, a, b, c, d, normal, uvs=None):
        start = len(self.v)
        self.v += [a, b, c, a, c, d]
        self.n += [normal] * 6
        self.c += [self.paint] * 6
        self.uv += [uvs[0], uvs[1], uvs[2], uvs[0], uvs[2], uvs[3]] if uvs else [(0.0, 0.0)] * 6
        self._added(start)

    def tri(self, a, b, c, normal):
        start = len(self.v)
        self.v += [a, b, c]
        self.n += [normal] * 3
        self.c += [self.paint] * 3
        self.uv += [(0.0, 0.0)] * 3
        self._added(start)

    def box(self, center, size):
        x, y, z = center
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        x0, x1, y0, y1, z0, z1 = x - hx, x + hx, y - hy, y + hy, z - hz, z + hz
        self.quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (1, 0, 0))
        self.quad((x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (-1, 0, 0))
        self.quad((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (0, 1, 0))
        self.quad((x0, y0, z1), (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (0, -1, 0))
        self.quad((x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (x0, y0, z1), (0, 0, 1))
        self.quad((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (0, 0, -1))

    def cylinder(self, base, radius, height, segments=14):
        """Standing up from base (the middle of its bottom)."""
        x, y, z = base
        ring = [(math.cos(2 * math.pi * k / segments), math.sin(2 * math.pi * k / segments)) for k in range(segments)]
        for (c0, s0), (c1, s1) in zip(ring, ring[1:] + ring[:1]):
            a, b = (x + c0 * radius, y, z + s0 * radius), (x + c1 * radius, y, z + s1 * radius)
            self.quad(a, b, (b[0], y + height, b[2]), (a[0], y + height, a[2]), ((c0 + c1) / 2, 0, (s0 + s1) / 2))
            self.tri((x, y + height, z), (a[0], y + height, a[2]), (b[0], y + height, b[2]), (0, 1, 0))
            self.tri((x, y, z), (b[0], y, b[2]), a, (0, -1, 0))

    def keycap(self, base, w, d):
        """A keycap standing on base (the middle of its bottom edge): its sides slope in towards the top, and the
        top dips a little in the middle, where your finger goes."""
        x, y, z = base
        rings = [(w / 2, d / 2, 0), (w / 2 - 0.11, d / 2 - 0.11, CAP_H), (w / 2 - 0.17, d / 2 - 0.17, CAP_H - DISH)]
        corners = [[(x + sx * hw, y + hy, z + sz * hd) for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                   for hw, hd, hy in rings]
        below = Vec3(x, y - 10, z)
        for lower, upper in ((corners[0], corners[1]), (corners[1], corners[2])):
            for i in range(4):
                a, b, c, dd = lower[i], lower[(i + 1) % 4], upper[(i + 1) % 4], upper[i]
                n = (Vec3(*b) - Vec3(*a)).cross(Vec3(*c) - Vec3(*a)).normalized()
                if n.dot(Vec3(*a) - below) < 0:  # make it face outwards
                    n = -n
                self.quad(a, b, c, dd, tuple(n))
        self.quad(*corners[2], (0, 1, 0))

    def rod(self, a, b, t):
        """A square bar of thickness t from a to b, any way round: wires, hair, leaves."""
        A, B = Vec3(*a), Vec3(*b)
        d = B - A
        if d.length() < 1e-6:
            return
        d = d.normalized()
        up = Vec3(0, 1, 0) if abs(d.y) < 0.9 else Vec3(1, 0, 0)
        u = d.cross(up).normalized() * (t / 2)
        w = d.cross(u).normalized() * (t / 2)
        ca = [A + u + w, A - u + w, A - u - w, A + u - w]
        cb = [B + u + w, B - u + w, B - u - w, B + u - w]
        for i in range(4):
            j = (i + 1) % 4
            normal = ((ca[i] + ca[j]) / 2 - A).normalized()
            self.quad(tuple(ca[i]), tuple(ca[j]), tuple(cb[j]), tuple(cb[i]), tuple(normal))
        self.quad(*[tuple(p) for p in ca], tuple(-d))
        self.quad(*[tuple(p) for p in reversed(cb)], tuple(d))

    def slab(self, points, y0, y1):
        """A flat piece cut to an outline (points round it, in x and z), from y0 up to y1."""
        cx = sum(p[0] for p in points) / len(points)
        cz = sum(p[1] for p in points) / len(points)
        for (x0, z0), (x1, z1) in zip(points, points[1:] + points[:1]):
            self.tri((cx, y1, cz), (x0, y1, z0), (x1, y1, z1), (0, 1, 0))
            self.tri((cx, y0, cz), (x1, y0, z1), (x0, y0, z0), (0, -1, 0))
            nx, nz = z1 - z0, -(x1 - x0)
            length = math.hypot(nx, nz) or 1
            nx, nz = nx / length, nz / length
            if nx * ((x0 + x1) / 2 - cx) + nz * ((z0 + z1) / 2 - cz) < 0:
                nx, nz = -nx, -nz
            self.quad((x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0), (nx, 0, nz))

    def surface(self, f, u0, u1, nu, v0, v1, nv, inside):
        """A smooth curved surface: f(u, v) gives a point, for u from u0 to u1 and v from v0 to v1, in nu by nv
        steps. Each corner is shaded smooth (its normal worked out from f round it), facing away from inside(p)."""
        def normal(u, v):
            e = 1e-3
            p = Vec3(*f(u, v))
            du = Vec3(*f(min(u + e, 1), v)) - Vec3(*f(max(u - e, 0), v))
            dv = Vec3(*f(u, v + e)) - Vec3(*f(u, v - e))
            n = du.cross(dv)
            n = n.normalized() if n.length() > 1e-9 else Vec3(0, 1, 0)
            return n if n.dot(p - Vec3(*inside(p))) >= 0 else -n
        grid = [[(u0 + (u1 - u0) * i / nu, v0 + (v1 - v0) * j / nv) for j in range(nv + 1)] for i in range(nu + 1)]
        pts = [[tuple(f(u, v)) for u, v in row] for row in grid]
        nrm = [[tuple(normal(u, v)) for u, v in row] for row in grid]
        start = len(self.v)
        for i in range(nu):
            for j in range(nv):
                for a, b in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j), (i + 1, j + 1), (i, j + 1)):
                    self.v.append(pts[a][b])
                    self.n.append(nrm[a][b])
                    self.c.append(self.paint)
                    self.uv.append((0.0, 0.0))
        self._added(start)

    def axle(self, center, radius, width, segments=18, along="x"):
        """A cylinder lying down, along x (like a wheel on its axle) or along z (like a battery)."""
        x, y, z = center

        def at(u, s, c):  # u along the cylinder, (s, c) round it
            return (x + u, y + s, z + c) if along == "x" else (x + c, y + s, z + u)

        def way(u, s, c):
            return (u, s, c) if along == "x" else (c, s, u)
        ring = [(math.cos(2 * math.pi * k / segments), math.sin(2 * math.pi * k / segments)) for k in range(segments)]
        h = width / 2
        for (c0, s0), (c1, s1) in zip(ring, ring[1:] + ring[:1]):
            a, b = (s0 * radius, c0 * radius), (s1 * radius, c1 * radius)
            self.quad(at(-h, *a), at(-h, *b), at(h, *b), at(h, *a), way(0, (s0 + s1) / 2, (c0 + c1) / 2))
            self.tri(at(h, 0, 0), at(h, *a), at(h, *b), way(1, 0, 0))
            self.tri(at(-h, 0, 0), at(-h, *b), at(-h, *a), way(-1, 0, 0))

    def wall(self, points, y0, y1, thick):
        """A thin wall standing round an outline (points round it, in x and z), `thick` thick, inside it."""
        cx = sum(p[0] for p in points) / len(points)
        cz = sum(p[1] for p in points) / len(points)
        inner = []
        for x, z in points:
            dx, dz = x - cx, z - cz
            d = math.hypot(dx, dz) or 1
            inner.append((x - dx / d * thick, z - dz / d * thick))
        for k in range(len(points)):
            (ax, az), (bx, bz) = points[k], points[(k + 1) % len(points)]
            (ix, iz), (jx, jz) = inner[k], inner[(k + 1) % len(points)]
            nx, nz = bz - az, -(bx - ax)
            length = math.hypot(nx, nz) or 1
            nx, nz = nx / length, nz / length
            if nx * ((ax + bx) / 2 - cx) + nz * ((az + bz) / 2 - cz) < 0:
                nx, nz = -nx, -nz
            self.quad((ax, y0, az), (bx, y0, bz), (bx, y1, bz), (ax, y1, az), (nx, 0, nz))
            self.quad((ix, y0, iz), (jx, y0, jz), (jx, y1, jz), (ix, y1, iz), (-nx, 0, -nz))
            self.quad((ax, y1, az), (bx, y1, bz), (jx, y1, jz), (ix, y1, iz), (0, 1, 0))

    def arrays(self):
        if self.cached is None:
            self.cached = (array("f", [c for p in self.v for c in p]), array("f", [c for p in self.n for c in p]),
                           array("f", [c for p in self.c for c in p]), array("f", [c for p in self.uv for c in p]))
        return self.cached

    def mesh(self, parent, name="mesh", **kwargs):
        pos, nrm, col, uv = self.arrays()
        return Mesh3(array("f", pos), nrm, array("f", col), uv, parent, name, self.items, self.ranges, **kwargs)


_FORMAT = []


def vertex_format():
    """Corners with a position, a normal, a colour and a texture point, each in its own array: so any one of
    them can be rewritten in one go."""
    if not _FORMAT:
        fmt = GeomVertexFormat()
        for name, n, contents in ((InternalName.getVertex(), 3, Geom.C_point),
                                  (InternalName.getNormal(), 3, Geom.C_normal),
                                  (InternalName.getColor(), 4, Geom.C_color),
                                  (InternalName.getTexcoord(), 2, Geom.C_texcoord)):
            column = GeomVertexArrayFormat()
            column.addColumn(name, n, Geom.NT_float32, contents)
            fmt.addArray(column)
        _FORMAT.append(GeomVertexFormat.registerFormat(fmt))
    return _FORMAT[0]


class Mesh3:
    """Shapes on the graphics card: one mesh, whose items can be moved, hidden or recoloured on their own by
    rewriting just their corners."""

    def __init__(self, pos, nrm, col, uv, parent, name="mesh", items=None, ranges=None, texture=None,
                 hidden=False, shadow=True):
        self.base, self.nrm, self.col, self.uv = pos, nrm, col, uv
        self.items, self.ranges, self.texture = items or {0: [0, len(pos) // 3]}, ranges or {}, texture
        rows = len(pos) // 3
        if not rows:
            self.np = parent.attachNewNode(name)
            return
        vdata = GeomVertexData(name, vertex_format(), Geom.UHDynamic)
        vdata.setNumRows(rows)
        for k, data in enumerate((pos, nrm, col, uv)):
            memoryview(vdata.modifyArray(k)).cast("B").cast("f")[:] = data
        prim = GeomTriangles(Geom.UHStatic)
        prim.addConsecutiveVertices(0, rows)
        prim.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        node = GeomNode(name)
        node.addGeom(geom)
        node.setBounds(OmniBoundingVolume())  # its corners move, so never let it be culled on old bounds
        node.setFinal(True)
        self.np = parent.attachNewNode(node)
        self.np.setTwoSided(True)
        if texture is not None:
            self.np.setTexture(getattr(texture, "_texture", texture), 1)
        if not shadow:
            self.np.hide(SHADOW_MASK)
        if hidden:
            for item in self.items:
                self.move(item, None)

    def view(self, k):
        vdata = self.np.node().modifyGeom(0).modifyVertexData()
        return memoryview(vdata.modifyArray(k)).cast("B").cast("f")

    def move(self, item, offset=(0, 0, 0)):
        """Put an item where it was made (shifted by offset), or with offset None, hide it."""
        span = self.items.get(item)
        if not span or self.np.node().getNumGeoms() == 0:
            return
        s, e = span
        if offset is None:
            vals = array("f", self.base[3 * s:3 * s + 3]) * (e - s)
        elif offset == (0, 0, 0):
            vals = self.base[3 * s:3 * e]
        else:
            vals = array("f", [v + offset[i % 3] for i, v in enumerate(self.base[3 * s:3 * e])])
        self.view(0)[3 * s:3 * e] = vals

    def paint(self, item, tag, colour):
        spans = self.ranges.get((item, tag))
        if not spans or self.np.node().getNumGeoms() == 0:
            return
        view = self.view(2)
        for s, e in spans:
            vals = array("f", (colour[0] / 255, colour[1] / 255, colour[2] / 255, 1.0)) * (e - s)
            self.col[4 * s:4 * e] = vals
            view[4 * s:4 * e] = vals

    def brighten(self, item, factor):
        """Light an item up (when the mouse is on it), or with factor 1, set it back."""
        span = self.items.get(item)
        if not span or self.np.node().getNumGeoms() == 0:
            return
        s, e = span
        seg = self.col[4 * s:4 * e]
        if factor != 1:
            seg = array("f", [min(1.0, v * factor) if i % 4 != 3 else v for i, v in enumerate(seg)])
        self.view(2)[4 * s:4 * e] = seg

    def piece(self, item, parent, center):
        """A copy of one item as a mesh of its own, centred on center, in its colours now: to fly about."""
        s, e = self.items[item]
        pos = array("f", [v - center[i % 3] for i, v in enumerate(self.base[3 * s:3 * e])])
        return Mesh3(pos, self.nrm[3 * s:3 * e], array("f", self.col[4 * s:4 * e]), self.uv[2 * s:2 * e], parent,
                     "piece", texture=self.texture)


COZY = Shader(language=Shader.GLSL, name="cozy", vertex="""#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat3 p3d_NormalMatrix;
uniform mat4 p3d_ViewMatrix;
uniform struct {
    vec4 position;
    vec3 color;
    vec3 attenuation;
    vec3 spotDirection;
    float spotCosCutoff;
    float spotExponent;
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
} p3d_LightSource[1];
in vec4 vertex;
in vec3 normal;
in vec4 p3d_Color;
in vec2 p3d_MultiTexCoord0;
out vec2 uv;
out vec4 tint;
out vec3 view_pos;
out vec3 view_normal;
out vec3 view_up;
out vec4 shadow_coord;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * vertex;
    view_pos = vec3(p3d_ModelViewMatrix * vertex);
    view_normal = normalize(p3d_NormalMatrix * normal);
    view_up = mat3(p3d_ViewMatrix) * vec3(0.0, 1.0, 0.0);
    shadow_coord = p3d_LightSource[0].shadowViewMatrix * vec4(view_pos, 1.0);
    uv = p3d_MultiTexCoord0;
    tint = p3d_Color;
}
""", fragment="""#version 150
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform struct {
    vec4 position;
    vec3 color;
    vec3 attenuation;
    vec3 spotDirection;
    float spotCosCutoff;
    float spotExponent;
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
} p3d_LightSource[1];
uniform vec3 sky_color;
uniform vec3 ground_color;
uniform float shadow_blur;
uniform float shadow_bias;
in vec2 uv;
in vec4 tint;
in vec3 view_pos;
in vec3 view_normal;
in vec3 view_up;
in vec4 shadow_coord;
out vec4 fragment_color;
void main() {
    vec4 base = texture(p3d_Texture0, uv) * tint * p3d_ColorScale;
    if (base.a < 0.35) discard;
    vec3 n = normalize(view_normal);
    vec3 to_light = p3d_LightSource[0].position.xyz - view_pos * p3d_LightSource[0].position.w;
    float facing = max(dot(n, normalize(to_light)), 0.0);
    float lit = 0.0;
    for (int x = -1; x <= 1; ++x) {
        for (int y = -1; y <= 1; ++y) {
            vec4 c = shadow_coord;
            c.xy += vec2(float(x), float(y)) * shadow_blur * c.w;
            c.z -= shadow_bias * c.w;
            lit += textureProj(p3d_LightSource[0].shadowMap, c);
        }
    }
    lit /= 9.0;
    float up = dot(n, normalize(view_up)) * 0.5 + 0.5;
    vec3 ambient = mix(ground_color, sky_color, up);
    vec3 light = ambient + p3d_LightSource[0].color * facing * mix(0.3, 1.0, lit);
    fragment_color = vec4(base.rgb * light, 1.0);
}
""", default_input={"sky_color": Vec3(0.5, 0.47, 0.45), "ground_color": Vec3(0.3, 0.25, 0.22),
                    "shadow_blur": 0.0011, "shadow_bias": 0.0006})


# ---- pictures: icons, textures, and the keycaps' legends, all drawn in code ----

FONT, BOLD_FONT = "OpenSans-Regular.ttf", "OpenSans-Regular.ttf"


def setup_fonts():
    """Candara (rounded and friendly) if this computer has it, else the font that comes with Ursina. They're
    copied into a small folder of their own, as Ursina searches its font folder for each text it makes."""
    global FONT, BOLD_FONT
    folder = os.path.join(CACHE, "fonts")
    system = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    try:
        os.makedirs(folder, exist_ok=True)
        for name in ("Candara.ttf", "Candarab.ttf"):
            if not os.path.exists(os.path.join(folder, name)) and os.path.exists(os.path.join(system, name)):
                shutil.copy(os.path.join(system, name), folder)
        if all(os.path.exists(os.path.join(folder, n)) for n in ("Candara.ttf", "Candarab.ttf")):
            FONT, BOLD_FONT = "Candara.ttf", "Candarab.ttf"
            application.fonts_folder = Path(folder)
    except OSError:
        pass
    Text.default_font = FONT


def font_file(bold=False):
    name = BOLD_FONT if bold else FONT
    for folder in (os.path.join(CACHE, "fonts"), os.path.join(os.path.dirname(ursina.__file__), "fonts")):
        if os.path.exists(os.path.join(folder, name)):
            return os.path.join(folder, name)
    return os.path.join(os.path.dirname(ursina.__file__), "fonts", "OpenSans-Regular.ttf")


def _capsule(d, a, b, w, fill):
    d.line([a, b], fill=fill, width=int(w))
    r = w / 2
    for x, y in (a, b):
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def draw_icon(name, size=128):
    """A white icon on a clear background (tinted when it's shown), drawn big and shrunk so its edges are smooth.
    Coordinates are out of 1024."""
    from PIL import Image, ImageDraw, ImageFont
    big = size * 4
    img = Image.new("RGBA", (big, big), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    k = big / 1024
    W, CLEAR = (255, 255, 255, 255), (255, 255, 255, 0)

    def P(x, y):
        return x * k, y * k

    def box(x0, y0, x1, y1, r=0, fill=W):
        d.rounded_rectangle([P(x0, y0), P(x1, y1)], radius=r * k, fill=fill)

    def cap(a, b, w, fill=W):
        _capsule(d, P(*a), P(*b), w * k, fill)

    if name == "hand":
        box(300, 470, 730, 880, 170)
        for x0, top in ((300, 250), (412, 180), (524, 200), (636, 290)):
            box(x0, top, x0 + 94, 640, 47)
        cap((350, 740), (190, 560), 100)
    elif name == "driver":
        cap((190, 834), (420, 604), 190)
        for t in (0.3, 0.55, 0.8):
            px, py = 190 + 230 * t, 834 - 230 * t
            cap((px - 45, py - 45), (px + 45, py + 45), 20, CLEAR)
        cap((420, 604), (480, 544), 120)
        cap((480, 544), (810, 214), 56)
        cap((810, 214), (850, 174), 34)
    elif name == "puller":
        d.ellipse([P(120, 640), P(420, 940)], outline=W, width=int(64 * k))
        cap((370, 690), (560, 500), 64)
        cap((560, 500), (560, 170), 52)
        cap((560, 500), (890, 500), 52)
        cap((560, 170), (630, 220), 46)
        cap((890, 500), (840, 430), 46)
    elif name == "switcher":
        cap((820, 200), (250, 560), 62)
        cap((820, 200), (470, 790), 62)
        cap((250, 560), (300, 650), 50)
        cap((470, 790), (380, 740), 50)
        d.ellipse([P(760, 140), P(880, 260)], fill=W)
    elif name == "brush":
        cap((170, 860), (500, 530), 110)
        cap((500, 530), (590, 440), 200)
        cap((610, 420), (790, 240), 250)
        for off in (-75, -25, 25, 75):
            ox, oy = off * 0.707, off * 0.707
            cap((640 + ox, 390 + oy), (850 + ox, 180 + oy), 12, CLEAR)
    elif name == "lube":  # a little tube of grease, and a drop coming out of its nozzle
        cap((230, 820), (560, 490), 230)
        cap((180, 870), (300, 750), 250)
        cap((560, 490), (690, 360), 90)
        cap((690, 360), (740, 310), 56)
        d.ellipse([P(760, 150), P(900, 290)], fill=W)
        d.polygon([P(780, 175), P(860, 105), P(880, 200)], fill=W)
        cap((330, 720), (470, 580), 40, CLEAR)
    elif name in ("sound", "mute"):
        d.polygon([P(170, 400), P(350, 400), P(560, 220), P(560, 804), P(350, 624), P(170, 624)], fill=W)
        if name == "sound":
            d.arc([P(470, 330), P(710, 694)], -55, 55, fill=W, width=int(60 * k))
            d.arc([P(540, 230), P(880, 794)], -55, 55, fill=W, width=int(60 * k))
        else:
            cap((680, 410), (880, 614), 60)
            cap((880, 410), (680, 614), 60)
    elif name in ("music", "music_off"):
        d.ellipse([P(170, 640), P(400, 830)], fill=W)
        d.ellipse([P(560, 560), P(790, 750)], fill=W)
        box(340, 250, 400, 740)
        box(730, 170, 790, 660)
        d.polygon([P(340, 250), P(790, 170), P(790, 290), P(340, 370)], fill=W)
        if name == "music_off":
            cap((130, 150), (890, 880), 90, CLEAR)
            cap((150, 160), (870, 860), 50)
    elif name == "power":
        d.arc([P(220, 230), P(804, 814)], -55, 235, fill=W, width=int(84 * k))
        cap((512, 140), (512, 470), 84)
    elif name == "home":
        d.polygon([P(512, 170), P(880, 500), P(780, 500), P(780, 850), P(244, 850), P(244, 500), P(144, 500)],
                  fill=W)
        box(440, 620, 584, 860, 30, CLEAR)
    elif name == "help":
        font = ImageFont.truetype(font_file(True), int(760 * k))
        d.text(P(512, 540), "?", font=font, fill=W, anchor="mm")
    elif name == "star":
        pts = []
        for i in range(10):
            r = 430 if i % 2 == 0 else 180
            a = -math.pi / 2 + i * math.pi / 5
            pts.append(P(512 + r * math.cos(a), 540 + r * math.sin(a)))
        d.polygon(pts, fill=W)
    elif name == "keycap":
        d.polygon([P(150, 780), P(874, 780), P(770, 280), P(254, 280)], fill=W)
        d.polygon([P(320, 640), P(704, 640), P(660, 380), P(364, 380)], outline=CLEAR, width=int(30 * k))
    elif name == "switch":
        box(220, 480, 804, 850, 50)
        box(300, 420, 724, 500, 20)
        box(470, 170, 554, 440)
        box(380, 250, 644, 330)
    elif name == "again":
        d.arc([P(200, 200), P(824, 824)], 20, 300, fill=W, width=int(90 * k))
        d.polygon([P(660, 120), P(900, 250), P(650, 400)], fill=W)
    elif name == "close":
        cap((260, 260), (764, 764), 110)
        cap((764, 260), (260, 764), 110)
    elif name == "dot":
        d.ellipse([P(312, 312), P(712, 712)], fill=W)
    return img.resize((size, size), Image.LANCZOS)


def draw_game_icon(size=256):
    """The game's own icon: a wrench and a screwdriver crossed on a warm orange tile."""
    from PIL import Image, ImageDraw, ImageFilter
    S = 1024
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 40, 984, 984], radius=230, fill=(236, 150, 78, 255))
    shine = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shine).rounded_rectangle([40, 40, 984, 560], radius=230, fill=(255, 190, 120, 70))
    img = Image.alpha_composite(img, shine)

    wrench = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    w = ImageDraw.Draw(wrench)
    cream, clear = (252, 244, 228, 255), (0, 0, 0, 0)
    _capsule(w, (300, 512), (700, 512), 118, cream)
    w.ellipse([760 - 150, 512 - 150, 760 + 150, 512 + 150], fill=cream)
    w.rectangle([770, 452, 960, 572], fill=clear)
    w.ellipse([760 - 62, 512 - 62, 760 + 62, 512 + 62], fill=clear)
    w.ellipse([255 - 125, 512 - 125, 255 + 125, 512 + 125], fill=cream)
    w.ellipse([255 - 60, 512 - 60, 255 + 60, 512 + 60], fill=clear)
    wrench = wrench.rotate(45, resample=Image.BICUBIC, center=(512, 512))

    driver = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    v = ImageDraw.Draw(driver)
    _capsule(v, (200, 512), (440, 512), 200, (70, 156, 150, 255))
    for x in (270, 330, 390):
        v.line([(x, 430), (x, 594)], fill=(52, 124, 120, 255), width=18)
    v.rectangle([450, 464, 520, 560], fill=(214, 216, 222, 255))
    v.rectangle([520, 488, 830, 536], fill=(236, 236, 240, 255))
    v.polygon([(830, 488), (884, 502), (884, 522), (830, 536)], fill=(196, 198, 206, 255))
    driver = driver.rotate(-45, resample=Image.BICUBIC, center=(512, 512))

    tools = Image.alpha_composite(wrench, driver)
    shadow = Image.new("RGBA", (S, S), (90, 40, 10, 0))
    shadow.putalpha(tools.getchannel("A").point(lambda a: a * 0.35))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    moved = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    moved.paste(shadow, (10, 22))
    img = Image.alpha_composite(img, moved)
    img = Image.alpha_composite(img, tools)
    return img.resize((size, size), Image.LANCZOS)


def window_icon_file():
    """The game icon as a .ico file, for the window and the taskbar."""
    path = os.path.join(CACHE, "fixer3d.ico")
    try:
        if not os.path.exists(path):
            os.makedirs(CACHE, exist_ok=True)
            draw_game_icon(256).save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
                                                  (256, 256)])
        return Filename.fromOsSpecific(path).getFullpath()
    except OSError:
        return "textures/ursina.ico"


def draw_wood(size=512):
    """Desk planks: four boards, each its own shade, with wavy grain; it tiles both ways."""
    from PIL import Image, ImageDraw, ImageFilter
    rnd = random.Random(3)
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    ph = size // 4
    for p in range(4):
        base = (rnd.randint(146, 168), rnd.randint(100, 114), rnd.randint(66, 78))
        d.rectangle([0, p * ph, size, (p + 1) * ph], fill=base)
        for _ in range(26):
            y = p * ph + rnd.uniform(4, ph - 4)
            amp, cycles, phase = rnd.uniform(1, 5), rnd.randint(1, 4), rnd.uniform(0, 6.28)
            col = tuple(int(c * rnd.uniform(0.84, 1.08)) for c in base)
            pts = [(x, y + amp * math.sin(2 * math.pi * cycles * x / size + phase)) for x in range(0, size + 8, 8)]
            d.line(pts, fill=col, width=rnd.choice((1, 1, 2, 3)))
        d.line([(0, p * ph), (size, p * ph)], fill=(104, 70, 48), width=3)
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    noise = Image.effect_noise((size, size), 18).convert("RGB")
    return Image.blend(img, noise, 0.05)


def draw_mat(size=512):
    """A green cutting mat with a grid on it; it tiles both ways."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (size, size), (56, 98, 84))
    d = ImageDraw.Draw(img)
    for i in range(0, size, 32):
        major = i % 128 == 0
        col = (88, 136, 118) if major else (70, 114, 99)
        d.line([(i, 0), (i, size)], fill=col, width=3 if major else 1)
        d.line([(0, i), (size, i)], fill=col, width=3 if major else 1)
    return img


def draw_glow(size=128, edge=(255, 255, 255)):
    from PIL import Image
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            r = math.hypot(x - size / 2 + 0.5, y - size / 2 + 0.5) / (size / 2)
            px[x, y] = (*edge, int(255 * max(0.0, 1 - r) ** 2))
    return img


def draw_vignette(size=256):
    """Soft dark corners round the screen, like the edge of a lamp's light."""
    from PIL import Image
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            r = math.hypot((x - size / 2) / (size / 2), (y - size / 2) / (size / 2))
            px[x, y] = (30, 20, 16, int(170 * min(1.0, max(0.0, (r - 0.62) / 0.75)) ** 1.6))
    return img


def draw_label(spec):
    """The sticker under the case."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (512, 168), (238, 234, 224, 255))
    d = ImageDraw.Draw(img)
    big, small = ImageFont.truetype(font_file(True), 44), ImageFont.truetype(font_file(), 30)
    d.text((24, 20), f"FIXER  {short_name(spec).upper()}", font=big, fill=(60, 60, 70, 255))
    d.text((24, 78), "5V  0.5A   USB-C   Made with care", font=small, fill=(90, 90, 100, 255))
    rnd = random.Random(spec["key"])
    x = 24
    while x < 480:  # a barcode
        w = rnd.choice((2, 3, 5))
        d.rectangle([x, 122, x + w, 152], fill=(50, 50, 58, 255))
        x += w + rnd.choice((3, 4, 6))
    return img


def legend_atlas(labels):
    """One texture with every legend on the keyboard drawn in white (its corners' colours tint it), and where
    each one is."""
    from PIL import Image, ImageDraw, ImageFont
    labels = sorted(set(labels))
    cell, cols = 96, 16
    rows = max(1, -(-len(labels) // cols))
    image = Image.new("RGBA", (cols * cell, rows * cell), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    fonts, where = {}, {}
    for i, text in enumerate(labels):
        size = 78  # as big as fits the cell
        while True:
            if size not in fonts:
                fonts[size] = ImageFont.truetype(font_file(True), size)
            if size <= 22 or fonts[size].getlength(text) <= cell * 0.9:
                break
            size -= 4
        col, row = i % cols, i // cols
        draw.text((col * cell + cell / 2, row * cell + cell / 2), text, font=fonts[size], fill=(255, 255, 255, 255),
                  anchor="mm")
        where[text] = (col / cols, 1 - (row + 1) / rows, (col + 1) / cols, 1 - row / rows)  # u0, v0, u1, v1
    return Texture(image, filtering="mipmap"), where


ART = {}


def art():
    """Every icon and texture, drawn once."""
    if not ART:
        for name in ("hand", "driver", "puller", "switcher", "brush", "lube", "sound", "mute", "music", "music_off",
                     "power", "home", "help", "star", "keycap", "switch", "again", "close", "dot"):
            ART[name] = Texture(draw_icon(name), filtering="mipmap")
        ART["game"] = Texture(draw_game_icon(256), filtering="mipmap")
        ART["wood"] = Texture(draw_wood(), filtering="mipmap")
        ART["mat"] = Texture(draw_mat(), filtering="mipmap")
        ART["glow"] = Texture(draw_glow(), filtering="bilinear")
        ART["vignette"] = Texture(draw_vignette(), filtering="bilinear")
    return ART


# ---- the keyboard ----

class Part3D:
    """One part of the 3D keyboard: what it looks like (one mesh), the boxes you can click it by, the parts it sits
    on (they go on first), and which way it lifts off. Positions are in the keyboard's own space; the part's
    origin is the point it turns about (a screw turns about its own middle)."""

    def __init__(self, kb, key, name, below=(), lift=(0, 1, 0), screw=False, origin=(0, 0, 0)):
        self.key, self.name, self.below = key, name, list(below)
        self.origin = Vec3(*origin)
        self.root = kb.attachNewNode(f"part-{key}")
        self.root.setPos(self.origin)
        self.lift = Vec3(*lift).normalized()
        self.screw = screw
        self.placed, self.style, self.token = True, 0, 0
        self.lo, self.hi = Vec3(1e9, 1e9, 1e9), Vec3(-1e9, -1e9, -1e9)  # its box, in the keyboard's space
        self.shapes = Shapes()
        self.extras = []  # (Shapes, texture): textured bits, drawn as meshes of their own
        self.mesh = None
        self.more = []  # more meshes of its own that move by themselves (a mouse's buttons), painted with it
        self.tags = set()
        self.hit = self.clicker(f"part-{key}")

    def clicker(self, name, tag=None):
        """A set of click boxes that tell the mouse which part they belong to (and, for a screw hole, which)."""
        node = self.root.attachNewNode(CollisionNode(name))
        node.node().setIntoCollideMask(PICK_MASK)
        node.setPythonTag("part", self)
        node.setPythonTag("tag", tag)
        return node

    def rel(self, p):
        return p[0] - self.origin.x, p[1] - self.origin.y, p[2] - self.origin.z

    def grow(self, center, size):
        c, half = Vec3(*center), Vec3(*size) / 2
        self.lo = Vec3(min(self.lo.x, c.x - half.x), min(self.lo.y, c.y - half.y), min(self.lo.z, c.z - half.z))
        self.hi = Vec3(max(self.hi.x, c.x + half.x), max(self.hi.y, c.y + half.y), max(self.hi.z, c.z + half.z))

    def target(self, center, size, tag=None):
        """A box you can click the part by; a tagged one (a screw hole) gets its own, so the mouse can tell."""
        x, y, z = self.rel(center)
        node = self.hit if tag is None else self.clicker(f"{self.key}-{tag}", tag)
        node.node().addSolid(CollisionBox(Point3(x, y, z), size[0] / 2, size[1] / 2, size[2] / 2))

    def colour(self, tint, fixed):
        if tint:
            self.tags.add(tint)
        return self.shapes.use(fixed if not tint else (255, 255, 255), tint)

    def box(self, pos, size, tint=None, fixed=SILVER, hit=True):
        self.colour(tint, fixed).box(self.rel(pos), size)
        self.grow(pos, size)
        if hit:
            self.target(pos, size)

    def post(self, base, radius, height, tint=None, fixed=SILVER, hit=True, tag=None, segments=14):
        """A cylinder standing on base (or hanging from it, with a negative height)."""
        y = base[1] if height > 0 else base[1] + height
        self.colour(tint, fixed).cylinder(self.rel((base[0], y, base[2])), radius, abs(height), segments)
        center, size = (base[0], y + abs(height) / 2, base[2]), (2 * radius, abs(height), 2 * radius)
        self.grow(center, size)
        if hit:
            self.target(center, size, tag)

    def wire(self, points, thickness, fixed, hit=False):
        """A wire bent along points, one straight bit at a time (each bit runs along one axis)."""
        for a, b in zip(points, points[1:]):
            center = tuple((a[i] + b[i]) / 2 for i in range(3))
            size = tuple(max(abs(a[i] - b[i]), thickness) for i in range(3))
            self.box(center, size, fixed=fixed, hit=hit)

    def finish(self):
        self.mesh = self.shapes.mesh(self.root, self.key)
        for shapes, texture in self.extras:
            shapes.mesh(self.root, self.key + " label", texture=texture, shadow=False)
        self.shapes = None

    def repaint(self, colours):
        for tag in self.tags:
            for mesh in [self.mesh] + self.more:
                mesh.paint(0, tag, colours[tag])

    @property
    def paintable(self):
        return bool(self.tags)


class KeySet:
    """All the keycaps of a keyboard, or all its switches. Each one comes off and goes back on by itself, but they're
    drawn together: as one mesh on the keyboard, and a copy in its tray that shows the ones taken off."""

    def __init__(self, kind, kb, shapes, legends=None, atlas=None):
        self.kind, self.shapes, self.legend_shapes, self.atlas = kind, shapes, legends, atlas
        self.root = kb.attachNewNode(kind)
        self.meshes = [shapes.mesh(self.root, kind)]
        if legends is not None and legends.v:
            self.meshes.append(legends.mesh(self.root, kind + " legends", texture=atlas, shadow=False))
        self.trays, self.tray = [], None
        self.items = []
        self.hits = self.root.attachNewNode("hits")

    def add_tray(self, node):
        self.tray = node
        self.trays = [self.shapes.mesh(node, self.kind + " tray", hidden=True)]
        if len(self.meshes) > 1:
            self.trays.append(self.legend_shapes.mesh(node, self.kind + " tray legends", texture=self.atlas,
                                                      hidden=True, shadow=False))

    def on_board(self, i, offset=(0, 0, 0)):
        for m in self.meshes:
            m.move(i, offset)

    def in_tray(self, i, shown):
        for m in self.trays:
            m.move(i, (0, 0, 0) if shown else None)

    def paint(self, i, body, legend=None, tray=False):
        meshes = self.trays if tray else self.meshes
        if not meshes:
            return
        meshes[0].paint(i, "cap" if self.kind == "keycap" else "stem", body)
        if legend is not None and len(meshes) > 1:
            meshes[1].paint(i, "legend", legend)

    def flyer(self, i, parent, center):
        """A copy of one, with its legend, to fly between the keyboard and the tray."""
        body = self.meshes[0].piece(i, parent, center)
        if len(self.meshes) > 1 and i in self.meshes[1].items:
            self.meshes[1].piece(i, body.np, center).np.hide(SHADOW_MASK)
        return body


class KeyItem:
    """One keycap or one switch: a part of its own, though it's drawn along with all the others of its kind."""
    screw = False
    paintable = False

    def __init__(self, keyset, i, key, row):
        label, cx, cz, w, h = key
        self.set, self.i, self.kind, self.row = keyset, i, keyset.kind, row
        self.label, self.cx, self.cz, self.w, self.h = label, cx, cz, w, h
        self.key = f"{self.kind}{i}"
        self.name = f"{nice_label(label)} {self.kind}"
        self.below = []
        self.placed, self.style, self.token = True, 0, 0
        self.body = self.legend = None  # a keycap's colours now (under any grime)
        self.grimy = False  # a keycap that wants a wash
        if self.kind == "keycap":
            y0, y1, sx, sz = CAP_Y, CAP_Y + CAP_H, w - 0.1, h - 0.1
        else:
            y0, y1, sx, sz = SWITCH_Y - 0.02, SWITCH_Y + 0.43, 0.74, 0.74
        self.center = Vec3(cx, (y0 + y1) / 2, cz)
        self.lo, self.hi = Vec3(cx - sx / 2, y0, cz - sz / 2), Vec3(cx + sx / 2, y1, cz + sz / 2)
        node = keyset.hits.attachNewNode(CollisionNode(self.key))
        node.node().addSolid(CollisionBox(Point3(*self.center), sx / 2, (y1 - y0) / 2, sz / 2))
        node.node().setIntoCollideMask(PICK_MASK)
        node.setPythonTag("part", self)
        node.setPythonTag("tag", None)
        self.hit = node
        keyset.items.append(self)


class Dirt:
    """Crumbs, dust and hair on one part, brushed away a speck at a time."""

    def __init__(self, host, specks):
        self.host = host
        shapes = Shapes()
        self.points = []
        for i, (kind, x, y, z, rnd) in enumerate(specks):
            shapes.begin(i)
            if kind == "dust":  # a fluffy grey-white clump
                c = rnd.randint(196, 226)
                for _ in range(rnd.randint(2, 3)):
                    shapes.use((c, c - 4, c - 12)).box((x + rnd.uniform(-0.05, 0.05), y + 0.012,
                                                        z + rnd.uniform(-0.05, 0.05)),
                                                       (rnd.uniform(0.08, 0.15), 0.024, rnd.uniform(0.08, 0.15)))
            elif kind == "crumb":  # biscuit
                base = (rnd.randint(200, 226), rnd.randint(146, 170), rnd.randint(78, 98))
                for _ in range(rnd.randint(1, 3)):
                    s = rnd.uniform(0.08, 0.15)
                    shapes.use(shade(base, rnd.uniform(0.85, 1.1))).box(
                        (x + rnd.uniform(-0.05, 0.05), y + s / 2, z + rnd.uniform(-0.05, 0.05)), (s, s * 0.7, s))
            else:  # a hair
                a = rnd.uniform(0, math.pi)
                length = rnd.uniform(0.5, 0.9)
                dx, dz = math.cos(a) * length / 2, math.sin(a) * length / 2
                shapes.use((46, 36, 32)).rod((x - dx, y + 0.01, z - dz), (x + dx, y + 0.01, z + dz), 0.016)
            self.points.append(Vec3(x, y, z))
        self.mesh = shapes.mesh(host.root, f"dirt on {host.key}")
        self.left = set(range(len(specks)))


def trinket_shapes(kind):
    """Something lost inside the keyboard, made round its own middle, lying flat."""
    s = Shapes()
    if kind == "lucky coin":
        s.use((214, 176, 86)).cylinder((0, 0, 0), 0.24, 0.04, 22)
        s.use((236, 202, 112)).cylinder((0, 0.04, 0), 0.18, 0.006, 22)
    elif kind == "paperclip":
        pts = [(-0.34, 0.08), (0.3, 0.08), (0.34, 0.0), (0.3, -0.08), (-0.26, -0.08), (-0.3, 0.0),
               (-0.26, 0.04), (0.2, 0.04)]
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            s.use((200, 204, 214)).rod((ax, 0.015, az), (bx, 0.015, bz), 0.026)
    elif kind == "guitar pick":
        outline = [(0.0, -0.26), (0.16, -0.12), (0.22, 0.06), (0.14, 0.18), (0.0, 0.21), (-0.14, 0.18),
                   (-0.22, 0.06), (-0.16, -0.12)]
        s.use((236, 112, 90)).slab(outline, 0, 0.025)
    elif kind == "tiny die":
        s.use((246, 242, 234)).box((0, 0.12, 0), (0.24, 0.24, 0.24))
        for dx, dz in ((-0.06, -0.06), (0.06, 0.06), (0, 0), (-0.06, 0.06), (0.06, -0.06)):
            s.use((40, 40, 46)).box((dx, 0.241, dz), (0.035, 0.004, 0.035))
    elif kind == "star sticker":
        pts = []
        for i in range(10):
            r = 0.24 if i % 2 == 0 else 0.1
            a = math.pi / 2 + i * math.pi / 5
            pts.append((r * math.cos(a), r * math.sin(a)))
        s.use((246, 200, 80)).slab(pts, 0, 0.012)
    else:  # a toy brick
        s.use((210, 70, 60)).box((0, 0.07, 0), (0.34, 0.14, 0.18))
        for dx in (-0.085, 0.085):
            s.use((224, 84, 72)).cylinder((dx, 0.14, 0), 0.05, 0.04, 12)
    return s


class Trinket:
    """Something that fell into the keyboard: find it and it goes in your collection."""

    def __init__(self, kind, host, pos, angle):
        self.kind, self.name, self.host, self.found = kind, kind, host, False
        self.holder = host.root.attachNewNode(kind)
        self.holder.setPos(*pos)
        self.holder.setH(angle)
        self.mesh = trinket_shapes(kind).mesh(self.holder, kind)
        self.pos = Vec3(*pos)
        node = self.holder.attachNewNode(CollisionNode(kind))
        node.node().addSolid(CollisionBox(Point3(0, 0.26, 0), 0.34, 0.3, 0.34))  # up past the switch tops
        node.node().setIntoCollideMask(PICK_MASK)
        node.setPythonTag("part", self)
        node.setPythonTag("tag", None)
        self.hit = node


class Board:
    """Everything one keyboard is made of, once it's built."""

    def __init__(self, spec):
        self.spec = spec
        self.parts = []  # the big parts, stabilisers, screws and feet: Part3D
        self.caps = self.switches = None
        self.keys, self.rows = [], []
        self.dirt, self.trinket = [], None
        self.size = self.inner = (0, 0)
        self.space_x = 0.0
        self.stab_of = {}  # key number -> the stabiliser under it
        self.knob = None
        self.height = FRAME_Y[1]  # how tall it is, put together
        self.mouse = {}  # a mouse's moving bits, for its test: its buttons, its wheel, its logo

    def in_order(self):
        """Every part, in the order it's built: they're made in that order, with the switches and keycaps going in
        just after the stabilisers."""
        if not self.caps.items:  # a mouse: just as they're made
            return list(self.parts)
        stabs = [p for p in self.parts if p.key.startswith("stab")]
        cut = self.parts.index(stabs[0]) if stabs else next(
            i for i, p in enumerate(self.parts) if p.key == "plate") + 1
        first = [p for p in self.parts[:cut] if p not in stabs]
        last = [p for p in self.parts[cut:] if p not in stabs]
        return first + stabs + self.switches.items + self.caps.items + last


def build_keyboard(kb, spec, extras=True, seed=None):
    """A keyboard of this type, in its own colours. The bottom case and the USB board in it; the case foam; the
    circuit board, with a socket, a diode and a light for every key; the internal cable; the plate foam; the steel
    plate with its cut-outs; the stabilisers; a switch and a keycap for every key; the top frame; then underneath,
    the screws that hold it all together and the rubber feet that hide four of them. Some keyboards have more of
    their own: a volume knob, a battery (and a receiver tucked underneath), gaskets and a brass weight. With extras,
    some dust and crumbs inside, and something someone lost in there."""
    layout, wu, hu = layout_for(spec["size"])
    cw, cd = wu + 2 * MARGIN, hu + 2 * MARGIN
    board = Board(spec)
    board.size, board.inner = (cw, cd), (wu, hu)
    parts = board.parts
    rnd = random.Random(seed)

    def part(*args, **kwargs):
        parts.append(Part3D(kb, *args, **kwargs))
        return parts[-1]

    keys = [(label, x + w / 2 - wu / 2, -(y + h / 2 - hu / 2), w, h) for label, x, y, w, h in layout]
    board.keys = keys
    board.rows = [y for _, x, y, w, h in layout]
    long_keys = [i for i, k in enumerate(keys) if k[3] >= 2 or k[4] >= 2]
    board.space_x = next((k[1] for k in keys if k[0] == "Space"), 0.0)
    knob_at = None
    if spec.get("knob"):  # in the layout's units, like the keys
        knob_at = (spec["knob"][0] - wu / 2, -(spec["knob"][1] - hu / 2))
    # The keycaps that want a wash: the ones typed on most, mostly (or, on an old keyboard, every one)
    grime = spec.get("grime", 0.12)
    worn = {"Space", "Enter", "Back", "Shift", "E", "A", "S", "D", "W", "R", "T", "O", "N", "I", "0", "1", "5", "Ent",
            "+"}
    grimy = {i for i, k in enumerate(keys)
             if grime >= 1 or rnd.random() < (grime * 3 if k[0] in worn else grime * 0.5)}
    if grime > 0 and len(grimy) < 2:  # always a couple
        grimy |= {i for i, k in enumerate(keys) if k[0] in worn} or set(rnd.sample(range(len(keys)), 2))

    def stab_ends(cx, cz, w, h):
        wide = w >= h
        reach = min((w if wide else h) / 2 - 0.4, 2.7)
        return wide, [(cx + d * reach, cz) if wide else (cx, cz + d * reach) for d in (-1, 1)]

    sx, sz = cw / 2 - 0.9, cd / 2 - 0.8
    spots = [(-sx, -sz), (sx, -sz), (-sx, sz), (sx, sz), (0, -sz), (0, sz)]  # screws: the four corners are under feet
    px = wu / 2 - 3.0  # where the USB socket is, along the back
    back_in = cd / 2 - WALL  # the inside of the back wall

    # The bottom case: floor, walls, the posts the screws go up into, the USB opening; underneath, the holes and
    # the sticker
    case = part("bottom_case", "bottom case")
    case.box((0, FLOOR / 2, 0), (cw, FLOOR, cd), "case")
    for z in (cd / 2 - WALL / 2, -cd / 2 + WALL / 2):
        case.box((0, WALL_H / 2, z), (cw, WALL_H, WALL), "case")
    for x in (cw / 2 - WALL / 2, -cw / 2 + WALL / 2):
        case.box((x, WALL_H / 2, 0), (WALL, WALL_H, cd - 2 * WALL), "case")
    for x, z in spots:
        case.post((x, FLOOR, z), 0.28, PCB_Y - 0.06 - FLOOR, "inside", hit=False)
        case.post((x, PCB_Y - 0.06, z), 0.1, -0.01, fixed=BLACK, hit=False)  # the screw's hole in the post
    for x in (-wu / 4, wu / 4):  # ribs that stiffen the floor
        case.box((x, FLOOR + 0.05, 0), (0.12, 0.1, cd - 2 * WALL), "inside", hit=False)
    case.box((px, 0.45, cd / 2 + 0.006), (0.8, 0.34, 0.01), fixed=BLACK, hit=False)  # the opening for the socket
    for i, (x, z) in enumerate(spots):
        case.post((x, 0, z), 0.24, -0.02, fixed=(24, 26, 30), tag=("hole", i), segments=12)
    if spec.get("wireless"):  # its power switch, on the back, and a slot underneath where its receiver lives
        case.box((px + 1.5, 0.6, cd / 2 + 0.01), (0.6, 0.2, 0.03), fixed=BLACK, hit=False)
        case.box((px + 1.38, 0.6, cd / 2 + 0.035), (0.22, 0.14, 0.05), fixed=spec["accent"], hit=False)
        case.box((cw / 4, -0.006, 0.2), (1.5, 0.01, 0.75), fixed=(24, 26, 30), hit=False)
    label = Shapes().use((255, 255, 255))
    lw, lh = min(3.6, cw - 1.6), min(3.6, cw - 1.6) * 168 / 512
    label.quad((-lw / 2, -0.008, -0.3 + lh / 2), (lw / 2, -0.008, -0.3 + lh / 2), (lw / 2, -0.008, -0.3 - lh / 2),
               (-lw / 2, -0.008, -0.3 - lh / 2), (0, -1, 0), [(0, 0), (1, 0), (1, 1), (0, 1)])  # reads turned over
    case.extras.append((label, Texture(draw_label(spec), filtering="mipmap")))

    legs = part("legs", "flip-out legs", ["bottom_case"], lift=(0, -1, 0))
    if cw > 8:
        leg, spread = 1.6, cw / 2 - 2.4
    else:  # a number pad's are smaller, and closer in
        leg, spread = min(1.6, cw / 4 - 0.3), cw / 4
    for x in (-spread, spread):
        legs.box((x, -0.04, cd / 2 - 0.45), (leg + 0.1, 0.08, 0.18), fixed=(60, 62, 70))  # the hinge
        legs.box((x, -0.07, cd / 2 - 0.85), (leg, 0.1, 0.7), "legs")
        legs.box((x, -0.13, cd / 2 - 1.15), (leg - 0.2, 0.03, 0.12), fixed=RUBBER, hit=False)  # its rubber tip

    usb = part("usb_board", "USB board", ["bottom_case"])
    uz = back_in - 0.5
    usb.box((px, 0.31, uz), (2.2, 0.12, 0.9), fixed=PCB_GREEN)
    usb.box((px, 0.48, back_in), (0.62, 0.22, 0.5), fixed=SILVER)  # the USB-C socket, into the back wall
    usb.box((px, 0.48, back_in + 0.26), (0.36, 0.08, 0.03), fixed=BLACK, hit=False)  # its opening
    usb.box((px - 0.65, 0.39, uz - 0.05), (0.32, 0.05, 0.32), fixed=BLACK, hit=False)  # a protection chip
    usb.box((px + 0.6, 0.44, uz - 0.25), (0.5, 0.14, 0.2), fixed=WHITE, hit=False)  # the socket for the cable inside
    for k in range(3):  # tiny capacitors
        usb.box((px - 0.2 + k * 0.22, 0.38, uz - 0.3), (0.1, 0.04, 0.06), fixed=(190, 150, 100), hit=False)

    cable = part("cable", "USB-C cable", ["usb_board"], lift=(0, 0.4, 1))
    bz = cd / 2
    cable.box((px, 0.48, bz + 0.3), (0.7, 0.34, 0.55), "cable")  # its plug
    cable.box((px, 0.48, bz + 0.6), (0.3, 0.24, 0.12), "cable")  # the plug's strain relief
    route = [(px, 0.48, bz + 0.66), (px, 0.48, bz + 2.0), (px + 2.4, 0.48, bz + 2.0), (px + 2.4, 0.48, bz + 4.6)]
    for a, b in zip(route, route[1:]):
        center = tuple((a[i] + b[i]) / 2 for i in range(3))
        cable.box(center, tuple(max(abs(a[i] - b[i]), 0.2) for i in range(3)), "cable")

    under_foam = ["bottom_case"]
    holes = [(x - 0.4, x + 0.4, z - 0.4, z + 0.4) for x, z in spots] + [(px - 1.2, px + 1.2, uz - 0.6, back_in)]
    if spec.get("weight"):  # a heavy brass bar on the floor: it makes the keyboard sit solid and sound deeper
        ww, wd = wu * 0.4, hu * 0.42
        weight = part("weight", "brass weight", ["bottom_case"])
        weight.box((0, FLOOR + 0.07, 0), (ww, 0.14, wd), fixed=(204, 166, 92))
        for k in range(3):  # brushed lines, and the maker's mark
            weight.box((0, FLOOR + 0.142, -wd / 2 + (k + 1) * wd / 4), (ww - 0.4, 0.004, 0.03), fixed=(180, 144, 78),
                       hit=False)
        weight.post((ww / 2 - 0.6, FLOOR + 0.14, 0), 0.22, 0.008, fixed=(224, 190, 116), hit=False)
        under_foam.append("weight")
        holes.append((-ww / 2 - 0.1, ww / 2 + 0.1, -wd / 2 - 0.1, wd / 2 + 0.1))
    battery_at = None
    if spec.get("wireless"):  # a flat battery pouch on the floor, in a hole in the foam
        bw, bd = min(5.0, wu / 2 - 1.0), 2.2  # (between the ribs on the floor)
        bx, bz = 0.0, -0.6
        battery_at = (bx, bz, bw, bd)
        battery = part("battery", "battery", ["bottom_case"])
        battery.box((bx, FLOOR + 0.06, bz), (bw, 0.12, bd), fixed=(176, 184, 198))
        battery.box((bx, FLOOR + 0.122, bz), (bw - 0.4, 0.004, bd * 0.5), fixed=(96, 140, 196), hit=False)  # label
        battery.box((bx + bw / 2 - 0.4, FLOOR + 0.06, bz + bd / 2 + 0.06), (0.36, 0.1, 0.12), fixed=SILVER,
                    hit=False)  # where its lead comes out
        under_foam.append("battery")
        holes.append((bx - bw / 2 - 0.1, bx + bw / 2 + 0.1, bz - bd / 2 - 0.1, bz + bd / 2 + 0.1))
    foam = part("case_foam", "case foam", under_foam)
    inner = (-cw / 2 + WALL, cw / 2 - WALL, -cd / 2 + WALL, back_in)
    for x0, x1, z0, z1 in rects_minus_holes(*inner, holes):
        foam.box(((x0 + x1) / 2, FOAM_Y, (z0 + z1) / 2), (x1 - x0, 0.14, z1 - z0), fixed=FOAM, hit=False)
    foam.target((0, FOAM_Y, 0), (cw - 2 * WALL, 0.14, cd - 2 * WALL))

    pcb = part("pcb", "circuit board", ["case_foam", "usb_board"])
    pcb.box((0, PCB_Y, 0), (wu + 0.3, 0.12, hu + 0.3), fixed=PCB_GREEN)
    top = PCB_Y + 0.06
    for label_, cx, cz, w, h in keys:  # for every key: its socket, its diode and its light
        pcb.box((cx, top + 0.006, cz), (0.16, 0.012, 0.16), fixed=BLACK, hit=False)  # the hole for the switch's post
        for dx, dz in ((-0.22, 0.2), (0.15, 0.3)):
            pcb.box((cx + dx, top + 0.008, cz + dz), (0.12, 0.016, 0.12), fixed=GOLDEN, hit=False)
        pcb.box((cx - 0.33, top + 0.02, cz - 0.15), (0.07, 0.04, 0.18), fixed=BLACK, hit=False)  # the diode
        pcb.box((cx, top + 0.02, cz - 0.27), (0.22, 0.04, 0.12), fixed=WHITE, hit=False)  # its light
    mx, mz = -wu / 2 + 1.6, hu / 2 - 0.65  # the chip that reads the keys, with its pins
    pcb.box((mx, top + 0.04, mz), (0.9, 0.08, 0.9), fixed=BLACK, hit=False)
    for k in range(8):
        off = -0.35 + k * 0.1
        for dx, dz in ((off, 0.5), (off, -0.5), (0.5, off), (-0.5, off)):
            pcb.box((mx + dx, top + 0.012, mz + dz), (0.05 if abs(dz) == 0.5 else 0.12, 0.024,
                                                     0.12 if abs(dz) == 0.5 else 0.05), fixed=SILVER, hit=False)
    pcb.box((mx + 1.0, top + 0.05, mz), (0.42, 0.1, 0.2), fixed=SILVER, hit=False)  # the crystal
    for k in range(5):
        pcb.box((mx - 0.4 + k * 0.22, top + 0.02, mz - 0.75), (0.1, 0.04, 0.06), fixed=(190, 150, 100), hit=False)
    pcb.box((px - 1.0, top + 0.07, hu / 2 + 0.02), (0.5, 0.14, 0.2), fixed=WHITE, hit=False)  # the cable's socket
    for x, z in spots:  # the mounting holes
        pcb.post((x, top, z), 0.2, 0.01, fixed=GOLDEN, hit=False)
    if knob_at:  # the knob's encoder, soldered on, its shaft up through the plate (the knob itself pulls off)
        kx, kz = knob_at
        pcb.box((kx, top + 0.15, kz), (0.62, 0.3, 0.62), fixed=(40, 42, 48), hit=False)
        pcb.post((kx, top + 0.3, kz), 0.12, CAP_Y + 0.2 - top - 0.3, fixed=SILVER, hit=False)

    later = []  # what has to be off before the plate foam and the plate go on
    if battery_at:  # the battery's lead: up the back, round the board's edge, and plugged in on top
        bx, bz, bw, bd = battery_at
        lx = bx + bw / 2 - 0.4
        lead = part("battery_lead", "battery lead", ["battery", "pcb"])
        lead.box((lx, top + 0.07, hu / 2 + 0.05), (0.42, 0.12, 0.17), fixed=WHITE)
        for d, col in ((-0.07, WIRES[0]), (0.07, WIRES[1])):
            lead.wire([(lx + d, FLOOR + 0.06, bz + bd / 2 + 0.1), (lx + d, FLOOR + 0.06, hu / 2 + 0.2),
                       (lx + d, top + 0.05, hu / 2 + 0.2), (lx + d, top + 0.05, hu / 2 + 0.12)], 0.04, col)
        lead.target((lx, top + 0.07, hu / 2 + 0.08), (0.7, 0.3, 0.5))
        later.append("battery_lead")

    inside = part("inner_cable", "internal cable", ["pcb", "usb_board"])
    inside.box((px + 0.6, 0.55, uz - 0.25), (0.46, 0.12, 0.18), fixed=WHITE)  # its plug on the USB board
    inside.box((px - 1.0, top + 0.2, hu / 2 + 0.02), (0.46, 0.12, 0.18), fixed=WHITE)  # and on the circuit board
    for k, col in enumerate(WIRES):
        x0, x1 = px + 0.45 + k * 0.1, px - 1.15 + k * 0.1
        inside.wire([(x0, 0.6, uz - 0.25), (x0, 0.6, hu / 2 + 0.2), (x0, top + 0.25, hu / 2 + 0.2),
                     (x1, top + 0.25, hu / 2 + 0.2), (x1, top + 0.25, hu / 2 + 0.02)], 0.04, col)
    inside.target((px - 0.2, 0.62, hu / 2), (2.2, 0.3, 0.6))

    plate_foam = part("plate_foam", "plate foam", ["pcb"] + later)
    cut = [(cx - 0.42, cx + 0.42, cz - 0.42, cz + 0.42) for _, cx, cz, _, _ in keys]
    if knob_at:
        cut.append((knob_at[0] - 0.4, knob_at[0] + 0.4, knob_at[1] - 0.4, knob_at[1] + 0.4))
    for x0, x1, z0, z1 in rects_minus_holes(-wu / 2 - 0.1, wu / 2 + 0.1, -hu / 2 - 0.1, hu / 2 + 0.1, cut):
        plate_foam.box(((x0 + x1) / 2, PLATE_FOAM_Y, (z0 + z1) / 2), (x1 - x0, 0.2, z1 - z0), fixed=PLATE_FOAM,
                       hit=False)
    plate_foam.target((0, PLATE_FOAM_Y, 0), (wu + 0.2, 0.2, hu + 0.2))

    plate = part("plate", "steel plate", ["plate_foam", "inner_cable"])
    plate_holes = [(cx - HOLE / 2, cx + HOLE / 2, cz - HOLE / 2, cz + HOLE / 2) for _, cx, cz, _, _ in keys]
    cut = list(plate_holes)
    if knob_at:  # a hole for the knob's shaft
        cut.append((knob_at[0] - 0.3, knob_at[0] + 0.3, knob_at[1] - 0.3, knob_at[1] + 0.3))
    for i in long_keys:  # and a slot for each stabiliser housing
        _, cx, cz, w, h = keys[i]
        wide, ends = stab_ends(cx, cz, w, h)
        cut += [(ex - (0.17 if wide else 0.27), ex + (0.17 if wide else 0.27), ez - (0.27 if wide else 0.17),
                 ez + (0.27 if wide else 0.17)) for ex, ez in ends]
    for x0, x1, z0, z1 in rects_minus_holes(-wu / 2 - 0.25, wu / 2 + 0.25, -hu / 2 - 0.25, hu / 2 + 0.25, cut):
        plate.box(((x0 + x1) / 2, PLATE_Y, (z0 + z1) / 2), (x1 - x0, 0.08, z1 - z0), fixed=STEEL, hit=False)
    plate.target((0, PLATE_Y, 0), (wu + 0.5, 0.08, hu + 0.5))

    stab_of = board.stab_of
    lube_spots = {}
    for i in long_keys:  # one stabiliser under each long key
        label_, cx, cz, w, h = keys[i]
        stab = part(f"stab{i}", f"{nice_label(label_)} stabiliser", ["plate"])
        stab.lubed = False  # they come dry, and rattle until they're lubed
        stab_of[i] = stab
        wide, ends = stab_ends(cx, cz, w, h)
        lube_spots[stab] = [(ex, ez, wide) for ex, ez in ends]
        for ex, ez in ends:
            stab.box((ex, SWITCH_Y + 0.11, ez), (0.26, 0.22, 0.42) if wide else (0.42, 0.22, 0.26), fixed=WHITE)
            stab.box((ex, SWITCH_Y + 0.25, ez), (0.12, 0.06, 0.12), fixed=(214, 214, 208), hit=False)  # its stem
        (ax, az), (bx_, bz_) = ends
        if wide:  # the wire: along under the key, bending up into each housing
            stab.wire([(ax, SWITCH_Y + 0.12, az - 0.2), (ax, SWITCH_Y + 0.03, az - 0.28),
                       (bx_, SWITCH_Y + 0.03, bz_ - 0.28), (bx_, SWITCH_Y + 0.12, bz_ - 0.2)], 0.05, SILVER)
        else:
            stab.wire([(ax + 0.2, SWITCH_Y + 0.12, az), (ax + 0.28, SWITCH_Y + 0.03, az),
                       (bx_ + 0.28, SWITCH_Y + 0.03, bz_), (bx_ + 0.2, SWITCH_Y + 0.12, bz_)], 0.05, SILVER)

    # A switch for every key: its housing with the light's window and the clips that hold it in the plate, the
    # coloured stem on top, and its pins underneath that go into the circuit board's socket
    stem = next(k for k in SWITCH_KINDS if k[0] == spec["switch"])[3]
    sw = Shapes()
    for i, (label_, cx, cz, w, h) in enumerate(keys):
        sw.begin(i)
        sw.use(HOUSING).box((cx, SWITCH_Y + 0.12, cz), (0.74, 0.24, 0.74))
        sw.use(HOUSING_TOP).box((cx, SWITCH_Y + 0.255, cz), (0.62, 0.03, 0.62))
        sw.use(LIGHT_WINDOW).box((cx, SWITCH_Y + 0.275, cz - 0.24), (0.22, 0.02, 0.12))
        for dz in (-0.385, 0.385):
            sw.use(CLIP).box((cx, SWITCH_Y + 0.06, cz + dz), (0.22, 0.1, 0.03))
        sw.use(stem, "stem").box((cx, SWITCH_Y + 0.35, cz), (0.3, 0.16, 0.08))
        sw.use(stem, "stem").box((cx, SWITCH_Y + 0.35, cz), (0.08, 0.16, 0.3))
        sw.tag = None
        sw.use(HOUSING).cylinder((cx, SWITCH_Y - 0.25, cz), 0.07, 0.25, 8)
        for dx, dz in ((-0.22, 0.2), (0.15, 0.3)):
            sw.use(GOLDEN).box((cx + dx, SWITCH_Y - 0.1, cz + dz), (0.04, 0.2, 0.04))
    board.switches = KeySet("switch", kb, sw)

    # A keycap for every key, with its legend on top
    used = [KEY_LEGENDS.get(k[0], k[0]) for k in keys]
    atlas, where = legend_atlas([t for t in used if t])
    caps, legends = Shapes(), Shapes()
    for i, (label_, cx, cz, w, h) in enumerate(keys):
        body, ink = cap_colours(spec, label_, None)
        if i in grimy:
            body, ink = grubby(body, ink)
        caps.begin(i).use(body, "cap").keycap((cx, CAP_Y, cz), w - 0.1, h - 0.1)
        text = KEY_LEGENDS.get(label_, label_)
        if text:
            u0, v0, u1, v1 = where[text]
            y, s = CAP_Y + CAP_H - DISH + 0.004, 0.25 if len(text) == 1 else 0.28
            legends.begin(i).use(ink, "legend").quad((cx - s, y, cz - s), (cx + s, y, cz - s), (cx + s, y, cz + s),
                                                     (cx - s, y, cz + s), (0, 1, 0),
                                                     [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    board.caps = KeySet("keycap", kb, caps, legends, atlas)
    for i, key in enumerate(keys):
        s = KeyItem(board.switches, i, key, board.rows[i])
        s.below = ["plate"]
        s.style = [k[0] for k in SWITCH_KINDS].index(spec["switch"])
        c = KeyItem(board.caps, i, key, board.rows[i])
        c.below = [s.key] + ([stab_of[i].key] if i in stab_of else [])
        c.body, c.legend = cap_colours(spec, key[0], None)
        c.grimy = i in grimy

    under_frame = ["plate"]
    if spec.get("gaskets"):  # rubber strips round the plate's edge: the plate floats on them, held by the frame
        for side, (gx, gz, sx_, sz_) in (("front", (0, -hu / 2 - 0.17, wu * 0.5, 0.14)),
                                          ("back", (0, hu / 2 + 0.17, wu * 0.5, 0.14)),
                                          ("left", (-wu / 2 - 0.17, 0, 0.14, hu * 0.5)),
                                          ("right", (wu / 2 + 0.17, 0, 0.14, hu * 0.5))):
            g = part(f"gasket_{side}", f"{side} gasket", ["plate"])
            g.box((gx, PLATE_Y + 0.14, gz), (sx_, 0.2, sz_), fixed=(226, 140, 116))  # soft coral silicone
            g.box((gx, PLATE_Y + 0.245, gz), (max(0.08, sx_ - 0.06), 0.01, max(0.08, sz_ - 0.06)),
                  fixed=(240, 166, 142), hit=False)
            under_frame.append(g.key)

    frame = part("top_frame", "top frame", under_frame)
    iw, idp = wu + 0.24, hu + 0.24  # the opening the keys come through
    fy, fh = sum(FRAME_Y) / 2, FRAME_Y[1] - FRAME_Y[0]
    for z in (1, -1):
        frame.box((0, fy, z * (idp + cd) / 4), (cw, fh, (cd - idp) / 2), "frame")
    for x in (1, -1):
        frame.box((x * (iw + cw) / 4, fy, 0), ((cw - iw) / 2, fh, idp), "frame")
    for k in range(3):  # its lock lights
        frame.box((cw / 2 - 0.9 - k * 0.45, FRAME_Y[1] + 0.01, cd / 2 - 0.27), (0.14, 0.02, 0.14), fixed=(40, 60, 44),
                  hit=False)

    if knob_at:  # the volume knob: an aluminium cap pushed onto the encoder's shaft, with a grip round it
        kx, kz = knob_at
        knob = part("knob", "volume knob", ["plate"], origin=(kx, 0, kz))
        knob.post((kx, CAP_Y - 0.02, kz), 0.42, 0.5, fixed=(206, 208, 214), segments=24)
        for k in range(16):  # the ridges you grip it by
            a = k * 2 * math.pi / 16
            knob.box((kx + math.cos(a) * 0.425, CAP_Y + 0.2, kz + math.sin(a) * 0.425), (0.05, 0.36, 0.05),
                     fixed=(176, 178, 186), hit=False)
        knob.post((kx, CAP_Y + 0.48, kz), 0.34, 0.012, fixed=(222, 224, 230), hit=False, segments=24)
        knob.box((kx, CAP_Y + 0.495, kz + 0.22), (0.06, 0.01, 0.14), fixed=spec["accent"], hit=False)  # its mark
        board.knob = knob

    for i, (x, z) in enumerate(spots):
        s = part(f"screw{i}", "screw", ["top_frame"], lift=(0, -1, 0), screw=True, origin=(x, 0, z))
        s.post((x, 0, z), 0.22, -0.07, fixed=SILVER)
        s.post((x, 0, z), 0.08, PCB_Y - 0.06, fixed=(170, 172, 180), hit=False)  # its thread, up into the post
        for size in ((0.34, 0.02, 0.05), (0.05, 0.02, 0.34)):  # the cross slot
            s.box((x, -0.072, z), size, fixed=(108, 110, 120), hit=False)
    for i, (x, z) in enumerate(spots[:4]):
        foot = part(f"foot{i}", "rubber foot", ["bottom_case", f"screw{i}"], lift=(0, -1, 0))
        foot.post((x, -0.01, z), 0.42, -0.12, fixed=RUBBER, segments=18)
    if spec.get("wireless"):  # its little USB receiver, kept safe in the slot underneath
        receiver = part("receiver", "USB receiver", ["bottom_case"], lift=(0, -1, 0))
        rx, rz = cw / 4, 0.2
        receiver.box((rx - 0.15, -0.07, rz), (1.0, 0.12, 0.5), fixed=(40, 42, 48))
        receiver.box((rx + 0.5, -0.06, rz), (0.4, 0.09, 0.4), fixed=SILVER)
        receiver.box((rx - 0.5, -0.135, rz), (0.2, 0.01, 0.3), fixed=spec["accent"], hit=False)

    for p in parts:
        p.finish()
        if p.paintable:
            p.repaint(part_colours(spec, None))
    for stab, ends in lube_spots.items():  # the lube, once it's on: a glossy dab where the wire meets each housing
        dabs = Shapes().use((236, 196, 110))
        for ex, ez, wide in ends:
            dabs.box((ex, SWITCH_Y + 0.235, ez), (0.2, 0.05, 0.2))
            bend = (ex, SWITCH_Y + 0.05, ez - 0.28) if wide else (ex + 0.28, SWITCH_Y + 0.05, ez)
            dabs.box(bend, (0.16, 0.08, 0.16))
        stab.lube = dabs.mesh(stab.root, f"lube on {stab.key}").np
        stab.lube.stash()

    if extras:
        def gap_point():
            """A spot on the plate between the switch holes, where crumbs collect."""
            for _ in range(40):
                _, cx, cz, w, h = rnd.choice(keys)
                x, z = cx + rnd.choice((-1, 1)) * 0.5 + rnd.uniform(-0.06, 0.06), cz + rnd.uniform(-0.45, 0.45)
                if rnd.random() < 0.5:
                    x, z = cx + rnd.uniform(-0.45, 0.45), cz + rnd.choice((-1, 1)) * 0.5
                if not any(a - 0.05 < x < b + 0.05 and c - 0.05 < z < d + 0.05 for a, b, c, d in plate_holes):
                    return x, z
            return 0.0, -hu / 2 - 0.15
        more = spec.get("dirt", 1.0)
        specks = []
        for _ in range(round(min(38, 4 + len(keys) / 2.4) * more)):  # (a small keyboard has less room for crumbs)
            x, z = gap_point()
            specks.append((rnd.choice(("dust", "dust", "crumb", "crumb", "hair")) if len(specks) % 9 else "hair",
                           x, PLATE_Y + 0.04, z, rnd))
        board.dirt.append(Dirt(plate, specks))
        specks = []
        for _ in range(round(min(14, 3 + len(keys) / 7) * more)):
            x, z = rnd.uniform(-wu / 2 + 0.3, wu / 2 - 0.3), rnd.uniform(-hu / 2 + 0.3, hu / 2 - 0.3)
            specks.append((rnd.choice(("dust", "dust", "crumb")), x, top + 0.02, z, rnd))
        board.dirt.append(Dirt(pcb, specks))
        kind = rnd.choice(TRINKETS)
        if rnd.random() < 0.6:
            x, z = gap_point()
            board.trinket = Trinket(kind, plate, (x, PLATE_Y + 0.04, z), rnd.uniform(0, 360))
        else:
            x, z = rnd.uniform(-wu / 2 + 1, wu / 2 - 1), rnd.uniform(-hu / 2 + 0.6, hu / 2 - 0.6)
            board.trinket = Trinket(kind, pcb, (x, top, z), rnd.uniform(0, 360))
    return board


# ---- computer mice ----

MOUSE_FLOOR, MOUSE_BASE = 0.08, 0.3  # the bottom shell's floor, and the top of its rim
MOUSE_PCB = (0.24, 0.32)  # the mouse's circuit board, bottom and top


def mouse_shape(spec):
    """A mouse's shape, along its length (t from 0 at your palm to 1 at the buttons, which point away from you): how
    wide it is there (half of it), how high its top is, and where that is. It's widest at the back, with a waist
    where your thumb and finger grip it, highest under your palm and low at the buttons, round at both ends."""
    W, L, H = spec["size"]

    def round_end(t):
        return max(0.0, 1 - abs(2 * t - 1) ** 5) ** 0.22

    def half(t):
        w = (0.88 + 0.12 * math.sin(math.pi * t)) * (1 - 0.07 * math.exp(-((t - 0.6) / 0.12) ** 2))
        return W / 2 * w * round_end(t)

    def top(t):
        h = 0.42 + 0.58 * math.exp(-((t - 0.38) / 0.36) ** 2)
        return MOUSE_BASE + (H - MOUSE_BASE) * h * round_end(t) ** 0.6

    def z(t):
        return -L / 2 + L * t
    return half, top, z


def build_mouse(kb, spec, extras=True, seed=None):
    """A computer mouse, the way they're made: the bottom shell, the sensor's lens in it, the circuit board (its two
    main switches, the wheel's encoder and the sensor are soldered on) held by a small screw, the scroll wheel, the
    cable, and the top shell with the buttons, held on by screws hidden under the feet. A gaming mouse has a
    weight, a board for its side buttons, and a light-up logo; a wireless one, a battery and its receiver under a
    cover on the bottom."""
    W, L, H = spec["size"]
    half, top, z = mouse_shape(spec)
    board = Board(spec)
    board.size = board.inner = (W, L)
    board.height = H
    parts = board.parts
    rnd = random.Random(seed)
    wireless = spec.get("wireless")

    def part(*args, **kwargs):
        parts.append(Part3D(kb, *args, **kwargs))
        return parts[-1]

    def outline(scale=1.0, t0=0.0, t1=1.0, n=28):
        ts = [t0 + (t1 - t0) * k / n for k in range(n + 1)]
        return [(half(t) * scale, z(t)) for t in ts] + [(-half(t) * scale, z(t)) for t in reversed(ts)]

    sensor_t = 0.72 if wireless else 0.45
    sz = z(sensor_t)
    bay = (0.22, 0.58) if wireless else None  # the battery's bay, in the floor
    bw = 1.25  # (its width)

    # The bottom shell: its floor (with a window for the sensor, and a bay for a battery), the rim round it
    shell = part("bottom_shell", "bottom shell")
    if bay:
        for t0, t1 in ((0.0, bay[0]), (bay[1], 1.0)):
            shell.colour("inside", None).slab(outline(1, t0, t1, 10), 0, MOUSE_FLOOR)
        ts = [bay[0] + (bay[1] - bay[0]) * k / 8 for k in range(9)]
        for side in (1, -1):
            strip = [(side * half(t), z(t)) for t in ts] + [(side * bw / 2, z(bay[1])), (side * bw / 2, z(bay[0]))]
            shell.colour("inside", None).slab(strip, 0, MOUSE_FLOOR)
    else:
        shell.colour("inside", None).slab(outline(), 0, MOUSE_FLOOR)
    shell.colour("inside", None).wall(outline(0.995), MOUSE_FLOOR, MOUSE_BASE, 0.1)
    shell.grow((0, MOUSE_BASE / 2, 0), (W, MOUSE_BASE, L))
    fy, fh = MOUSE_FLOOR / 2 + 0.01, MOUSE_FLOOR + 0.02  # you click it by its floor (round the battery's bay, if it has one)
    if bay:
        zb0, zb1 = z(bay[0]), z(bay[1])
        for z0, z1 in ((-L * 0.46, zb0), (zb1, L * 0.46)):
            shell.target((0, fy, (z0 + z1) / 2), (W * 0.9, fh, z1 - z0))
        for side in (1, -1):
            shell.target((side * (bw / 2 + W * 0.2), fy, (zb0 + zb1) / 2), (W * 0.4, fh, zb1 - zb0))
    else:
        shell.target((0, fy, 0), (W * 0.9, fh, L * 0.92))
    shell.box((0, -0.003, sz), (0.46, 0.008, 0.56), fixed=(20, 20, 24), hit=False)  # the sensor's window
    shell.box((0, -0.006, sz + 0.12), (0.1, 0.004, 0.1), fixed=(120, 30, 30), hit=False)  # its light, glowing through
    if not wireless:
        label = Shapes().use((255, 255, 255))
        lw = min(1.6, W * 0.45)
        lh, lz = lw * 168 / 512, z(0.27)
        label.quad((-lw / 2, -0.008, lz + lh / 2), (lw / 2, -0.008, lz + lh / 2), (lw / 2, -0.008, lz - lh / 2),
                   (-lw / 2, -0.008, lz - lh / 2), (0, -1, 0), [(0, 0), (1, 0), (1, 1), (0, 1)])
        shell.extras.append((label, Texture(draw_label(spec), filtering="mipmap")))
    else:  # its on/off switch, on the bottom
        shell.box((0, -0.004, z(0.63)), (0.5, 0.01, 0.22), fixed=BLACK, hit=False)
        shell.box((-0.1, -0.012, z(0.63)), (0.18, 0.012, 0.16), fixed=spec["accent"], hit=False)

    lens = part("lens", "sensor lens", ["bottom_shell"])
    lens.box((0, MOUSE_FLOOR + 0.06, sz), (0.62, 0.12, 0.72), fixed=(176, 214, 226))
    lens.box((0, MOUSE_FLOOR + 0.13, sz + 0.05), (0.26, 0.04, 0.26), fixed=(206, 234, 240), hit=False)

    under_board = ["lens", "bottom_shell"]
    if spec.get("weight"):  # a steel weight on the floor, so it glides steady
        weight = part("mouse_weight", "steel weight", ["bottom_shell"])
        weight.box((0, MOUSE_FLOOR + 0.06, z(0.27)), (min(1.5, W * 0.42), 0.12, 1.1), fixed=(150, 154, 162))
        weight.box((0, MOUSE_FLOOR + 0.122, z(0.27)), (0.5, 0.004, 0.5), fixed=(120, 124, 132), hit=False)
        under_board.append("mouse_weight")

    # The circuit board: its two main switches under the buttons, the wheel's encoder, the sensor, a chip
    t0 = 0.62 if wireless else 0.14
    y0, y1 = MOUSE_PCB
    pcb = part("pcb", "circuit board", under_board)
    pcb.shapes.use(PCB_GREEN).slab(outline(0.8, t0, 0.95, 12), y0, y1)
    pcb.grow((0, (y0 + y1) / 2, (z(t0) + z(0.95)) / 2), (W * 0.8, y1 - y0, z(0.95) - z(t0)))
    pcb.target((0, (y0 + y1) / 2, (z(t0) + z(0.95)) / 2), (W * 0.75, y1 - y0, z(0.95) - z(t0)))
    switch_t = 0.86
    for side in (-1, 1):  # the main switches: a black box each, with a little white plunger
        x = side * half(switch_t) * 0.42
        pcb.box((x, y1 + 0.12, z(switch_t)), (0.5, 0.24, 0.42), fixed=BLACK, hit=False)
        pcb.box((x, y1 + 0.27, z(switch_t)), (0.12, 0.06, 0.12), fixed=WHITE, hit=False)
    wheel_t, R = 0.79, 0.4
    wz = z(wheel_t)
    wy = top(wheel_t) - R + 0.14  # (it pokes up out of the slot between the buttons)
    pcb.box((0.31, (y1 + wy + 0.12) / 2, wz), (0.22, wy + 0.12 - y1, 0.46), fixed=(58, 60, 66), hit=False)  # encoder
    pcb.box((-0.31, (y1 + wy + 0.06) / 2, wz), (0.06, wy + 0.06 - y1, 0.2), fixed=(58, 60, 66), hit=False)  # bracket
    pcb.box((0, y1 + 0.09, sz), (0.7, 0.18, 0.78), fixed=BLACK, hit=False)  # the sensor
    for k in range(4):
        for side in (-1, 1):
            pcb.box((side * 0.38, y1 + 0.02, sz - 0.27 + k * 0.18), (0.08, 0.03, 0.06), fixed=SILVER, hit=False)
    pcb.box((0.3, y1 + 0.03, sz - 0.48), (0.12, 0.06, 0.12), fixed=(210, 50, 50), hit=False)  # its red light
    chip_x, chip_t = (-0.75, 0.68) if wireless else (-0.45, 0.3)
    pcb.box((chip_x, y1 + 0.03, z(chip_t)), (0.5, 0.06, 0.5), fixed=BLACK, hit=False)
    for k in range(0 if wireless else 3):
        pcb.box((0.25 + k * 0.18, y1 + 0.02, z(chip_t)), (0.1, 0.04, 0.06), fixed=(190, 150, 100), hit=False)
    if spec.get("rgb"):  # the lights for its logo
        for k in range(3):
            pcb.box((-0.25 + k * 0.25, y1 + 0.03, z(0.24)), (0.14, 0.06, 0.14), fixed=WHITE, hit=False)
    sx_, sz_ = 0.55, z(0.66 if wireless else 0.6)  # its little screw's hole
    pcb.post((sx_, y1, sz_), 0.16, 0.006, fixed=GOLDEN, hit=False)
    pcb.target((sx_, y1 + 0.012, sz_), (0.34, 0.024, 0.34), ("hole", 0))  # (below the screw's head, when it's in)  # (the screws are counted in build order)
    plug_at = (-0.55, z(0.92))
    if not wireless:
        pcb.box((plug_at[0], y1 + 0.08, plug_at[1]), (0.5, 0.16, 0.24), fixed=WHITE, hit=False)  # the cable's socket

    board_screw = part("board_screw", "board screw", ["pcb"], lift=(0, 1, 0), screw=True, origin=(sx_, y1, sz_))
    board_screw.post((sx_, y1, sz_), 0.14, 0.06, fixed=SILVER)
    for size in ((0.22, 0.02, 0.04), (0.04, 0.02, 0.22)):
        board_screw.box((sx_, y1 + 0.065, sz_), size, fixed=(108, 110, 120), hit=False)

    under_top = ["bottom_shell", "board_screw", "wheel"]
    if spec.get("side"):  # the side buttons' own little board, standing up inside the left side
        side_t = 0.56
        sxb = -(half(side_t) - 0.3)
        side_board = part("side_board", "side button board", ["pcb"])
        side_board.box((sxb, 0.78, z(side_t)), (0.06, 0.46, 1.0), fixed=PCB_GREEN)
        for k in (-1, 1):
            side_board.box((sxb - 0.08, 0.86, z(side_t) + k * 0.24), (0.1, 0.18, 0.24), fixed=BLACK, hit=False)
        side_board.wire([(sxb + 0.05, 0.6, z(side_t)), (sxb + 0.4, y1 + 0.04, z(side_t))], 0.05, (220, 180, 90))
        under_top.append("side_board")

    wheel = part("wheel", "scroll wheel", ["pcb"], origin=(0, wy, wz))
    wheel.shapes.use((52, 52, 58)).axle((0, 0, 0), R, 0.26, 22)  # (made about its own middle: it turns)
    for k in range(14):  # the grip on its rubber tyre
        a = k * 2 * math.pi / 14
        p, q = math.sin(a) * (R + 0.012), math.cos(a) * (R + 0.012)
        wheel.shapes.use((70, 70, 78)).rod((-0.13, p, q), (0.13, p, q), 0.035)
    wheel.shapes.use(spec["accent"]).axle((0, 0, 0), R * 0.6, 0.28, 16)  # its hub, showing at the sides
    wheel.shapes.use(SILVER).axle((0.03, 0, 0), 0.05, 0.62, 8)  # its axle
    wheel.grow((0, wy, wz), (0.3, 2 * R, 2 * R))
    wheel.target((0, wy, wz), (0.32, 2 * R, 2 * R))

    if not wireless:
        cable = part("cable", "USB cable", ["pcb", "bottom_shell"], lift=(0, 0.4, 1))
        cy = MOUSE_BASE + 0.12
        cable.box((plug_at[0], y1 + 0.2, plug_at[1]), (0.46, 0.12, 0.2), fixed=WHITE)  # its plug, in the socket
        cable.wire([(plug_at[0], y1 + 0.26, plug_at[1]), (plug_at[0], cy, plug_at[1]), (0, cy, plug_at[1]),
                    (0, cy, L / 2 - 0.1)], 0.06, (40, 40, 44))
        cable.colour("cable", None).rod((0, cy, L / 2 - 0.15), (0, cy, L / 2 + 0.45), 0.24)  # its strain relief
        route = [(0, cy, L / 2 + 0.45), (0.08, cy - 0.08, L / 2 + 1.2), (0.45, cy - 0.18, L / 2 + 1.85),
                 (1.1, cy - 0.24, L / 2 + 2.3), (1.9, cy - 0.27, L / 2 + 2.55)]
        for a, b in zip(route, route[1:]):
            cable.colour("cable", None).rod(a, b, 0.14)
        cable.grow((0.9, cy - 0.1, L / 2 + 1.5), (2.0, 0.4, 2.2))
        cable.target((0, cy, L / 2 + 0.15), (0.4, 0.4, 0.8))
        under_top.append("cable")

    # The top shell, with the buttons: a smooth dome over it all. The buttons are meshes of their own, so they can
    # go down when they're clicked; the slot between them, where the wheel pokes through, is dark.
    def dome(lift=0.0):
        def f(t, a):
            c, s = math.cos(a), math.sin(a)
            return (half(t) * math.copysign(abs(c) ** 0.75, c), MOUSE_BASE + (top(t) - MOUSE_BASE) * abs(s) ** 0.85
                    - lift, z(t))
        return f

    def inside(p):
        return (0, MOUSE_BASE * 0.5, p[2])
    top_shell = part("top_shell", "top shell", under_top)
    tb, g = 0.64, 0.07
    top_shell.colour("case", None).surface(dome(), 0, tb, 16, 0, math.pi, 22, inside)
    top_shell.colour("case", None).surface(dome(), tb, 1, 10, 0, 0.22 * math.pi - 0.02, 4, inside)
    top_shell.colour("case", None).surface(dome(), tb, 1, 10, 0.78 * math.pi + 0.02, math.pi, 4, inside)
    top_shell.shapes.use((34, 34, 40)).surface(dome(0.05), tb, 1, 10, math.pi / 2 - g, math.pi / 2 + g, 2, inside)
    top_shell.grow((0, (MOUSE_BASE + H) / 2, 0), (W, H - MOUSE_BASE, L))
    top_shell.target((0, (MOUSE_BASE + H) / 2, 0), (W * 0.92, H - MOUSE_BASE, L * 0.94))
    buttons = {}
    for name, (a0, a1) in (("right", (0.22 * math.pi, math.pi / 2 - g - 0.015)),
                           ("left", (math.pi / 2 + g + 0.015, 0.78 * math.pi))):
        s = Shapes().use((255, 255, 255), "case")
        s.surface(dome(), tb + 0.008, 1, 10, a0, a1, 8, inside)
        buttons[name] = s
    if spec.get("side"):  # two side buttons, under your thumb
        for k, t in enumerate((0.5, 0.63)):
            p = dome()(t, 0.84 * math.pi)
            top_shell.box((p[0] - 0.04, p[1], p[2]), (0.14, 0.2, 0.5), fixed=shade(spec["case"], 1.9), hit=False)
            top_shell.target((p[0] - 0.08, p[1], p[2]), (0.3, 0.3, 0.55), ("side", k))
    logo = None
    if spec.get("rgb"):  # its logo, lit from inside
        p = dome()(0.24, math.pi / 2)
        logo = Shapes().use(spec["accent"], "logo")
        logo.slab([(-0.28, p[2]), (0, p[2] + 0.2), (0.28, p[2]), (0, p[2] - 0.2)], p[1] - 0.02, p[1] + 0.012)

    # Underneath: the screws, each under a foot
    n = spec["feet"]
    if n == 2:
        spots, feet = [(0, 0.1), (0, 0.93)], [(0, 0.1, 1.5, 0.32), (0, 0.92, 1.7, 0.28)]
    elif n == 3:
        spots = [(0, 0.08), (-0.5, 0.88), (0.5, 0.88)]
        feet = [(0, 0.08, 1.2, 0.3), (-0.5, 0.88, 0.42, 0.42), (0.5, 0.88, 0.42, 0.42)]
    else:
        spots = [(-0.55, 0.13), (0.55, 0.13), (-0.55, 0.88), (0.55, 0.88)]
        feet = [(x, t, 0.5, 0.5) for x, t in spots]
    screws = []
    for i, (fx, t) in enumerate(spots):
        x = fx * half(t) * 1.25
        zz = z(t)
        shell.post((x, 0, zz), 0.17, -0.004, fixed=(24, 26, 30), tag=("hole", i + 1), segments=12)  # its well
        s = part(f"screw{i}", "screw", ["top_shell"], lift=(0, -1, 0), screw=True, origin=(x, 0, zz))
        s.post((x, 0, zz), 0.15, -0.018, fixed=SILVER)
        s.post((x, 0, zz), 0.06, MOUSE_BASE + 0.5, fixed=(170, 172, 180), hit=False)
        for size in ((0.24, 0.006, 0.04), (0.04, 0.006, 0.24)):
            s.box((x, -0.02, zz), size, fixed=(108, 110, 120), hit=False)
        screws.append((x, zz))
    for i, ((x, zz), (_, t, fw, fd)) in enumerate(zip(screws, feet)):
        foot = part(f"foot{i}", "foot", ["bottom_shell", f"screw{i}"], lift=(0, -1, 0))
        cx = x if n != 2 else 0.0
        r = min(fw, fd) / 2
        pts = []
        for k in range(20):  # a rounded strip, or a round pad
            a = k * 2 * math.pi / 20
            ex, ez = math.cos(a), math.sin(a)
            pts.append((cx + ex * r + math.copysign(fw / 2 - r, ex) * (abs(ex) > 1e-6),
                        zz + ez * r + math.copysign(fd / 2 - r, ez) * (abs(ez) > 1e-6)))
        foot.shapes.use(spec["skate"]).slab(pts, -0.045, -0.001)
        foot.grow((cx, -0.023, zz), (fw, 0.045, fd))
        foot.target((cx, -0.025, zz), (fw, 0.05, fd))

    if wireless:  # under a cover on the bottom: an AA battery, and the receiver tucked in beside it
        bz0, bz1 = z(bay[0]), z(bay[1])
        bm = (bz0 + bz1) / 2
        battery = part("mouse_battery", "AA battery", ["bottom_shell", "top_shell"], lift=(0, -1, 0))
        battery.shapes.use((70, 150, 96)).axle((-0.2, 0.38, bm), 0.36, 2.4, 18, along="z")
        battery.shapes.use((212, 176, 90)).axle((-0.2, 0.38, bm + 0.8), 0.365, 0.4, 18, along="z")
        battery.shapes.use(SILVER).axle((-0.2, 0.38, bm + 1.26), 0.12, 0.12, 10, along="z")  # its + end
        battery.grow((-0.2, 0.38, bm), (0.74, 0.74, 2.6))
        battery.target((-0.2, 0.38, bm), (0.74, 0.74, 2.6))
        receiver = part("receiver", "USB receiver", ["bottom_shell", "top_shell"], lift=(0, -1, 0))
        receiver.box((0.42, 0.12, bm - 0.15), (0.3, 0.14, 0.7), fixed=(40, 42, 48))
        receiver.box((0.42, 0.12, bm + 0.32), (0.26, 0.1, 0.3), fixed=SILVER)
        cover = part("battery_cover", "battery cover", ["mouse_battery", "receiver"], lift=(0, -1, 0))
        cover.box((0, -0.012, bm), (bw + 0.2, 0.03, bz1 - bz0 + 0.16), "inside")
        for k in range(4):  # the ridges you push it off by
            cover.box((0, -0.03, bz0 + 0.15 + k * 0.1), (0.5, 0.01, 0.04), fixed=(40, 40, 46), hit=False)

    for p in parts:
        p.finish()
    for name, s in buttons.items():
        mesh = s.mesh(top_shell.root, f"{name} button")
        top_shell.more.append(mesh)
        board.mouse[name] = mesh.np
    if logo is not None:
        board.mouse["logo"] = logo.mesh(top_shell.root, "logo", shadow=False)
    for p in parts:
        if p.paintable:
            p.repaint(part_colours(spec, None))
    board.mouse["wheel"] = wheel
    board.mouse["sensor"] = (0, sz)

    if extras:  # hair caught round the wheel, dust on the board, crumbs in the bottom
        specks = []
        for _ in range(3):  # caught round the wheel's axle
            specks.append(("hair", rnd.uniform(-0.2, 0.2), y1 + 0.02, wz + rnd.uniform(-0.5, 0.5), rnd))
        for _ in range(9):
            t = rnd.uniform(t0 + 0.04, 0.9)
            specks.append((rnd.choice(("dust", "dust", "hair", "crumb")), rnd.uniform(-0.5, 0.5) * half(t), y1 + 0.02,
                           z(t), rnd))
        board.dirt.append(Dirt(pcb, specks))
        specks = []
        for _ in range(8):
            t = rnd.uniform(0.1, 0.9)
            if bay and bay[0] - 0.03 < t < bay[1] + 0.03:
                continue
            specks.append((rnd.choice(("crumb", "dust", "crumb")), rnd.uniform(-0.6, 0.6) * half(t),
                           MOUSE_FLOOR + 0.01, z(t), rnd))
        board.dirt.append(Dirt(shell, specks))
    board.caps, board.switches = KeySet("keycap", kb, Shapes()), KeySet("switch", kb, Shapes())
    return board


def build_product(kb, spec, extras=True, seed=None):
    """A keyboard or a mouse, whichever spec is."""
    return (build_mouse if kind_of(spec) == "mouse" else build_keyboard)(kb, spec, extras, seed)


# ---- the desk ----

def mug_shapes():
    s = Shapes()
    body = (232, 150, 112)
    s.use(body).cylinder((0, 0, 0), 1.0, 2.0, 26)
    s.use((250, 240, 222)).cylinder((0, 0.75, 0), 1.012, 0.42, 26)  # a cream stripe
    s.use((78, 50, 36)).cylinder((0, 2.0, 0), 0.86, 0.012, 26)  # the tea in it
    for a, b in (((0.95, 1.6, 0), (1.55, 1.6, 0)), ((1.55, 1.6, 0), (1.55, 0.6, 0)), ((1.55, 0.6, 0), (0.95, 0.6, 0))):
        s.use(shade(body, 0.92)).rod(a, b, 0.24)
    return s


def plant_shapes():
    s = Shapes()
    rnd = random.Random(5)
    pot = (196, 112, 82)
    s.use(pot).cylinder((0, 0, 0), 0.82, 1.1, 22)
    s.use(shade(pot, 0.88)).cylinder((0, 1.0, 0), 0.92, 0.22, 22)
    s.use((74, 52, 40)).cylinder((0, 1.2, 0), 0.8, 0.02, 22)
    for i in range(11):  # a little succulent: an outer ring of leaves, and smaller ones standing up inside
        a = i * 2 * math.pi / 11 + rnd.uniform(-0.2, 0.2)
        r, h = rnd.uniform(0.75, 1.0), rnd.uniform(0.35, 0.6)
        s.use(shade((112, 162, 104), rnd.uniform(0.9, 1.1))).rod((0, 1.25, 0), (math.cos(a) * r, 1.25 + h,
                                                                                math.sin(a) * r), 0.3)
    for i in range(6):
        a = i * 2 * math.pi / 6 + 0.4
        s.use((150, 192, 128)).rod((0, 1.25, 0), (math.cos(a) * 0.35, 1.25 + rnd.uniform(0.7, 0.95),
                                                  math.sin(a) * 0.35), 0.24)
    return s


def note_shapes():
    s = Shapes()
    s.use((250, 226, 130)).box((0, 0.01, 0), (2.4, 0.02, 2.4))
    for k, w in enumerate((1.7, 1.3, 1.6, 0.9)):  # someone's handwriting
        s.use((90, 92, 120)).box((-1.0 + w / 2, 0.022, 0.7 - k * 0.42), (w, 0.004, 0.06))
    return s


def pencil_shapes():
    s = Shapes()
    s.use((240, 192, 72)).rod((-1.7, 0.13, 0), (1.5, 0.13, 0), 0.26)
    s.use((228, 196, 150)).rod((1.5, 0.13, 0), (1.9, 0.13, 0), 0.16)
    s.use((60, 60, 66)).rod((1.9, 0.13, 0), (2.02, 0.13, 0), 0.06)
    s.use((236, 150, 160)).rod((-2.0, 0.13, 0), (-1.7, 0.13, 0), 0.26)
    s.use((200, 202, 210)).rod((-1.78, 0.13, 0), (-1.62, 0.13, 0), 0.28)
    return s


def tray_shapes(w, d, wall, colour, floor=0.18):
    s = Shapes().use(colour)
    s.box((0, floor / 2, 0), (w, floor, d))
    rim = shade(colour, 1.08)
    s.use(rim)
    for z in (d / 2 - wall / 2, -d / 2 + wall / 2):
        s.box((0, floor + 0.12, z), (w, 0.24, wall))
    for x in (w / 2 - wall / 2, -w / 2 + wall / 2):
        s.box((x, floor + 0.12, 0), (wall, 0.24, d - 2 * wall))
    return s


def dish_shapes():
    s = Shapes()
    s.use((64, 68, 78)).cylinder((0, 0, 0), 1.25, 0.22, 28)
    s.use((96, 100, 112)).cylinder((0, 0.22, 0), 1.05, 0.004, 28)
    return s


def screw_head(s, x, z):
    """A screw lying head up in the dish."""
    s.use(SILVER).cylinder((x, 0, z), 0.22, 0.07, 14)
    for size in ((0.34, 0.02, 0.05), (0.05, 0.02, 0.34)):
        s.use((108, 110, 120)).box((x, 0.072, z), size)


def bowl_shapes():
    """A glazed bowl of warm, soapy water, with a sponge beside it."""
    s = Shapes()
    glaze = (92, 134, 176)
    s.use(shade(glaze, 0.86)).cylinder((0, 0, 0), 0.8, 0.12, 26)  # its foot
    s.use(glaze).cylinder((0, 0.12, 0), 1.05, 0.3, 26)
    s.use(glaze).cylinder((0, 0.42, 0), 1.3, 0.34, 26)
    s.use(shade(glaze, 1.25)).cylinder((0, 0.76, 0), 1.32, 0.05, 26)  # its rim
    s.use((124, 186, 218)).cylinder((0, 0.66, 0), 1.16, 0.12, 26)  # the water
    rnd = random.Random(8)
    for _ in range(9):  # suds, round the edge
        a, r = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.6, 1.0)
        size = rnd.uniform(0.1, 0.2)
        s.use((246, 250, 255)).cylinder((math.cos(a) * r, 0.78, math.sin(a) * r), size, size * 0.6, 10)
    s.use((250, 214, 100)).box((1.75, 0.16, -0.5), (0.9, 0.32, 0.6))  # the sponge, with its green scrubby side
    s.use((96, 160, 96)).box((1.75, 0.35, -0.5), (0.9, 0.06, 0.6))
    return s


class Bowl:
    """The wash bowl on the desk: click it to wash the keycaps waiting in the tray, the way you'd soak real ones in
    warm, soapy water to get years of grime off."""
    name = "wash bowl"

    def __init__(self, parent, pos):
        self.root = parent.attachNewNode("bowl")
        self.root.setPos(*pos)
        bowl_shapes().mesh(self.root, "bowl")
        node = self.root.attachNewNode(CollisionNode("bowl"))
        node.node().addSolid(CollisionBox(Point3(0.3, 0.4, 0), 1.6, 0.5, 1.35))
        node.node().setIntoCollideMask(PICK_MASK)
        node.setPythonTag("part", self)
        node.setPythonTag("tag", None)


# ---- sound ----

class Sounds:
    """Every sound effect and the music. They're made by fixer3d_sounds.py, in another process the first time, so
    the game starts at once; each one plays as soon as its file is there. The sound effects and the music (with
    the rain) each have a volume, and can each be switched off."""
    MUSIC, RAIN = 0.3, 0.14

    def __init__(self, enabled=True, settings=None):
        settings = settings or {}
        self.enabled = enabled
        self.on, self.music_on = bool(settings.get("sound_on", True)), bool(settings.get("music_on", True))
        self.volume = {kind: min(1.0, max(0.0, float(settings.get(kind, 0.8)))) for kind in ("sound", "music")}
        self.pools, self.loops = {}, {}
        self.next_check = 0.0
        if not enabled:
            return
        if os.path.isdir(CACHE):  # sounds made by an older version of the game
            for name in os.listdir(CACHE):
                old = os.path.join(CACHE, name)
                if name.startswith("sounds") and name[6:].isdigit() and old != SOUNDS:
                    shutil.rmtree(old, ignore_errors=True)
        if not all(os.path.exists(fixer3d_sounds.path(SOUNDS, n)) for n in [*fixer3d_sounds.ALL_FILES, "rain", "music"]):
            try:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.Popen([sys.executable, os.path.join(HERE, "fixer3d_sounds.py"), SOUNDS],
                                 creationflags=flags)
            except OSError:
                fixer3d_sounds.make_effects(SOUNDS)

    def load(self, name):
        file = fixer3d_sounds.path(SOUNDS, name)
        if not os.path.exists(file):
            return None
        return _audio_manager.getSound(Filename.fromOsSpecific(file), False)

    def settings(self):
        """What's kept in the save file."""
        return {"sound": round(self.volume["sound"], 2), "music": round(self.volume["music"], 2),
                "sound_on": self.on, "music_on": self.music_on}

    def play(self, name, volume=1.0, pitch=1.0, vary=0.03):
        """Play a sound effect: one of its takes (never the same one twice running), a touch higher or lower and
        louder or softer each time, the way no two real taps are quite the same."""
        if not (self.enabled and self.on) or self.volume["sound"] <= 0 or name not in fixer3d_sounds.EFFECTS:
            return
        pool = self.pools.get(name)
        if pool is None:
            files = fixer3d_sounds.files(name)
            if not all(os.path.exists(fixer3d_sounds.path(SOUNDS, f)) for f in files):
                return  # not made yet
            copies = -(-5 // len(files))  # five or more in all, so quick ones can overlap
            pool = self.pools[name] = [[self.load(f) for _ in range(copies) for f in files], 0, len(files)]
        sounds, i, takes = pool
        s = sounds[i]
        pool[1] = (i + (random.choice((1, 2)) if takes > 2 else 1)) % len(sounds)
        s.stop()
        s.setPlayRate(pitch * random.uniform(1 - vary, 1 + vary))
        s.setVolume(min(1.0, volume * self.volume["sound"] * random.uniform(0.88, 1.0)))
        s.play()

    def update(self, now):
        """Start the music and the rain once they're made."""
        if not self.enabled or self.loops or now < self.next_check:
            return
        self.next_check = now + 1.0
        rain, music = self.load("rain"), self.load("music")
        if rain is None or music is None:
            return
        self.loops = {"rain": (rain, self.RAIN), "music": (music, self.MUSIC)}
        for s, _ in self.loops.values():
            s.setLoop(True)
        self.set_music(self.music_on)

    def set_music(self, on):
        """The music and the rain: on or off, at their volume."""
        self.music_on = on
        level = self.volume["music"]
        for s, volume in self.loops.values():
            s.setVolume(volume * level)
            if on and level > 0:
                if s.status() != s.PLAYING:
                    s.play()
            else:
                s.stop()

    def set_on(self, on):
        """The sound effects (the music has its own switch)."""
        self.on = on

    def set_volume(self, kind, level):
        self.volume[kind] = min(1.0, max(0.0, level))
        if kind == "music":
            self.set_music(self.music_on)


def material(part):
    """What a big part is made of, for the sound it makes coming off and going on."""
    key = part.key
    if "foam" in key:
        return "foam"
    if key in ("plate", "weight", "mouse_weight", "mouse_battery"):
        return "metal"
    if key in ("pcb", "usb_board", "side_board"):
        return "board"
    if key.startswith(("foot", "gasket")) or key in ("battery", "wheel"):
        return "rubber"
    if "cable" in key or key in ("battery_lead", "receiver", "knob", "lens"):
        return "cable"  # (a small click)
    return "plastic"  # the case, the frame, the legs, the stabilisers


def load_save():
    try:
        with open(SAVE_FILE, encoding="utf-8") as f:
            save = json.load(f)
    except (OSError, ValueError):
        save = {}
    save.setdefault("found", [])
    save.setdefault("fixed", {})
    save.setdefault("audio", {})
    return save


def write_save(save):
    try:
        os.makedirs(os.path.dirname(SAVE_FILE), exist_ok=True)
        with open(SAVE_FILE + ".part", "w", encoding="utf-8") as f:
            json.dump(save, f, indent=1)
        os.replace(SAVE_FILE + ".part", SAVE_FILE)
    except OSError:
        pass


def nlerp(a, b, s):
    if a.dot(b) < 0:
        b = Quat(-b.getR(), -b.getI(), -b.getJ(), -b.getK())
    q = Quat(a.getR() + (b.getR() - a.getR()) * s, a.getI() + (b.getI() - a.getI()) * s,
             a.getJ() + (b.getJ() - a.getJ()) * s, a.getK() + (b.getK() - a.getK()) * s)
    q.normalize()
    return q


FLIP = Quat()
FLIP.setHpr((0, 180, 0))  # turned over, about x


# ---- the workshop ----

class Workshop(Entity):
    """The 3D bench: the keyboard you're holding up to look at, the trays on the desk, the screen round it, and
    everything you do."""

    def __init__(self, offscreen=False):
        super().__init__()
        self.offscreen = offscreen  # drawing test pictures, with no window or mouse
        self.save = load_save() if not offscreen else {"found": [], "fixed": {}, "audio": {}}
        self.sounds = Sounds(enabled=not offscreen, settings=self.save["audio"])
        self.art = art()
        self.ui, self.tips, self.flights, self.tweens = [], {}, [], {}
        self.parts, self.part_set, self.board = [], set(), None
        self.spec = _BY_KEY["tkl"]
        self.menu_kind = "keyboard"  # which the menu shows
        self.kind, self.tools = "keyboard", TOOLS
        self.state, self.phase = "menu", "apart"
        self.lit = self.held = None
        self.turning = {}  # screws turning out (or in): screw -> how far along, 0 to 1
        self.dragging = self.help_open = self.confirming = False
        self.frames, self.frame_clock, self.show_fps = 0, 0.0, False
        self.clock = 0.0
        self.cam, self.cam_target = None, Vec3(0, 0, 0)
        self.layout_aspect = window.aspect_ratio
        self.ui_hovered = None
        self.volumes, self.volume_drag = {}, None  # the volume pop-ups, and the one being dragged
        self.said = set()
        self.next_tick = 0.0
        self.brushing, self.brush_from, self.brush_travel = False, None, 0.0  # the brush, held down and moving
        self.next_brush = 0.0
        self.corners, self.desk_lift = [], 0.0  # the keyboard's box, and how far it's lifted to clear the desk
        self.message_time = 0.0
        self.make_room()
        self.make_picker()
        self.make_showcase()
        self.show_menu(instant=True)

    # ---- the room ----

    def make_room(self):
        """The desk and the things on it, the lamp over it, and the camera."""
        window.color = rgb(BACKDROP)
        self.room = Entity(shader=COZY)
        s, tile = 90, 9
        desk = Shapes().use((255, 255, 255))
        desk.quad((-s, DESK_Y, -s), (-s, DESK_Y, s), (s, DESK_Y, s), (s, DESK_Y, -s), (0, 1, 0),
                  [(-s / tile, -s / tile), (-s / tile, s / tile), (s / tile, s / tile), (s / tile, -s / tile)])
        desk.mesh(self.room, "desk", texture=self.art["wood"]._texture)
        self.mat = self.room.attachNewNode("mat")
        self.tray_root = self.room.attachNewNode("trays")
        self.mug = self.room.attachNewNode("mug")
        mug_shapes().mesh(self.mug)
        self.plant = self.room.attachNewNode("plant")
        plant_shapes().mesh(self.plant)
        self.note = self.room.attachNewNode("note")
        note_shapes().mesh(self.note)
        self.pencil = self.room.attachNewNode("pencil")
        pencil_shapes().mesh(self.pencil)
        self.sun = DirectionalLight(shadows=True, shadow_map_resolution=(2048, 2048))
        self.sun.color = rgb(SUN)
        self.sun.look_at(Vec3(0.45, -1, 0.6))
        self.sun.update_bounds(Entity(model="cube", scale=(66, 16, 50), y=-0.5, visible=False))
        self.steam = []
        for k in range(4):  # wisps rising off the tea
            card = CardMaker("steam")
            card.setFrame(-0.5, 0.5, -0.5, 0.5)
            np = application.base.render.attachNewNode(card.generate())
            np.setTexture(self.art["glow"]._texture)
            np.setTransparency(TransparencyAttrib.M_alpha)
            np.setDepthWrite(False)
            np.setLightOff(1)
            np.setShaderOff(1)
            np.setBillboardPointEye()
            np.setBin("fixed", 10)
            np.hide(SHADOW_MASK)
            self.steam.append(np)
        self.bubbles = []
        for k in range(8):  # soap bubbles, rising off the wash bowl while keycaps soak
            card = CardMaker("bubble")
            card.setFrame(-0.5, 0.5, -0.5, 0.5)
            np = application.base.render.attachNewNode(card.generate())
            np.setTexture(self.art["glow"]._texture)
            np.setTransparency(TransparencyAttrib.M_alpha)
            np.setDepthWrite(False)
            np.setLightOff(1)
            np.setShaderOff(1)
            np.setBillboardPointEye()
            np.setBin("fixed", 11)
            np.hide()
            self.bubbles.append(np)
        glow = Shapes().use((255, 255, 255))  # a mouse's sensor light, shining on the mat under it as it moves
        glow.quad((-0.5, 0, -0.5), (-0.5, 0, 0.5), (0.5, 0, 0.5), (0.5, 0, -0.5), (0, 1, 0),
                  [(0, 0), (0, 1), (1, 1), (1, 0)])
        self.sensor_light = glow.mesh(application.base.render, "sensor light", texture=self.art["glow"],
                                      shadow=False).np
        self.sensor_light.setTransparency(TransparencyAttrib.M_alpha)
        self.sensor_light.setDepthWrite(False)
        self.sensor_light.setLightOff(1)
        self.sensor_light.setShaderOff(1)
        self.sensor_light.setBin("fixed", 9)
        self.sensor_light.hide()
        self.pitch = Entity(position=(0, PIVOT_Y, 0), shader=COZY)  # turns it over, round the x axis
        self.yaw = Entity(parent=self.pitch, shader=None)  # turns it round, about its own up
        self.kb = Entity(parent=self.yaw, y=-0.9, shader=None)  # so it turns about its middle
        self.flyers = Entity(shader=COZY)  # parts in the air, on their way to or from a tray
        self.vignette = Entity(parent=camera.ui, model="quad", texture=self.art["vignette"], z=0.9,
                               scale=(window.aspect_ratio + 0.02, 1.02))
        self.vignette.setTransparency(TransparencyAttrib.M_alpha)

    def arrange_desk(self, spec, trays):
        """Lay the desk out round a keyboard of this size: the cutting mat under it, the trays in front, the tea and
        the plant behind."""
        cw, cd = footprint(spec)
        for np in self.mat.getChildren():
            np.removeNode()
        w, d, cz = cw + 7, cd + 11, -2.2
        mat = Shapes().use((255, 255, 255))
        y = DESK_Y + 0.062
        mat.quad((-w / 2, y, cz - d / 2), (-w / 2, y, cz + d / 2), (w / 2, y, cz + d / 2), (w / 2, y, cz - d / 2),
                 (0, 1, 0), [(0, 0), (0, d / 4), (w / 4, d / 4), (w / 4, 0)])
        mat.mesh(self.mat, "mat", texture=self.art["mat"]._texture)
        edge = Shapes().use((44, 80, 68))
        edge.box((0, DESK_Y + 0.025, cz), (w, 0.05, d))
        edge.mesh(self.mat, "mat edge")
        self.mug.setPos(cw / 2 + 3.2, DESK_Y, cd / 2 + 2.0)
        self.mug.setH(-30)
        self.plant.setPos(-cw / 2 - 3.0, DESK_Y, cd / 2 + 2.4)
        self.note.setPos(-cw / 2 + 1.2, DESK_Y + 0.05, cd / 2 + 4.4)
        self.note.setH(8)
        self.pencil.setPos(cw / 2 - 2.0, DESK_Y + 0.05, cd / 2 + 4.6)
        self.pencil.setH(-14)
        if trays:
            self.tray_root.unstash()
        else:
            self.tray_root.stash()

    def make_trays(self, board):
        """The keycap tray, the switch tin and the screw dish, in front of the keyboard: what you take off lands in
        them, laid out the way it came off."""
        for np in self.tray_root.getChildren():
            np.removeNode()
        cw, cd = board.size
        wu, hu = board.inner
        if kind_of(board.spec) == "mouse":  # nothing to lay out but its screws: just the dish, in front
            self.bowl = None
            dish_at = (0, -cd / 2 - 1.7)
        else:
            tw, td = wu * TRAY_SCALE + 0.8, hu * TRAY_SCALE + 0.8
            gap, dish_w, bowl_w = 0.9, 2.6, 3.6
            z = -cd / 2 - 1.5 - td / 2
            x0 = -(bowl_w + 2 * tw + 3 * gap + dish_w) / 2 + bowl_w + gap  # the wash bowl, the trays, the dish
            centres = [x0 + tw / 2, x0 + tw + gap + tw / 2, x0 + 2 * tw + 2 * gap + dish_w / 2]
            self.bowl = Bowl(self.tray_root, (x0 - gap - 2.25, DESK_Y + 0.05, z - 0.1))  # (its sponge on the right)
            floor = 0.18
            for cx, colour, keyset, base in ((centres[0], (184, 136, 96), board.caps, CAP_Y),
                                             (centres[1], (176, 182, 192), board.switches, SWITCH_Y - 0.25)):
                frame = self.tray_root.attachNewNode("tray")
                frame.setPos(cx, DESK_Y + 0.05, z)
                tray_shapes(tw, td, 0.22, colour, floor).mesh(frame)
                holder = frame.attachNewNode("contents")
                holder.setPos(0, floor - base * TRAY_SCALE, 0)
                holder.setScale(TRAY_SCALE)
                keyset.add_tray(holder)
            dish_at = (centres[2], z)
        dish = self.tray_root.attachNewNode("dish")
        dish.setPos(dish_at[0], DESK_Y + 0.05, dish_at[1])
        dish_shapes().mesh(dish)
        self.dish = dish.attachNewNode("screws")
        self.dish.setPos(0, 0.226, 0)
        heads = Shapes()
        self.dish_spots = []
        for i in range(len(self.screws)):
            a = i * 2 * math.pi / max(1, len(self.screws)) + 0.3
            x, zz = math.cos(a) * 0.62, math.sin(a) * 0.62
            heads.begin(i)
            screw_head(heads, x, zz)
            self.dish_spots.append(Vec3(x, 0, zz))
        self.dish_mesh = heads.mesh(self.dish, "dish screws", hidden=True)

    def make_picker(self):
        """The mouse's ray into the keyboard. Ursina's own only looks at the buttons: it checks every entity
        against everything it hits, which gets slow with a lot of them."""
        mouse.traverse_target = None
        self.traverser, self.queue, self.ray = CollisionTraverser("parts"), CollisionHandlerQueue(), CollisionRay()
        node = CollisionNode("mouse ray")
        node.addSolid(self.ray)
        node.setFromCollideMask(PICK_MASK)
        node.setIntoCollideMask(BitMask32.allOff())
        self.traverser.addCollider(camera.attachNewNode(node), self.queue)

    def make_showcase(self):
        """The keyboards on the menu, one of each, turning slowly on show."""
        self.show_root = Entity(position=(0, 1.4, 0), shader=COZY)
        self.show_spin = Entity(parent=self.show_root, shader=None)
        self.showcase = {}
        for spec in ALL_MODELS:
            holder = self.show_spin.attachNewNode(spec["key"])
            holder.setY(-0.9)
            build_product(holder, spec, extras=False)
            holder.stash()
            self.showcase[spec["key"]] = holder
        self.shown = None

    def pick(self, film=None):
        """What's under the mouse on the keyboard: (part, tag, the point in the keyboard's space), or Nones. film is
        a point on the screen from -1 to 1 each way, to look somewhere other than the mouse."""
        if film is None:
            if self.offscreen or not application.base.mouseWatcherNode.hasMouse():
                return None, None, None
            film = (mouse.x * 2 / window.aspect_ratio, mouse.y * 2)
        self.ray.setFromLens(camera.lens_node, *film)
        self.traverser.traverse(self.kb)
        self.queue.sortEntries()
        for entry in self.queue.getEntries():
            node = entry.getIntoNodePath()
            part = node.getPythonTag("part")
            if part is None:
                continue
            if isinstance(part, Trinket):
                ok = not part.found and part.host.placed
            else:
                ok = part.placed and part in self.part_set
            if ok:
                return part, node.getPythonTag("tag"), Vec3(*entry.getSurfacePoint(self.kb))
        if self.bowl is not None:  # off the keyboard: the wash bowl, on the desk
            self.traverser.traverse(self.bowl.root)
            if self.queue.getNumEntries():
                return self.bowl, None, None
        return None, None, None

    def over_panel(self):
        """Is the mouse over the cards and buttons round the keyboard, rather than the keyboard itself?"""
        return not self.offscreen and mouse.hovered_entity is not None

    # ---- the camera ----

    def view(self, spec, where):
        cw, cd = footprint(spec)
        if kind_of(spec) == "mouse":  # (small: seen from a little further off, so it doesn't fill the screen)
            cw = max(cw, 10.5)
        if where == "menu":
            target, elevation, distance, width = Vec3(0, 0.5, 0), 24, 34, cw / 0.6
        elif where == "result":
            target, elevation, distance, width = Vec3(cw * 0.24, 0.6, 0), 30, 34, cw / 0.52
        else:
            target, elevation, distance, width = Vec3(cw * 0.05, -0.3, -cd * 0.45 - 1.6), 54, 40, cw / 0.56
        fov = math.degrees(2 * math.atan(width / 2 / distance))
        e = math.radians(elevation)
        return target + Vec3(0, math.sin(e), -math.cos(e)) * distance, target, fov

    def fit_view(self, points, rect, elevation, fov=34.0):
        """A camera looking down at `elevation` degrees that fits these points (in the world) into rect on the
        screen (x0, x1, y0, y1, in the UI's units): so the keyboard and its trays sit in the space between the
        cards, whatever shape the screen is."""
        e = math.radians(elevation)
        back = Vec3(0, math.sin(e), -math.cos(e))  # from what it looks at, back towards the camera
        target = sum(points, Vec3(0, 0, 0)) / len(points)
        distance, aspect = 40.0, window.aspect_ratio
        saved = Vec3(camera.position), Vec3(camera.rotation), camera.fov
        render, cam = application.base.render, application.base.cam
        camera.fov = fov
        for _ in range(5):
            camera.position = target + back * distance
            camera.look_at(target)
            xs, ys = [], []
            for p in points:
                film = Point2()
                camera.lens.project(cam.getRelativePoint(render, Point3(*p)), film)
                xs.append(film.x * aspect / 2)
                ys.append(film.y / 2)
            k = max((max(xs) - min(xs)) / (rect[1] - rect[0]), (max(ys) - min(ys)) / (rect[3] - rect[2]))
            per_unit = 2 * distance * math.tan(math.radians(fov) / 2) / aspect  # world size of a UI unit, there
            dx = (rect[0] + rect[1]) / 2 - (min(xs) + max(xs)) / 2
            dy = (rect[2] + rect[3]) / 2 - (min(ys) + max(ys)) / 2
            target -= (camera.right * dx + camera.up * dy) * per_unit
            distance *= k
        pos = target + back * distance
        camera.position, camera.rotation, camera.fov = saved
        return pos, target, fov

    def play_view(self):
        """Where the camera goes while you work: the keyboard (as it sits, level) and the trays in front of it."""
        cw, cd = self.board.size
        lift = PIVOT_Y + self.kb.y
        points = [Vec3(x, y + lift, z) for x in (-cw / 2, cw / 2) for y in (0, self.board.height + 0.3)
                  for z in (-cd / 2, cd / 2)]
        render = application.base.render
        for tray in self.tray_root.getChildren():
            bounds = tray.getTightBounds(render)
            if bounds:
                lo, hi = bounds
                points += [Vec3(x, y, z) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
        L, R = -window.aspect_ratio / 2, window.aspect_ratio / 2
        return self.fit_view(points, (L + 0.15, R - 0.43, -0.38, 0.27), 56)

    def aim(self, where, duration=0.9):
        pos, target, fov = self.play_view() if where == "play" else self.view(self.spec, where)
        if duration <= 0 or self.cam is None:
            camera.position, camera.fov = pos, fov
            camera.look_at(target)
            self.cam_target, self.cam = target, {}
            return
        self.cam = {"t": 0.0, "d": duration, "p0": Vec3(camera.position), "p1": pos, "t0": Vec3(self.cam_target),
                    "t1": target, "f0": camera.fov, "f1": fov}
        self.cam_target = target

    def update_camera(self):
        if not self.cam or "d" not in self.cam:
            return
        c = self.cam
        c["t"] += time.dt
        s = smooth(min(1.0, c["t"] / c["d"]))
        camera.position = c["p0"] + (c["p1"] - c["p0"]) * s
        camera.look_at(c["t0"] + (c["t1"] - c["t0"]) * s)
        camera.fov = c["f0"] + (c["f1"] - c["f0"]) * s
        if s >= 1:
            self.cam = {}

    # ---- moving things about ----

    def measure_board(self):
        """The corners of the keyboard's box (in its own space), to keep it out of the desk as it turns."""
        bounds = self.kb.getTightBounds(self.kb)
        if not bounds:
            self.corners = []
            return
        lo, hi = bounds
        self.corners = [Point3(x, y, z) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]

    def keep_above_desk(self):
        """However it's turned, lift the keyboard just enough that no corner of it goes into the desk, the way
        you'd lift one off the table to turn it over. It comes back down gently once it's level again."""
        if not self.corners:
            return
        render = application.base.render
        self.pitch.y = PIVOT_Y
        low = min(render.getRelativePoint(self.kb, p).y for p in self.corners)
        need = max(0.0, DESK_Y + CLEARANCE - low)
        if need >= self.desk_lift:
            self.desk_lift = need
        else:
            self.desk_lift += (need - self.desk_lift) * min(1.0, time.dt * 8)
        self.pitch.y = PIVOT_Y + self.desk_lift

    def lift_distance(self, part):
        """How far a big part can fly off before it would go into the desk: all the way (LIFT) if it comes off
        upwards, less when the keyboard is turned so that it comes off downwards."""
        render = application.base.render
        way = render.getRelativeVector(self.kb, part.lift)
        if way.y >= -0.05:
            return LIFT
        low = min(render.getRelativePoint(self.kb, Point3(x, y, z)).y
                  for x in (part.lo.x, part.hi.x) for y in (part.lo.y, part.hi.y) for z in (part.lo.z, part.hi.z))
        return max(0.0, min(LIFT, (low - DESK_Y - CLEARANCE) / -way.y))

    def tween(self, np, end, duration, ease=out_quad, then=None):
        self.tweens[np.getKey()] = [np, Vec3(*np.getPos()), Vec3(*end), duration, 0.0, ease, then, "pos"]

    def jiggle(self, np):
        base = Vec3(*np.getPos())
        key = np.getKey()
        if key in self.tweens:
            return
        self.tweens[key] = [np, base, base, 0.25, 0.0, None, None, "shake"]

    def update_tweens(self):
        for key, tw in list(self.tweens.items()):
            np, a, b, d, t, ease, then, kind = tw
            if np.isEmpty():
                del self.tweens[key]
                continue
            t += time.dt
            tw[4] = t
            if kind == "shake":
                k = max(0.0, 1 - t / d) * 0.12
                np.setPos(a + Vec3(random.uniform(-k, k), random.uniform(-k, k), random.uniform(-k, k)))
            else:
                np.setPos(a + (b - a) * ease(min(1.0, t / d)))
            if t >= d:
                if kind == "shake":
                    np.setPos(a)
                del self.tweens[key]
                if then:
                    then()

    def spot(self, node, point, flip=False):
        """Where a point on a node is in the world, which way round the node is, and how big."""
        render = application.base.render
        quat = node.getQuat(render)
        return render.getRelativePoint(node, Point3(*point)), FLIP * quat if flip else quat, node.getScale(render).x

    def fly(self, mesh, start, end, duration=0.45, arc=1.4, then=None, end_scale=None):
        """Fly a copy of something from one spot (a node, and a point on it) to another, in an arc."""
        self.flights.append([mesh, start, end, duration, 0.0, arc, then, end_scale])
        self.update_flight(self.flights[-1], 0.0)

    def update_flight(self, f, dt):
        mesh, start, end, d, t, arc, then, end_scale = f
        t += dt
        f[4] = t
        s = smooth(min(1.0, t / d))
        p0, q0, k0 = self.spot(*start)
        p1, q1, k1 = self.spot(*end)
        if end_scale is not None:
            k1 = end_scale
        pos = p0 + (p1 - p0) * s + LVector3f(0, arc * math.sin(math.pi * s), 0)
        k = k0 + (k1 - k0) * s
        mesh.np.setPosQuatScale(pos, nlerp(q0, q1, s), LVector3f(k, k, k))
        return s >= 1

    def update_flights(self):
        for f in list(self.flights):
            if self.update_flight(f, time.dt):
                self.flights.remove(f)
                f[0].np.removeNode()
                if f[6]:
                    f[6]()

    def update_steam(self):
        top = application.base.render.getRelativePoint(self.mug, Point3(0, 2.1, 0))
        for k, np in enumerate(self.steam):
            phase = (self.clock * 0.28 + k / len(self.steam)) % 1.0
            np.setPos(top + LVector3f(math.sin(self.clock * 0.9 + k * 2.1) * 0.25 * phase, phase * 2.8,
                                      math.cos(self.clock * 0.7 + k) * 0.15 * phase))
            np.setScale(0.7 + phase * 1.6)
            np.setColorScale(1, 0.98, 0.95, math.sin(math.pi * phase) * 0.3)

    # ---- screens ----

    def clear_ui(self):
        for e in self.ui:
            destroy(e)
        self.ui, self.tips = [], {}
        self.tool_buttons, self.chips, self.swatches, self.switch_swatches = [], [], [], []
        self.groups = {}
        self.volumes, self.volume_drag = {}, None
        self.ui_hovered = None
        self.help_open = self.confirming = False

    def add(self, e, group=None):
        self.ui.append(e)
        if group:
            self.groups.setdefault(group, []).append(e)
        return e

    def card(self, center, size, col=CREAM, corner=0.018, z=0.2, shadow=True, group=None, collider=True,
             body=True):
        w, h = size
        if shadow:
            self.add(Entity(parent=camera.ui, model=Quad(radius=min(0.5, corner / h), aspect=w / h),
                            position=(center[0] + 0.003, center[1] - 0.005, z + 0.01), scale=(w, h),
                            color=color.rgba32(40, 24, 16, 60)), group).setTransparency(TransparencyAttrib.M_alpha)
        if not body:
            return None
        return self.add(Entity(parent=camera.ui, model=Quad(radius=min(0.5, corner / h), aspect=w / h),
                               position=(center[0], center[1], z), scale=(w, h), color=rgb(col),
                               collider="box" if collider else None), group)

    def text(self, value, pos, scale=1.0, col=COCOA, origin=(-0.5, 0.5), bold=False, z=-0.01, group=None, **kwargs):
        t = Text(value or " ", parent=camera.ui, position=(pos[0], pos[1], z), scale=scale, color=rgb(col),
                 origin=origin, font=BOLD_FONT if bold else FONT, **kwargs)  # (Ursina can't wrap an empty text)
        t.shown = value
        return self.add(t, group)

    def icon(self, name, pos, size, col=COCOA, z=-0.02, group=None):
        return self.add(Entity(parent=camera.ui, model="quad", texture=self.art[name], position=(pos[0], pos[1], z),
                               scale=size, color=rgb(col)), group)

    def clicked(self, fn, sound="ui"):
        def run():
            self.sounds.play(sound, 0.6)
            fn()
        return run

    def button(self, label, pos, size, on_click, back=CREAM, fore=COCOA, text_size=0.8, tip=None, group=None,
               corner=0.35, z=0.0, sound="ui"):
        b = Button(parent=camera.ui, text=label, position=(pos[0], pos[1], z), scale=size, color=rgb(back),
                   text_color=rgb(fore), text_size=text_size, radius=corner, on_click=self.clicked(on_click, sound),
                   highlight_color=rgb(shade(back, 1.04)), pressed_color=rgb(shade(back, 0.92)))
        b.painted = (back, fore)
        if tip:
            self.tips[b] = tip
        return self.add(b, group)

    def icon_button(self, name, pos, size, on_click, tip=None, back=CREAM, fore=COCOA, group=None, z=0.0):
        b = self.button("", pos, (size, size), on_click, back, fore, tip=tip, group=group, corner=0.5, z=z)
        b.glyph = Entity(parent=b, model="quad", texture=self.art[name], scale=0.6, z=-0.01, color=rgb(fore))
        return b

    def set_text(self, t, value):
        """Change a text only when it's different: Ursina rebuilds a text's letters every time it's set."""
        if getattr(t, "shown", None) != value:
            t.text, t.shown = value or " ", value

    def set_colors(self, b, back, fore):
        if getattr(b, "painted", None) != (back, fore):
            b.color, b.text_color, b.painted = rgb(back), rgb(fore), (back, fore)
            b.highlight_color, b.pressed_color = rgb(shade(back, 1.04)), rgb(shade(back, 0.92))
            if hasattr(b, "glyph"):
                b.glyph.color = rgb(fore)

    def show_group(self, name, shown):
        for e in self.groups.get(name, []):
            if e.enabled != shown:
                e.enabled = shown

    def corner_buttons(self):
        """Sound and music, top right (point at one for its volume); on the menu, a way out too."""
        R = window.aspect_ratio / 2
        x, z = R - 0.05, -0.25  # in front of the volume pop-ups, which open out of the buttons
        if self.state == "menu":
            self.icon_button("power", (x, 0.45), 0.058, application.quit, "Quit", z=z)
        else:
            self.icon_button("home", (x, 0.45), 0.058, self.ask_leave if self.state == "play" else self.show_menu,
                             "Menu", z=z)
        self.volumes = {}
        self.sound_button = self.icon_button(self.glyph_for("sound"), (x - 0.068, 0.45), 0.058, self.toggle_sound,
                                             z=z)
        self.music_button = self.icon_button(self.glyph_for("music"), (x - 0.136, 0.45), 0.058, self.toggle_music,
                                             z=z)
        self.volume_popup("sound", self.sound_button)
        self.volume_popup("music", self.music_button)
        if self.state == "play":
            self.icon_button("help", (x - 0.204, 0.45), 0.058, self.toggle_help, "Help", z=z)
        self.fps_text = self.text("", (0, 0.49), 0.8, (236, 226, 208), origin=(0, 0.5))

    def glyph_for(self, kind):
        s = self.sounds
        if kind == "sound":
            return "sound" if s.on and s.volume["sound"] > 0 else "mute"
        return "music" if s.music_on and s.volume["music"] > 0 else "music_off"

    def volume_popup(self, kind, button):
        """A little slider that opens out of the button while the mouse is on it: scroll on it, or click (or drag)
        along it, to set the volume. The button itself still switches it off and on."""
        group = "volume " + kind
        x = button.x
        top, bottom = button.y + 0.036, 0.205
        pill = self.card((x, (top + bottom) / 2), (0.072, top - bottom), CREAM, corner=0.036, z=-0.2, group=group)
        lo, hi = VOLUME_TRACK
        self.card((x, (lo + hi) / 2), (0.012, hi - lo + 0.012), PAPER_DARK, corner=0.006, z=-0.21, shadow=False,
                  collider=False, group=group)
        cap = self.add(Entity(parent=camera.ui, model=Quad(radius=0.5), scale=0.012, position=(x, lo, -0.22),
                              color=rgb(HONEY)), group)
        fill = self.add(Entity(parent=camera.ui, model="quad", origin=(0, -0.5), scale=(0.012, 0.001),
                               position=(x, lo, -0.22), color=rgb(HONEY)), group)
        knob = self.add(Entity(parent=camera.ui, model=Quad(radius=0.5), scale=0.032, position=(x, lo, -0.23),
                               color=rgb(HONEY)), group)
        dot = self.add(Entity(parent=camera.ui, model=Quad(radius=0.5), scale=0.014, position=(x, lo, -0.235),
                              color=rgb(CREAM)), group)
        label = self.text("", (x, bottom + 0.026), 0.78, MUTED, origin=(0, 0), z=-0.23, group=group)
        hit = self.add(Entity(parent=camera.ui, model="quad", scale=(0.072, hi - lo + 0.05),
                              position=(x, (lo + hi) / 2, -0.24), collider="box", visible=False), group)
        self.volumes[kind] = {"button": button, "hover": {button, pill, hit}, "hit": hit, "cap": cap, "fill": fill,
                              "knob": knob, "dot": dot, "label": label, "open": 0.0, "shown": None, "level": None}
        self.show_volume(kind)
        self.show_group(group, False)
        self.volumes[kind]["shown"] = False

    def show_volume(self, kind):
        """Bring a slider (and its button's icon) up to date with the volume."""
        pop = self.volumes.get(kind)
        if not pop:
            return
        on = self.sounds.on if kind == "sound" else self.sounds.music_on
        level = self.sounds.volume[kind] if on else 0.0
        if pop["level"] != level:
            pop["level"] = level
            lo, hi = VOLUME_TRACK
            y = lo + (hi - lo) * level
            pop["fill"].scale_y = max(0.001, y - lo)
            pop["knob"].y = pop["dot"].y = y
            self.set_text(pop["label"], f"{round(level * 100)}%")
        glyph = self.art[self.glyph_for(kind)]
        if pop["button"].glyph.texture != glyph:
            pop["button"].glyph.texture = glyph

    def set_volume(self, kind, level, sound=True):
        level = round(min(1.0, max(0.0, level)), 2)
        before = self.sounds.volume[kind]
        if kind == "sound":
            self.sounds.on = level > 0 or self.sounds.on
        else:
            self.sounds.music_on = level > 0 or self.sounds.music_on
        self.sounds.set_volume(kind, level)
        if sound and kind == "sound" and abs(level - before) > 0.001 and self.clock >= self.next_tick:
            self.next_tick = self.clock + 0.06
            self.sounds.play("ui", 0.6)  # so you hear how loud it is
        self.show_volume(kind)

    def update_volumes(self):
        """Open a volume pop-up while the mouse is on its button (or on the pop-up), and close it a moment after
        the mouse leaves; follow a drag along the slider."""
        if self.offscreen:
            return
        hovered = mouse.hovered_entity
        if self.volume_drag and not held_keys["left mouse"]:
            self.volume_drag = None
        for kind, pop in self.volumes.items():
            if self.volume_drag == kind:
                lo, hi = VOLUME_TRACK
                self.set_volume(kind, (mouse.y - lo) / (hi - lo))
            if hovered in pop["hover"] or self.volume_drag == kind:
                pop["open"] = 0.35
            else:
                pop["open"] -= time.dt
            shown = pop["open"] > 0
            if shown != pop["shown"]:
                pop["shown"] = shown
                self.show_group("volume " + kind, shown)
                if not shown:
                    self.keep_audio()

    def volume_input(self, key):
        """Scrolling or clicking on a volume pop-up: True if it was, so nothing else takes it too."""
        if self.offscreen:
            return False
        hovered = mouse.hovered_entity
        for kind, pop in self.volumes.items():
            if not pop["shown"] or hovered not in pop["hover"]:
                continue
            if key in ("scroll up", "scroll down"):
                on = self.sounds.on if kind == "sound" else self.sounds.music_on
                level = self.sounds.volume[kind] if on else 0.0
                self.set_volume(kind, level + (0.05 if key == "scroll up" else -0.05))
                return True
            if key == "left mouse down" and hovered is pop["hit"]:
                self.volume_drag = kind
                lo, hi = VOLUME_TRACK
                self.set_volume(kind, (mouse.y - lo) / (hi - lo))
                return True
        if key == "left mouse up" and self.volume_drag is not None:
            self.volume_drag = None
            self.keep_audio()
        return False

    def keep_audio(self):
        """Remember the volumes for next time."""
        if not self.offscreen and self.save.get("audio") != self.sounds.settings():
            self.save["audio"] = self.sounds.settings()
            write_save(self.save)

    def toggle_sound(self):
        if self.sounds.volume["sound"] <= 0:
            self.set_volume("sound", 0.5, sound=False)  # off because it was turned all the way down
            self.sounds.on = True
        else:
            self.sounds.set_on(not self.sounds.on)
        self.show_volume("sound")
        self.keep_audio()

    def toggle_music(self):
        if self.sounds.volume["music"] <= 0:
            self.sounds.music_on = True
            self.set_volume("music", 0.5)
        else:
            self.sounds.set_music(not self.sounds.music_on)
        self.show_volume("music")
        self.keep_audio()

    # -- the menu --

    def show_menu(self, instant=False):
        self.state = "menu"
        self.clear_play()
        self.menu_kind = kind_of(self.spec)
        self.show_root.enabled = True
        self.show_root.position = (0, 1.4, 0)
        self.arrange_desk(self.spec, trays=False)
        self.shown = None
        self.preview(self.spec)
        self.aim("menu", 0 if instant else 1.0)
        self.menu_ui()

    def menu_ui(self):
        """Just the name, and a button for each keyboard: point at one to see it."""
        self.clear_ui()
        self.layout_aspect = window.aspect_ratio
        self.icon("game", (-0.25, 0.375), 0.13, col=(255, 255, 255))
        self.text("FIXER 3D", (-0.165, 0.377), 4.2, CREAM, origin=(-0.5, 0), bold=True)
        self.model_buttons = []
        per_row = 4
        for k, (kind, label) in enumerate(KINDS):  # keyboards, or mice
            on = kind == self.menu_kind
            self.button(label, ((k - (len(KINDS) - 1) / 2) * 0.2, -0.232), (0.18, 0.05),
                        lambda kind=kind: self.pick_kind(kind), HONEY if on else PAPER, CREAM if on else COCOA,
                        text_size=0.95, corner=0.5, z=0.2)
        for i, spec in enumerate(m for m in ALL_MODELS if kind_of(m) == self.menu_kind):  # smallest first
            x = (i % per_row - (per_row - 1) / 2) * 0.33
            y = -0.315 - (i // per_row) * 0.1
            self.card((x, y), (0.3, 0.072), CREAM, corner=0.026, z=0.25, collider=False, body=False)
            b = self.button(short_name(spec), (x, y), (0.3, 0.072), lambda s=spec: self.start(s), CREAM, COCOA,
                            text_size=1.1, corner=0.35, z=0.2)
            b.spec = spec
            self.model_buttons.append(b)
        self.menu_marker = self.add(Entity(parent=camera.ui, model=Quad(radius=0.5, aspect=0.12 / 0.007),
                                           scale=(0.12, 0.007), color=rgb(HONEY), z=0.15))
        self.corner_buttons()

    def pick_kind(self, kind):
        """The menu's tabs: keyboards, or mice."""
        if kind != self.menu_kind:
            self.menu_kind = kind
            self.preview(next(m for m in ALL_MODELS if kind_of(m) == kind))
            self.menu_ui()

    def preview(self, spec):
        """Show this keyboard (or mouse) on the menu."""
        if self.shown == spec["key"]:
            return
        if self.shown:
            self.showcase[self.shown].stash()
            self.sounds.play("swap", 0.5)
        self.shown = spec["key"]
        self.spec = spec
        holder = self.showcase[spec["key"]]
        holder.unstash()
        holder.setPos(0, -2.2, 0)
        self.tween(holder, (0, -0.9, 0), 0.35)
        self.arrange_desk(spec, trays=False)
        if self.state == "menu" and self.cam is not None:
            self.aim("menu", 0.5)

    def update_menu(self):
        self.show_spin.rotation_y += 16 * time.dt
        self.show_root.y = 1.4 + math.sin(self.clock * 1.2) * 0.12
        hovered = mouse.hovered_entity if not self.offscreen else None
        for b in self.model_buttons:
            if hovered is b:
                self.preview(b.spec)
        for b in self.model_buttons:
            if b.spec["key"] == self.shown:
                self.menu_marker.position = (b.x, b.y - 0.046, 0.15)
        if not self.offscreen and held_keys["left mouse"] and hovered is None and not self.volume_drag:
            self.show_spin.rotation_y -= mouse.velocity.x * 200

    # -- playing --

    def start(self, spec):
        """A new keyboard of this type on the bench, all in one piece."""
        self.clear_ui()
        self.clear_play()
        self.spec = spec
        spin = (self.show_spin.rotation_y + 180) % 360 - 180
        self.show_root.enabled = False
        self.pitch.rotation = Vec3(0, 0, 0)
        self.pitch.y, self.desk_lift = PIVOT_Y, 0.0
        self.yaw.rotation = Vec3(0, spin, 0)
        self.yaw.animate("rotation_y", 0, duration=0.9, curve=curve.in_out_sine)
        self.board = build_product(self.kb, spec, extras=True)
        self.measure_board()
        self.parts = self.board.in_order()
        by_key = {p.key: p for p in self.parts}
        for p in self.parts:
            p.below = [by_key[k] for k in p.below]
        self.part_set = set(self.parts)
        self.big = [p for p in self.parts if isinstance(p, Part3D) and not p.screw]
        self.screws = [p for p in self.parts if p.screw]
        self.caps, self.switches = self.board.caps.items, self.board.switches.items
        self.kind = kind_of(spec)
        # (a mouse needs no keycap or switch pullers, and has no stabilisers to lube)
        self.tools = TOOLS if self.kind == "keyboard" else [t for t in TOOLS if t[0] in ("hand", "driver", "brush")]
        self.make_trays(self.board)
        self.arrange_desk(spec, trays=True)
        self.phase, self.tool, self.paint = "apart", "puller" if self.kind == "keyboard" else "hand", 0
        self.switch_kind = [k[0] for k in SWITCH_KINDS].index(spec["switch"])
        self.checks = {}  # a mouse's test: what's been tried
        self.moved, self.mouse_down = 0.0, {}  # how far it's been moved; its buttons held down
        self.held = self.lit = None
        self.turning = {}
        self.dragging = False
        self.said, self.found = set(), None
        self.tested, self.keys_down, self.flash, self.wave = set(), set(), {}, -1.0
        self.mouse_key = None
        self.knob = self.board.knob
        self.knob_turned = False
        self.stabs = [p for p in self.parts if p.key.startswith("stab")]
        self.washing, self.washed = 0.0, 0
        self.state = "play"
        self.aim("play", 0.9)
        self.build_ui()
        self.say(spec.get("intro", "Click a keycap with the keycap puller to pull it off."))

    def clear_play(self):
        for np in self.kb.getChildren():
            np.removeNode()
        for np in self.tray_root.getChildren():
            np.removeNode()
        for f in self.flights:
            f[0].np.removeNode()
        self.flights, self.tweens = [], {}
        self.parts, self.part_set, self.board = [], set(), None
        self.held = self.lit = None
        self.turning = {}
        self.corners = []
        self.bowl, self.washing = None, 0.0

    def build_ui(self):
        """The screen round the keyboard: the job card, the tools on the left, the parts box and the colours on the
        right, and a line for messages."""
        self.clear_ui()
        self.layout_aspect = window.aspect_ratio
        L, R = -window.aspect_ratio / 2, window.aspect_ratio / 2
        test = self.phase == "test"
        # the job card, top left
        self.card((L + 0.31, 0.38), (0.56, 0.18))
        self.icon("game", (L + 0.072, 0.43), 0.06, col=(255, 255, 255))
        self.text(short_name(self.spec), (L + 0.112, 0.458), 1.45, COCOA, bold=True)
        self.steps, x = [], L + 0.112
        for i, name in enumerate(("Take apart", "Build", "Test")):
            if i:
                self.text(">", (x, 0.413), 0.8, PAPER_DARK)
                x += 0.03
            self.steps.append(self.text(name, (x, 0.413), 0.95, MUTED))
            x += self.steps[-1].width + 0.03
        self.card((L + 0.27, 0.355), (0.4, 0.018), PAPER_DARK, corner=0.009, z=0.15, shadow=False, collider=False)
        self.bar = self.add(Entity(parent=camera.ui, model="quad", origin=(-0.5, 0), position=(L + 0.07, 0.355, 0.1),
                                   scale=(0.001, 0.018), color=rgb(HONEY)))
        self.bar_text = self.text("", (L + 0.575, 0.366), 0.85, MUTED, origin=(0.5, 0.5))
        self.clean_text = self.text("", (L + 0.07, 0.334), 0.85, MUTED)
        self.corner_buttons()
        # the tools, down the left
        rail = L + 0.072
        n = len(self.tools)
        self.card((rail, 0.244 - n * 0.044), (0.1, n * 0.088 + 0.032), group="tools")
        for i, (tool, name) in enumerate(self.tools):
            y = 0.2 - i * 0.088
            b = self.icon_button(tool, (rail, y), 0.076, lambda t=tool: self.pick_tool(t), name, group="tools")
            self.text(str(i + 1), (rail + 0.03, y - 0.022), 0.75, MUTED, group="tools")
            self.tool_buttons.append((tool, b))
        # the parts box, top right
        bx = R - 0.21
        chips = (["keycaps", "switches"] if self.kind == "keyboard" else []) + self.big
        rows = (len(chips) + 1) // 2
        top = 0.405
        height = 0.07 + rows * 0.034
        self.card((bx, top - height / 2), (0.38, height), group="box")
        self.text("Parts box", (bx - 0.172, top - 0.014), 1.1, COCOA, bold=True, group="box")
        self.box_count = self.text("", (bx + 0.172, top - 0.018), 0.85, MUTED, origin=(0.5, 0.5), group="box")
        for k, item in enumerate(chips):
            x, y = bx - 0.088 + (k % 2) * 0.178, top - 0.064 - (k // 2) * 0.034
            b = self.button(" ", (x, y), (0.17, 0.028), lambda it=item: self.pick_up(it), PAPER, MUTED,
                            text_size=0.62, group="box", corner=0.4)
            b.item = item
            self.chips.append(b)
        # colours and switches, under it
        py = top - height - 0.095
        self.card((bx, py), (0.38, 0.15), group="paint")
        self.text("Colour", (bx - 0.172, py + 0.065), 1.05, COCOA, bold=True, group="paint")
        self.paint_name = self.text("", (bx + 0.172, py + 0.061), 0.85, MUTED, origin=(0.5, 0.5), group="paint")
        self.paint_ring = self.add(Entity(parent=camera.ui, model=Quad(radius=0.5), scale=0.05, color=rgb(HONEY),
                                          z=0.1), "paint")
        for k, (name, paint) in enumerate(PAINTS):
            x, y = bx - 0.156 + (k % 7) * 0.052, py + 0.013 - (k // 7) * 0.05
            swatch = paint or self.spec["cap"]
            b = self.button("", (x, y), (0.04, 0.04), lambda k=k: self.pick_paint(k), swatch, legend_for(swatch),
                            tip=name, group="paint", corner=0.5,
                            sound="paint")
            if paint is None:
                b.glyph = Entity(parent=b, model="quad", texture=self.art["star"], scale=0.55, z=-0.01,
                                 color=rgb(legend_for(swatch)))
            self.swatches.append(b)
        sy = py - 0.14
        self.card((bx, sy), (0.38, 0.105), group="switches")
        self.text("Switches", (bx - 0.172, sy + 0.042), 1.05, COCOA, bold=True, group="switches")
        self.switch_name = self.text("", (bx + 0.172, sy + 0.038), 0.85, MUTED, origin=(0.5, 0.5), group="switches")
        self.switch_ring = self.add(Entity(parent=camera.ui, model=Quad(radius=0.5), scale=0.05, color=rgb(HONEY),
                                           z=0.1), "switches")
        for k, (_, kind, _, stem) in enumerate(SWITCH_KINDS):
            b = self.button("", (bx - 0.156 + k * 0.06, sy - 0.012), (0.04, 0.04), lambda k=k: self.pick_switch(k),
                            stem, CREAM, tip=kind, group="switches", corner=0.5, sound="paint")
            self.switch_swatches.append(b)
        # testing it, at the end
        self.check_rows = []
        if self.kind == "mouse":  # a row for each thing to try, with a dot that lights up once it works
            checks = self.mouse_checks()
            height = 0.17 + len(checks) * 0.034
            self.card((R - 0.21, 0.39 - height / 2), (0.38, height), group="test")
            self.text("Test it", (R - 0.382, 0.37), 1.1, COCOA, bold=True, group="test")
            self.text("Use your own mouse:", (R - 0.382, 0.335), 0.82, MUTED, group="test")
            for k, (check, label) in enumerate(checks):
                y = 0.29 - k * 0.034
                dot = self.icon("dot", (R - 0.37, y), 0.024, PAPER_DARK, group="test")
                text = self.text(label, (R - 0.35, y), 0.9, MUTED, origin=(-0.5, 0), group="test")
                self.check_rows.append((check, dot, text))
            self.test_count = self.knob_text = None
            self.button("Finish", (R - 0.21, 0.39 - height + 0.045), (0.2, 0.055), self.finish_test, HONEY, CREAM,
                        text_size=1.1, group="test", z=-0.05)
        else:
            self.card((R - 0.21, 0.24), (0.38, 0.3), group="test")
            self.text("Test every key", (R - 0.382, 0.37), 1.1, COCOA, bold=True, group="test")
            self.text("Type on your own keyboard, or click the keys. Each one lights up and clicks, the way its "
                      "switch feels.", (R - 0.382, 0.335), 0.82, MUTED, group="test", wordwrap=34)
            self.test_count = self.text("", (R - 0.382, 0.235), 0.95, HONEY_DARK, group="test")
            self.knob_text = self.text("", (R - 0.382, 0.205), 0.85, MUTED, group="test")
            self.button("Finish", (R - 0.21, 0.135), (0.2, 0.055), self.finish_test, HONEY, CREAM, text_size=1.1,
                        group="test", z=-0.05)
        # the message line, the tooltip, and what's in your hand
        self.toast = self.add(Entity(parent=camera.ui, model=Quad(radius=0.5, aspect=12), scale=(0.6, 0.05),
                                     position=(0, -0.44, 0.05), color=rgb(CREAM)))
        self.toast_text = self.text("", (0, -0.44), 1.0, COCOA, origin=(0, 0), z=-0.02)
        self.toast_width = 0.0
        # the tooltip: a name on a little cocoa pill, sized to it whenever it changes
        self.tip_back = self.add(Entity(parent=camera.ui, model=Quad(radius=0.5, aspect=3), scale=(0.1, 0.034),
                                        color=rgb(COCOA), z=-0.39))
        self.tooltip = self.text("", (0, 0), 0.85, CREAM, origin=(-0.5, 0), z=-0.4)
        self.tip_width = 0.0
        self.badge = self.add(Entity(parent=camera.ui, model=Quad(radius=0.5), scale=0.04, color=rgb(HONEY), z=-0.3))
        self.badge_icon = self.add(Entity(parent=camera.ui, model="quad", texture=self.art["hand"], scale=0.027,
                                          color=rgb(CREAM), z=-0.31))
        # help, and leaving
        self.card((0, 0.02), (0.78, 0.62), CREAM, group="help")
        self.text("How to play", (-0.36, 0.315), 1.6, COCOA, bold=True, group="help")
        if self.kind == "mouse":
            lines = ["Take it all apart, into the box. Then build it back up in",
                     "any colour, and test it with your own mouse.",
                     "",
                     "One click, one part. Pick the tool for it first:",
                     "1  Hand: lift parts off; click a part in the box to hold it,",
                     "    then click where it goes. The feet peel off underneath.",
                     "2  Screwdriver: click a screw. They hide under the feet.",
                     "3  Brush: hold it down and drag it over the dust.",
                     "",
                     "Right-click: put back what you hold.   Drag: turn it round.",
                     "Scroll: zoom.   F: flip over.   R: level.   M: music.",
                     "F11: full screen or window.   Esc: back."]
        else:
            lines = ["Take it all apart, into the box and the trays. Then build it",
                     "back up in any colours, and test every key.",
                     "",
                     "One click, one part. Pick the tool for it first:",
                     "1  Hand: lift parts off; click a part in the box to hold it,",
                     "    then click where it goes.",
                     "2  Screwdriver: click a screw. Some hide under the feet.",
                     "3  Keycap puller: click a keycap.",
                     "4  Switch puller: click a switch, once its keycap is off.",
                     "5  Brush: hold it down and drag it over the crumbs.",
                     "6  Lube: click a stabiliser, so its long key won't rattle.",
                     "Wash bowl: click it to wash the grimy keycaps in the tray.",
                     "",
                     "Right-click: put back what you hold.   Drag: turn it round.",
                     "Scroll: zoom.   F: flip over.   R: level.   M: music.",
                     "F11: full screen or window.   Esc: back."]
        self.text("\n".join(lines), (-0.36, 0.255), 0.95, COCOA, group="help")
        self.button("Got it", (0, -0.24), (0.16, 0.055), self.toggle_help, HONEY, CREAM, group="help")
        self.card((0, 0.02), (0.56, 0.2), CREAM, group="leave")
        self.text(f"Leave this {self.kind}?", (0, 0.08), 1.4, COCOA, origin=(0, 0), bold=True, group="leave")
        self.text("It goes back on the shelf as it was.", (0, 0.035), 0.95, MUTED, origin=(0, 0), group="leave")
        self.button("Stay", (-0.1, -0.035), (0.16, 0.055), self.ask_leave, PAPER, COCOA, group="leave")
        self.button("Leave", (0.1, -0.035), (0.16, 0.055), self.show_menu, HONEY, CREAM, group="leave")
        self.show_group("help", False)
        self.show_group("leave", False)
        self.show_group("test", test)
        for name in ("tools", "box", "paint", "switches"):
            self.show_group(name, not test)
        self.refresh_ui(None)

    def toggle_help(self):
        self.help_open = not self.help_open
        self.show_group("help", self.help_open)

    def ask_leave(self):
        self.confirming = not self.confirming
        self.show_group("leave", self.confirming)

    # -- the end --

    def show_result(self):
        self.state = "result"
        self.held = None
        self.unhighlight()
        spotless = all(not d.left for d in self.board.dirt) and not any(c.grimy for c in self.caps)
        smooth = all(s.lubed for s in self.stabs)
        if not self.offscreen:
            key = self.spec["key"]
            self.save["fixed"][key] = self.save["fixed"].get(key, 0) + 1
            write_save(self.save)
        if self.kind == "mouse":
            self.stars = [(True, "Built"), (spotless, "Spotless"), (self.all_tested(), "All tested")]
        else:
            self.stars = [(True, "Built"), (spotless, "Spotless"), (smooth, "Smooth"), (self.all_tested(), "All tested")]
        self.aim("result", 1.0)
        self.result_ui()

    def result_ui(self):
        self.clear_ui()
        self.layout_aspect = window.aspect_ratio
        R = window.aspect_ratio / 2
        cx = R - 0.36
        self.card((cx, 0.0), (0.6, 0.78))
        self.text("Good as new!", (cx, 0.32), 2.6, COCOA, origin=(0, 0), bold=True)
        self.text(f"{short_name(self.spec)}, taken apart and built your way", (cx, 0.255), 0.95, MUTED, origin=(0, 0))
        for i, (got, what) in enumerate(self.stars):
            x = cx + (i - (len(self.stars) - 1) / 2) * (0.14 if len(self.stars) > 3 else 0.18)
            self.icon("star", (x, 0.165), 0.08, HONEY if got else PAPER_DARK)
            self.text(what, (x, 0.105), 0.85, COCOA if got else MUTED, origin=(0, 0))
        crumbs = sum(len(d.points) - len(d.left) for d in self.board.dirt)
        lines = [f"{crumbs} crumbs and specks of dust brushed out"]
        if self.washed:
            lines.append(f"{self.washed} keycaps washed")
        if self.stabs:
            lines.append(f"{sum(s.lubed for s in self.stabs)} of {len(self.stabs)} stabilisers lubed")
        if self.kind == "mouse":
            checks = self.mouse_checks()
            lines.append(f"{sum(c in self.checks for c, _ in checks)} of {len(checks)} things tested")
        else:
            lines.append(f"{len(self.tested)} of {len(self.caps)} keys tested" +
                         ("" if not self.knob else ", and the knob" if self.knob_turned else " (not the knob)"))
        if self.found:
            lines.append(f"Found inside: a {self.found}")
        found = len(set(self.save.get("found", [])))
        lines.append(f"Things found so far: {found} of {len(TRINKETS)}")
        self.text("\n".join(lines), (cx - 0.25, 0.04), 1.0, COCOA)
        tip = ("Real repairers photograph every step, and keep each part's screws together. Keycaps in different "
               "rows are shaped differently, so they go back in the rows they came from." if self.kind == "keyboard"
               else "A mouse's screws nearly always hide under its feet, and the feet don't stick as well once "
                    "they're peeled: repairers keep spare ones.")
        self.text(tip, (cx - 0.25, -0.17), 0.82, MUTED, wordwrap=50)
        self.button("Fix another", (cx - 0.13, -0.32), (0.22, 0.065), self.show_menu, HONEY, CREAM, text_size=1.1)
        self.button("Again", (cx + 0.13, -0.32), (0.22, 0.065), lambda: self.start(self.spec), PAPER, COCOA,
                    text_size=1.1)
        self.corner_buttons()

    # ---- what you do ----

    def say(self, text, col=COCOA):
        self.message_time = 4.0
        if not hasattr(self, "toast_text"):
            return
        self.set_text(self.toast_text, text)
        self.toast_text.color = rgb(col)
        width = min(window.aspect_ratio - 0.2, 0.07 + self.toast_text.width)
        if abs(width - self.toast_width) > 0.001:
            self.toast_width = width
            self.toast.model = Quad(radius=0.5, aspect=width / 0.05)
            self.toast.scale = (width, 0.05)
        self.toast.enabled = self.toast_text.enabled = True

    def nope(self):
        self.sounds.play("nope", 0.5)

    def pick_tool(self, tool):
        self.tool = tool
        if not isinstance(self.held, Part3D):
            self.held = None

    def pick_paint(self, k):
        self.paint = k
        if self.phase == "build" and self.held is None:
            self.held = "keycaps"
            self.say("Click a switch to put a keycap on it in this colour, or click a keycap to repaint it.")

    def pick_switch(self, k):
        self.switch_kind = k
        self.sounds.play(f"press_{SWITCH_KINDS[k][0]}", 0.8)
        if self.phase == "build" and self.held is None:
            self.held = "switches"
            self.say(f"{SWITCH_KINDS[k][1]} switches: click a hole in the plate to press one in.")

    def pick_up(self, item):
        """A click on the parts box: pick something up to put on."""
        if self.phase == "apart":
            self.say("Take everything apart first, into the box and the trays. Then build it back up.")
            self.nope()
            return
        if item in ("keycaps", "switches"):
            self.held = item
            self.say("Click a switch to put a keycap on it, in the colour you've picked."
                     if item == "keycaps" else "Click a hole in the plate to press a switch in.")
        elif item.placed:
            self.say(f"The {item.name} is on the keyboard.")
        else:
            self.held = item
            self.say(f"Click the keyboard where the {item.name} goes. Right-click puts it back.")

    def above(self, part):
        """The parts still on that sit on this one."""
        return [q for q in self.parts if q.placed and part in q.below]

    def blocker_message(self, part, above):
        first = next((q for q in above if not q.screw), None)
        if first is None:
            return "It's still screwed on from underneath: flip it over (F) and undo the screws (2)."
        if first.key == "battery_lead":
            return "Unplug the battery lead first: never work on a circuit board with its battery connected."
        if first.key == "mouse_battery":
            return "Take the battery out first, from underneath: never open up a mouse with its battery in."
        if first.key == "receiver":
            return "Its USB receiver is still tucked in underneath: flip it over (F) and take it out."
        if isinstance(first, KeyItem):
            n = sum(isinstance(q, KeyItem) and q.kind == first.kind for q in above)
            tool = "keycap puller (3)" if first.kind == "keycap" else "switch puller (4)"
            return f"{n} {first.kind}{'s are' if n > 1 else ' is'} still in the way: use the {tool}."
        return f"The {first.name} is in the way: take it off first."

    def take_off(self, part):
        """The hand on a big part."""
        above = self.above(part)
        if above:
            self.say(self.blocker_message(part, above))
            self.nope()
            self.jiggle(part.root)
            return
        self.lift_off(part)

    def lift_off(self, part):
        part.placed = False
        part.token += 1
        token = part.token
        self.unhighlight(part)
        if part.screw:  # into the dish
            i = self.screws.index(part)
            part.root.stash()
            flyer = part.mesh.piece(0, self.flyers, (0, 0, 0))
            self.fly(flyer, (part.root, (0, 0, 0)), (self.dish, self.dish_spots[i], True), 0.55, 1.8,
                     lambda: self.landed_screw(part, token))
        else:
            self.sounds.play(f"lift_{material(part)}", 0.65)
            self.tween(part.root, part.origin + part.lift * self.lift_distance(part), 0.35,
                       then=lambda: part.token == token and not part.placed and part.root.stash())
        self.after_change()

    def landed_screw(self, screw, token):
        if screw.token == token and not screw.placed:
            self.dish_mesh.move(self.screws.index(screw), (0, 0, 0))

    def put_on(self, part):
        part.placed, part.style = True, self.paint
        part.token += 1
        if part.paintable:
            part.repaint(part_colours(self.spec, PAINTS[self.paint][1]))
        part.root.unstash()
        part.root.setPos(part.origin + part.lift * self.lift_distance(part))
        self.tween(part.root, part.origin, 0.3, then=lambda: self.sounds.play(f"put_{material(part)}", 0.65))
        self.after_change()

    def fit(self, part, hit):
        """Put the part you're holding on, if everything it sits on is there and you clicked where it goes."""
        missing = [q for q in part.below if not q.placed]
        if missing:
            first = missing[0]
            if first.screw:
                self.say("Do up the screws first: it goes on over them.")
            elif isinstance(first, KeyItem):
                self.say(f"Put the {first.kind}s back first: the {part.name} sits on them.")
            else:
                self.say(f"Put the {first.name} on first: the {part.name} sits on it.")
            self.nope()
            return
        if part.below:
            on, _, p = hit
            if on is None:
                self.say("Click on the keyboard, where it goes.")
                return
            lo, hi = part.lo - Vec3(0.7, 1.3, 0.7), part.hi + Vec3(0.7, 1.3, 0.7)
            if not (lo.x <= p.x <= hi.x and lo.y <= p.y <= hi.y and lo.z <= p.z <= hi.z):
                self.say("That's not where it goes.")
                self.nope()
                return
        self.put_on(part)
        self.held = None

    # -- keycaps and switches --

    def slot_at(self, part, point):
        """Which key a click is on: the keycap or switch itself, or the spot on the plate where one goes."""
        if isinstance(part, KeyItem):
            return part.i
        if point is None or part is None:
            return None
        for i, (_, cx, cz, w, h) in enumerate(self.board.keys):
            if abs(point.x - cx) <= w / 2 and abs(point.z - cz) <= h / 2:
                return i
        return None

    def key_action(self, mode, i):
        """One click on one key: pull its keycap or its switch, or put one on (or repaint it, or swap the switch's
        kind)."""
        cap, sw = self.caps[i], self.switches[i]
        if mode == "pull keycaps":
            if cap.placed:
                self.pull(cap)
            else:
                self.say("That keycap's already off. Switches come out with the switch puller (4).")
        elif mode == "pull switches":
            if sw.placed:
                if cap.placed:
                    self.say("Pull the keycap off first, with the keycap puller (3).")
                    self.nope()
                else:
                    self.pull(sw)
        elif mode == "place keycaps":
            body, ink = cap_colours(self.spec, cap.label, PAINTS[self.paint][1])
            if not cap.placed:
                missing = [q for q in cap.below if not q.placed]
                if missing:
                    self.say(f"Put the {missing[0].name} in first: the keycap sits on it.")
                    self.nope()
                else:
                    self.put_key(cap)
            elif (body, ink) != (cap.body, cap.legend):
                cap.body, cap.legend = body, ink
                cap.set.paint(i, *look(cap))
                self.sounds.play("paint", 0.35)
        elif mode == "place switches":
            if not sw.placed:
                if not sw.below[0].placed:
                    self.say("Put the steel plate on first: the switches clip into it.")
                    self.nope()
                else:
                    self.put_key(sw)
            elif sw.style != self.switch_kind and not cap.placed:
                sw.style = self.switch_kind
                sw.set.paint(i, SWITCH_KINDS[sw.style][3])
                self.sounds.play(f"press_{SWITCH_KINDS[sw.style][0]}", 0.5)

    def pull(self, item):
        """A keycap or a switch, off the keyboard and into its tray."""
        item.placed = False
        item.token += 1
        token = item.token
        self.unhighlight(item)
        ks = item.set
        ks.on_board(item.i, None)
        item.hit.stash()
        if item.kind == "keycap":
            ks.paint(item.i, *look(item), tray=True)
        else:
            ks.paint(item.i, SWITCH_KINDS[item.style][3], tray=True)
        flyer = ks.flyer(item.i, self.flyers, item.center)
        self.sounds.play("pop" if item.kind == "keycap" else "snick", 0.6)
        self.fly(flyer, (self.kb, item.center), (ks.tray, item.center), 0.5, 1.6, lambda: self.landed(item, token))
        self.after_change()

    def landed(self, item, token):
        if item.token == token and not item.placed:
            item.set.in_tray(item.i, True)
            self.sounds.play("drop_cap" if item.kind == "keycap" else "drop_switch", 0.25)

    def put_key(self, item):
        """A keycap (in the colour picked) or a switch (of the kind picked), from its tray onto the keyboard."""
        item.placed = True
        item.token += 1
        token = item.token
        ks = item.set
        if item.kind == "keycap":
            item.body, item.legend = cap_colours(self.spec, item.label, PAINTS[self.paint][1])
            ks.paint(item.i, *look(item))
        else:
            item.style = self.switch_kind
            ks.paint(item.i, SWITCH_KINDS[item.style][3])
        ks.in_tray(item.i, False)
        ks.on_board(item.i, None)
        item.hit.unstash()
        flyer = ks.flyer(item.i, self.flyers, item.center)
        self.fly(flyer, (ks.tray, item.center), (self.kb, item.center), 0.45, 1.6,
                 lambda: self.key_landed(item, token))
        self.after_change()

    def key_landed(self, item, token):
        if item.token != token or not item.placed:
            return
        item.set.on_board(item.i, (0, 0, 0))
        self.sounds.play("clack" if item.kind == "keycap" else "switch_in", 0.6)

    # -- screws --

    def screw_under(self, part, tag):
        """The screw under the mouse: one that's in, or the one whose empty hole it's over."""
        if part is not None and part.screw:
            return part
        if tag and tag[0] == "hole":
            return self.screws[tag[1]]
        return None

    def start_turn(self, screw):
        """A click with the screwdriver: the screw turns itself out (and flies to the dish), or comes out of the
        dish and turns itself in."""
        if screw in self.turning:
            return  # already turning
        if screw.placed:
            cover = self.above(screw)
            if cover:
                self.say(f"The {cover[0].name} covers it: peel that off first, with the hand (1).")
                self.nope()
                return
        elif self.phase == "apart":
            self.say("Take everything apart first, then build it back up.")
            return
        elif not all(q.placed for q in screw.below):
            self.say(f"Put the {screw.below[0].name} on first: the screw goes into it.")
            self.nope()
            return
        else:  # it comes out of the dish, and turns into the hole
            screw.style = self.paint
            screw.root.unstash()
            screw.root.setPos(screw.origin + screw.lift * 0.35)
            self.dish_mesh.move(self.screws.index(screw), None)
        self.turning[screw] = 0.0
        self.sounds.play("screw_out" if screw.placed else "screw_in", 0.5)  # the whole turn, start to finish

    def update_turns(self):
        for screw, progress in list(self.turning.items()):
            undoing = screw.placed
            progress = min(1.0, progress + time.dt / TURN_TIME)
            screw.root.setH(screw.root.getH() + (-1 if undoing else 1) * 720 * time.dt)
            rise = smooth(progress if undoing else 1 - progress)
            screw.root.setPos(screw.origin + screw.lift * 0.35 * rise)
            if progress < 1:
                self.turning[screw] = progress
                continue
            del self.turning[screw]
            if undoing:
                self.lift_off(screw)
            else:
                screw.placed = True
                screw.token += 1
                screw.root.setPos(screw.origin)
                self.after_change()

    # -- the brush, and what it finds --

    def brush_at(self, point, sound=True):
        """The brush at a point: it sweeps away the specks round it."""
        if point is None:
            return
        if sound:
            self.sounds.play("brush", 0.4, vary=0.05)
        swept = 0
        for dirt in self.board.dirt:
            if not dirt.host.placed or not dirt.left:
                continue
            for i in list(dirt.left):
                p = dirt.points[i]
                if (p.x - point.x) ** 2 + (p.z - point.z) ** 2 < BRUSH_REACH ** 2 and abs(p.y - point.y) < 0.6:
                    self.sweep_speck(dirt, i)
                    swept += 1
            if swept and not dirt.left:
                self.sounds.play("sparkle", 0.6)
                self.say(f"The {dirt.host.name} is spotless!", HONEY_DARK)

    def brush_drag(self, point):
        """The brush held down and moved: it sweeps all along the way, with a swish for every stroke's worth."""
        if point is None:  # off the keyboard for now
            self.brush_from = None
            return
        if self.brush_from is not None:
            self.brush_travel += (point - self.brush_from).length()
        self.brush_from = point
        stroke = self.brush_travel >= BRUSH_STROKE and self.clock >= self.next_brush
        if stroke:
            self.brush_travel, self.next_brush = 0.0, self.clock + 0.16  # never a flurry, however fast you go
        self.brush_at(point, sound=stroke)

    def sweep_speck(self, dirt, i):
        dirt.left.discard(i)
        p = dirt.points[i]
        flyer = dirt.mesh.piece(i, self.flyers, tuple(p))
        dirt.mesh.move(i, None)
        a = random.uniform(0, 2 * math.pi)
        away = (p.x + math.cos(a) * 0.9, p.y + 0.3, p.z + math.sin(a) * 0.9)
        self.fly(flyer, (dirt.host.root, tuple(p)), (dirt.host.root, away), 0.35, 0.5, end_scale=0.05)

    def collect(self, trinket):
        trinket.found = True
        trinket.holder.stash()
        flyer = trinket.mesh.piece(0, self.flyers, (0, 0, 0))
        self.fly(flyer, (trinket.holder, (0, 0, 0)), (camera, (0, -0.6, 9)), 0.9, 1.0, end_scale=2.5)
        self.sounds.play("sparkle", 0.8)
        self.found = trinket.name
        if not self.offscreen and trinket.name not in self.save["found"]:
            self.save["found"].append(trinket.name)
            write_save(self.save)
        n = len(set(self.save["found"]))
        self.say(f"You found a {trinket.name} in there! ({n} of {len(TRINKETS)} things found so far)", HONEY_DARK)

    # -- the wash bowl, the lube, the knob --

    def wash(self):
        """A click on the wash bowl: the grimy keycaps in the tray go in for a soak."""
        if self.washing > 0:
            return
        dirty = [c for c in self.caps if not c.placed and c.grimy]
        if not dirty:
            if any(c.grimy for c in self.caps):
                self.say("Pull the grimy keycaps off first: they go in the bowl from the tray.")
            elif any(not c.placed for c in self.caps):
                self.say("The keycaps in the tray are clean already.")
            else:
                self.say("The bowl is for keycaps: pull some off, then give them a wash.")
            return
        self.washing = WASH_TIME
        self.sounds.play("wash", 0.6)
        self.jiggle(self.board.caps.tray)
        self.say(f"Into the warm, soapy water with {len(dirty)} keycap{'s' if len(dirty) > 1 else ''}...")

    def finish_wash(self):
        ks = self.board.caps
        n = 0
        for c in self.caps:
            if not c.placed and c.grimy:
                c.grimy = False
                ks.paint(c.i, c.body, c.legend, tray=True)
                n += 1
        self.washed += n
        if n:
            self.sounds.play("sparkle", 0.5)
            left = sum(c.grimy for c in self.caps)
            self.say(f"Squeaky clean! {n} keycap{'s' if n > 1 else ''} washed." +
                     (f" {left} more still want a wash." if left else ""), HONEY_DARK)

    def update_wash(self):
        """Bubbles rising off the bowl while the keycaps soak."""
        shown = self.washing > 0 and self.bowl is not None
        if shown:
            self.washing -= time.dt
            top = application.base.render.getRelativePoint(self.bowl.root, Point3(0, 0.8, 0))
            for k, np in enumerate(self.bubbles):
                phase = (self.clock * 0.9 + k / len(self.bubbles)) % 1.0
                a = k * 2.4
                np.setPos(top + LVector3f(math.cos(a) * 0.8 * (1 - phase), 0.2 + phase * 2.2, math.sin(a) * 0.6))
                np.setScale(0.5 + 0.5 * math.sin(math.pi * phase))
                np.setColorScale(0.86, 0.95, 1.0, math.sin(math.pi * phase))
            if self.washing <= 0:
                self.finish_wash()
        if self.bubbles[0].isHidden() == shown:
            for np in self.bubbles:
                if shown:
                    np.show()
                    np.hide(SHADOW_MASK)  # (no shadows from a bubble)
                else:
                    np.hide()

    def lube(self, stab):
        """A dab of lube on a stabiliser's wire, where it meets each housing: no more rattle."""
        if stab.lubed:
            self.say(f"The {stab.name} is lubed already.")
            return
        stab.lubed = True
        stab.lube.unstash()
        self.sounds.play("lube", 0.6)
        n = sum(s.lubed for s in self.stabs)
        self.say(f"Nice and smooth: {n} of {len(self.stabs)} stabilisers lubed.", HONEY_DARK if n == len(self.stabs)
                 else COCOA)

    def turn_knob(self, way):
        """The knob, in the test: a notch of volume up (or down), with its soft click."""
        self.knob.root.setH(self.knob.root.getH() - way * 18)
        self.sounds.play("knob", 0.6)
        if not self.knob_turned:
            self.knob_turned = True
            self.say("The knob turns, notch by notch: volume up, volume down. It works!", HONEY_DARK)
            self.check_all_tested()

    def all_tested(self):
        if self.kind == "mouse":
            return all(c in self.checks for c, _ in self.mouse_checks())
        return len(self.tested) >= len(self.caps) and (self.knob is None or self.knob_turned)

    def check_all_tested(self):
        if self.all_tested():
            self.sounds.play("fanfare", 0.6)
            self.say("Everything works! Press Finish when you're done" + (" typing." if self.kind == "keyboard"
                                                                         else "."), HONEY_DARK)

    # -- testing a mouse, with your own --

    def mouse_checks(self):
        checks = [("left", "Left click"), ("right", "Right click"), ("scroll", "Scroll the wheel"),
                  ("middle", "Click the wheel"), ("move", "Move it about")]
        if self.spec.get("side"):
            checks.append(("side", "Side buttons"))
        return checks

    def mouse_try(self, check):
        """Something tried in a mouse's test: it works, and the first time it's ticked off."""
        if check in self.checks:
            return
        self.checks[check] = True
        if self.all_tested():
            self.check_all_tested()

    def mouse_button(self, name, down):
        """Its left or right button, or the wheel (clicked down): it goes down, and clicks."""
        if self.mouse_down.get(name) == down:
            return
        self.mouse_down[name] = down
        m = self.board.mouse
        if name == "middle":
            wheel = m["wheel"]
            wheel.root.setPos(wheel.origin + Vec3(0, -0.05 if down else 0, 0))
        elif name in m:
            m[name].setPos(0, -0.045 if down else 0, 0)
        if down:
            self.sounds.play("mouse_click", 0.6, pitch=0.85 if name == "middle" else 1.0)
            self.mouse_try(name)
        else:
            self.sounds.play("mouse_click", 0.25, pitch=1.15)  # (and a softer one as it comes back up)

    def mouse_input(self, key):
        """The real mouse's buttons and wheel, in a mouse's test. True if that's all the key was for."""
        if key in ("right mouse down", "right mouse up"):
            self.mouse_button("right", key.endswith("down"))
            return False  # (a right drag still turns it round)
        if key in ("middle mouse down", "middle mouse up"):
            self.mouse_button("middle", key.endswith("down"))
            return True
        if key in ("scroll up", "scroll down"):  # the wheel turns, notch by notch
            wheel = self.board.mouse["wheel"]
            wheel.root.setP(wheel.root.getP() + (-20 if key == "scroll up" else 20))
            self.sounds.play("knob", 0.5)
            self.mouse_try("scroll")
            return True
        if key in ("mouse4", "mouse5"):  # (the side buttons, on a mouse that has them)
            if self.spec.get("side"):
                self.sounds.play("mouse_click", 0.5, pitch=1.2)
                self.mouse_try("side")
            return True
        return False

    def update_mouse_test(self):
        """Moving your own mouse moves this one's sensor: its light shines on the mat under it; and a gaming
        mouse's logo glows round the colours."""
        testing = self.state == "play" and self.kind == "mouse" and self.phase == "test"
        if not testing:
            if not self.sensor_light.isHidden():
                self.sensor_light.hide()
            return
        speed = 0.0 if self.offscreen else Vec3(mouse.velocity).length()
        self.moved += speed
        if self.moved > 0.6:
            self.mouse_try("move")
        glow = getattr(self, "glow", 0.0)
        self.glow = glow + (min(1.0, 0.3 + speed * 60) - glow) * min(1.0, time.dt * 10)
        x, z = self.board.mouse["sensor"]
        p = application.base.render.getRelativePoint(self.kb, Point3(x, 0, z))
        self.sensor_light.setPos(p.x, DESK_Y + 0.08, p.z)
        self.sensor_light.setScale(3.2 + 1.2 * self.glow)
        self.sensor_light.setColorScale(1.0, 0.25, 0.22, 0.25 + 0.6 * self.glow)
        if self.sensor_light.isHidden():
            self.sensor_light.show()
            self.sensor_light.hide(SHADOW_MASK)
        logo = self.board.mouse.get("logo")
        if logo is not None:
            logo.paint(0, "logo", hue(self.clock * 0.2, 0.6))

    # -- how it's going --

    def after_change(self):
        if self.phase == "apart":
            if not any(p.placed for p in self.parts):
                self.phase = "build"
                self.held = None
                self.sounds.play("chime", 0.7)
                self.say("It's all apart! Now build it back up, in any colours you like.", HONEY_DARK)
                self.show_group("paint", True)
                return
            self.hint()
        elif self.phase == "build" and all(p.placed for p in self.parts) and not self.turning:
            self.start_test()

    def hint(self):
        """A word on what to do next, as each stage gets done."""
        if self.kind == "mouse":
            self.mouse_hint()
            return
        if "caps" not in self.said and not any(c.placed for c in self.caps):
            self.said.add("caps")
            dirty = any(d.left and d.host.key == "plate" for d in self.board.dirt)
            grimy = sum(c.grimy for c in self.caps)
            dry = any(not s.lubed for s in self.stabs)
            self.say("All the keycaps are off! " + (
                f"{grimy} of them are grimy: click the wash bowl to give them a soak." if grimy else
                "Lube the stabilisers (6) while you can reach them." if dry else
                "Brush the crumbs off the plate (5), then pull the switches (4)." if dirty else
                "Now pull the switches (4)."))
        elif "switches" not in self.said and not any(s.placed for s in self.switches):
            self.said.add("switches")
            if any(p.key.startswith("stab") and p.placed for p in self.parts):
                self.say("Switches out! Lube the stabilisers (6), then lift them out with the hand (1)."
                         if any(not s.lubed for s in self.stabs) else
                         "Switches out! Lift the stabilisers out with the hand (1).")
            elif self.knob is not None and self.knob.placed:
                self.say("Switches out! Lift the volume knob off with the hand (1).")
            else:
                self.say("Switches out! The top frame is screwed on from underneath: flip it over (F).")

    def mouse_hint(self):
        by_key = {p.key: p for p in self.parts}
        feet = [p for p in self.parts if p.key.startswith("foot")]
        screws = [p for p in self.parts if p.key.startswith("screw")]
        battery = by_key.get("mouse_battery")
        if "feet" not in self.said and not any(f.placed for f in feet):
            self.said.add("feet")
            self.say("Feet off! Undo the screws that were under them, with the screwdriver (2).")
        elif "screws" not in self.said and not any(q.placed for q in screws):
            self.said.add("screws")
            self.say("Screws out! Now pop the battery cover off, and take the battery out." if battery and battery.placed
                     else "Screws out! Flip it back over (F), and lift the top shell off with the hand (1).")
        elif battery and "battery" not in self.said and not battery.placed:
            self.said.add("battery")
            self.say("Battery out: now it's safe to open. Flip it back over (F) and lift the top shell off.")
        elif "shell" not in self.said and not by_key["top_shell"].placed:
            self.said.add("shell")
            self.say("The top shell's off! Lift the scroll wheel out, and undo the board's little screw (2).")

    # -- testing it --

    def start_test(self):
        self.phase = "test"
        self.held = None
        self.tested, self.keys_down, self.flash = set(), set(), {}
        self.wave = 0.0
        lookup = {}
        for i, (label, cx, cz, w, h) in enumerate(self.board.keys):
            if label in SIDED:
                names = [f"{'left' if cx < self.board.space_x else 'right'} {SIDED[label]}"]
            else:
                names = INPUT_NAMES.get(label, [label.lower()])
            for name in names:
                lookup.setdefault(name, []).append(i)
        self.key_lookup = lookup
        self.checks, self.moved, self.mouse_down = {}, 0.0, {}
        self.sounds.play("fanfare", 0.7)
        self.build_ui()
        self.say("It's back together! Type on it: every key you press lights up." if self.kind == "keyboard" else
                 "It's back together! Click, scroll and move your own mouse: this one does it too.", HONEY_DARK)

    def press_key(self, i):
        if i in self.keys_down or not self.caps[i].placed:
            return
        self.keys_down.add(i)
        self.board.caps.on_board(i, (0, -PRESS, 0))
        self.sounds.play(f"press_{SWITCH_KINDS[self.switches[i].style][0]}", 0.8, vary=0.06)
        self.flash[i] = 0.6
        new = i not in self.tested
        self.tested.add(i)
        done = new and len(self.tested) == len(self.caps)
        stab = self.board.stab_of.get(i)
        if stab is not None and not stab.lubed:  # a dry stabiliser: its wire rattles
            self.sounds.play("rattle", 0.5)
            if "rattle" not in self.said and not done:
                self.said.add("rattle")
                self.say(f"Hear that rattle? The {nice_label(self.caps[i].label)} key's stabiliser wants lube "
                         "(6). Next time!")
        if done:
            if self.knob is not None and not self.knob_turned:
                self.say("Every key works! Now turn the knob: scroll on it, or click it.", HONEY_DARK)
            else:
                self.check_all_tested()

    def release_key(self, i):
        if i in self.keys_down:
            self.keys_down.discard(i)
            self.board.caps.on_board(i, (0, 0, 0))

    def test_key(self, key):
        up = key.endswith(" up")
        indexes = self.key_lookup.get(key[:-3] if up else key)
        if not indexes:
            return False
        for i in indexes:
            self.release_key(i) if up else self.press_key(i)
        return True

    def update_test(self):
        ks = self.board.caps
        for i, left in list(self.flash.items()):
            left -= time.dt
            cap = self.caps[i]
            if left <= 0:
                del self.flash[i]
                ks.paint(i, look(cap)[0], GLOW if i in self.tested else look(cap)[1])
            else:
                self.flash[i] = left
                lit = hue(self.board.keys[i][1] / 24 + self.clock * 0.2, 0.45)
                ks.paint(i, mix(look(cap)[0], lit, min(1.0, left / 0.6) * 0.75), GLOW)
        if self.wave >= 0:  # when it's first together: a rainbow ripples across the legends
            self.wave += time.dt
            for i, cap in enumerate(self.caps):
                if i in self.flash:
                    continue
                k = self.board.keys[i][1] / 6 - self.wave * 3
                ks.meshes[1].paint(i, "legend", hue(k / 4, 0.6) if self.wave < 2.4 else look(cap)[1])
            if self.wave >= 2.4:
                self.wave = -1.0

    def finish_test(self):
        self.show_result()

    # ---- input ----

    def input(self, key):
        if self.volume_input(key):
            return
        if key == "f11":
            self.toggle_fullscreen()
            return
        if key == "f3":
            self.show_fps = not self.show_fps
            if not self.show_fps and hasattr(self, "fps_text"):
                self.set_text(self.fps_text, "")
        if self.state == "menu":
            if key == "escape":
                application.quit()
            return
        if self.state == "result":
            if key == "escape":
                self.show_menu()
            return
        if self.state != "play":
            return
        if self.phase == "test" and not self.confirming and self.test_key(key):
            return
        if self.phase == "test" and self.kind == "mouse" and not self.confirming and self.mouse_input(key):
            return
        if key == "escape":
            if self.help_open:
                self.toggle_help()
            elif self.held is not None:
                self.held = None
            else:
                self.ask_leave()
            return
        if key == "m":
            self.toggle_music()
        elif key == "h":
            self.toggle_help()
        if self.phase != "test":
            if key in [str(k + 1) for k in range(len(self.tools))]:
                self.pick_tool(self.tools[int(key) - 1][0])
            elif key == "f":
                self.pitch.animate("rotation_x", self.pitch.rotation_x + 180, duration=0.5, curve=curve.in_out_sine)
                self.sounds.play("turn", 0.5)
            elif key == "r":
                self.pitch.animate("rotation_x", round(self.pitch.rotation_x / 360) * 360, duration=0.4)
                self.yaw.animate("rotation_y", round(self.yaw.rotation_y / 360) * 360, duration=0.4)
        if key in ("scroll up", "scroll down") and self.phase == "test" and self.knob is not None \
                and self.pick()[0] is self.knob:  # scrolling on the knob turns it
            self.turn_knob(1 if key == "scroll up" else -1)
        elif key == "scroll up":
            camera.fov = max(12, camera.fov - 2)
        elif key == "scroll down":
            camera.fov = min(70, camera.fov + 2)
        elif key == "right mouse down":
            self.dragging, self.right_from = True, self.mouse_at()
        elif key == "right mouse up":
            self.dragging = False
            if self.held is not None and (self.mouse_at() - self.right_from).length() < 0.01:
                self.held = None  # a right click puts back what you're holding
        elif key == "left mouse down":
            self.click()
        elif key == "left mouse up":
            self.dragging = self.brushing = False
            if self.phase == "test" and self.kind == "mouse":
                self.mouse_button("left", False)
            if self.mouse_key is not None:
                self.release_key(self.mouse_key)
                self.mouse_key = None

    def mouse_at(self):
        return Vec3(0, 0, 0) if self.offscreen else Vec3(mouse.position)

    def toggle_fullscreen(self):
        if self.offscreen:
            return
        full = not window.fullscreen
        window.borderless = full
        window.fullscreen = full

    def click(self):
        if self.over_panel() or self.help_open or self.confirming:
            return  # its buttons handle themselves
        part, tag, point = self.pick()
        if self.phase == "test" and self.kind == "mouse":  # your own mouse's left button: this one's goes down too
            if tag and tag[0] == "side":
                self.sounds.play("mouse_click", 0.5, pitch=1.2)
                self.mouse_try("side")
            else:
                self.mouse_button("left", True)
                self.dragging = True  # (and a drag still turns it round)
            return
        if self.phase == "test":
            i = self.slot_at(part, point) if isinstance(part, KeyItem) else None
            if i is not None and self.caps[i].placed:
                self.press_key(i)
                self.mouse_key = i
            elif part is not None and part is self.knob:
                self.turn_knob(1)
            else:
                self.dragging = True
            return
        if isinstance(part, Trinket):
            self.collect(part)
            return
        if isinstance(part, Bowl):
            self.wash()
            return
        if self.held in ("keycaps", "switches"):
            if part is None:
                self.dragging = True
                return
            i = self.slot_at(part, point)
            if i is None:
                self.say("Click a switch to put a keycap on it." if self.held == "keycaps" else
                         "Click a hole in the plate, where a switch goes.")
            else:
                self.key_action("place " + self.held, i)
            return
        if self.held is not None:
            self.fit(self.held, (part, tag, point))
            return
        if part is None:
            self.dragging = True
            return
        tool = self.tool
        if tool == "driver":
            screw = self.screw_under(part, tag)
            if screw:
                self.start_turn(screw)
            else:
                self.say(self.advice(part))
        elif tool in ("puller", "switcher"):
            if isinstance(part, KeyItem):
                self.key_action("pull keycaps" if tool == "puller" else "pull switches", part.i)
            else:
                self.say(self.advice(part))
        elif tool == "brush":  # the one tool you can hold down and drag
            self.brushing, self.brush_from, self.brush_travel = True, point, 0.0
            self.brush_at(point)
        elif tool == "lube":
            if part in self.stabs:
                self.lube(part)
            else:
                self.say("Lube goes on the stabilisers: the wire clips under the long keys, once their keycaps "
                         "are off.")
        elif isinstance(part, KeyItem) or part.screw:
            self.say(self.advice(part))
        else:
            self.take_off(part)

    def advice(self, part):
        """Which tool a part needs."""
        if part is not None and part.screw:
            return "Screws need the screwdriver (2): click one with it."
        if isinstance(part, KeyItem):
            return ("Keycaps come off with the keycap puller (3)." if part.kind == "keycap" else
                    "Switches come out with the switch puller (4).")
        return "Lift parts off with the hand (1)."

    def actionable(self, part):
        """Can the tool in your hand do something to this?"""
        if part is None:
            return False
        if isinstance(part, Bowl):  # (whatever's in your hand)
            return self.phase != "test" and any(not c.placed and c.grimy for c in self.caps)
        if self.phase == "test":  # the keys to press, and the knob to turn
            return part is self.knob or isinstance(part, KeyItem) and part.kind == "keycap"
        if self.held is not None:
            return False
        if isinstance(part, Trinket):
            return True
        tool = self.tool
        if tool == "lube":
            return part in self.stabs and not part.lubed
        if tool == "hand":
            return isinstance(part, Part3D) and not part.screw
        if tool == "driver":
            return part.screw
        if tool == "puller":
            return isinstance(part, KeyItem) and part.kind == "keycap"
        if tool == "switcher":
            return isinstance(part, KeyItem) and part.kind == "switch"
        return False

    def highlight(self, part):
        if isinstance(part, KeyItem):
            part.set.meshes[0].brighten(part.i, 1.3)
        elif isinstance(part, Trinket):
            part.holder.setColorScale(1.4, 1.4, 1.3, 1)
        elif part is not None:
            part.root.setColorScale(1.22, 1.22, 1.22, 1)

    def unhighlight(self, part=None):
        part = part or self.lit
        if part is None:
            return
        if isinstance(part, KeyItem):
            part.set.meshes[0].brighten(part.i, 1)
        elif isinstance(part, Trinket):
            part.holder.setColorScale(1, 1, 1, 1)
        else:
            part.root.setColorScale(1, 1, 1, 1)
        if part is self.lit:
            self.lit = None

    # ---- every frame ----

    def update(self):
        self.clock += time.dt
        self.count_frames()
        self.sounds.update(self.clock)
        self.update_camera()
        self.update_tweens()
        self.update_flights()
        self.update_steam()
        self.update_wash()
        self.update_mouse_test()
        if abs(window.aspect_ratio - self.layout_aspect) > 0.01:
            self.vignette.scale = (window.aspect_ratio + 0.02, 1.02)
            {"menu": self.menu_ui, "play": self.build_ui, "result": self.result_ui}[self.state]()
        self.hover_sounds()
        self.update_volumes()
        if self.state == "menu":
            self.update_menu()
            return
        if self.state == "result":
            self.yaw.rotation_y += 14 * time.dt
            self.keep_above_desk()
            return
        if self.state != "play":
            return
        if self.dragging and (held_keys["left mouse"] or held_keys["right mouse"]):
            self.yaw.rotation_y -= mouse.velocity.x * 260
            self.pitch.rotation_x += mouse.velocity.y * 260
        self.keep_above_desk()
        self.update_turns()
        busy = self.dragging or self.over_panel() or self.help_open or self.confirming
        under = (None, None, None) if busy else self.pick()
        if self.brushing:
            if held_keys["left mouse"] and self.tool == "brush" and self.phase != "test":
                self.brush_drag(under[2])
            else:
                self.brushing = False
        if self.phase == "test":
            self.update_test()
        target = under[0] if self.actionable(under[0]) else None
        if target is not self.lit:
            self.unhighlight()
            self.highlight(target)
            self.lit = target
        self.refresh_ui(under[0])

    def hover_sounds(self):
        hovered = mouse.hovered_entity if not self.offscreen else None
        if hovered is not self.ui_hovered:
            self.ui_hovered = hovered
            if isinstance(hovered, Button):
                self.sounds.play("hover", 0.3)

    def count_frames(self):
        self.frames += 1
        self.frame_clock += time.dt
        if self.frame_clock >= 0.25 and hasattr(self, "fps_text") and self.fps_text:
            if self.show_fps:
                self.set_text(self.fps_text, f"{self.frames / self.frame_clock:.0f} fps")
            self.frames, self.frame_clock = 0, 0.0

    def refresh_ui(self, under):
        """Bring the screen up to date. Only what's changed is touched: setting a text or a colour every frame is
        what makes Ursina slow."""
        phase = self.phase
        total = len(self.parts)
        on = sum(p.placed for p in self.parts)
        if phase == "test":
            done, total = len(self.tested), len(self.caps)
            if self.kind == "mouse":
                checks = self.mouse_checks()
                done, total = sum(c in self.checks for c, _ in checks), len(checks)
        else:
            done = total - on if phase == "apart" else on
        for i, t in enumerate(self.steps):
            now = ("apart", "build", "test").index(phase)
            col = HONEY_DARK if i == now else SAGE if i < now else MUTED
            if getattr(t, "tinted", None) != col:
                t.color, t.tinted = rgb(col), col
        fill = 0.4 * done / max(1, total)
        if abs(self.bar.scale_x - max(0.001, fill)) > 1e-4:
            self.bar.scale_x = max(0.001, fill)
        self.set_text(self.bar_text, f"{done} / {total}")
        left = sum(len(d.left) for d in self.board.dirt)
        found = "" if not self.found else f",  and you found a {self.found}"
        self.set_text(self.clean_text, (f"Crumbs left: {left}" if left else "Spotless inside") + found)
        if phase != "test":
            in_box = sum(not p.placed for p in self.big)
            self.set_text(self.box_count, f"{in_box} of {len(self.big)} in it")
            for b in self.chips:
                item = b.item
                if item in ("keycaps", "switches"):
                    group = self.caps if item == "keycaps" else self.switches
                    n = sum(not q.placed for q in group)
                    label = f"{'Keycaps' if item == 'keycaps' else 'Switches'}  {n}"
                    boxed, held = n > 0, self.held == item
                else:
                    label = item.name[0].upper() + item.name[1:]
                    boxed, held = not item.placed, self.held is item
                self.set_text(b.text_entity, label)
                self.set_colors(b, HONEY if held else CREAM if boxed else PAPER,
                                CREAM if held else COCOA if boxed else MUTED)
            for tool, b in self.tool_buttons:
                on_tool = tool == self.tool and self.held is None
                self.set_colors(b, HONEY if on_tool else CREAM, CREAM if on_tool else COCOA)
            name, paint = PAINTS[self.paint]
            self.set_text(self.paint_name, name)
            ring = self.swatches[self.paint]
            if (self.paint_ring.x, self.paint_ring.y) != (ring.x, ring.y):
                self.paint_ring.position = (ring.x, ring.y, 0.1)
            kind = SWITCH_KINDS[self.switch_kind]
            self.set_text(self.switch_name, f"{kind[1]} ({kind[0]})")
            ring = self.switch_swatches[self.switch_kind]
            if (self.switch_ring.x, self.switch_ring.y) != (ring.x, ring.y):
                self.switch_ring.position = (ring.x, ring.y, 0.1)
            building = phase == "build"
            self.show_group("paint", building)
            self.show_group("switches", building and self.kind == "keyboard")
        else:
            for check, dot, text in self.check_rows:  # (a mouse's)
                done = check in self.checks
                for e, col in ((dot, HONEY if done else PAPER_DARK), (text, COCOA if done else MUTED)):
                    if getattr(e, "tinted", None) != col:
                        e.color, e.tinted = rgb(col), col
            if self.test_count is not None:
                self.set_text(self.test_count, f"{len(self.tested)} of {len(self.caps)} keys tested")
            if self.knob is not None:
                self.set_text(self.knob_text, "The knob works!" if self.knob_turned else
                              "And turn the knob: scroll on it.")
        if self.message_time > 0:
            self.message_time -= time.dt
            if self.message_time <= 0:
                self.toast.enabled = self.toast_text.enabled = False
        # what's in your hand, by the mouse
        held = self.held
        glyph = ("keycap" if held == "keycaps" else "switch" if held == "switches" else
                 "hand" if isinstance(held, Part3D) else self.tool)
        if phase == "test":
            glyph = "keycap" if self.kind == "keyboard" else "hand"
        if self.badge_icon.texture != self.art[glyph]:
            self.badge_icon.texture = self.art[glyph]
        tip = ""
        hovered_ui = self.ui_hovered
        if hovered_ui in self.tips:
            tip = self.tips[hovered_ui]
        elif isinstance(held, Part3D):
            tip = held.name[0].upper() + held.name[1:]
        elif under is not None and not self.over_panel():
            tip = under.name[0].upper() + under.name[1:]
        self.set_text(self.tooltip, tip)
        visible = bool(tip) and not self.offscreen
        if not self.offscreen:
            mx, my = mouse.x, mouse.y
            self.badge.position = (mx + 0.03, my - 0.03, -0.3)
            self.badge_icon.position = (mx + 0.03, my - 0.03, -0.31)
            if visible:
                self.place_tip(mx, my)
        if self.tooltip.enabled != visible:
            self.tooltip.enabled = self.tip_back.enabled = visible

    def place_tip(self, mx, my):
        """Put the tooltip by the mouse (to its left, near the right edge), on a pill that just fits it."""
        pad, h, w = 0.013, 0.034, self.tooltip.width
        if abs(w - self.tip_width) > 0.001:
            self.tip_width = w
            self.tip_back.model = Quad(radius=0.5, aspect=(w + 2 * pad) / h)
            self.tip_back.scale = (w + 2 * pad, h)
        x = mx + 0.065
        if x + w + pad > window.aspect_ratio / 2 - 0.01:
            x = mx - 0.02 - w - pad
        y = my + 0.03
        self.tooltip.position = (x, y, -0.4)
        self.tip_back.position = (x + w / 2, y, -0.39)


def cap_frame_rate(fps):
    """Draw no more than fps frames a second. (With vsync off, as it is by default here, the game would otherwise
    run as fast as it can, or as fast as the monitor refreshes with it on: often only 60.) Panda3D's clock is made
    when the engine loads, so this has to be set on it once the app is running."""
    from panda3d.core import ClockObject
    clock = ClockObject.getGlobalClock()
    clock.setMode(ClockObject.MLimited)
    clock.setFrameRate(fps)


def main():
    args = sys.argv[1:]
    shots = args[args.index("--shot") + 1] if "--shot" in args else None
    fps = int(args[args.index("--fps") + 1]) if "--fps" in args else 120
    vsync = "--vsync" in args  # wait for the monitor instead: no tearing, but no faster than it refreshes
    windowed = "--windowed" in args
    setup_fonts()
    if shots:
        app = Ursina(title="Fixer 3D", size=(1280, 720), development_mode=False, vsync=False,
                     window_type="offscreen")
    else:
        app = Ursina(title="Fixer 3D", icon=window_icon_file(), development_mode=False, vsync=vsync,
                     fullscreen=not windowed, borderless=not windowed, size=(1280, 720) if windowed else None)
        window._fullscreen = not windowed
    if fps > 0 and not vsync:
        cap_frame_rate(fps)
    shop = Workshop(offscreen=bool(shots))
    if shots:
        take_shots(app, shop, shots)
        return
    app.run()


def take_shots(app, shop, folder):
    """Pictures of it working, without a window, for checking how it looks."""
    from panda3d.core import Filename as F
    aspect = 16 / 9  # offscreen, Ursina doesn't size its cameras to the picture, so do it here
    camera.perspective_lens.set_aspect_ratio(aspect)
    camera.ui_lens.set_film_size(camera._ui_size * 0.5 * aspect, camera._ui_size * 0.5)

    def wait(seconds):
        started = time.perf_counter()
        while time.perf_counter() - started < seconds:
            app.step()

    def snap(name, seconds=0.3):
        wait(seconds)
        app.win.saveScreenshot(F.fromOsSpecific(os.path.join(folder, name + ".png")))

    def board():
        return shop.board

    snap("3d_menu", 1.2)
    shop.preview(KEYBOARD_MODELS[2])
    snap("3d_menu_compact", 1.0)
    shop.start(KEYBOARD_MODELS[1])
    snap("3d_start", 1.3)
    for i, cap in enumerate(shop.caps):
        if board().rows[i] <= 2.25:
            shop.pull(cap)
    snap("3d_pulling", 0.25)
    for cap in shop.caps:
        if cap.placed:
            shop.pull(cap)
    snap("3d_caps_off", 1.0)
    plate_dirt = board().dirt[0]
    for p in list(plate_dirt.points[:20]):
        shop.brush_at(p)
    snap("3d_brushed", 0.6)
    if board().trinket and board().trinket.host.key == "plate":
        shop.collect(board().trinket)
    for sw in shop.switches[:30]:
        shop.pull(sw)
    shop.yaw.rotation_y, shop.pitch.rotation_x = -20, 20
    snap("3d_switches", 1.0)
    shop.yaw.rotation_y, shop.pitch.rotation_x = 90, 80  # stood on its end: it must be lifted clear of the desk
    snap("3d_on_end", 0.4)
    render = application.base.render
    low = min(render.getRelativePoint(shop.kb, p).y for p in shop.corners)
    assert low >= DESK_Y + CLEARANCE * 0.5, f"the keyboard went into the desk (lowest corner {low:.2f})"
    shop.pitch.rotation_x, shop.yaw.rotation_y = 0, 0
    shop.show_group("volume music", True)  # (offscreen there's no mouse to open it)
    snap("3d_volume", 0.2)
    shop.show_group("volume music", False)

    # the rest apart, as a player would: whatever's free, each with its own tool
    for _ in range(400):
        free = [p for p in reversed(shop.parts) if p.placed and not shop.above(p)]
        if not free:
            break
        p = free[0]
        if isinstance(p, KeyItem):
            shop.pull(p)
        else:
            shop.lift_off(p)
        if p.key == "foot0":
            shop.pitch.rotation_x = 180
            snap("3d_underside", 0.8)
            shop.pitch.rotation_x = 0
        if p.key == "plate":
            snap("3d_plate_off", 0.6)
        if p.key == "inner_cable":
            if board().trinket and not board().trinket.found:
                shop.collect(board().trinket)
            snap("3d_pcb", 0.6)
    assert shop.phase == "build", f"still {shop.phase} after taking everything off"
    snap("3d_apart", 1.0)
    for p in shop.parts:  # build it back up, in mixed colours
        assert all(q.placed for q in p.below), f"{p.name} would go on before what it sits on"
        shop.paint = random.randrange(len(PAINTS))
        shop.switch_kind = random.randrange(len(SWITCH_KINDS))
        if isinstance(p, KeyItem):
            shop.put_key(p)
        elif p.screw:
            p.root.unstash()
            p.placed = True
            shop.dish_mesh.move(shop.screws.index(p), None)
            shop.after_change()
        else:
            shop.put_on(p)
        if p.key == "switch40":
            snap("3d_building", 0.5)
    assert shop.phase == "test", f"phase is {shop.phase} once it's built"
    snap("3d_test", 1.0)
    for i in range(0, len(shop.caps), 3):
        shop.press_key(i)
        shop.release_key(i)
    shop.press_key(5)
    snap("3d_typing", 0.2)
    shop.finish_test()
    snap("3d_result", 1.4)
    assert shop.state == "result"
    print("3D cycle ok:", len(shop.parts), "parts")


if __name__ == "__main__":
    main()
