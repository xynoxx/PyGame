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
SWAB, BLOWER = ("swab", "Alcohol swab"), ("blower", "Air blower")  # (only the jobs that need them have these)
SOLDER = ("solder", "Soldering iron")
FRESH = {"battery": "fresh battery", "cushions": "fresh cushions", "swollen": "new battery", "paste": "thermal paste"}  # a new part, in the box
SWAB_WORK = 3  # swabs to work the alcohol into a sticky switch, or the crust off a battery contact
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
# Microphones: five real kinds, each made the way it really is (form says which). size is the room one takes on the
# desk (width, depth); height is how tall it stands.
MICS = [
    dict(kind="mic", key="mic_lav", form="lav", name="Lavalier mic", size=(8.6, 4.2), height=1.35,
         case=(52, 54, 60), accent=(236, 150, 78), cable=(44, 44, 50),
         intro="A tiny clip-on mic, for interviews and videos. Its long, thin cable has tied itself in knots."),
    dict(kind="mic", key="mic_stage", form="stage", name="Stage mic", size=(11.4, 3.2), height=2.6,
         case=(58, 60, 68), accent=(214, 72, 64), cable=(36, 36, 40),
         intro="A tough dynamic mic, for singing on stage. Its ball grille unscrews by hand: click it with the hand."),
    dict(kind="mic", key="mic_wireless", form="wireless", name="Wireless mic", size=(10.6, 3.0), height=2.4,
         case=(40, 42, 50), accent=(90, 170, 230), cable=(40, 42, 50),
         intro="A wireless handheld mic. Its battery sleeve twists off: take the batteries out before you open it."),
    dict(kind="mic", key="mic_podcast", form="podcast", name="USB podcast mic", size=(5.0, 5.0), height=7.8,
         case=(232, 226, 214), accent=(222, 120, 96), cable=(232, 226, 214),
         intro="A USB mic for podcasts, on its own desk stand. The thumb screws on its yoke turn by hand."),
    dict(kind="mic", key="mic_studio", form="studio", name="Studio condenser", size=(5.4, 5.4), height=8.9,
         case=(70, 82, 104), accent=(212, 176, 90), cable=(40, 40, 44),
         intro="A studio condenser in its shock mount. Its gold capsule is delicate: handle it with care."),
]
# Webcams: three real kinds, each built the way it really is. size is the room one takes on the desk; height is
# how tall it stands.
WEBCAMS = [
    dict(kind="webcam", key="cam_clip", form="clipcam", name="Clip-on webcam", size=(7.0, 4.0), height=3.1,
         case=(58, 60, 68), accent=(150, 154, 162), cable=(40, 40, 44),
         intro="A webcam that clips on top of a monitor. Somebody's left a big greasy thumbprint on its lens window."),
    dict(kind="webcam", key="cam_ball", form="ballcam", name="Ball webcam", size=(5.0, 5.0), height=5.1,
         case=(232, 228, 218), accent=(90, 170, 220), cable=(232, 228, 218),
         intro="A round old webcam on a weighted stand. Its focus ring turns by hand, and it's out of focus."),
    dict(kind="webcam", key="cam_stream", form="streamcam", name="Streaming webcam", size=(4.6, 4.2), height=4.6,
         case=(44, 46, 54), accent=(236, 150, 78), cable=(44, 46, 54),
         intro="A streamer's webcam with a ring light round its lens, on a little tripod. Its light flickers."),
]
# Headsets, lying flat on the desk with their cushions up, the way you'd put one down. bottom is the cushions' colour.
HEADSETS = [
    dict(kind="headset", key="hs_office", form="office_hs", name="Office headset", size=(9.0, 7.2), height=1.6,
         case=(60, 62, 70), bottom=(40, 40, 44), accent=(90, 150, 210), cable=(36, 36, 40),
         intro="A USB headset for calls. Its ear cushions are old and flaking: you'll fit fresh ones."),
    dict(kind="headset", key="hs_gaming", form="gaming_hs", name="Gaming headset", size=(10.0, 7.8), height=1.8,
         case=(34, 36, 42), bottom=(56, 56, 62), accent=(90, 220, 160), cable=(30, 30, 34),
         intro="A gaming headset with lights round its cups. The left side has gone silent."),
    dict(kind="headset", key="hs_wireless", form="wireless_hs", name="Wireless headphones", size=(9.4, 7.4),
         height=1.65, case=(214, 204, 188), bottom=(160, 140, 120), accent=(196, 120, 90), cable=(214, 204, 188),
         intro="Bluetooth headphones with a battery in the right cup, and the battery's swollen up. Careful with it."),
]
# Computers, lying on their sides on the bench with their glass up, the way you'd work on one: a case on its own, and
# a whole desktop PC (just the tower: no screen, no keyboard). bottom is their plastic trim's colour.
COMPUTERS = [
    dict(kind="computer", key="pc_case", form="pc_case", name="PC case", size=(14.4, 14.8), height=6.95,
         case=(104, 128, 156), bottom=(48, 48, 54), accent=(240, 200, 120), cable=(30, 30, 34),
         intro="An empty PC case, on its side with its glass up. Some of its dust filters are clogged."),
    dict(kind="computer", key="pc_tower", form="pc_tower", name="Desktop PC", size=(14.4, 14.8), height=6.95,
         case=(46, 48, 56), bottom=(34, 34, 38), accent=(236, 150, 78), cable=(30, 30, 34),
         intro="A whole desktop PC, on its side with its glass up. It's been running hot."),
]
for _m in MICE + MICS + WEBCAMS + HEADSETS + COMPUTERS:  # (what the colour picker and the switch card expect of any)
    _m.setdefault("cap", _m["case"])
    _m.setdefault("switch", "blue")
_BY_KEY = {m["key"]: m for m in KEYBOARD_MODELS + MORE_KEYBOARDS + MICE + MICS + WEBCAMS + HEADSETS + COMPUTERS}
# Every one has a job of its own, besides taking it apart, building it back and testing it, and a star for doing it:
# what the job card calls it, the star's name, and how it's done ({hand}, {swab}... become the tools' numbers).
SPECIALS = {
    "sum": ("Do a sum on it", "Sum", "In the test, work out the sum on the card: type the answer, then Enter."),
    "fn_layer": ("Try the Fn layer", "Fn layer",
                 "In the test, click Fn: I, J, K and L turn into the arrow keys. Press all four."),
    "pair": ("Pair it", "Paired", "In the test, hold Esc down for two seconds to pair it over Bluetooth."),
    "volume": ("Turn the music with it", "Volume",
               "In the test, its knob turns the music: all the way down, then all the way up."),
    "sticky": ("Unstick the sticky key", "Unstuck",
               "A drink was spilled in it, and the {sticky} switch sticks. Once its keycap is off, swab the switch "
               "with alcohol ({swab})."),
    "swap": ("Fit new switches", "New switches",
             "It's hot-swap: build it back with new switches, all of one kind, but not the red ones it came with."),
    "pangram": ("Type the quick brown fox", "Typed",
                "In the test, type the line on the card. It has every letter in it, so a bad key can't hide."),
    "shake": ("Shake out the loose crumbs", "Shaken out",
              "Before you take it apart, flip it over (F) and shake it (drag it about) to tip the loose crumbs out."),
    "double_click": ("Fix the double-click", "One click",
                     "Its left button double-clicks. With the top shell off, click the left switch on the board "
                     "with the hand ({hand}) to bend its spring back."),
    "dpi": ("Try every DPI speed", "DPI",
            "In the test, click the DPI button behind the wheel, through all four speeds."),
    "battery": ("Fit a fresh battery", "Battery",
                "Its battery is flat. Once it's out, click Fresh battery in the parts box to swap it."),
    "foam": ("Wash the foam", "Fresh foam",
             "The foam windscreen under the grille is grubby. Hold it (click it in the parts box), then click the "
             "wash bowl."),
    "gain": ("Set the gain", "Gain",
             "In the test, hold Space to talk, and turn the gain knob (scroll on it) until the meter sits in the "
             "green."),
    "blower": ("Puff the capsule clean", "Capsule",
               "The capsule is dusty. With the headbasket off, puff it clean with the air blower ({blower}): never "
               "brush a capsule."),
    "untangle": ("Untangle the cable", "Untangled", "Click each knot in the cable with the hand ({hand}) to undo it."),
    "contacts": ("Clean the contacts", "Contacts",
                 "The battery contacts are crusty. With the batteries out, swab them clean ({swab})."),
    "smudge": ("Wipe the lens clean", "Clear lens",
               "A greasy thumbprint smudges its lens window: wipe it with the alcohol swab ({swab}) till it's clear."),
    "focus": ("Focus it", "In focus", "In the test, turn its focus ring (scroll on it) until the picture is sharp."),
    "flicker": ("Stop the flicker", "Steady light",
                "Its ring light flickers: the ribbon cable inside has worked loose. With the front panel off, press "
                "its loose end home with the hand ({hand})."),
    "cushions": ("Fit fresh ear cushions", "Fresh cushions",
                 "Its ear cushions are flaking. Once both are off, click Fresh cushions in the parts box."),
    "solder": ("Fix the dead left side", "Both sides",
               "The left side's silent: a wire's come off the little board in the left cup. With the left driver "
               "out, touch the soldering iron ({solder}) to it."),
    "swollen": ("Swap the swollen battery", "Safe battery",
                "Its battery has swollen up. Unplug its lead, lift it out gently, and click New battery in the parts "
                "box."),
    "filters": ("Wash the dust filters", "Clean filters",
                "Some of its dust filters are clogged grey. Once it's apart, hold each one (click it in the parts "
                "box), then click the wash bowl."),
    "paste": ("Fresh thermal paste", "Cool CPU",
              "Its CPU runs hot: the old paste has dried out. With the cooler off, wipe it off the CPU with the swab "
              "({swab}), then click Thermal paste in the box."),
}
for _key, _special in (("numpad", "sum"), ("compact", "fn_layer"), ("wireless65", "pair"), ("knob75", "volume"),
                       ("tkl", "sticky"), ("gasket96", "swap"), ("full", "pangram"), ("vintage", "shake"),
                       ("mouse_office", "double_click"), ("mouse_gaming", "dpi"), ("mouse_travel", "battery"),
                       ("mic_lav", "untangle"), ("mic_stage", "foam"), ("mic_wireless", "contacts"),
                       ("mic_podcast", "gain"), ("mic_studio", "blower"), ("cam_clip", "smudge"),
                       ("cam_ball", "focus"), ("cam_stream", "flicker"), ("hs_office", "cushions"),
                       ("hs_gaming", "solder"), ("hs_wireless", "swollen"), ("pc_case", "filters"),
                       ("pc_tower", "paste")):
    _BY_KEY[_key]["special"] = _special
PANGRAM = "the quick brown fox jumps over the lazy dog"
# What a real repairer knows about each job, for the end
TIPS = {
    "sum": "A number pad's Enter is a key of its own, and Num Lock decides whether its keys type numbers or move "
           "the cursor about.",
    "fn_layer": "Small keyboards keep their missing keys on layers: holding Fn changes what the keys do, the way "
                "Shift turns letters into capitals.",
    "pair": "Wireless keyboards pair by holding a key combination until the light blinks. After that, they remember "
            "the computer.",
    "volume": "A volume knob like this is a rotary encoder: it sends one pulse for every notch it turns, one way or "
              "the other.",
    "sticky": "Isopropyl alcohol (90% or more) dissolves dried drink and dries fast, leaving nothing behind: swab "
              "it in, press the switch again and again, and let it dry.",
    "swap": "On a hot-swap board, switches push into sockets. Pull each one straight out, and push the new one "
            "straight in with its pins straight.",
    "pangram": "'The quick brown fox jumps over the lazy dog' has every letter in it, so typing it shows up a dead "
               "or sticky key at once.",
    "shake": "Turn a keyboard over and shake it before you take it apart: most of the loose crumbs fall straight "
             "out.",
    "double_click": "A mouse that double-clicks has a worn switch: the little spring inside has gone soft. Bending "
                    "it back helps for a while; a new switch fixes it for good.",
    "dpi": "DPI is how far the pointer moves for each inch you move the mouse: the higher it is, the faster.",
    "battery": "A flat battery makes a wireless mouse stutter and skip. Take old batteries out before they leak.",
    "foam": "A stage mic's foam collects lipstick and breath: wash it in warm, soapy water, and let it dry right "
            "through before it goes back in.",
    "gain": "Set the gain so your voice sits in the green: too low and it's lost in hiss, too high and it clips "
            "and crackles.",
    "blower": "Never touch a condenser's diaphragm: it's thinner than a hair. A puff of air from a blower is all "
              "the cleaning it wants.",
    "untangle": "Coil a mic cable over-under, one loop forwards and the next one back, and it won't twist into "
                "knots next time.",
    "contacts": "That green-white crust is from a battery that leaked. Alcohol on a swab dissolves it; then fresh "
                "batteries, and take them out when it's put away.",
    "smudge": "Clean a lens with a little alcohol on a soft swab or a lens wipe: never a tissue or your shirt, which "
              "leave scratches and lint.",
    "focus": "A manual focus ring moves the lens nearer the sensor or further away: further for things up close, "
             "nearer for things far off.",
    "flicker": "Ribbon cables sit in their sockets under a little latch: a knock can lift one end, and the light (or "
               "the screen) flickers. Seat it straight, and close the latch.",
    "cushions": "Ear cushions are made to be swapped: most twist or clip off, and fresh ones make an old headset "
                "comfy (and clean) again.",
    "solder": "A wire that breaks off a board is the commonest headset fault. Heat the pad and the wire together, "
              "and let the solder flow: a shiny joint is a good one.",
    "swollen": "A lithium battery that swells is worn out and unsafe: never press, bend or puncture it, and take it "
               "to a battery recycling point, not the bin.",
    "filters": "Dust filters keep the fluff out of a PC. Wash them every few months in warm, soapy water, and let "
               "them dry right through before they go back on.",
    "paste": "Thermal paste fills the tiny gaps between a CPU and its cooler. When it dries out, wipe the old off with "
             "alcohol and put on a pea-sized dot: the cooler spreads it thin.",
}
# On the menu, smallest first
MODELS = [_BY_KEY[k] for k in ("numpad", "compact", "wireless65", "knob75", "tkl", "gasket96", "full", "vintage")]
ALL_MODELS = MODELS + MICE + MICS + WEBCAMS + HEADSETS + COMPUTERS
KINDS = [("keyboard", "Keyboards"), ("mouse", "Mice"), ("mic", "Mics"), ("webcam", "Webcams"), ("headset", "Headsets"),
         ("computer", "Computers")]
HEARS = ("mic", "webcam", "headset")  # the kinds with a microphone in them, tested by talking


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


def turn(np, axis, degrees):
    """Turn a node to this many degrees about one axis: y is upright (a screw, a knob on top), x lies across (a
    wheel, a grille on a mic lying down), z points back (a knob on a mic's front)."""
    {"x": np.setP, "y": np.setH, "z": np.setR}[axis](degrees)


def turned(np, axis):
    return {"x": np.getP, "y": np.getH, "z": np.getR}[axis]()


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
    if kind_of(spec) != "keyboard":
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

    def lathe(self, profile, axis="x", center=(0, 0, 0), segments=20):
        """A round thing, turned as on a lathe: profile is (along, radius) points down its axis (x, y or z), through
        center. A radius of 0 closes an end; two points at the same place along it make a flat ring or disc."""
        cx, cy, cz = center
        n = len(profile) - 1

        def at(u):
            k = min(n - 1, int(u * n))
            s = u * n - k
            (a0, r0), (a1, r1) = profile[k], profile[k + 1]
            return a0 + (a1 - a0) * s, r0 + (r1 - r0) * s

        def f(u, v):
            a, r = at(u)
            c, s = math.cos(v) * r, math.sin(v) * r
            if axis == "x":
                return cx + a, cy + c, cz + s
            if axis == "y":
                return cx + c, cy + a, cz + s
            return cx + c, cy + s, cz + a

        def inside(p):  # the point on the axis beside it
            return (p[0], cy, cz) if axis == "x" else (cx, p[1], cz) if axis == "y" else (cx, cy, p[2])
        self.surface(f, 0, 1, 2 * n, 0, 2 * math.pi, segments, inside)

    def ring(self, center, radius, thick, segments=24):
        """A thin hoop lying flat (round the y axis), like a shock mount's frame."""
        x, y, z = center
        pts = [(x + math.cos(2 * math.pi * k / segments) * radius, y, z + math.sin(2 * math.pi * k / segments) * radius)
               for k in range(segments + 1)]
        for a, b in zip(pts, pts[1:]):
            self.rod(a, b, thick)

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

    def show_glyph(self, item, where):
        """Point a legend's square at another spot in its texture (u0, v0, u1, v1): another letter on the same key."""
        span = self.items.get(item)
        if not span or self.np.node().getNumGeoms() == 0:
            return
        s, e = span
        u0, v0, u1, v1 = where
        corners = [(u0, v0), (u1, v0), (u1, v1), (u0, v0), (u1, v1), (u0, v1)]  # (as Shapes.quad lays them)
        vals = array("f", [c for k in range(e - s) for c in corners[k % 6]])
        self.view(3)[2 * s:2 * e] = vals  # (just on the card: its uv array is shared with the tray's copy)

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
    elif name == "swab":  # a cotton bud, soaked in alcohol: a thin stick with a fluffy tip at each end
        cap((250, 774), (774, 250), 46)
        for x, y in ((214, 810), (810, 214)):
            d.ellipse([P(x - 120, y - 120), P(x + 120, y + 120)], fill=W)
        d.ellipse([P(560, 690), P(680, 810)], fill=W)  # a drop of the alcohol
        d.polygon([P(575, 710), P(620, 610), P(665, 710)], fill=W)
    elif name == "solder":  # a soldering iron: a fat handle, a thin barrel, a fine tip, and a wisp of smoke
        cap((170, 860), (430, 600), 180)
        cap((430, 600), (520, 510), 110)
        cap((520, 510), (760, 270), 56)
        cap((760, 270), (850, 180), 22)
        for t in (0.35, 0.6):
            px, py = 170 + 260 * t, 860 - 260 * t
            cap((px - 60, py - 60), (px + 60, py + 60), 18, CLEAR)
        d.arc([P(760, 40), P(940, 220)], 200, 330, fill=W, width=int(30 * k))
    elif name == "blower":  # a rubber air blower: a round bulb, and a nozzle with a puff coming out of it
        d.ellipse([P(130, 380), P(600, 850)], fill=W)
        cap((520, 470), (720, 270), 110)
        cap((720, 270), (800, 190), 56)
        for r in (110, 200):
            d.arc([P(800 - r, 190 - r), P(800 + r, 190 + r)], -80, 10, fill=W, width=int(36 * k))
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


FOCUS_AT = 0.6  # where a ball webcam's focus ring is sharp, from 0 to 1


def draw_preview(blur=0.0, bright=1.0, closed=False):
    """What a webcam sees, for its test card: you at your desk, smiling, with a window and a plant behind you. It's
    blurred when the lens is smudged or out of focus, darker in dim light, and black with the shutter closed."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
    W, H = 320, 180
    if closed:
        img = Image.new("RGB", (W, H), (20, 20, 24))
        ImageDraw.Draw(img).text((W / 2, H / 2), "Shutter closed", font=ImageFont.truetype(font_file(), 22),
                                 fill=(120, 116, 110), anchor="mm")
        return img
    img = Image.new("RGB", (W, H), (226, 206, 178))  # a warm wall
    d = ImageDraw.Draw(img)
    d.rectangle([196, 18, 296, 106], fill=(250, 244, 232))  # a window, and the sky through it
    d.rectangle([202, 24, 290, 100], fill=(168, 208, 236))
    d.ellipse([214, 40, 258, 60], fill=(250, 250, 252))
    d.line([(246, 24), (246, 100)], fill=(250, 244, 232), width=4)
    d.line([(202, 62), (290, 62)], fill=(250, 244, 232), width=4)
    d.rectangle([186, 106, 306, 112], fill=(196, 160, 120))  # its sill, and a plant on it
    d.rectangle([272, 88, 292, 106], fill=(196, 112, 82))
    for x, y in ((276, 74), (284, 70), (290, 78), (270, 80)):
        d.ellipse([x - 7, y - 9, x + 7, y + 9], fill=(112, 162, 104))
    d.rectangle([30, 36, 82, 80], fill=(150, 110, 80))  # a picture on the wall
    d.rectangle([35, 41, 77, 75], fill=(236, 196, 140))
    d.ellipse([92, 128, 228, 236], fill=(120, 160, 200))  # you: a cosy jumper,
    d.rectangle([146, 112, 174, 136], fill=(232, 190, 154))
    d.ellipse([118, 38, 202, 110], fill=(84, 58, 44))  # your hair,
    d.ellipse([126, 52, 194, 128], fill=(238, 198, 162))  # your face,
    d.pieslice([120, 36, 200, 92], 180, 360, fill=(84, 58, 44))
    for x in (146, 174):
        d.ellipse([x - 4, 82, x + 4, 92], fill=(60, 44, 40))
        d.ellipse([x - 11, 96, x - 1, 104] if x < 160 else [x + 1, 96, x + 11, 104], fill=(244, 170, 160))
    d.arc([146, 92, 174, 116], 20, 160, fill=(150, 80, 70), width=3)  # and a smile
    d.rectangle([0, 160, W, H], fill=(150, 112, 84))  # the edge of the desk
    if blur > 0.05:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if abs(bright - 1) > 0.01:
        img = ImageEnhance.Brightness(img).enhance(bright)
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
                     "power", "home", "help", "star", "keycap", "switch", "again", "close", "dot", "swab", "blower",
                     "solder"):
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
        self.material = None  # what it sounds like coming off and going on, when its key doesn't say
        self.twist = None  # "x", "y" or "z": it unscrews by hand (a grille, a cap), turning about that axis
        self.thumb = False  # a thumb screw: it turns by hand, as well as with the screwdriver
        self.spin = "y"  # which way round a screw (or a knob) turns: about y (upright), x or z
        self.grimy = False  # (a mic's foam that wants a wash)

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

    def lathe(self, profile, axis, center, tint=None, fixed=SILVER, hit=True, tag=None, segments=20):
        """A round piece turned on a lathe (see Shapes.lathe), clickable by the box round it."""
        self.colour(tint, fixed).lathe(profile, axis, self.rel(center), segments)
        along = [a for a, _ in profile]
        r, mid, length = max(r for _, r in profile), (min(along) + max(along)) / 2, max(along) - min(along)
        i = "xyz".index(axis)
        c = [center[0], center[1], center[2]]
        c[i] += mid
        size = [2 * r, 2 * r, 2 * r]
        size[i] = max(length, 0.04)
        self.grow(c, size)
        if hit:
            self.target(c, size, tag)

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
            if tag in colours:  # (a tag of its own, like a mic's foam, is painted by itself)
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


# How messy a thing comes in: a new level for every job. The builders scatter MESS_MOST times the specks a dusty one
# has, and each part keeps its own share of them (some a lot, some none at all), so it's never the same twice.
MESS_MOST = 1.8
MESS_LEVELS = ((0.3, "Nearly clean"), (0.7, "A bit dusty"), (1.05, "Dusty"), (1.4, "Grubby"), (1.8, "Filthy"))
_mess = {"level": 1.05}  # (this job's, while it's being built)


class Dirt:
    """Crumbs, dust and hair on one part, brushed away a speck at a time. It keeps its share of the specks it's
    given, as messy as this job is (and least of them, whatever)."""

    def __init__(self, host, specks, delicate=False, least=0):
        self.host = host
        self.delicate = delicate  # on a mic's capsule: only air may touch it, never the brush
        if specks:
            rnd = specks[0][4]
            share = _mess["level"] * rnd.uniform(0.35, 1.45) / MESS_MOST
            if rnd.random() < 0.12 / _mess["level"]:  # now and then, a part that's stayed clean
                share = 0.0
            keep = min(len(specks), max(least, 3 if delicate else 0, round(len(specks) * min(1.0, share))))
            specks = rnd.sample(specks, keep)
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
        self.mess = "Dusty"  # how messy it came in (see MESS_LEVELS)
        self.size = self.inner = (0, 0)
        self.space_x = 0.0
        self.stab_of = {}  # key number -> the stabiliser under it
        self.knob = None
        self.height = FRAME_Y[1]  # how tall it is, put together
        self.mouse = {}  # a mouse's moving bits, for its test: its buttons, its wheel, its logo
        self.mic = {}  # a mic's: its lights, the knots in its cable, the crust on its contacts
        self.special = {}  # what its own job needs: which key is sticky, the spill, the pairing light...
        self.legend_where = {}  # where each legend is in the keycaps' texture
        self.attach = []  # (shapes, part key, name, hidden): meshes of their own on a part, made once it's finished

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
    if grime < 1:  # (as grubby as this one's messy)
        grime *= _mess["level"]
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

    px = wu / 2 - 3.0 if wu > 8 else 0.0  # where the USB socket is, along the back (a number pad's is in the middle)
    back_in = cd / 2 - WALL  # the inside of the back wall
    uz = back_in - 0.5  # the middle of the USB board, just inside it
    lw = min(3.6, cw - 1.6)  # the sticker underneath
    lh = lw * 168 / 512
    # The chip that reads the keys sits where there's room on top of the circuit board: under the space bar, between
    # its switch and the stabiliser at its left end. A number pad has no room on top, so its chip is underneath.
    space = next((k for k in keys if k[0] == "Space"), None)
    mcu = (space[1] - 1.45, space[2]) if space else None
    battery_at = (0.0, -0.6, min(5.0, wu / 2 - 1.0), 2.2) if spec.get("wireless") else None  # (x, z, width, depth)
    weight_at = (wu * 0.4, hu * 0.42) if spec.get("weight") else None  # (width, depth), in the middle
    lead_x = battery_at[0] + battery_at[2] / 2 - 0.4 if battery_at else None  # where the battery's lead plugs in

    def clear_of(x, z, boxes, r):
        """Is a circle of radius r at (x, z) clear of every one of these boxes (x0, x1, z0, z1)?"""
        for x0, x1, z0, z1 in boxes:
            dx, dz = max(x0 - x, 0.0, x - x1), max(z0 - z, 0.0, z - z1)
            if dx * dx + dz * dz < r * r:
                return False
        return True

    # Where the screws go. Each goes up through a post in the bottom case to a mounting hole in the circuit board,
    # so it has to miss everything: on the board, each switch's pads, the stabilisers' holes, the chip, the knob's
    # encoder and the sockets; in the case, the USB board, the battery, the weight and the ribs on the floor;
    # underneath, the sticker and the receiver's slot. They go in the gaps between the switches, where four keys
    # meet: one at each corner, under a rubber foot, and on a bigger board one or two along the front and the back.
    on_board = [(cx - 0.37, cx + 0.37, cz - 0.37, cz + 0.37) for _, cx, cz, _, _ in keys]
    for i in long_keys:
        wide, ends = stab_ends(*keys[i][1:])
        on_board += [(ex - (0.13 if wide else 0.21), ex + (0.13 if wide else 0.21),
                      ez - (0.21 if wide else 0.13), ez + (0.21 if wide else 0.13)) for ex, ez in ends]
    if mcu:
        on_board.append((mcu[0] - 0.68, mcu[0] + 0.85, mcu[1] - 0.58, mcu[1] + 0.58))
    if knob_at:
        on_board.append((knob_at[0] - 0.31, knob_at[0] + 0.31, knob_at[1] - 0.31, knob_at[1] + 0.31))
    on_board.append((px - 1.25, px - 0.75, hu / 2 - 0.08, hu / 2 + 0.12))  # the internal cable's socket
    in_case = [(px - 1.1, px + 1.1, uz - 0.45, back_in)] + [(x - 0.06, x + 0.06, -cd / 2, cd / 2)
                                                            for x in (-wu / 4, wu / 4)]
    if battery_at:
        bx, bz, bw, bd = battery_at
        on_board.append((lead_x - 0.21, lead_x + 0.21, hu / 2 - 0.04, hu / 2 + 0.14))
        in_case += [(bx - bw / 2 - 0.1, bx + bw / 2 + 0.1, bz - bd / 2 - 0.1, bz + bd / 2 + 0.1),
                    (lead_x - 0.1, lead_x + 0.1, bz + bd / 2, hu / 2 + 0.25)]  # (and its lead, along the floor)
    if weight_at:
        in_case.append((-weight_at[0] / 2 - 0.1, weight_at[0] / 2 + 0.1, -weight_at[1] / 2 - 0.1,
                        weight_at[1] / 2 + 0.1))
    underneath = [(-lw / 2, lw / 2, -0.3 - lh / 2, -0.3 + lh / 2)]
    if spec.get("wireless"):
        underneath.append((cw / 4 - 0.75, cw / 4 + 0.75, 0.2 - 0.375, 0.2 + 0.375))
    gaps = {(round(x, 3), round(z, 3)) for _, cx, cz, w, h in keys for x in (cx - w / 2, cx + w / 2)
            for z in (cz - h / 2, cz + h / 2)}
    gaps |= {(sx_ * wu / 2, sz_ * hu / 2) for sx_ in (-1, 1) for sz_ in (-1, 1)}  # (the corners, if no key's there)
    spots = []

    def screw_spot(tx, tz, under):
        """The gap nearest (tx, tz) that a screw fits in, `under` being the room its foot or head takes."""
        fits = [(math.hypot(x - tx, z - tz), x, z) for x, z in sorted(gaps)
                if clear_of(x, z, on_board, 0.17) and clear_of(x, z, in_case, 0.3) and clear_of(x, z, underneath, under)
                and all(math.hypot(x - a, z - b) > 1.5 for a, b in spots)]
        assert fits, f"{spec['key']}: nowhere for a screw near {tx:.2f}, {tz:.2f}"
        return min(fits)[1:]
    for tz in (-hu / 2, hu / 2):  # the four corners, first: (their screws are under the feet)
        for tx in (-wu / 2, wu / 2):
            spots.append(screw_spot(tx, tz, 0.47))
    middle = [] if wu <= 8 else [0.0] if wu <= 16.5 else [-wu / 6, wu / 6]
    for tz in (-hu / 2, hu / 2):
        for tx in middle:
            spots.append(screw_spot(tx, tz, 0.27))

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
    for x in (-wu / 4, wu / 4):  # ribs that stiffen the floor (stopping short of the USB board, where it's over one)
        z0, z1 = -cd / 2 + WALL, (uz - 0.5 if abs(x - px) < 1.2 else back_in)
        case.box((x, FLOOR + 0.05, (z0 + z1) / 2), (0.12, 0.1, z1 - z0), "inside", hit=False)
    case.box((px, 0.45, cd / 2 + 0.006), (0.8, 0.34, 0.01), fixed=BLACK, hit=False)  # the opening for the socket
    for i, (x, z) in enumerate(spots):
        case.post((x, 0, z), 0.24, -0.02, fixed=(24, 26, 30), tag=("hole", i), segments=12)
    if spec.get("wireless"):  # its power switch, on the back, and a slot underneath where its receiver lives
        case.box((px + 1.5, 0.6, cd / 2 + 0.01), (0.6, 0.2, 0.03), fixed=BLACK, hit=False)
        case.box((px + 1.38, 0.6, cd / 2 + 0.035), (0.22, 0.14, 0.05), fixed=spec["accent"], hit=False)
        case.box((cw / 4, -0.006, 0.2), (1.5, 0.01, 0.75), fixed=(24, 26, 30), hit=False)
    label = Shapes().use((255, 255, 255))
    label.quad((-lw / 2, -0.008, -0.3 + lh / 2), (lw / 2, -0.008, -0.3 + lh / 2), (lw / 2, -0.008, -0.3 - lh / 2),
               (-lw / 2, -0.008, -0.3 - lh / 2), (0, -1, 0), [(0, 0), (1, 0), (1, 1), (0, 1)])  # reads turned over
    case.extras.append((label, Texture(draw_label(spec), filtering="mipmap")))

    if wu > 8:  # flip-out legs at the back, just inside the back feet (a number pad just sits flat on its feet)
        legs = part("legs", "flip-out legs", ["bottom_case"], lift=(0, -1, 0))
        leg = 1.6
        for side in (-1, 1):
            x = spots[3 if side > 0 else 2][0] - side * (0.42 + 0.3 + leg / 2)  # (a gap between it and the foot)
            legs.box((x, -0.04, cd / 2 - 0.45), (leg + 0.1, 0.08, 0.18), fixed=(60, 62, 70))  # the hinge
            # folded flat, a leg is no deeper than the feet, so the keyboard stands on its feet, not on its legs
            legs.box((x, -0.06, cd / 2 - 0.85), (leg, 0.08, 0.7), "legs")
            legs.box((x, -0.1, cd / 2 - 1.15), (leg - 0.2, 0.02, 0.12), fixed=RUBBER, hit=False)  # its rubber tip

    usb = part("usb_board", "USB board", ["bottom_case"])
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
    if weight_at:  # a heavy brass bar on the floor: it makes the keyboard sit solid and sound deeper
        ww, wd = weight_at
        weight = part("weight", "brass weight", ["bottom_case"])
        weight.box((0, FLOOR + 0.07, 0), (ww, 0.14, wd), fixed=(204, 166, 92))
        for k in range(3):  # brushed lines, and the maker's mark
            weight.box((0, FLOOR + 0.142, -wd / 2 + (k + 1) * wd / 4), (ww - 0.4, 0.004, 0.03), fixed=(180, 144, 78),
                       hit=False)
        weight.post((ww / 2 - 0.6, FLOOR + 0.14, 0), 0.22, 0.008, fixed=(224, 190, 116), hit=False)
        under_foam.append("weight")
        holes.append((-ww / 2 - 0.1, ww / 2 + 0.1, -wd / 2 - 0.1, wd / 2 + 0.1))
    if battery_at:  # a flat battery pouch on the floor, in a hole in the foam (between the ribs on the floor)
        bx, bz, bw, bd = battery_at
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
    for i in long_keys:  # the holes the stabilisers' housings clip through
        wide, ends = stab_ends(*keys[i][1:])
        for ex, ez in ends:
            pcb.box((ex, top + 0.006, ez), (0.22, 0.012, 0.36) if wide else (0.36, 0.012, 0.22), fixed=BLACK, hit=False)
    # the chip that reads the keys, with its pins, its crystal and its capacitors (see mcu, above)
    mx, mz = mcu if mcu else (0.0, 0.0)
    face, up = (top, 1) if mcu else (PCB_Y - 0.06, -1)  # (on top, or on the underside)
    pcb.box((mx, face + up * 0.04, mz), (0.9, 0.08, 0.9), fixed=BLACK, hit=False)
    for k in range(8):
        off = -0.35 + k * 0.1
        for dx, dz in ((off, 0.5), (off, -0.5), (0.5, off), (-0.5, off)):
            pcb.box((mx + dx, face + up * 0.012, mz + dz), (0.05 if abs(dz) == 0.5 else 0.12, 0.024,
                                                           0.12 if abs(dz) == 0.5 else 0.05), fixed=SILVER, hit=False)
    pcb.box((mx + 0.72, face + up * 0.05, mz + 0.12), (0.2, 0.1, 0.42), fixed=SILVER, hit=False)  # the crystal
    for k in range(5):
        pcb.box((mx - 0.62, face + up * 0.02, mz - 0.4 + k * 0.2), (0.06, 0.04, 0.1), fixed=(190, 150, 100), hit=False)
    pcb.box((px - 1.0, top + 0.07, hu / 2 + 0.02), (0.5, 0.14, 0.2), fixed=WHITE, hit=False)  # the cable's socket
    for x, z in spots:  # the mounting holes: a plated ring round each, for the screw's post to bear on
        pcb.post((x, top, z), 0.15, 0.01, fixed=GOLDEN, hit=False)
        pcb.post((x, top, z), 0.07, 0.012, fixed=BLACK, hit=False)
    if knob_at:  # the knob's encoder, soldered on, its shaft up through the plate (the knob itself pulls off)
        kx, kz = knob_at
        pcb.box((kx, top + 0.15, kz), (0.62, 0.3, 0.62), fixed=(40, 42, 48), hit=False)
        pcb.post((kx, top + 0.3, kz), 0.12, CAP_Y + 0.2 - top - 0.3, fixed=SILVER, hit=False)

    later = []  # what has to be off before the plate foam and the plate go on
    if battery_at:  # the battery's lead: up the back, round the board's edge, and plugged in on top
        bx, bz, bw, bd = battery_at
        lx = lead_x
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
    if spec.get("special") == "fn_layer":  # the arrows its Fn layer puts on I, J, K and L
        used += [KEY_LEGENDS[a] for a in ("Up", "Left", "Down", "Right")]
    atlas, where = legend_atlas([t for t in used if t])
    board.legend_where = where
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
    # its lock lights: Num, Caps and Scroll Lock on a board with a number pad or a Scroll Lock key; just the one on a
    # number pad (Num Lock) or a small board (Caps Lock)
    lights = 1 if spec["size"] in ("numpad", "60", "65", "75") else 3
    for k in range(lights):
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

    special = spec.get("special")
    if special == "sticky":  # a spilled drink, dried round one of the letters: its switch sticks down
        sticky = rnd.choice([i for i, k in enumerate(keys) if len(k[0]) == 1 and k[0].isalpha()])
        _, cx, cz, _, _ = keys[sticky]
        spill = Shapes()
        for dx, dz, w, d, col in ((0, 0, 1.06, 0.98, (150, 104, 52)), (0.12, -0.1, 0.84, 1.2, (166, 118, 60)),
                                  (-0.16, 0.12, 0.7, 0.86, (138, 94, 46)), (0.3, 0.3, 0.4, 0.36, (176, 128, 66))):
            spill.use(col).box((cx + dx, PLATE_Y + 0.041 + 0.002 * (dx > 0), cz + dz), (w, 0.004, d))
        board.special["sticky"] = sticky
        board.special["spill"] = spill.mesh(plate.root, "spill").np  # (it shows through round the switch)
    if special == "pair":  # a little status light on the frame, by the lock lights: it blinks blue to pair
        light = Shapes().use((255, 255, 255), "light")
        light.box((cw / 2 - 0.9 - lights * 0.45, FRAME_Y[1] + 0.012, cd / 2 - 0.27), (0.2, 0.024, 0.2))
        frame_part = next(p for p in parts if p.key == "top_frame")
        board.special["light"] = light.mesh(frame_part.root, "pairing light", shadow=False)
        board.special["light"].paint(0, "light", (40, 52, 70))

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
        more = spec.get("dirt", 1.0) * MESS_MOST
        specks = []
        for _ in range(round(min(38, 4 + len(keys) / 2.4) * more)):  # (a small keyboard has less room for crumbs)
            x, z = gap_point()
            specks.append((rnd.choice(("dust", "dust", "crumb", "crumb", "hair")) if len(specks) % 9 else "hair",
                           x, PLATE_Y + 0.04, z, rnd))
        board.dirt.append(Dirt(plate, specks, least=12 if special == "shake" else 0))  # (enough to shake out)
        specks = []
        for _ in range(round(min(14, 3 + len(keys) / 7) * more)):
            x, z = rnd.uniform(-wu / 2 + 0.3, wu / 2 - 0.3), rnd.uniform(-hu / 2 + 0.3, hu / 2 - 0.3)
            specks.append((rnd.choice(("dust", "dust", "crumb")), x, top + 0.02, z, rnd))
        board.dirt.append(Dirt(pcb, specks))
        kind = rnd.choice(TRINKETS)
        if rnd.random() < 0.2:  # (not always something lost in there)
            pass
        elif rnd.random() < 0.6:
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

    # The sensor looks down through the floor, near the middle; in a wireless mouse the battery is there, so the
    # sensor sits in front of it, just behind the wheel (it clears the wheel's underside).
    sensor_t = 0.67 if wireless else 0.45
    sz = z(sensor_t)
    bay = (0.115, 0.585) if wireless else None  # the battery's bay, in the floor: long enough to lift an AA out of
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
    else:  # its on/off switch, on the bottom, in front of the sensor
        shell.box((0, -0.004, z(0.8)), (0.5, 0.01, 0.22), fixed=BLACK, hit=False)
        shell.box((-0.1, -0.012, z(0.8)), (0.18, 0.012, 0.16), fixed=spec["accent"], hit=False)

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
    t0 = 0.595 if wireless else 0.14  # where the board starts (a wireless one's, just past the battery's + end)
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
        if side == -1 and spec.get("special") == "double_click":  # the worn left one, to click on by itself
            pcb.target((x, y1 + 0.16, z(switch_t)), (0.56, 0.34, 0.48), ("left switch",))
    wheel_t, R = 0.79, 0.4
    wz = z(wheel_t)
    wy = top(wheel_t) - R + 0.14  # (it pokes up out of the slot between the buttons)
    pcb.box((0.31, (y1 + wy + 0.12) / 2, wz), (0.22, wy + 0.12 - y1, 0.46), fixed=(58, 60, 66), hit=False)  # encoder
    pcb.box((-0.31, (y1 + wy + 0.06) / 2, wz), (0.06, wy + 0.06 - y1, 0.2), fixed=(58, 60, 66), hit=False)  # bracket
    pcb.box((0, y1 + 0.09, sz), (0.7, 0.18, 0.78), fixed=BLACK, hit=False)  # the sensor
    for k in range(4):
        for side in (-1, 1):
            pcb.box((side * 0.38, y1 + 0.02, sz - 0.27 + k * 0.18), (0.08, 0.03, 0.06), fixed=SILVER, hit=False)
    led = (-0.45, sz + 0.44) if wireless else (0.3, sz - 0.48)  # its red light (on the board, beside the sensor)
    pcb.box((led[0], y1 + 0.03, led[1]), (0.12, 0.06, 0.12), fixed=(210, 50, 50), hit=False)
    chip_x, chip_t = (-0.75, 0.68) if wireless else (-0.45, 0.3)
    pcb.box((chip_x, y1 + 0.03, z(chip_t)), (0.5, 0.06, 0.5), fixed=BLACK, hit=False)
    for k in range(0 if wireless else 3):
        pcb.box((0.25 + k * 0.18, y1 + 0.02, z(chip_t)), (0.1, 0.04, 0.06), fixed=(190, 150, 100), hit=False)
    if spec.get("rgb"):  # the lights for its logo
        for k in range(3):
            pcb.box((-0.25 + k * 0.25, y1 + 0.03, z(0.24)), (0.14, 0.06, 0.14), fixed=WHITE, hit=False)
    sx_, sz_ = (0.62, z(0.66)) if wireless else (0.55, z(0.6))  # its little screw's hole (clear of the sensor's pins)
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
        side_board.wire([(sxb + 0.03, 0.6, z(side_t)), (sxb + 0.25, 0.6, z(side_t)),  # (bent along: wire() draws
                         (sxb + 0.25, y1 + 0.03, z(side_t)), (sxb + 0.45, y1 + 0.03, z(side_t))],  # straight runs)
                        0.05, (220, 180, 90))
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
        nose = L / 2 - 0.22  # (it runs up its own side to the nose, then across: clear of a screw in the middle)
        cable.wire([(plug_at[0], y1 + 0.26, plug_at[1]), (plug_at[0], cy, plug_at[1]), (plug_at[0], cy, nose),
                    (0, cy, nose), (0, cy, L / 2 - 0.1)], 0.06, (40, 40, 44))
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
    dpi_light = None
    if spec.get("special") == "dpi":  # a DPI button in the slot behind the wheel, and a light that shows its speed
        p = dome(0.05)(0.69, math.pi / 2)
        top_shell.box((0, p[1] + 0.03, p[2]), (0.17, 0.08, 0.3), fixed=(54, 56, 64), hit=False)
        top_shell.target((0, p[1] + 0.05, p[2]), (0.36, 0.3, 0.42), ("dpi",))
        q = dome()(0.6, math.pi / 2)
        dpi_light = Shapes().use((255, 255, 255), "light")
        dpi_light.box((0, q[1] + 0.006, q[2]), (0.1, 0.02, 0.22))

    # Underneath: the screws, each under a foot, up through a boss in the bottom shell into the top shell. The
    # front ones are in front of the main switches; where one goes up through the circuit board, the board has a
    # hole for it, and rests on its boss.
    n = spec["feet"]
    if n == 2:
        spots, feet = [(0, 0.1), (0, 0.93)], [(0, 0.1, 1.5, 0.32), (0, 0.92, 1.7, 0.28)]
    elif n == 3:
        spots = [(0, 0.07), (-0.5, 0.93), (0.5, 0.93)]
        feet = [(0, 0.07, 1.2, 0.3), (-0.5, 0.93, 0.42, 0.42), (0.5, 0.93, 0.42, 0.42)]
    else:
        spots = [(-0.55, 0.11), (0.55, 0.11), (-0.55, 0.92), (0.55, 0.92)]
        feet = [(x, t, 0.5, 0.5) for x, t in spots]
    screws = []
    for i, (fx, t) in enumerate(spots):
        x = fx * half(t) * 1.25
        zz = z(t)
        through = t0 <= t <= 0.95  # (it goes up through the circuit board)
        boss_top = y0 if through else MOUSE_BASE
        shell.post((x, MOUSE_FLOOR, zz), 0.15, boss_top - MOUSE_FLOOR, "inside", hit=False)  # its boss
        shell.post((x, boss_top, zz), 0.06, 0.004, fixed=BLACK, hit=False)
        if through:
            pcb.post((x, y1, zz), 0.15, 0.006, fixed=GOLDEN, hit=False)
            pcb.post((x, y1, zz), 0.065, 0.008, fixed=BLACK, hit=False)
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
        bm = (bz0 + bz1) / 2 - 0.06  # (its + nub sticks out the front: so centred, all of it fits in the bay)
        battery = part("mouse_battery", "AA battery", ["bottom_shell", "top_shell"], lift=(0, -1, 0))
        flat = spec.get("special") == "battery"  # (it came in with a tired old one, faded and scuffed)
        battery.shapes.use((128, 132, 120) if flat else (70, 150, 96)).axle((-0.2, 0.38, bm), 0.36, 2.4, 18,
                                                                           along="z")
        battery.shapes.use((150, 140, 112) if flat else (212, 176, 90)).axle((-0.2, 0.38, bm + 0.8), 0.365, 0.4, 18,
                                                                              along="z")
        battery.shapes.use(SILVER).axle((-0.2, 0.38, bm + 1.26), 0.12, 0.12, 10, along="z")  # its + end
        if flat:  # and a fresh one, ready to swap in
            fresh = Shapes()
            fresh.use((70, 150, 96)).axle((-0.2, 0.38, bm), 0.36, 2.4, 18, along="z")
            fresh.use((212, 176, 90)).axle((-0.2, 0.38, bm + 0.8), 0.365, 0.4, 18, along="z")
            fresh.use((236, 236, 230)).axle((-0.2, 0.38, bm - 0.4), 0.37, 0.5, 18, along="z")  # its white band
            fresh.use(SILVER).axle((-0.2, 0.38, bm + 1.26), 0.12, 0.12, 10, along="z")
            board.special["fresh"] = fresh
        battery.grow((-0.2, 0.38, bm), (0.74, 0.74, 2.6))
        battery.target((-0.2, 0.38, bm), (0.74, 0.74, 2.6))
        receiver = part("receiver", "USB receiver", ["bottom_shell", "top_shell"], lift=(0, -1, 0))
        receiver.box((0.42, 0.12, bm - 0.15), (0.3, 0.14, 0.7), fixed=(40, 42, 48))
        receiver.box((0.42, 0.12, bm + 0.32), (0.26, 0.1, 0.3), fixed=SILVER)
        cover = part("battery_cover", "battery cover", ["mouse_battery", "receiver"], lift=(0, -1, 0))
        cover.box((0, -0.012, (bz0 + bz1) / 2), (bw + 0.2, 0.03, bz1 - bz0 + 0.16), "inside")
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
    if dpi_light is not None:
        board.mouse["dpi"] = dpi_light.mesh(top_shell.root, "DPI light", shadow=False)
        board.mouse["dpi"].paint(0, "light", (226, 92, 80))  # (its first speed: red)
    if "fresh" in board.special:  # the fresh battery, hidden away until it's swapped in
        battery = next(p for p in parts if p.key == "mouse_battery")
        board.special["old"] = battery.mesh.np
        board.special["fresh"] = board.special["fresh"].mesh(battery.root, "fresh battery").np
        board.special["fresh"].stash()
    for p in parts:
        if p.paintable:
            p.repaint(part_colours(spec, None))
    board.mouse["wheel"] = wheel
    board.mouse["sensor"] = (0, sz)

    if extras:  # hair caught round the wheel, dust on the board, crumbs in the bottom
        specks = []
        for _ in range(5):  # caught round the wheel's axle
            specks.append(("hair", rnd.uniform(-0.2, 0.2), y1 + 0.02, wz + rnd.uniform(-0.5, 0.5), rnd))
        for _ in range(16):
            t = rnd.uniform(t0 + 0.04, 0.9)
            specks.append((rnd.choice(("dust", "dust", "hair", "crumb")), rnd.uniform(-0.5, 0.5) * half(t), y1 + 0.02,
                           z(t), rnd))
        board.dirt.append(Dirt(pcb, specks))
        specks = []
        for _ in range(15):
            t = rnd.uniform(0.1, 0.9)
            if bay and bay[0] - 0.03 < t < bay[1] + 0.03:
                continue
            specks.append((rnd.choice(("crumb", "dust", "crumb")), rnd.uniform(-0.6, 0.6) * half(t),
                           MOUSE_FLOOR + 0.01, z(t), rnd))
        board.dirt.append(Dirt(shell, specks))
    board.caps, board.switches = KeySet("keycap", kb, Shapes()), KeySet("switch", kb, Shapes())
    return board


# ---- microphones ----

def ball_profile(radius, t1=math.pi, tip=-1, steps=12):
    """A ball as a lathe profile, from its tip (along the axis, the way tip says) round to t1 radians (pi is all the
    way round; less leaves it open at the back, the way a grille is where it screws on)."""
    return [(tip * radius * math.cos(t1 * k / steps), radius * math.sin(t1 * k / steps)) for k in range(steps + 1)]


def mesh_lines(part, center, radius, axis="x", tip=-1, t1=math.pi, rings=5, spokes=12, colour=(150, 152, 160),
               thick=0.024):
    """A ball grille's wire mesh, just proud of the ball: rings round it, and lines over it from its tip."""
    R = radius * 1.012

    def at(t, a):
        along, r = tip * R * math.cos(t), R * math.sin(t)
        c, s = r * math.cos(a), r * math.sin(a)
        x, y, z = center
        p = (x + along, y + c, z + s) if axis == "x" else (x + c, y + along, z + s) if axis == "y" else \
            (x + c, y + s, z + along)
        return part.rel(p)
    s = part.shapes.use(colour)
    for k in range(1, rings + 1):
        t = t1 * k / (rings + 1)
        pts = [at(t, 2 * math.pi * j / 18) for j in range(19)]
        for a, b in zip(pts, pts[1:]):
            s.rod(a, b, thick)
    for j in range(spokes):
        pts = [at(0.14 + (t1 - 0.14) * k / 8, 2 * math.pi * j / spokes) for k in range(9)]
        for a, b in zip(pts, pts[1:]):
            s.rod(a, b, thick)


def knurl(part, center, radius, length, axis="x", n=14, colour=(150, 152, 160)):
    """Ridges round a collar or a knob, the grip your fingers turn it by."""
    x, y, z = center
    s = part.shapes.use(colour)
    for k in range(n):
        a = 2 * math.pi * k / n
        c, d = math.cos(a) * radius, math.sin(a) * radius
        if axis == "x":
            s.rod(part.rel((x - length / 2, y + c, z + d)), part.rel((x + length / 2, y + c, z + d)), 0.04)
        elif axis == "y":
            s.rod(part.rel((x + c, y - length / 2, z + d)), part.rel((x + c, y + length / 2, z + d)), 0.04)
        else:
            s.rod(part.rel((x + c, y + d, z - length / 2)), part.rel((x + c, y + d, z + length / 2)), 0.04)


def specks_on(rnd, n, where, kinds=("dust", "dust", "hair", "crumb")):
    """Specks of dust (or crumbs, or hair) at spots where() picks: n on a dusty one (so, for Dirt to pick from, as
    many as on the messiest)."""
    return [(rnd.choice(kinds), *where(), rnd) for _ in range(round(n * MESS_MOST))]


def build_stage_mic(board, part, spec, rnd, extras):
    """A dynamic stage mic, lying on its side: the handle, the ball grille that screws onto it (with a foam
    windscreen lining it), the capsule on its rubber shock mount, the XLR insert in the tail held by a grub screw
    underneath, and the cable."""
    cy, gx, R = 1.3, -3.3, 1.3
    body = part("body", "handle")
    body.lathe([(-2.15, 0.0), (-2.15, 0.96), (-1.8, 1.02), (-1.45, 0.97), (-1.2, 0.9), (4.3, 0.64), (4.55, 0.6),
                (4.55, 0.5)], "x", (0, cy, 0), "case", hit=False)
    body.lathe([(-1.66, 1.035), (-1.5, 1.012)], "x", (0, cy, 0), fixed=spec["accent"], hit=False)  # a coloured band
    body.target((1.0, cy, 0), (5.8, 1.9, 1.9))  # (not round the tail, where the XLR insert is)
    sy = cy - 0.64  # (the underside of the handle there)
    body.post((4.3, sy, 0), 0.13, -0.012, fixed=(24, 26, 30), tag=("hole", 0))  # the grub screw's hole
    mount = part("shock_mount", "shock mount", ["body"], lift=(-1, 0.3, 0))
    mount.lathe([(-2.3, 0.5), (-2.3, 0.84), (-1.9, 0.84), (-1.9, 0.5)], "x", (0, cy, 0), fixed=RUBBER)
    mount.material = "rubber"
    capsule = part("capsule", "capsule", ["shock_mount"], lift=(-1, 0.3, 0))
    capsule.lathe([(-3.95, 0.0), (-3.95, 0.6), (-3.8, 0.7), (-2.3, 0.7), (-2.3, 0.0)], "x", (0, cy, 0),
                  fixed=(48, 48, 54))
    capsule.lathe([(-3.97, 0.0), (-3.97, 0.48)], "x", (0, cy, 0), fixed=(132, 134, 142), hit=False)  # its front
    capsule.material = "board"
    foam = part("foam", "foam windscreen", ["capsule"], lift=(-1, 0.35, 0))
    foam.lathe(ball_profile(1.2, 2.5), "x", (gx, cy, 0), "foam")
    foam.material, foam.grimy = "foam", True
    grille = part("grille", "ball grille", ["foam", "body"], lift=(-1, 0, 0), origin=(gx, cy, 0))
    grille.lathe(ball_profile(R, 2.42) + [(1.0, 0.99), (1.18, 0.99)], "x", (gx, cy, 0), fixed=(204, 206, 212))
    mesh_lines(grille, (gx, cy, 0), R, "x", -1, 2.42, rings=5, spokes=14)
    grille.twist, grille.material = "x", "metal"
    insert = part("xlr_insert", "XLR insert", ["body", "capsule"], lift=(1, 0, 0))
    insert.lathe([(4.05, 0.0), (4.05, 0.49), (4.62, 0.49), (4.62, 0.0)], "x", (0, cy, 0), fixed=(36, 36, 42))
    for py, pz in ((0.2, 0.0), (-0.12, -0.17), (-0.12, 0.17)):  # its three pins
        insert.shapes.use(SILVER).axle(insert.rel((4.68, cy + py, pz)), 0.055, 0.12, 8)
    insert.material = "cable"
    screw = part("screw0", "grub screw", ["xlr_insert"], lift=(0, -1, 0), screw=True, origin=(4.3, sy, 0))
    screw.post((4.3, sy, 0), 0.11, -0.03, fixed=SILVER)
    screw.box((4.3, sy - 0.032, 0), (0.18, 0.01, 0.035), fixed=(108, 110, 120), hit=False)
    cable = part("cable", "XLR cable", ["xlr_insert"], lift=(1, 0.25, 0))
    cable.lathe([(4.64, 0.0), (4.64, 0.56), (5.9, 0.52), (6.25, 0.32), (6.6, 0.2), (6.6, 0.0)], "x", (0, cy, 0),
                "cable")
    route = [(6.6, cy, 0), (7.3, cy - 0.25, 0.4), (7.9, cy - 0.45, 1.3), (8.2, cy - 0.55, 2.6)]
    for a, b in zip(route, route[1:]):
        cable.colour("cable", None).rod(a, b, 0.2)
    cable.grow((7.4, cy - 0.3, 1.2), (1.8, 0.6, 2.8))
    cable.material = "cable"
    if extras:  # dust on the capsule, under the grille; and on the handle, from years of hands
        board.dirt.append(Dirt(capsule, specks_on(rnd, 8, lambda: (rnd.uniform(-3.7, -2.5), cy + 0.71,
                                                                 rnd.uniform(-0.3, 0.3)))))
        def on_handle():
            x = rnd.uniform(-0.8, 3.8)
            return x, cy + 0.9 - (x + 1.2) * 0.26 / 5.5, rnd.uniform(-0.15, 0.15)
        board.dirt.append(Dirt(body, specks_on(rnd, 6, on_handle, ("dust", "dust", "hair"))))
    board.size = board.inner = (11.4, 3.2)
    board.height = cy + R


def build_lav_mic(board, part, spec, rnd, extras):
    """A lavalier: the tiny capsule (big on the bench), its foam windscreen and tie clip, and the long thin cable
    to its little locking connector. The cable has tied itself in knots."""
    cy, cz = 0.66, -0.9  # the capsule's axis (its foam ball rests on the mat, as the cable does)
    lie = 0.06  # the cable's middle, lying on the mat
    pts = []
    for k in range(41):  # the cable, from the middle of the capsule's tail, down onto the mat and across it
        t = k / 40
        x = -1.85 + 4.35 * t
        z = cz + (0.7 - cz) * t + 1.1 * math.sin(math.pi * 3 * t) * (1 - abs(2 * t - 1)) ** 0.5
        y = lie + (cy - lie) * max(0.0, 1 - k / 3) ** 2 if k < 40 else 0.3  # (and up into its connector)
        pts.append((x, y, z))
    cable = part("cable", "cable")
    for a, b in zip(pts, pts[1:]):
        cable.colour("cable", None).rod(a, b, 0.12)
    for k in range(0, 40, 4):
        cable.target(pts[k], (0.42, 0.32, 0.42))
    cable.grow((0.3, cy / 2, 0.0), (4.6, cy + 0.1, 3.6))
    cable.material = "cable"
    knots = []
    spots = sorted(rnd.sample((7, 13, 19, 25, 31), rnd.randint(2, 4)))  # (along it, somewhere: never two together)
    for k, i in enumerate(i + rnd.randint(-1, 1) for i in spots):  # each knot, a little loop of the cable pulled tight
        x, y, z = pts[i]
        knot = Shapes().use(spec["cable"])
        loop = [(x + 0.22 * math.sin(2 * math.pi * j / 12), y + 0.22 * (1 - math.cos(2 * math.pi * j / 12)), z +
                 0.08 * math.sin(4 * math.pi * j / 12)) for j in range(13)]
        for a, b in zip(loop, loop[1:]):
            knot.rod(a, b, 0.1)
        knot.box((x, y + 0.04, z), (0.24, 0.16, 0.2))
        knots.append(knot)
        cable.target((x, y + 0.2, z), (0.62, 0.6, 0.62), ("knot", k))
    capsule = part("capsule", "capsule", ["cable"], lift=(0, 1, 0))
    capsule.lathe([(-3.25, 0.0), (-3.25, 0.4), (-3.1, 0.44), (-2.0, 0.44), (-1.85, 0.22), (-1.85, 0.0)], "x",
                  (0, cy, cz), "case")
    capsule.lathe([(-3.27, 0.0), (-3.27, 0.3)], "x", (0, cy, cz), fixed=(150, 152, 160), hit=False)
    capsule.material = "board"
    foam = part("foam", "foam windscreen", ["capsule"], lift=(-1, 0.6, 0))
    foam.lathe(ball_profile(0.66, 2.3), "x", (-3.05, cy, cz), fixed=(56, 56, 62))
    foam.material = "foam"
    clip = part("clip", "tie clip", ["capsule"], lift=(0, 1, 0))
    for dy in (0.48, -0.48):  # its jaws, round the capsule
        clip.box((-2.4, cy + dy, cz), (0.5, 0.08, 0.5), fixed=SILVER)
    clip.box((-2.4, cy, cz + 0.52), (0.5, 1.04, 0.08), fixed=SILVER)
    for dy in (0.12, -0.1):  # and the spring clip, for a shirt or a tie
        clip.box((-2.4, cy + dy, cz + 1.1), (0.44, 0.06, 1.1), fixed=(176, 178, 186))
    clip.material = "metal"
    con = part("connector", "TA4 connector", ["cable"], lift=(1, 0.3, 0))
    con.lathe([(2.5, 0.0), (2.5, 0.22), (2.7, 0.3), (3.7, 0.3), (3.76, 0.0)], "x", (0, 0.3, 0.7), fixed=(34, 34, 40))
    con.material = "cable"
    collar = part("collar", "locking collar", ["connector"], lift=(1, 0, 0), origin=(3.25, 0.3, 0.7))
    collar.lathe([(2.95, 0.31), (2.95, 0.37), (3.55, 0.37), (3.55, 0.31)], "x", (0, 0.3, 0.7), fixed=SILVER)
    knurl(collar, (3.25, 0.3, 0.7), 0.375, 0.5, "x")
    collar.twist, collar.material = "x", "metal"
    board.special["knots"] = knots  # (meshed once the cable is: see build_mic)
    if extras:  # lint and dust along the cable
        board.dirt.append(Dirt(cable, [(rnd.choice(("dust", "dust", "hair")), pts[k][0], lie + 0.07, pts[k][2], rnd)
                                       for k in rnd.sample(range(3, 38), 16)]))
    board.size = board.inner = (8.6, 4.2)
    board.height = cy + 0.66


def build_podcast_mic(board, part, spec, rnd, extras):
    """A USB podcast mic standing in its yoke on a desk stand: the stand, the yoke, the body (its mute button and
    its light on the front), the thumb screws that hold it in the yoke, the gain knob, the capsule under the
    grille that screws off the top, and round the back the USB board under a panel held by a screw, and the
    cable."""
    base = part("base", "stand base")
    base.post((0, 0, 0), 2.1, 0.3, "inside", segments=28)
    base.post((0, 0.3, 0), 0.3, 0.32, fixed=SILVER, hit=False)  # the stem the yoke turns on
    for k in range(4):  # rubber feet underneath, so it doesn't slide about the desk
        a = math.pi / 4 + k * math.pi / 2
        base.post((math.cos(a) * 1.6, 0, math.sin(a) * 1.6), 0.26, -0.06, fixed=RUBBER, hit=False)
    base.material = "metal"
    yoke = part("yoke", "yoke", ["base"])
    yoke.box((0, 0.72, 0), (3.3, 0.2, 0.5), "frame")
    for i, x in enumerate((-1.55, 1.55)):
        yoke.box((x, 2.0, 0), (0.2, 2.6, 0.5), "frame")
        yoke.target((x * 1.12, 3.0, 0), (0.5, 0.8, 0.8), ("hole", i))  # where its thumb screw goes in
    yoke.material = "metal"
    body = part("body", "mic body", ["yoke"])
    # The body: round, with an opening in its back for the USB board, under the back panel (so the board shows
    # once the panel's off), and a recess inside that the board sits in. The panel's screw goes into the body just
    # above the opening.
    lo, hi = 1.55, 2.97  # (the opening, bottom to top)
    body.lathe([(1.4, 0.0), (1.4, 0.98), (1.5, 1.05), (lo, 1.05)], "y", (0, 0, 0), "case", hit=False, segments=48)
    body.lathe([(hi, 1.05), (5.95, 1.05), (6.05, 1.0), (6.05, 0.0)], "y", (0, 0, 0), "case", hit=False, segments=48)
    gap = math.radians(22.5)  # half the opening, round the body (0.8 wide): its edges on the round parts' facets
    body.colour("case", None).surface(lambda u, v: (math.cos(v) * 1.05, lo + (hi - lo) * u, math.sin(v) * 1.05),
                                      0, 1, 2, math.pi / 2 + gap, math.pi / 2 - gap + 2 * math.pi, 42,
                                      lambda p: (0, p[1], 0))
    recess, side = (40, 40, 44), 1.05 * math.sin(gap)
    body.box((0, (lo + hi) / 2, 0.5), (2 * side, hi - lo, 0.06), fixed=recess, hit=False)  # its back wall
    for x in (-side, side):  # and its sides
        body.box((x, (lo + hi) / 2, 0.74), (0.02, hi - lo, 0.48), fixed=recess, hit=False)
    for y in (lo, hi):  # bottom and top
        body.box((0, y, 0.74), (2 * side, 0.02, 0.48), fixed=recess, hit=False)
    body.target((0, 3.72, -0.28), (2.1, 4.65, 1.55))  # (all but the bottom of its back, where the USB board is)
    body.target((0, 4.68, 0.78), (2.1, 2.74, 0.55))
    body.shapes.use((64, 64, 70)).axle(body.rel((0, 5.25, -1.07)), 0.22, 0.12, 18, along="z")  # the mute button
    body.target((0, 5.25, -1.15), (0.6, 0.6, 0.4), ("mute",))
    light = Shapes().use((255, 255, 255), "light")
    light.box((0, 5.72, -1.03), (0.38, 0.08, 0.06))
    for i, x in enumerate((-1.75, 1.75)):  # the thumb screws, through the yoke into the body
        s = part(f"screw{i}", "thumb screw", ["body"], lift=(math.copysign(1, x), 0, 0), screw=True,
                 origin=(x, 3.0, 0))
        s.shapes.use((54, 56, 62)).axle(s.rel((x, 3.0, 0)), 0.36, 0.26, 18)
        knurl(s, (x, 3.0, 0), 0.37, 0.24, "x", 12, (40, 42, 48))
        s.shapes.use(SILVER).axle(s.rel((math.copysign(1.31, x), 3.0, 0)), 0.09, 0.62, 8)  # (through the yoke, in)
        s.grow((x, 3.0, 0), (0.3, 0.74, 0.74))
        s.target((x, 3.0, 0), (0.34, 0.8, 0.8))
        s.thumb, s.spin = True, "x"
    knob = part("gain_knob", "gain knob", ["body"], lift=(0, 0, -1), origin=(0, 3.2, -1.25))
    knob.shapes.use(spec["accent"]).axle(knob.rel((0, 3.2, -1.25)), 0.4, 0.34, 22, along="z")
    knob.box((0, 3.45, -1.43), (0.07, 0.22, 0.02), fixed=CREAM, hit=False)  # its mark
    knob.grow((0, 3.2, -1.25), (0.8, 0.8, 0.34))
    knob.target((0, 3.2, -1.25), (0.84, 0.84, 0.4))
    knob.spin, knob.material = "z", "cable"
    capsule = part("capsule", "capsule", ["body"], lift=(0, 1, 0))
    capsule.lathe([(5.4, 0.0), (5.4, 0.72), (6.5, 0.72), (6.5, 0.0)], "y", (0, 0, 0), fixed=(212, 176, 90))
    capsule.lathe([(6.52, 0.0), (6.52, 0.55)], "y", (0, 0, 0), fixed=(236, 206, 120), hit=False)
    capsule.material = "board"
    grille = part("grille", "grille", ["capsule"], lift=(0, 1, 0), origin=(0, 6.9, 0))
    dome = [(5.98, 1.03), (6.1, 1.08), (7.0, 1.08)] + [(7.0 + 0.8 * math.sin(math.pi / 2 * k / 8),
                                                        1.08 * math.cos(math.pi / 2 * k / 8)) for k in range(1, 9)]
    grille.lathe(dome, "y", (0, 0, 0), fixed=(206, 208, 214))
    for k in range(5):  # its mesh: rings round it, and lines up it
        grille.shapes.use((150, 152, 160)).ring(grille.rel((0, 6.25 + k * 0.2, 0)), 1.092, 0.024)
    for j in range(16):
        a = 2 * math.pi * j / 16
        c, s_ = math.cos(a) * 1.092, math.sin(a) * 1.092
        grille.shapes.use((150, 152, 160)).rod(grille.rel((c, 6.15, s_)), grille.rel((c, 7.0, s_)), 0.024)
    grille.twist, grille.material = "y", "metal"
    usb = part("usb_board", "USB board", ["body"], lift=(0, 0, 1))
    usb.box((0, 2.26, 0.62), (0.76, 1.3, 0.1), fixed=PCB_GREEN)  # (in the recess: it comes out through the opening)
    usb.box((0, 1.8, 0.86), (0.5, 0.2, 0.36), fixed=SILVER, hit=False)  # the USB-C socket, out to the panel
    usb.box((0, 2.75, 0.85), (0.3, 0.3, 0.36), fixed=BLACK, hit=False)  # the headphone jack, behind its socket
    usb.box((0, 2.25, 0.72), (0.36, 0.36, 0.1), fixed=BLACK, hit=False)  # its chip
    usb.material = "board"
    panel = part("rear_panel", "back panel", ["usb_board"], lift=(0, 0, 1))
    panel.box((0, 2.35, 1.06), (1.0, 1.8, 0.08), "frame")
    panel.box((0, 1.8, 1.105), (0.36, 0.12, 0.02), fixed=BLACK, hit=False)  # the USB port's opening
    panel.box((0, 2.75, 1.105), (0.16, 0.16, 0.02), fixed=BLACK, hit=False)  # the headphone socket
    panel.target((0, 3.05, 1.1), (0.3, 0.3, 0.12), ("hole", 2))
    s = part("screw2", "panel screw", ["rear_panel"], lift=(0, 0, 1), screw=True, origin=(0, 3.05, 1.12))
    s.shapes.use(SILVER).axle(s.rel((0, 3.05, 1.13)), 0.1, 0.05, 12, along="z")
    s.box((0, 3.05, 1.157), (0.16, 0.03, 0.01), fixed=(108, 110, 120), hit=False)
    s.grow((0, 3.05, 1.13), (0.2, 0.2, 0.06))
    s.target((0, 3.05, 1.13), (0.26, 0.26, 0.1))
    s.spin = "z"
    cable = part("cable", "USB-C cable", ["rear_panel", "usb_board"], lift=(0, 0, 1))
    cable.box((0, 1.8, 1.37), (0.34, 0.2, 0.5), "cable")  # its plug: the grip outside,
    cable.box((0, 1.8, 1.05), (0.3, 0.09, 0.16), fixed=SILVER)  # and its metal tip, in through the panel to the socket
    route = [(0, 1.8, 1.62), (0, 1.62, 2.3), (0.2, 0.7, 2.85), (0.6, 0.18, 3.5), (1.4, 0.12, 4.3)]
    for a, b in zip(route, route[1:]):
        cable.colour("cable", None).rod(a, b, 0.14)
    cable.grow((0.6, 0.9, 3.0), (1.6, 1.8, 3.0))
    cable.material = "cable"
    board.mic["light"] = light  # (meshed onto the body once it's made: see build_mic)
    board.knob = knob
    if extras:  # dust on the stand's base, and on the capsule under the grille
        def on_base():
            a, r = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.6, 1.9)
            return math.cos(a) * r, 0.31, math.sin(a) * r
        board.dirt.append(Dirt(base, specks_on(rnd, 9, on_base, ("dust", "dust", "crumb", "hair"))))
        board.dirt.append(Dirt(capsule, specks_on(rnd, 4, lambda: (rnd.uniform(-0.4, 0.4), 6.53,
                                                                    rnd.uniform(-0.4, 0.4)), ("dust",))))
    board.size = board.inner = (5.0, 5.0)
    board.height = 7.8


def build_wireless_mic(board, part, spec, rnd, extras):
    """A wireless handheld mic, lying on its side: the body (its little screen, its light and its power switch on
    top), the ball grille and the capsule under it, and the sleeve that twists off the handle to show the two AA
    batteries, between their contacts."""
    cy, gx, R = 1.2, -3.55, 1.15
    body = part("body", "mic body")
    body.lathe([(-2.45, 0.0), (-2.45, 0.86), (-2.15, 0.93), (-1.85, 0.86), (0.95, 0.72), (1.0, 0.3), (1.0, 0.0)],
               "x", (0, cy, 0), "case", hit=False)
    body.lathe([(5.3, 0.0), (5.3, 0.62), (5.5, 0.6), (5.85, 0.42), (5.85, 0.0)], "x", (0, cy, 0), "case", hit=False)
    body.box((3.15, cy - 0.44, 0), (4.3, 0.1, 0.56), fixed=(60, 62, 70), hit=False)  # the spine the batteries lie on
    body.target((-0.75, cy, 0), (3.4, 1.8, 1.8))  # (its head end and its tail: the batteries lie between)
    body.target((5.58, cy, 0), (0.55, 1.3, 1.3))
    body.box((-0.55, cy + 0.805, 0), (0.6, 0.04, 0.4), fixed=(24, 28, 34), hit=False)  # its screen, on the handle
    body.box((0.45, cy + 0.74, 0), (0.34, 0.1, 0.2), fixed=(80, 82, 90), hit=False)  # its power switch
    body.target((0.45, cy + 0.78, 0), (0.5, 0.3, 0.42), ("power",))
    light = Shapes().use((255, 255, 255), "light")
    light.box((-0.55, cy + 0.83, 0), (0.4, 0.016, 0.24))
    crust = []
    crusty = rnd.choice(({0}, {1}, {0, 1}, {0, 1}))  # (which of them the leak got to)
    for k, x in enumerate((1.04, 5.26)):  # the battery contacts, at each end of the bay, crusted green-white
        body.box((x, cy, 0), (0.05, 0.36, 0.36), fixed=SILVER, hit=False)
        body.target((x, cy, 0), (0.42, 0.6, 0.6), ("contact", k))
        if k not in crusty:
            crust.append(None)
            continue
        lumps = Shapes()
        for _ in range(rnd.randint(4, 10)):
            s = rnd.uniform(0.06, 0.12)
            lumps.use(rnd.choice(((196, 218, 196), (150, 196, 168), (226, 232, 214)))).box(
                (x + (0.04 if k == 0 else -0.04), cy + rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15)),
                (s * 0.6, s, s))
        crust.append(lumps)
    capsule = part("capsule", "capsule", ["body"], lift=(-1, 0.3, 0))
    capsule.lathe([(-4.15, 0.0), (-4.15, 0.55), (-4.0, 0.62), (-2.5, 0.62), (-2.5, 0.0)], "x", (0, cy, 0),
                  fixed=(44, 44, 50))
    capsule.material = "board"
    grille = part("grille", "ball grille", ["capsule", "body"], lift=(-1, 0, 0), origin=(gx, cy, 0))
    grille.lathe(ball_profile(R, 2.45) + [(0.92, 0.88), (1.12, 0.88)], "x", (gx, cy, 0), fixed=(52, 54, 62))
    mesh_lines(grille, (gx, cy, 0), R, "x", -1, 2.45, rings=5, spokes=14, colour=(30, 30, 36))
    grille.twist, grille.material = "x", "metal"
    # Two AA batteries, end to end, + to -: the second one's + end against the flat contact at the tail, and the
    # first one's - end against a coil spring on the contact at the head end (it takes up the slack, as in a torch)
    spring = [(1.065 + 0.17 * j / 30, cy - 0.04 + 0.16 * math.cos(j * math.pi / 5), 0.16 * math.sin(j * math.pi / 5))
              for j in range(31)]
    for a, b in zip(spring, spring[1:]):
        body.shapes.use(SILVER).rod(body.rel(a), body.rel(b), 0.03)
    for k, bx in enumerate((2.185, 4.135)):
        b = part(f"battery{k}", "AA battery", ["body"], lift=(0, 1, 0))
        b.shapes.use((70, 150, 96)).axle(b.rel((bx, cy - 0.04, 0)), 0.34, 1.8, 18)
        b.shapes.use((212, 176, 90)).axle(b.rel((bx + 0.6, cy - 0.04, 0)), 0.345, 0.4, 18)
        b.shapes.use(SILVER).axle(b.rel((bx + 0.95, cy - 0.04, 0)), 0.11, 0.1, 10)
        b.grow((bx, cy, 0), (2.0, 0.7, 0.7))
        b.target((bx, cy, 0), (2.0, 0.7, 0.7))
        b.material = "metal"
    sleeve = part("sleeve", "battery sleeve", ["battery0", "battery1", "body"], lift=(1, 0, 0),
                  origin=(3.15, cy, 0))
    sleeve.lathe([(1.0, 0.7), (1.0, 0.74), (5.25, 0.6), (5.25, 0.55)], "x", (0, cy, 0), "case")
    sleeve.twist = "x"
    board.mic["light"] = light
    board.special["crust"] = crust
    if extras:  # dust on the capsule, and on the handle
        board.dirt.append(Dirt(capsule, specks_on(rnd, 7, lambda: (rnd.uniform(-3.9, -2.7), cy + 0.63,
                                                                 rnd.uniform(-0.3, 0.3)))))
        board.dirt.append(Dirt(body, specks_on(rnd, 5, lambda: (rnd.uniform(-1.6, 0.0), cy + 0.82,
                                                              rnd.uniform(-0.2, 0.2)), ("dust", "hair"))))
    board.size = board.inner = (10.6, 3.0)
    board.height = cy + R


def build_studio_mic(board, part, spec, rnd, extras):
    """A large-diaphragm studio condenser in its spider shock mount, on a little desk stand: the stand, the shock
    mount (its frame floats the mic on elastic bands), the thumb screw that clamps the mic in, the body, the
    capsule on top (screwed down, its gold diaphragm under the headbasket), the ring nut at the bottom and the
    XLR cable."""
    stand = part("stand", "desk stand")
    stand.post((0, 0, 1.0), 2.2, 0.28, "inside", segments=28)
    stand.post((0, 0.28, 2.45), 0.16, 3.3, fixed=SILVER, hit=False)  # its pole, at the back
    for k in range(4):  # rubber feet underneath
        a = math.pi / 4 + k * math.pi / 2
        stand.post((math.cos(a) * 1.7, 0, 1.0 + math.sin(a) * 1.7), 0.26, -0.06, fixed=RUBBER, hit=False)
    stand.box((0, 3.58, 2.15), (0.3, 0.3, 0.75), fixed=SILVER, hit=False)  # and the arm over to the mount
    stand.material = "metal"
    mount = part("shock_mount", "shock mount", ["stand"])
    for y in (2.7, 4.7):  # two hoops, each holding the mic on elastic bands
        mount.colour("frame", None).ring(mount.rel((0, y, 0)), 1.85, 0.12)
        mount.shapes.use((44, 44, 48)).ring(mount.rel((0, y, 0)), 1.24, 0.07)
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            p = (math.cos(a) * 1.24, y, math.sin(a) * 1.24)
            q = (math.cos(a + 0.6) * 1.85, y, math.sin(a + 0.6) * 1.85)
            mount.shapes.use((30, 30, 34)).rod(mount.rel(p), mount.rel(q), 0.05)
    for x in (-1.85, 1.85):
        mount.box((x, 3.7, 0), (0.12, 2.0, 0.12), "frame", hit=False)
    mount.box((0, 3.58, 1.84), (0.3, 2.1, 0.14), "frame", hit=False)
    mount.grow((0, 3.7, 0), (3.84, 2.2, 3.84))
    for x in (-1.85, 1.85):
        mount.target((x, 3.7, 0), (0.4, 2.2, 0.6))
    mount.target((0, 3.7, 1.84), (1.0, 2.2, 0.4))
    mount.target((0, 2.7, -1.62), (0.6, 0.6, 0.5), ("hole", 2))  # where the clamp's thumb screw goes in
    mount.material = "metal"
    body = part("body", "mic body", ["shock_mount"])
    body.lathe([(2.0, 0.0), (2.0, 1.08), (2.12, 1.15), (6.55, 1.15), (6.6, 1.1), (6.6, 0.0)], "y", (0, 0, 0), "case")
    body.box((0, 5.6, -1.16), (0.5, 0.3, 0.02), fixed=spec["accent"], hit=False)  # its badge
    for k, x in enumerate((-0.55, 0.55)):
        body.target((x, 6.62, 0), (0.3, 0.12, 0.3), ("hole", k))  # where the capsule's screws go in
    capsule = part("capsule", "capsule", ["body"], lift=(0, 1, 0))
    capsule.box((0, 6.63, 0), (1.5, 0.06, 0.5), fixed=SILVER)  # its mounting plate
    capsule.post((0, 6.66, 0), 0.1, 0.3, fixed=SILVER, hit=False)
    capsule.shapes.use((40, 40, 46)).axle(capsule.rel((0, 7.75, 0)), 0.85, 0.36, 26, along="z")  # its rim
    for side in (-1, 1):  # and the gold diaphragm, front and back
        capsule.shapes.use((226, 190, 96)).axle(capsule.rel((0, 7.75, side * 0.19)), 0.72, 0.02, 26, along="z")
    capsule.grow((0, 7.3, 0), (1.8, 1.4, 0.6))
    capsule.target((0, 7.75, 0), (1.7, 1.7, 0.5))
    capsule.material = "board"
    for k, x in enumerate((-0.55, 0.55)):
        s = part(f"screw{k}", "capsule screw", ["capsule"], lift=(0, 1, 0), screw=True, origin=(x, 6.66, 0))
        s.post((x, 6.66, 0), 0.1, 0.05, fixed=SILVER)
        s.box((x, 6.712, 0), (0.16, 0.01, 0.03), fixed=(108, 110, 120), hit=False)
    clamp = part("screw2", "thumb screw", ["body"], lift=(0, 0, -1), screw=True, origin=(0, 2.7, -1.62))
    clamp.shapes.use((54, 56, 62)).axle(clamp.rel((0, 2.7, -1.62)), 0.3, 0.24, 18, along="z")
    knurl(clamp, (0, 2.7, -1.62), 0.31, 0.22, "z", 12, (40, 42, 48))
    clamp.shapes.use(SILVER).axle(clamp.rel((0, 2.7, -1.36)), 0.07, 0.4, 8, along="z")
    clamp.grow((0, 2.7, -1.5), (0.64, 0.64, 0.5))
    clamp.target((0, 2.7, -1.62), (0.66, 0.66, 0.3))
    clamp.thumb, clamp.spin = True, "z"
    basket = part("headbasket", "headbasket", ["capsule", "screw0", "screw1"], lift=(0, 1, 0), origin=(0, 7.7, 0))
    basket.lathe([(6.55, 1.16), (6.75, 1.2), (8.35, 1.2), (8.7, 0.9), (8.9, 0.4), (8.95, 0.0)], "y", (0, 0, 0),
                 fixed=(212, 214, 220))
    for k in range(6):
        basket.shapes.use((150, 152, 160)).ring(basket.rel((0, 6.95 + k * 0.27, 0)), 1.212, 0.024)
    for j in range(18):
        a = 2 * math.pi * j / 18
        c, s_ = math.cos(a) * 1.212, math.sin(a) * 1.212
        basket.shapes.use((150, 152, 160)).rod(basket.rel((c, 6.8, s_)), basket.rel((c, 8.32, s_)), 0.024)
    basket.twist, basket.material = "y", "metal"
    nut = part("ring_nut", "ring nut", ["body"], lift=(0, -0.25, -1), origin=(0, 1.82, 0))
    nut.lathe([(1.62, 1.0), (1.62, 1.13), (2.02, 1.13), (2.02, 1.0)], "y", (0, 0, 0), fixed=(176, 178, 186))
    knurl(nut, (0, 1.82, 0), 1.14, 0.36, "y", 24)
    nut.twist, nut.material = "y", "metal"
    cable = part("cable", "XLR cable", ["ring_nut"], lift=(0, -0.2, -1))
    cable.lathe([(0.9, 0.0), (0.9, 0.4), (1.55, 0.5), (1.6, 0.0)], "y", (0, 0, 0), "cable")
    route = [(0, 0.9, 0), (0, 0.62, -0.8), (0.3, 0.4, -1.6), (0.8, 0.34, -2.6)]
    for a, b in zip(route, route[1:]):
        cable.colour("cable", None).rod(a, b, 0.2)
    cable.grow((0.4, 0.6, -1.3), (1.2, 0.8, 2.6))
    cable.material = "cable"
    if extras:  # dust on the stand; and on the capsule's diaphragm, where only a puff of air may touch it
        def on_stand():
            a, r = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.5, 2.0)
            return math.cos(a) * r, 0.29, 1.0 + math.sin(a) * r
        board.dirt.append(Dirt(stand, specks_on(rnd, 9, on_stand, ("dust", "dust", "crumb", "hair"))))

        def on_diaphragm():
            a, r = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.1, 0.6)
            return math.cos(a) * r, 7.75 + math.sin(a) * r, -0.215
        board.dirt.append(Dirt(capsule, specks_on(rnd, 7, on_diaphragm, ("dust", "dust", "hair")), delicate=True))
    board.size = board.inner = (5.4, 5.4)
    board.height = 8.95


# ---- webcams ----

def capsule(r, half, center):
    """A capsule lying along x (a pill: round in section, with round ends) as a surface f(u, v), u along it from end
    to end and v round it (0 at the top, pi/2 at the back, pi underneath, 3pi/2 at the front)."""
    cx, cy, cz = center
    total = half + r

    def f(u, v):
        s = -total + 2 * total * u
        rad = r if abs(s) <= half else math.sqrt(max(0.0, r * r - (abs(s) - half) ** 2))
        return cx + s, cy + math.cos(v) * rad, cz + math.sin(v) * rad
    return f


def plank(shapes, a, b, width, thick):
    """A flat bar from a to b, `width` across x and `thick` the other way: a clip's leg, a ribbon cable."""
    A, B = Vec3(*a), Vec3(*b)
    d = (B - A).normalized()
    w = Vec3(width / 2, 0, 0)
    n = d.cross(Vec3(1, 0, 0)).normalized() * (thick / 2)
    ca, cb = [A + w + n, A - w + n, A - w - n, A + w - n], [B + w + n, B - w + n, B - w - n, B + w - n]
    for i in range(4):
        j = (i + 1) % 4
        shapes.quad(tuple(ca[i]), tuple(ca[j]), tuple(cb[j]), tuple(cb[i]), tuple(((ca[i] + ca[j]) / 2 - A).normalized()))
    shapes.quad(*[tuple(p) for p in ca], tuple(-d))
    shapes.quad(*[tuple(p) for p in reversed(cb)], tuple(d))


def ribbon(shapes, pts, y0, y1, thick):
    """A band standing on its edge along a path in x and z (from y0 up to y1, `thick` across): a headband lying on
    its side on the desk, or the pad along it."""
    sides = []
    for i, (x, z) in enumerate(pts):
        (ax, az), (bx, bz) = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        tx, tz = bx - ax, bz - az
        length = math.hypot(tx, tz) or 1
        sides.append((tz / length, -tx / length))
    h = thick / 2
    out = [(x + nx * h, z + nz * h) for (x, z), (nx, nz) in zip(pts, sides)]
    inn = [(x - nx * h, z - nz * h) for (x, z), (nx, nz) in zip(pts, sides)]
    for i in range(len(pts) - 1):
        nx, nz = (sides[i][0] + sides[i + 1][0]) / 2, (sides[i][1] + sides[i + 1][1]) / 2
        (a, b), (c, d) = out[i], out[i + 1]
        shapes.quad((a, y0, b), (c, y0, d), (c, y1, d), (a, y1, b), (nx, 0, nz))
        (a, b), (c, d) = inn[i], inn[i + 1]
        shapes.quad((c, y0, d), (a, y0, b), (a, y1, b), (c, y1, d), (-nx, 0, -nz))
        shapes.quad((out[i][0], y1, out[i][1]), (out[i + 1][0], y1, out[i + 1][1]), (inn[i + 1][0], y1, inn[i + 1][1]),
                    (inn[i][0], y1, inn[i][1]), (0, 1, 0))
        shapes.quad((inn[i][0], y0, inn[i][1]), (inn[i + 1][0], y0, inn[i + 1][1]), (out[i + 1][0], y0, out[i + 1][1]),
                    (out[i][0], y0, out[i][1]), (0, -1, 0))
    for k, sign in ((0, -1), (len(pts) - 1, 1)):  # its two ends
        (a, b), (c, d) = out[k], inn[k]
        tx, tz = sides[k][1] * -sign, sides[k][0] * sign
        shapes.quad((a, y0, b), (c, y0, d), (c, y1, d), (a, y1, b), (tx, 0, tz))


def screw_head_z(part, x, y, z, toward=-1):
    """A small screw's head facing along z (toward the front, or the back), with its cross."""
    part.shapes.use(SILVER).axle(part.rel((x, y, z)), 0.13, 0.05, 12, along="z")
    face = z + toward * 0.027
    for size in ((0.2, 0.035, 0.008), (0.035, 0.2, 0.008)):
        part.box((x, y, face), size, fixed=(108, 110, 120), hit=False)
    part.grow((x, y, z), (0.26, 0.26, 0.05))
    part.target((x, y, z), (0.3, 0.3, 0.07))
    part.spin = "z"


def build_clip_cam(board, part, spec, rnd, extras):
    """A webcam that clips onto a monitor: a pill-shaped body (the back shell, and the front cover with the lens
    window), the circuit board inside (the sensor under its lens mount, two mics, a light, the USB socket on its
    back) held by two screws, the lens that screws into its mount, the USB cable, the privacy shutter on its rails,
    and the hinged clip underneath."""
    cy, r, half = 2.2, 0.8, 2.4
    f = capsule(r, half, (0, cy, 0))

    def inside(p):
        return max(-half, min(half, p[0])), cy, 0
    back = part("back_shell", "back shell")
    back.colour("case", None).surface(f, 0, 1, 40, 0, math.pi, 12, inside)
    back.grow((0, cy, 0.4), (2 * (half + r), 2 * r, r))
    back.target((0, cy, 0.42), (2 * (half + r) - 0.1, 2 * r - 0.06, 0.8))
    for x in (-2.0, 2.0):  # the posts its board screws into
        back.shapes.use(shade(spec["case"], 0.7)).axle((x, cy, 0.43), 0.14, 0.64, 10, along="z")
    for x in (-0.7, 0.7):  # the lugs the clip hinges on
        back.box((x, 1.27, 0.12), (0.22, 0.34, 0.36), fixed=shade(spec["case"], 0.8), hit=False)
    back.shapes.use(BLACK).axle((0, cy, 0.8), 0.17, 0.08, 12, along="z")  # the cable's grommet
    cable = part("cable", "USB cable", ["back_shell"], lift=(0, 0, 1))
    cable.box((0, cy, 0.38), (0.42, 0.22, 0.26), fixed=(40, 40, 44))  # its plug, inside, for the board's socket
    cable.box((0, cy, 0.22), (0.34, 0.1, 0.08), fixed=SILVER, hit=False)
    cable.colour("cable", None).rod((0, cy, 0.5), (0, cy, 0.8), 0.12)
    cable.lathe([(0.8, 0.16), (1.3, 0.1)], "z", (0, cy, 0), "cable")  # its strain relief, out of the back
    route = [(0, cy, 1.3), (0, cy - 0.35, 1.85), (0.25, 1.0, 2.5), (0.7, 0.25, 3.1), (1.5, 0.08, 3.8)]
    for a, b in zip(route, route[1:]):
        cable.colour("cable", None).rod(a, b, 0.12)
        cable.target(tuple((a[i] + b[i]) / 2 for i in range(3)), (0.4, 0.4, 0.4))
    cable.grow((0.7, 1.2, 2.5), (1.8, 2.4, 2.6))
    cable.material = "cable"
    pcb = part("cam_board", "circuit board", ["back_shell", "cable"], lift=(0, 0, -1))
    pcb.box((0, cy, 0.05), (4.9, 1.1, 0.1), fixed=PCB_GREEN)
    pcb.shapes.use((40, 40, 46)).axle((0, cy, -0.17), 0.36, 0.34, 20, along="z")  # the lens mount, over the sensor
    for x in (-1.6, 1.6):  # its two mics
        pcb.shapes.use(SILVER).axle((x, cy + 0.25, -0.05), 0.13, 0.1, 12, along="z")
    pcb.box((-0.75, cy + 0.3, -0.02), (0.14, 0.1, 0.04), fixed=WHITE, hit=False)  # its light
    pcb.box((-0.9, cy - 0.25, -0.025), (0.45, 0.4, 0.05), fixed=BLACK, hit=False)  # its chip
    pcb.box((0, cy, 0.17), (0.5, 0.2, 0.14), fixed=SILVER, hit=False)  # the USB socket, on its back
    for i, x in enumerate((-2.0, 2.0)):
        pcb.shapes.use(GOLDEN).axle((x, cy, -0.003), 0.16, 0.006, 12, along="z")
        pcb.target((x, cy, -0.01), (0.34, 0.34, 0.02), ("hole", i))
    pcb.material = "board"
    for i, x in enumerate((-2.0, 2.0)):
        s = part(f"screw{i}", "screw", ["cam_board"], lift=(0, 0, -1), screw=True, origin=(x, cy, -0.035))
        screw_head_z(s, x, cy, -0.035)
    lens = part("lens", "lens", ["cam_board"], lift=(0, 0, -1), origin=(0, cy, -0.5))
    lens.lathe([(-0.3, 0.0), (-0.3, 0.3), (-0.6, 0.3), (-0.64, 0.25), (-0.64, 0.0)], "z", (0, cy, 0),
               fixed=(36, 36, 42))
    lens.lathe([(-0.645, 0.0), (-0.645, 0.2)], "z", (0, cy, 0), fixed=(50, 70, 104), hit=False)  # its glass
    knurl(lens, (0, cy, -0.45), 0.305, 0.2, "z", 12, (60, 60, 68))
    lens.twist, lens.material = "z", "cable"
    front = part("front_cover", "front cover", ["cam_board", "lens", "back_shell"], lift=(0, 0, -1))
    front.shapes.use((30, 30, 34)).surface(f, 0, 1, 40, math.pi, 2 * math.pi, 12, inside)
    front.shapes.use(spec["accent"]).axle((0, cy, -0.69), 0.5, 0.28, 24, along="z")  # the bezel round the window
    front.shapes.use((24, 26, 34)).axle((0, cy, -0.845), 0.42, 0.04, 24, along="z")  # the glass window
    for x in (-1.6, 1.6):  # the holes for its mics
        front.shapes.use(BLACK).axle((x, cy + 0.25, -0.765), 0.07, 0.02, 10, along="z")
    for y in (cy + 0.56, cy - 0.56):  # the shutter's rails
        front.box((0.575, y, -0.74), (2.35, 0.06, 0.32), fixed=(36, 36, 40), hit=False)
    front.grow((0, cy, -0.42), (2 * (half + r), 2 * r, 0.86))
    front.target((0, cy, -0.42), (2 * (half + r) - 0.1, 2 * r - 0.06, 0.8))
    front.target((0, cy, -0.84), (0.9, 0.9, 0.06), ("lens",))
    light = Shapes().use((255, 255, 255), "light")
    light.box((-0.75, cy + 0.3, -0.746), (0.14, 0.09, 0.02))
    smudge = Shapes()  # a greasy thumbprint on the window (or two), somewhere on it
    for _ in range(rnd.choice((1, 1, 2))):
        a0, d0, spread = rnd.uniform(0, 2 * math.pi), rnd.uniform(0, 0.12), rnd.uniform(0.12, 0.22)
        x0, y0 = math.cos(a0) * d0, math.sin(a0) * d0
        for _ in range(rnd.randint(6, 11)):
            a, d = rnd.uniform(0, 2 * math.pi), rnd.uniform(0, spread)
            smudge.use(rnd.choice(((122, 118, 112), (138, 132, 124), (108, 106, 104)))).box(
                (x0 + math.cos(a) * d, cy + y0 + math.sin(a) * d, -0.867),
                (rnd.uniform(0.08, 0.18), rnd.uniform(0.06, 0.12), 0.004))
    shutter = part("shutter", "privacy shutter", ["front_cover"], lift=(0, 0, -1), origin=(1.15, cy, -0.88))
    shutter.box((1.15, cy, -0.88), (0.95, 1.04, 0.05), "frame")
    for k in range(3):  # its grip
        shutter.box((1.45 + k * 0.08, cy, -0.91), (0.03, 0.6, 0.02), fixed=(80, 82, 90), hit=False)
    clip = part("clip", "monitor clip", ["back_shell"], lift=(0, -1, 0))
    clip.shapes.use((40, 40, 46)).axle((0, 1.22, 0.12), 0.13, 1.1, 14)  # its hinge, between the lugs
    clip.shapes.use(SILVER).axle((0, 1.22, 0.12), 0.05, 1.8, 8)  # and the pin, through them
    plank(clip.shapes.use((40, 40, 46)), (0, 1.15, 0.02), (0, 0.08, -0.55), 1.0, 0.12)  # its front lip
    plank(clip.shapes.use((40, 40, 46)), (0, 1.15, 0.22), (0, 0.08, 1.9), 1.5, 0.12)  # and its back flap
    clip.box((0, 0.04, -0.57), (1.0, 0.08, 0.22), fixed=RUBBER, hit=False)
    clip.box((0, 0.04, 1.88), (1.5, 0.08, 0.3), fixed=RUBBER, hit=False)
    clip.grow((0, 0.65, 0.65), (1.5, 1.35, 2.75))
    clip.target((0, 1.22, 0.12), (1.2, 0.3, 0.3))
    clip.target((0, 0.6, -0.27), (1.0, 1.0, 0.45))
    clip.target((0, 0.6, 1.05), (1.5, 1.0, 1.6))
    board.mic["light"], board.mic["light_host"] = light, "front_cover"
    board.attach.append((smudge, "front_cover", "smudge", False))
    if extras:  # dust along the top of its body
        def on_top():
            x, zz = rnd.uniform(-2.3, 2.3), rnd.uniform(0.05, 0.35)
            return x, cy + math.sqrt(r * r - zz * zz) + 0.005, zz
        board.dirt.append(Dirt(back, specks_on(rnd, 9, on_top, ("dust", "dust", "hair"))))
    board.size = board.inner = spec["size"]
    board.height = cy + r


def build_ball_cam(board, part, spec, rnd, extras):
    """A round webcam on a stand: the stand (a hollow base, a steel weight inside it, a base plate held by three
    screws underneath) and its neck; the ball's back half on the neck, with its snapshot button on top; the round
    circuit board inside, held by a screw; the USB cable; the front half, held to the back by two screws; and the
    focus ring, the lens barrel that threads through the front into its mount."""
    R, cy = 1.6, 3.4
    profile = [(0.0, 1.95), (0.25, 2.0), (0.42, 1.7), (0.5, 1.0), (0.52, 0.3), (0.52, 0.0)]

    def base_top(radius):  # how high the stand's dome is, that far out
        for (y0, r0), (y1, r1) in zip(profile[1:], profile[2:]):
            if r1 <= radius <= r0:
                return y0 + (y1 - y0) * (r0 - radius) / (r0 - r1)
        return 0.52
    stand = part("stand", "stand")
    stand.lathe(profile, "y", (0, 0, 0), "case", hit=False, segments=32)
    neck_top = cy - math.sqrt(R * R - 0.09) + 0.08
    stand.post((0, 0.5, 0.3), 0.22, neck_top - 0.5, fixed=shade(spec["case"], 0.82), hit=False)  # the neck
    screws_at = [(math.cos(a) * 1.2, math.sin(a) * 1.2) for a in (math.pi / 2, math.pi * 7 / 6, math.pi * 11 / 6)]
    for x, z in screws_at:  # the posts the base plate's screws go up into
        stand.post((x, 0.0, z), 0.12, base_top(1.2) - 0.02, fixed=shade(spec["case"], 0.7), hit=False)
    stand.target((0, 0.42, 0), (3.6, 0.2, 3.6))  # (by its top: from underneath, what's inside it comes first)
    stand.target((0, (0.5 + neck_top) / 2, 0.3), (0.5, neck_top - 0.5, 0.5))
    stand.material = "metal"
    weight = part("weight", "steel weight", ["stand"], lift=(0, -1, 0))
    weight.post((0, 0.06, 0), 1.0, 0.22, fixed=(150, 154, 162))
    weight.material = "metal"
    plate = part("base_plate", "base plate", ["stand", "weight"], lift=(0, -1, 0))
    plate.post((0, 0, 0), 1.95, -0.06, "inside", hit=False, segments=32)
    plate.lathe([(-0.06, 1.55), (-0.1, 1.58), (-0.1, 1.82), (-0.06, 1.85)], "y", (0, 0, 0), fixed=RUBBER, hit=False,
                segments=32)  # a rubber ring, so it doesn't slide
    plate.target((0, -0.04, 0), (3.8, 0.08, 3.8))
    for i, (x, z) in enumerate(screws_at):
        plate.target((x, -0.07, z), (0.34, 0.04, 0.34), ("hole", i))
    for i, (x, z) in enumerate(screws_at):
        s = part(f"screw{i}", "screw", ["base_plate"], lift=(0, -1, 0), screw=True, origin=(x, -0.06, z))
        s.post((x, -0.06, z), 0.13, -0.04, fixed=SILVER)
        for size in ((0.2, 0.006, 0.035), (0.035, 0.006, 0.2)):
            s.box((x, -0.102, z), size, fixed=(108, 110, 120), hit=False)
    back = part("back_half", "back half", ["stand"])
    back.lathe([(R * math.cos(t), R * math.sin(t)) for t in [math.pi / 2 * k / 12 for k in range(13)]], "z",
               (0, cy, 0), "case", hit=False, segments=32)
    back.post((0, cy + 1.45, 0.35), 0.28, 0.2, fixed=spec["accent"], hit=False)  # its snapshot button
    back.target((0, cy + 1.62, 0.35), (0.62, 0.14, 0.62), ("snap",))
    zb = math.sqrt(R * R - 0.64)
    for k, x in enumerate((-0.8, 0.8)):  # where the shell's screws go in, at the back
        back.target((x, cy, zb), (0.3, 0.3, 0.06), ("hole", 4 + k))
    back.shapes.use(BLACK).axle((0, cy - 0.9, 1.32), 0.17, 0.08, 12, along="z")  # the cable's grommet
    back.target((0, cy, 0.65), (2 * R, 2 * R, 1.3))
    cable = part("cable", "USB cable", ["back_half"], lift=(0, -0.3, 1))
    cable.box((0, cy - 0.75, 0.12), (0.36, 0.14, 0.2), fixed=(40, 40, 44))  # its plug, for the board's socket
    cable.colour("cable", None).rod((0, cy - 0.75, 0.22), (0, cy - 0.9, 1.3), 0.1)
    route = [(0, cy - 0.9, 1.3), (0, cy - 1.05, 1.75), (0, 1.6, 2.35), (0.3, 0.55, 2.85), (0.9, 0.1, 3.5),
             (1.8, 0.08, 4.3)]
    for k, (a, b) in enumerate(zip(route, route[1:])):
        cable.colour("cable", None).rod(a, b, 0.2 if k == 0 else 0.13)
        cable.target(tuple((a[i] + b[i]) / 2 for i in range(3)), (0.4, 0.4, 0.4))
    cable.grow((0.9, 1.4, 2.8), (1.8, 2.8, 3.0))
    cable.material = "cable"
    pcb = part("cam_board", "circuit board", ["back_half", "cable"], lift=(0, 0, -1))
    pcb.shapes.use(PCB_GREEN).axle((0, cy, -0.12), 1.35, 0.08, 28, along="z")
    pcb.shapes.use((40, 40, 46)).axle((0, cy, -0.4), 0.42, 0.48, 20, along="z")  # the lens mount, over the sensor
    pcb.shapes.use(SILVER).axle((0.75, cy + 0.6, -0.2), 0.12, 0.08, 12, along="z")  # its mic
    pcb.box((-0.75, cy + 0.55, -0.18), (0.14, 0.1, 0.04), fixed=WHITE, hit=False)  # its light
    pcb.box((0.6, cy - 0.55, -0.18), (0.4, 0.4, 0.04), fixed=BLACK, hit=False)  # its chip
    pcb.box((0, cy - 0.75, -0.02), (0.4, 0.16, 0.12), fixed=SILVER, hit=False)  # the USB socket, on its back
    pcb.shapes.use(GOLDEN).axle((-0.85, cy - 0.7, -0.163), 0.15, 0.006, 12, along="z")
    pcb.target((-0.85, cy - 0.7, -0.17), (0.32, 0.32, 0.02), ("hole", 3))
    pcb.grow((0, cy, -0.3), (2.7, 2.7, 0.6))
    pcb.target((0, cy, -0.12), (2.7, 2.7, 0.08))
    pcb.material = "board"
    s = part("screw3", "screw", ["cam_board"], lift=(0, 0, -1), screw=True, origin=(-0.85, cy - 0.7, -0.19))
    screw_head_z(s, -0.85, cy - 0.7, -0.19)
    front = part("front_half", "front half", ["cam_board", "back_half"], lift=(0, 0, -1))
    t0 = math.asin(0.55 / R)
    front.lathe([(-R * math.cos(t), R * math.sin(t)) for t in [t0 + (math.pi / 2 - t0) * k / 12 for k in range(13)]],
                "z", (0, cy, 0), "case", hit=False, segments=32)
    front.lathe([(-1.505, 0.55), (-1.455, 0.66)], "z", (0, cy, 0), fixed=spec["accent"], hit=False)  # round the hole
    front.shapes.use(BLACK).axle((0.75, cy + 0.6, -1.29), 0.07, 0.02, 10, along="z")  # the hole for its mic
    front.target((0, cy, -0.75), (2 * R, 2 * R, 1.5))
    light = Shapes().use((255, 255, 255), "light")
    light.box((-0.75, cy + 0.55, -1.31), (0.14, 0.1, 0.03))
    for k, x in enumerate((-0.8, 0.8)):  # the screws holding the halves together, in from the back
        s = part(f"screw{4 + k}", "screw", ["front_half"], lift=(0, 0, 1), screw=True, origin=(x, cy, zb + 0.04))
        screw_head_z(s, x, cy, zb + 0.04, toward=1)
    ring = part("focus_ring", "focus ring", ["cam_board", "front_half"], lift=(0, 0, -1), origin=(0, cy, -1.68))
    ring.lathe([(-0.6, 0.0), (-0.6, 0.38), (-1.5, 0.38), (-1.5, 0.62), (-1.86, 0.62), (-1.89, 0.5), (-1.89, 0.0)], "z",
               (0, cy, 0), fixed=(40, 40, 46))
    knurl(ring, (0, cy, -1.68), 0.625, 0.3, "z", 18, (70, 70, 78))
    ring.lathe([(-1.895, 0.0), (-1.895, 0.34)], "z", (0, cy, 0), fixed=(50, 70, 104), hit=False)  # its glass
    ring.twist, ring.spin, ring.material = "z", "z", "cable"
    board.knob = ring
    board.mic["light"], board.mic["light_host"] = light, "front_half"
    if extras:  # dust on the stand, and on top of the ball
        def on_stand():
            a, rr = rnd.uniform(0, 2 * math.pi), rnd.uniform(1.1, 1.6)
            return math.cos(a) * rr, base_top(rr) + 0.005, math.sin(a) * rr
        board.dirt.append(Dirt(stand, specks_on(rnd, 8, on_stand, ("dust", "dust", "crumb"))))

        def on_ball():
            x, zz = rnd.choice((-1, 1)) * rnd.uniform(0.4, 0.8), rnd.uniform(0.1, 0.7)
            return x, cy + math.sqrt(R * R - x * x - zz * zz) + 0.005, zz
        board.dirt.append(Dirt(back, specks_on(rnd, 6, on_ball, ("dust", "dust", "hair"))))
    board.size = board.inner = spec["size"]
    board.height = cy + R + 0.1


def build_stream_cam(board, part, spec, rnd, extras):
    """A streaming webcam with a ring light, on a little tripod: the tripod and the thumb screw that holds the
    camera on it; the round housing; the main board inside (lens mount, mics, the ribbon's socket) held by two
    screws; the lens; the LED ring on its standoffs; the ribbon cable between them; and the front panel, its glossy
    rim and the frosted diffuser that the LEDs shine through, which twists off."""
    cy, R = 2.6, 1.9
    tripod = part("tripod", "tripod")
    tripod.post((0, 0.55, 0), 0.34, 0.15, fixed=(40, 40, 46), hit=False)  # its head
    for a in (90, 210, 330):  # three legs, splayed out
        ra = math.radians(a)
        top, foot = (math.cos(ra) * 0.28, 0.58, math.sin(ra) * 0.28), (math.cos(ra) * 1.7, 0.06, math.sin(ra) * 1.7)
        tripod.shapes.use((40, 40, 46)).rod(top, foot, 0.13)
        tripod.box(foot, (0.24, 0.1, 0.24), fixed=RUBBER, hit=False)
        tripod.target(tuple(top[i] * 0.4 + foot[i] * 0.6 for i in range(3)), (0.45, 0.35, 0.45))
    tripod.grow((0, 0.35, 0), (3.6, 0.7, 3.6))
    tripod.target((0, 0.625, 0), (0.75, 0.15, 0.75))
    tripod.target((0, 0.53, 0), (0.4, 0.06, 0.4), ("hole", 0))
    tripod.material = "metal"
    housing = part("housing", "housing", ["tripod"])
    housing.lathe([(-0.25, 1.75), (-0.25, 1.9), (0.3, 1.9), (0.6, 1.75), (0.8, 1.3), (0.88, 0.0)], "z", (0, cy, 0),
                  "case", hit=False, segments=36)
    housing.post((0, 0.68, 0), 0.26, 0.14, fixed=(40, 40, 46), hit=False)  # its mount, for the tripod screw
    bx = math.sqrt(R * R - 0.36)
    housing.post((0.6, cy + bx - 0.04, 0.25), 0.26, 0.14, fixed=spec["accent"], hit=False)  # the light's button
    housing.target((0.6, cy + bx + 0.07, 0.25), (0.56, 0.18, 0.56), ("light",))
    housing.box((0, cy, 0.866), (0.5, 0.16, 0.03), fixed=BLACK, hit=False)  # its USB-C socket, round the back
    for x in (-1.1, 1.1):  # the posts its board screws into
        housing.shapes.use(shade(spec["case"], 0.7)).axle((x, cy - 0.6, 0.6), 0.14, 0.36, 10, along="z")
    housing.target((0, cy, 0.665), (3.8, 3.8, 0.43))  # (its back, and round the rim: not over the opening)
    for x, y, w, h in ((0, cy + 1.82, 2.4, 0.16), (0, cy - 1.82, 2.4, 0.16), (1.82, cy, 0.16, 2.4),
                       (-1.82, cy, 0.16, 2.4)):
        housing.target((x, y, 0.1), (w, h, 0.7))
    s = part("screw0", "tripod screw", ["housing"], lift=(0, -1, 0), screw=True, origin=(0, 0.45, 0))
    s.post((0, 0.3, 0), 0.3, 0.16, fixed=(54, 56, 62))
    knurl(s, (0, 0.38, 0), 0.31, 0.14, "y", 14, (40, 42, 48))
    s.post((0, 0.46, 0), 0.07, 0.34, fixed=SILVER, hit=False)  # its thread, up through the head into the camera
    s.thumb = True
    pcb = part("cam_board", "main board", ["housing"], lift=(0, 0, -1))
    pcb.shapes.use(PCB_GREEN).axle((0, cy, 0.38), 1.62, 0.08, 32, along="z")
    pcb.shapes.use((40, 40, 46)).axle((0, cy, 0.18), 0.4, 0.32, 20, along="z")  # the lens mount, over the sensor
    for x in (-1.2, 1.2):  # its mics
        pcb.shapes.use(SILVER).axle((x, cy + 0.75, 0.3), 0.12, 0.08, 12, along="z")
    pcb.box((0.7, cy - 0.9, 0.32), (0.4, 0.4, 0.04), fixed=BLACK, hit=False)  # its chip
    pcb.box((1.5, cy, 0.31), (0.12, 0.5, 0.06), fixed=WHITE, hit=False)  # the ribbon's socket, at its edge
    for i, x in enumerate((-1.1, 1.1)):
        pcb.shapes.use(GOLDEN).axle((x, cy - 0.6, 0.337), 0.15, 0.006, 12, along="z")
        pcb.target((x, cy - 0.6, 0.33), (0.32, 0.32, 0.02), ("hole", 1 + i))
    pcb.grow((0, cy, 0.25), (3.3, 3.3, 0.35))
    pcb.target((0, cy, 0.38), (3.2, 3.2, 0.08))
    pcb.material = "board"
    for i, x in enumerate((-1.1, 1.1)):
        s = part(f"screw{1 + i}", "screw", ["cam_board"], lift=(0, 0, -1), screw=True, origin=(x, cy - 0.6, 0.31))
        screw_head_z(s, x, cy - 0.6, 0.31)
    lens = part("lens", "lens", ["cam_board"], lift=(0, 0, -1), origin=(0, cy, -0.1))
    lens.lathe([(0.04, 0.0), (0.04, 0.32), (-0.27, 0.32), (-0.3, 0.26), (-0.3, 0.0)], "z", (0, cy, 0),
               fixed=(36, 36, 42))
    lens.lathe([(-0.305, 0.0), (-0.305, 0.2)], "z", (0, cy, 0), fixed=(50, 70, 104), hit=False)
    lens.twist, lens.material = "z", "cable"
    leds = part("led_ring", "LED ring", ["cam_board"], lift=(0, 0, -1))
    leds.lathe([(0.0, 0.62), (0.0, 1.56), (0.06, 1.56), (0.06, 0.62), (0.0, 0.62)], "z", (0, cy, 0),
               fixed=(236, 236, 230), hit=False, segments=36)
    for k in range(16):  # its LEDs
        a = 2 * math.pi * k / 16
        leds.box((math.cos(a) * 1.1, cy + math.sin(a) * 1.1, -0.015), (0.16, 0.16, 0.03), fixed=(255, 224, 150),
                 hit=False)
    for k in range(4):  # its standoffs, back to the main board
        a = math.pi / 4 + k * math.pi / 2
        leds.shapes.use(SILVER).axle((math.cos(a) * 1.35, cy + math.sin(a) * 1.35, 0.2), 0.07, 0.28, 8, along="z")
    leds.grow((0, cy, 0.1), (3.12, 3.12, 0.3))
    leds.target((0, cy, 0.03), (3.12, 3.12, 0.06))
    leds.material = "board"
    # The ribbon: from the LED ring's edge into the gap beside it, and back to the main board's socket (on the
    # right, between the ring and the housing's wall, where you can see it with the front panel off)
    rib = part("ribbon", "ribbon cable", ["cam_board", "led_ring"], lift=(0, 0, -1))
    amber = (214, 160, 70)
    rib.box((1.62, cy, 0.05), (0.13, 0.4, 0.02), fixed=amber)
    rib.box((1.68, cy, 0.14), (0.02, 0.4, 0.18), fixed=amber)
    rib.grow((1.62, cy, 0.17), (0.2, 0.4, 0.34))
    rib.target((1.64, cy, 0.1), (0.22, 0.5, 0.2))
    rib.target((1.66, cy, 0.27), (0.26, 0.5, 0.14), ("ribbon",))
    rib.material = "cable"
    loose, seated = Shapes(), Shapes()  # its end: worked loose, sticking up out of its socket; or pressed home
    loose.use(amber).box((1.71, cy, 0.27), (0.02, 0.4, 0.08))
    loose.use(amber).box((1.74, cy, 0.31), (0.06, 0.4, 0.02))
    seated.use(amber).box((1.6, cy, 0.25), (0.18, 0.4, 0.02))
    front = part("front_panel", "front panel", ["led_ring", "lens", "ribbon", "housing"], lift=(0, 0, -1),
                 origin=(0, cy, -0.32))
    front.lathe([(-0.33, 1.56), (-0.36, 1.62), (-0.36, 1.88), (-0.31, 1.95), (-0.25, 1.95)], "z", (0, cy, 0),
                fixed=(28, 28, 32), hit=False, segments=36)
    front.lathe([(-0.33, 0.62), (-0.33, 1.56)], "z", (0, cy, 0), "glow", hit=False, segments=36)  # the diffuser
    front.lathe([(-0.33, 0.33), (-0.36, 0.4), (-0.36, 0.58), (-0.33, 0.62)], "z", (0, cy, 0), fixed=(28, 28, 32),
                hit=False, segments=24)
    front.lathe([(-0.345, 0.0), (-0.345, 0.33)], "z", (0, cy, 0), fixed=(30, 40, 60), hit=False)  # its glass
    front.target((0, cy, -0.3), (3.9, 3.9, 0.12))
    front.twist = "z"
    board.mic["glow"] = "front_panel"
    board.attach.append((loose, "ribbon", "loose", False))
    board.attach.append((seated, "ribbon", "seated", True))
    if extras:  # dust on top of the housing
        def on_top():
            x, zz = rnd.uniform(-0.9, 0.9), rnd.uniform(-0.1, 0.3)
            return x, cy + math.sqrt(R * R - x * x) + 0.005, zz
        board.dirt.append(Dirt(housing, specks_on(rnd, 8, on_top, ("dust", "dust", "hair", "crumb"))))
    board.size = board.inner = spec["size"]
    board.height = cy + R + 0.14


# ---- headsets ----

def build_headset(board, part, spec, rnd, extras):
    """A headset lying flat with its cushions up: the headband (its steel sliders at the ends) and its pad; a yoke
    at each end, holding a cup on two pivot pins; in each cup, the driver on its baffle, screwed down, and over the
    screws an ear cushion that twists off. The office one has a boom mic with a foam windscreen, and a cable with
    a volume remote on it; the gaming one, lights round its cups, a little board in the left cup that its boom mic
    plugs into, and a braided cable; the wireless one, a board, a battery and its lead in the right cup, and buttons
    on the cup's edge."""
    form = spec["form"]
    gaming, wireless = form == "gaming_hs", form == "wireless_hs"
    R = 1.8 if gaming else 1.65 if wireless else 1.55
    X = 3.5 if gaming else 3.3 if wireless else 3.2
    cz, top = -0.5, 1.7 if gaming else 1.55
    zb, depth = cz + R + 0.65, 2.4
    angles = (45, 135, 225, 315) if gaming else (30, 150, 270)
    cushion_col = spec["bottom"]
    path = [(-X * math.cos(math.pi * k / 30), zb + 0.5 + depth * math.sin(math.pi * k / 30)) for k in range(31)]
    band = part("headband", "headband")
    ribbon(band.colour("case", None), path, 0.06, 0.84, 0.22)
    for x in (-X, X):  # its steel sliders, out to the yokes
        band.box((x, 0.45, zb + 0.27), (0.08, 0.5, 0.6), fixed=SILVER, hit=False)
    for k in range(0, 31, 3):
        band.target((path[k][0], 0.45, path[k][1]), (0.6, 0.8, 0.6))
    band.grow((0, 0.45, zb + 0.5 + depth / 2), (2 * X + 0.4, 0.8, depth + 0.4))
    inner = [(x * 0.92, zb + 0.5 + (z - zb - 0.5) * 0.89) for x, z in path[6:25]]
    pad = part("headband_pad", "headband pad", ["headband"])
    ribbon(pad.colour("inside", None), inner, 0.12, 0.78, 0.3)
    for k in range(0, len(inner), 3):
        pad.target((inner[k][0], 0.45, inner[k][1]), (0.5, 0.7, 0.5))
    pad.grow((0, 0.45, zb + 0.5 + depth * 0.7), (2 * X, 0.7, depth))
    pad.material = "foam"
    hole = 0
    for side, cx in (("left", -X), ("right", X)):
        yoke = part(f"{side}_yoke", f"{side} yoke", ["headband"])
        arc = [(cx - math.cos(math.pi * k / 12) * (R + 0.22), 0.45, cz + math.sin(math.pi * k / 12) * (R + 0.22))
               for k in range(13)]
        for a, b in zip(arc, arc[1:]):
            yoke.colour("frame", None).rod(a, b, 0.2)
        for k in range(0, 13, 3):
            yoke.target(arc[k], (0.36, 0.36, 0.36))
        yoke.colour("frame", None).rod((cx, 0.45, cz + R + 0.22), (cx, 0.45, zb + 0.1), 0.2)  # up into the slider
        yoke.target((cx, 0.45, (cz + R + zb) / 2 + 0.15), (0.3, 0.3, zb - cz - R))
        for sx in (-1, 1):  # its pivot pins, into the cup's sides
            yoke.shapes.use(SILVER).axle((cx + sx * (R + 0.11), 0.45, cz), 0.09, 0.24, 8)
        yoke.grow((cx, 0.45, cz + R / 2), (2 * R + 0.6, 0.3, R + 1.2))
        yoke.material = "plastic"
        cup = part(f"{side}_cup", f"{side} cup", [f"{side}_yoke"])
        cup.lathe([(0.05, 0.0), (0.0, R - 0.3), (0.1, R - 0.05), (0.35, R + 0.02), (0.85, R + 0.05), (0.85, R - 0.14)],
                  "y", (cx, 0, cz), "case", hit=False, segments=36)
        for a in angles:  # the posts its screws go down into
            ra = math.radians(a)
            cup.post((cx + math.cos(ra) * (R - 0.3), 0.03, cz + math.sin(ra) * (R - 0.3)), 0.12, 0.82,
                     fixed=shade(spec["case"], 0.7), hit=False)
        cup.target((cx, 0.05, cz), (2 * R, 0.1, 2 * R))  # (its floor, and round its rim: not over the inside)
        back_half = (R - 0.3) / 2  # (its sides from the back round to the pivots; the front, just its middle: clear of
        for dx, dz, w, d in ((0, R - 0.1, 2 * R, 0.25), (0, -R + 0.1, 1.6, 0.25),  # the buttons on its edge)
                             (R - 0.1, back_half, 0.25, R + 0.3), (-R + 0.1, back_half, 0.25, R + 0.3)):
            cup.target((cx + dx, 0.45, cz + dz), (w, 0.85, d))
        if gaming:  # its lights, a glowing band round the cup
            rgb = Shapes().use((255, 255, 255), "glow")
            rgb.lathe([(0.32, R + 0.04), (0.5, R + 0.045)], "y", (cx, 0, cz), 36)
            board.attach.append((rgb, f"{side}_cup", "rgb", False))
        cup.material = "plastic"
        under = [f"{side}_cup"]
        if side == "left" and gaming:  # the little board its boom plugs into, and its controls
            ctl = part("control_board", "control board", ["left_cup"])
            ctl.post((cx, 0.1, cz), 0.95, 0.06, fixed=PCB_GREEN)
            ctl.box((cx - 0.3, 0.19, cz + 0.3), (0.4, 0.06, 0.4), fixed=BLACK, hit=False)  # its chip
            ctl.box((cx, 0.3, cz - R + 0.35), (0.3, 0.3, 0.6), fixed=(30, 30, 34), hit=False)  # the mic's socket
            ctl.box((cx + 0.6, 0.18, cz + 0.2), (0.22, 0.04, 0.22), fixed=GOLDEN, hit=False)  # the pad the wire's off
            ctl.box((cx + 0.1, 0.18, cz + 0.65), (0.2, 0.04, 0.2), fixed=GOLDEN, hit=False)  # and the one it's on
            ctl.target((cx + 0.55, 0.26, cz + 0.3), (0.55, 0.3, 0.55), ("joint",))
            ctl.material = "board"
            loose, fixed_ = Shapes(), Shapes()  # the red wire from the driver's plug: off its pad, or soldered on
            loose.use((210, 60, 55)).rod(ctl.rel((cx + 0.1, 0.2, cz + 0.65)), ctl.rel((cx + 0.35, 0.36, cz + 0.45)), 0.05)
            loose.use((210, 60, 55)).rod(ctl.rel((cx + 0.35, 0.36, cz + 0.45)), ctl.rel((cx + 0.62, 0.42, cz + 0.32)),
                                         0.05)
            fixed_.use((210, 60, 55)).rod(ctl.rel((cx + 0.1, 0.2, cz + 0.65)), ctl.rel((cx + 0.6, 0.2, cz + 0.2)), 0.05)
            fixed_.use((200, 202, 208)).box(ctl.rel((cx + 0.6, 0.21, cz + 0.2)), (0.16, 0.04, 0.16))  # the solder
            board.attach.append((loose, "control_board", "loose", False))
            board.attach.append((fixed_, "control_board", "soldered", True))
            under.append("control_board")
        if side == "left" and not wireless:  # the cable, in through the back of the left cup
            cable = part("cable", "USB cable", ["left_cup"] + (["control_board"] if gaming else []), lift=(-1, 0, 0.6))
            ex, ez = cx - (R - 0.05) * 0.72, cz + (R - 0.05) * 0.72
            cable.shapes.use((40, 40, 44)).rod((ex + 0.2, 0.15, ez - 0.2), (cx - 0.55, 0.3, cz + 0.55), 0.08)
            cable.box((cx - 0.5, 0.3, cz + 0.5), (0.3, 0.14, 0.22), fixed=WHITE, hit=False)  # the driver plugs in here
            route = [(ex, 0.15, ez), (ex - 0.45, 0.12, ez + 0.4), (cx - 2.0, 0.1, cz + 2.1), (cx - 2.1, 0.1, cz + 3.4),
                     (cx - 2.0, 0.08, cz + 4.6)]
            for k, (a, b) in enumerate(zip(route, route[1:])):
                col = shade(spec["cable"], 1.6) if gaming and k % 2 else None
                (cable.shapes.use(col) if col else cable.colour("cable", None)).rod(a, b, 0.17 if k == 0 else 0.12)
                cable.target(tuple((a[i] + b[i]) / 2 for i in range(3)), (0.45, 0.35, 0.45))
            if not gaming:  # its volume remote, on the way
                cable.box((cx - 2.08, 0.2, cz + 2.9), (0.5, 0.24, 0.9), fixed=(44, 44, 50))
                cable.shapes.use((80, 82, 90)).axle((cx - 1.83, 0.2, cz + 2.9), 0.14, 0.08, 14)  # its wheel
            cable.grow((cx - 1.2, 0.15, cz + 2.4), (2.6, 0.3, 4.6))
            cable.material = "cable"
            under.append("cable")
        if side == "right" and wireless:  # its board, and the battery with its lead
            mb = part("main_board", "main board", ["right_cup"])
            mb.box((cx, 0.13, cz - 0.55), (1.6, 0.06, 0.9), fixed=PCB_GREEN)
            mb.box((cx - 0.3, 0.18, cz - 0.6), (0.45, 0.05, 0.45), fixed=BLACK, hit=False)  # its Bluetooth chip
            mb.box((cx + 0.45, 0.2, cz - 0.2), (0.3, 0.1, 0.16), fixed=WHITE, hit=False)  # the battery's socket
            mb.material = "board"
            bat = part("battery", "battery", ["right_cup"])
            bat.box((cx, 0.16, cz + 0.92), (1.25, 0.24, 0.6), fixed=(176, 184, 198))
            bat.box((cx, 0.36, cz + 0.92), (1.15, 0.18, 0.5), fixed=(170, 178, 192), hit=False)  # puffed up, swollen
            bat.box((cx, 0.455, cz + 0.92), (0.8, 0.02, 0.3), fixed=(96, 140, 196), hit=False)  # its label
            bat.target((cx, 0.24, cz + 0.92), (1.25, 0.42, 0.6))
            new = Shapes()  # the new one, flat as a battery should be
            new.use((176, 184, 198)).box(bat.rel((cx, 0.16, cz + 0.92)), (1.25, 0.24, 0.6))
            new.use((96, 140, 196)).box(bat.rel((cx, 0.285, cz + 0.92)), (0.8, 0.02, 0.3))
            board.attach.append((new, "battery", "fresh", True))
            lead = part("battery_lead", "battery lead", ["battery", "main_board"])
            for k, col in ((-0.05, WIRES[0]), (0.05, WIRES[1])):
                lead.wire([(cx + 0.4 + k, 0.2, cz + 0.6), (cx + 0.4 + k, 0.2, cz - 0.15)], 0.04, col)
            lead.box((cx + 0.45, 0.27, cz - 0.2), (0.32, 0.08, 0.18), fixed=WHITE)
            lead.target((cx + 0.45, 0.25, cz + 0.2), (0.4, 0.2, 0.9))
            lead.material = "cable"
            under += ["main_board", "battery", "battery_lead"]
        baffle = part(f"{side}_baffle", f"{side} driver", under)
        baffle.post((cx, 0.85, cz), R - 0.03, 0.1, fixed=(40, 40, 46), hit=False)
        baffle.post((cx, 0.45, cz), 0.5, 0.4, fixed=(70, 72, 80), hit=False)  # its magnet, down in the cup
        baffle.post((cx, 0.95, cz), 1.0, 0.012, fixed=(26, 26, 30), hit=False)  # the cloth over the driver
        baffle.post((cx, 0.962, cz), 0.3, 0.02, fixed=(46, 46, 52), hit=False)
        baffle.post((cx, 0.95, cz + 1.12 * (R - 0.3) / 1.25), 0.09, 0.012,
                    fixed=(90, 140, 220) if side == "left" else (220, 90, 90), hit=False)  # L blue, R red
        screws = []
        for a in angles:
            ra = math.radians(a)
            x, z = cx + math.cos(ra) * (R - 0.3), cz + math.sin(ra) * (R - 0.3)
            baffle.target((x, 0.94, z), (0.3, 0.04, 0.3), ("hole", hole))
            screws.append((x, z, hole))
            hole += 1
        for w, d in ((0.92, 0.55), (0.55, 0.92)):  # (round rather than square, like the cushion)
            baffle.target((cx, 0.9, cz), (2 * (R - 0.03) * w, 0.1, 2 * (R - 0.03) * d))
        baffle.material = "board"
        keys = []
        for x, z, i in screws:
            s = part(f"screw{i}", "screw", [f"{side}_baffle"], screw=True, origin=(x, 0.95, z))
            s.post((x, 0.95, z), 0.11, 0.04, fixed=SILVER)
            for size in ((0.18, 0.008, 0.03), (0.03, 0.008, 0.18)):
                s.box((x, 0.992, z), size, fixed=(108, 110, 120), hit=False)
            keys.append(s.key)
        cushion = part(f"{side}_cushion", f"{side} ear cushion", [f"{side}_baffle"] + keys, origin=(cx, 1.2, cz))
        ri, ro = 0.95, R + 0.03
        cushion.lathe([(0.95, ri + 0.05), (1.03, ri), (top - 0.12, ri - 0.02), (top, ri + 0.12), (top + 0.02, (ri + ro) / 2),
                       (top, ro - 0.12), (top - 0.12, ro + 0.02), (1.03, ro), (0.95, ro - 0.05), (0.95, ri + 0.05)],
                      "y", (cx, 0, cz), "inside", hit=False, segments=36)
        for w, d in ((0.92, 0.55), (0.55, 0.92)):  # (clicked by a cross, round rather than square: so what's
            cushion.target((cx, (0.95 + top) / 2, cz), (2 * ro * w, top - 0.95, 2 * ro * d))  # beside it isn't hidden)
        cushion.twist, cushion.material = "y", "foam"
        if spec.get("special") == "cushions":  # flaking: bits of the old leatherette peeling off
            flakes = Shapes()
            for _ in range(rnd.randint(7, 24)):
                a, rr = rnd.uniform(0, 2 * math.pi), rnd.uniform(ri + 0.15, ro - 0.12)
                flakes.use(rnd.choice(((150, 146, 140), (176, 172, 164), (120, 118, 116)))).box(
                    cushion.rel((cx + math.cos(a) * rr, top + 0.025, cz + math.sin(a) * rr)),
                    (rnd.uniform(0.1, 0.22), 0.012, rnd.uniform(0.08, 0.18)))
            board.attach.append((flakes, f"{side}_cushion", "flakes", False))
        if extras:  # dust on the driver's cloth, under the cushion
            def on_cloth(cx=cx):
                a, rr = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.35, 0.9)
                return cx + math.cos(a) * rr, 0.97, cz + math.sin(a) * rr
            board.dirt.append(Dirt(baffle, specks_on(rnd, 6, on_cloth, ("dust", "dust", "hair"))))
    lx = -X
    if not wireless:  # its boom mic, from the front of the left cup
        if gaming:  # plugged into its socket, through the cup's wall
            boom = part("boom", "boom mic", ["left_cup", "control_board"], lift=(0, 0, -1))
            boom.shapes.use((30, 30, 34)).axle((lx, 0.3, cz - R - 0.15), 0.14, 0.7, 14, along="z")
            start = (lx, 0.3, cz - R - 0.5)
        else:
            boom = part("boom", "boom mic", ["left_cup"])
            boom.post((lx + 0.35, 0.25, cz - R - 0.12), 0.26, 0.45, fixed=(40, 40, 46))  # its pivot, on the cup
            start = (lx + 0.35, 0.5, cz - R - 0.3)
        arm = [start, (lx + 0.9, start[1], cz - R - 1.3), (lx + 1.8, start[1], cz - R - 2.0),
               (lx + 2.6, start[1], cz - R - 2.25)]
        for a, b in zip(arm, arm[1:]):
            boom.shapes.use((36, 36, 40)).rod(a, b, 0.12)
            boom.target(tuple((a[i] + b[i]) / 2 for i in range(3)), (0.4, 0.3, 0.4))
        tip = (lx + 2.75, start[1], cz - R - 2.3)
        boom.shapes.use((44, 44, 50)).axle(tip, 0.16, 0.3, 14)  # the mic, at its tip
        boom.target(tip, (0.4, 0.4, 0.4))
        boom.grow((lx + 1.4, start[1], cz - R - 1.2), (3.0, 0.5, 2.6))
        boom.material = "cable"
        if not gaming:
            foam = part("boom_foam", "foam windscreen", ["boom"])
            foam.lathe(ball_profile(0.3, math.pi), "x", tip, fixed=(40, 40, 44))
            foam.material = "foam"
    if wireless:  # its buttons and its light on the right cup's edge, and the mics' holes on the left one
        rx = X
        rc = next(p for p in board.parts if p.key == "right_cup")
        def rim(deg, out=0.04):  # a point on the cup's edge, round the front (clear of the yoke, round the back)
            a = math.radians(deg)
            return rx + math.cos(a) * (R + out), cz + math.sin(a) * (R + out)
        x, z = rim(-28)
        rc.box((x, 0.45, z), (0.2, 0.22, 0.2), fixed=(70, 66, 62), hit=False)  # its power button
        rc.target((x, 0.45, z), (0.32, 0.3, 0.32), ("power",))
        for deg in (-52, -64):  # volume up and down
            x, z = rim(deg)
            rc.box((x, 0.45, z), (0.17, 0.2, 0.17), fixed=(70, 66, 62), hit=False)
        x, z = rim(-85, 0.0)
        rc.box((x, 0.3, z), (0.3, 0.12, 0.1), fixed=BLACK, hit=False)  # its USB-C socket
        light = Shapes().use((255, 255, 255), "light")
        x, z = rim(-12, 0.06)
        light.box(rc.rel((x, 0.62, z)), (0.08, 0.08, 0.08))
        board.mic["light"], board.mic["light_host"] = light, "right_cup"
        lc = next(p for p in board.parts if p.key == "left_cup")
        for dx in (-0.25, 0.25):
            lc.shapes.use(BLACK).axle(lc.rel((lx + dx, 0.5, cz - R - 0.04)), 0.06, 0.02, 10, along="z")
    if extras:  # dust and a hair or two on the headband's pad
        def on_pad():
            x, z = inner[rnd.randrange(len(inner))]
            return x, 0.79, z
        board.dirt.append(Dirt(pad, specks_on(rnd, 7, on_pad, ("dust", "hair", "hair"))))
    board.size = board.inner = spec["size"]
    board.height = top + 0.05


# ---- computers ----

# A tower lies on its right side on the bench, the way you'd work on one, with its glass side panel up: its bottom to
# the left (-x), its top to the right, its front towards you (-z) and its back away. (A computer is drawn at 30 mm a
# unit, not a key width's 19, so it fits on the bench.)
PC_X = PC_Z = 6.7  # half its height (along x) and half its depth (along z)
PC_T = 0.08  # its steel
PC_TRAY = 0.7  # the top of its motherboard tray (the right side panel is under it, with room for cables between)
PC_GLASS = 6.72  # the top of its walls, where the glass side panel sits
PC_SHROUD = -3.51  # the top of the shroud over the power supply
PC_SLOTS = (0.6, -0.08, -0.76, -1.44)  # its expansion slots, down the back (the first is the graphics card's)
PC_FANS = ((3.6, 3.71), (-0.6, 3.71))  # its front fans' middles (x, y); they're 4 units (120 mm) square
PC_REAR_FAN = (4.1, 4.42)
MB_HOLES = ((6.05, -1.35), (6.05, 4.2), (1.3, -1.35), (1.3, 4.5), (-1.5, -1.35), (-1.5, 6.1))  # x, z
PC_GROMMETS = ((6.34, 6.58, 4.6, 5.4), (6.34, 6.58, -5.6, -5.0), (-2.9, -2.1, -1.6, -0.4), (3.0, 4.4, -2.55, -2.05))
PC_CPU_CUT, PC_PSU_CUT = (2.9, 5.1, 1.8, 4.0), (-6.4, -5.2, 0.9, 1.7)  # the tray's cut-outs (x0, x1, z0, z1)
FILTER_DIRTY, FILTER_CLEAN = (150, 140, 122), (40, 40, 44)
CABLE_BLACK, COPPER = (30, 30, 34), (200, 124, 82)


def sheet(part, axis, at, thick, u, v, tint="case", fixed=SILVER, hit=True):
    """A flat piece of sheet across axis, at `at`: spanning u (x for a sheet across y or z, z across x) and v (z
    across y, y across x or z)."""
    cu, cv, su, sv = (u[0] + u[1]) / 2, (v[0] + v[1]) / 2, u[1] - u[0], v[1] - v[0]
    if axis == "y":
        c, s = (cu, at, cv), (su, thick, sv)
    elif axis == "z":
        c, s = (cu, cv, at), (su, sv, thick)
    else:
        c, s = (at, cv, cu), (thick, sv, su)
    part.box(c, s, tint, fixed, hit)


def holed(part, axis, at, thick, u, v, holes, tint="case", fixed=SILVER, hit=True):
    """A sheet of steel with holes in it (each u0, u1, v0, v1), made of the pieces round them."""
    us = sorted({u[0], u[1]} | {e for h in holes for e in h[:2] if u[0] < e < u[1]})
    vs = sorted({v[0], v[1]} | {e for h in holes for e in h[2:] if v[0] < e < v[1]})
    for v0, v1 in zip(vs, vs[1:]):
        run = None
        for u0, u1 in zip(us, us[1:]):
            cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
            solid = not any(h[0] < cu < h[1] and h[2] < cv < h[3] for h in holes)
            if solid and run is None:
                run = u0
            elif not solid and run is not None:
                sheet(part, axis, at, thick, (run, u0), (v0, v1), tint, fixed, hit)
                run = None
        if run is not None:
            sheet(part, axis, at, thick, (run, us[-1]), (v0, v1), tint, fixed, hit)


def fan_hole(cx, cy, r=1.8):
    """The opening a fan blows through, nearly round (so the corners, where its screws go, stay solid): bands
    across it, each as wide as the circle is at its edge."""
    holes = []
    for y0, y1 in ((0.0, 0.3), (0.3, 0.55), (0.55, 0.75), (0.75, 0.88), (0.88, 0.97)):
        w = r * math.sqrt(1 - y1 * y1)
        holes += [(cx - w, cx + w, cy + y0 * r, cy + y1 * r), (cx - w, cx + w, cy - y1 * r, cy - y0 * r)]
    return holes


def face(shapes, a, b, c, d):
    """A quad, its normal worked out from its corners (wound the way Shapes.box winds them)."""
    A, B, C = Vec3(*a), Vec3(*b), Vec3(*c)
    n = (B - A).cross(C - A)
    shapes.quad(tuple(a), tuple(b), tuple(c), tuple(d), tuple(n.normalized()) if n.length() > 1e-9 else (0, 1, 0))


def fan_blades(board, part, c, r0, r1, depth, axis="z", n=7, colour=(48, 48, 54)):
    """A fan's blades round its hub, swept and pitched: a mesh of their own, on a hub that spins (about z for a fan
    facing along z; about x for a graphics card's, facing down)."""
    def way(u, v, w):
        return (u, v, w) if axis == "z" else (w, v, u)
    s = Shapes().use(colour)
    s.axle(way(0, 0, 0), r0, depth * 0.5, 18, along=axis)  # its hub's cap
    for k in range(n):
        a = 2 * math.pi * k / n
        edges = []
        for r, sweep, chord in ((r0 * 0.95, 0.0, 0.55), (r1, 0.42, 1.0)):
            b = a + sweep
            d, t = (math.cos(b), math.sin(b)), (-math.sin(b), math.cos(b))
            w = chord * 2 * math.pi * r1 / n * 0.42
            lead = way(d[0] * r + t[0] * w / 2, d[1] * r + t[1] * w / 2, depth * 0.3)
            trail = way(d[0] * r - t[0] * w / 2, d[1] * r - t[1] * w / 2, -depth * 0.3)
            edges.append((lead, trail))
        (l0, t0), (l1, t1) = edges
        face(s, l0, l1, t1, t0)  # (both sides of it)
        face(s, t0, t1, l1, l0)
    hub = part.root.attachNewNode(f"{part.key} hub")
    hub.setPos(*part.rel(c))
    s.mesh(hub, f"{part.key} blades")
    board.special.setdefault("fans", []).append((hub, axis, part.key))


def fan_frame(part, c, size=4.0, depth=0.83, colour=(34, 34, 38)):
    """A square fan's frame, facing along z: its four sides, its corners (each with a screw hole through it) filled
    in round the opening, and the motor's hub held on three struts at the back."""
    x, y, z = c
    h, b = size / 2, 0.2
    for dy in (h - b / 2, -h + b / 2):
        part.box((x, y + dy, z), (size, b, depth), fixed=colour)
    for dx in (h - b / 2, -h + b / 2):
        part.box((x + dx, y, z), (b, size - 2 * b, depth), fixed=colour)
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.box((x + sx * (h - 0.42), y + sy * (h - 0.42), z), (0.44, 0.44, depth), fixed=colour, hit=False)
            for f in (-1, 1):
                part.shapes.use((14, 14, 16)).axle(part.rel((x + sx * (h - 0.32), y + sy * (h - 0.32),
                                                             z + f * depth / 2)), 0.09, 0.014, 10, along="z")
    hub = size * 0.17
    part.shapes.use(colour).axle(part.rel((x, y, z + depth * 0.3)), hub, depth * 0.36, 18, along="z")  # its motor
    for k in range(3):  # its struts, out to the frame
        a = math.pi / 2 + k * 2 * math.pi / 3
        part.shapes.use(colour).rod(part.rel((x + math.cos(a) * hub, y + math.sin(a) * hub, z + depth * 0.42)),
                                    part.rel((x + math.cos(a) * (h - 0.1), y + math.sin(a) * (h - 0.1),
                                              z + depth * 0.42)), 0.07)
    part.target(c, (size, size, depth))


def case_fan(board, part, c, colour=(34, 34, 38)):
    """A 120 mm case fan facing along z, with its blades."""
    fan_frame(part, c, 4.0, 0.83, colour)
    fan_blades(board, part, c, 0.62, 1.7, 0.83)


def thumb_z(part, x, y, z, toward):
    """A thumb screw going in along z (from the front, or the back): a knurled head you can turn by hand."""
    hz = z + toward * 0.07
    part.shapes.use((44, 44, 50)).axle(part.rel((x, y, hz)), 0.2, 0.14, 16, along="z")
    knurl(part, (x, y, hz), 0.205, 0.12, "z", 14, (30, 30, 34))
    part.shapes.use(SILVER).axle(part.rel((x, y, z - toward * 0.12)), 0.06, 0.24, 8, along="z")  # its thread
    part.grow((x, y, hz), (0.42, 0.42, 0.16))
    part.target((x, y, hz), (0.46, 0.46, 0.2))
    part.spin, part.thumb = "z", True


def fixed_screw_z(part, x, y, z, toward):
    """A screw head that stays put (holding something that isn't a part of its own), facing along z."""
    part.shapes.use(SILVER).axle(part.rel((x, y, z)), 0.12, 0.05, 12, along="z")
    for size in ((0.18, 0.03, 0.008), (0.03, 0.18, 0.008)):
        part.box((x, y, z + toward * 0.027), size, fixed=(108, 110, 120), hit=False)


def pc_chassis(board, part, spec, full):
    """The case's steel: its walls (with openings for its fans, its I/O shield, its slots and its power supply), the
    motherboard tray (its brass standoffs, its grommets, the cut-out behind the CPU), the shroud over the power
    supply, its feet underneath, and the front I/O across the top of its front. A complete PC has its fans, filters,
    front panel and right side panel fixed on too (a case on its own has them as parts)."""
    X, Z, T, top = PC_X, PC_Z, PC_T, PC_GLASS
    y0 = 0.08  # (the right side panel is under the walls)
    ch = part("chassis", "chassis")
    ch.material = "metal"
    io = (1.0, 6.1, 0.76, 2.3)
    rear_fan = fan_hole(*PC_REAR_FAN)
    psu_hole = (-6.2, -4.05, 1.3, 5.5)
    slots = [(c - 0.25, c + 0.25, 1.15, 4.45) for c in PC_SLOTS]
    holed(ch, "z", Z - T / 2, T, (-X, X), (y0, top), [io, psu_hole] + rear_fan + slots)  # its back
    fronts = [h for x, y in PC_FANS for h in fan_hole(x, y)]
    holed(ch, "z", -Z + T / 2, T, (-X, X), (y0, top), fronts)  # its front
    holed(ch, "x", X - T / 2, T, (-Z + T, Z - T), (y0, top), [(-4.6, 4.6, 1.0, 5.8)])  # its top
    holed(ch, "x", -X + T / 2, T, (-Z + T, Z - T), (y0, top), [(1.9, 6.3, 1.0, 5.8)])  # its bottom
    grille = (60, 62, 68)  # (stamped grilles over the openings: thin bars)
    for k in range(1, 6):
        ch.box((PC_REAR_FAN[0] - 1.8 + k * 0.6, PC_REAR_FAN[1], Z - T / 2), (0.05, 3.6, T * 0.6), fixed=grille,
               hit=False)
    for k in range(1, 8):
        ch.box((X - T / 2, 1.0 + k * 0.6, 0), (T * 0.6, 0.05, 9.2), fixed=grille, hit=False)
        ch.box((-X + T / 2, 1.0 + k * 0.6, 4.1), (T * 0.6, 0.05, 4.4), fixed=grille, hit=False)
    # the motherboard tray, with its cut-outs, and rubber grommets for the cables to pass through
    holed(ch, "y", PC_TRAY - T / 2, T, (-X + T, X - T), (-Z + T, Z - T),
          [PC_CPU_CUT, PC_PSU_CUT] + list(PC_GROMMETS))
    for x0, x1, z0, z1 in PC_GROMMETS:
        ch.box(((x0 + x1) / 2, PC_TRAY - T / 2, (z0 + z1) / 2), (x1 - x0, T * 0.6, z1 - z0), fixed=RUBBER, hit=False)
        wide = x1 - x0 > z1 - z0  # (and its slit)
        ch.box(((x0 + x1) / 2, PC_TRAY - T * 0.2, (z0 + z1) / 2),
               ((x1 - x0) * 0.8 if wide else 0.03, T * 0.7, 0.03 if wide else (z1 - z0) * 0.8), fixed=(10, 10, 12),
               hit=False)
    for x, z in MB_HOLES:  # the brass standoffs the motherboard screws onto
        ch.post((x, PC_TRAY, z), 0.1, 0.28, fixed=GOLDEN, hit=False)
    # the shroud over the power supply (its cover is a part of its own), with holes for the power cables
    sx = PC_SHROUD
    holed(ch, "x", sx, T, (-5.6, Z - T), (PC_TRAY, 6.62), [(-2.6, -1.8, 1.9, 5.6), (0.2, 1.0, 1.9, 5.6)])
    sheet(ch, "z", -5.64, T, (-X + T, sx + T / 2), (PC_TRAY, 6.62))  # its front end
    ch.box(((-X + T + sx + T / 2) / 2, 6.58, 6.29), (sx + T / 2 - (-X + T), 0.08, 0.66), "case", hit=False)
    for z in (2.5, 5.8):  # rubber pads on the floor, for the power supply to sit on
        ch.box((-6.59, 3.4, z), (0.06, 4.4, 0.4), fixed=RUBBER, hit=False)
    for z in (-5.9, 5.9):  # its feet, underneath (the side towards the bench's left, as it lies)
        for y in (0.5, 6.3):
            ch.shapes.use(RUBBER).axle(ch.rel((-X - 0.17, y, z)), 0.3, 0.34, 16, along="x")
    ch.grow((-X - 0.17, 3.4, 0), (0.34, 6.4, 12.4))
    for x in (-6.35, 6.35):  # brackets in the corners, for the glass panel's thumb screws
        for z in (-6.35, 6.35):
            ch.box((x, 6.66, z), (0.5, 0.08, 0.5), "case", hit=False)
            ch.post((x, 6.7, z), 0.18, 0.02, fixed=RUBBER, hit=False)
    # the slot covers in the back, where no card is (each held by a screw at its end), and the I/O shield's frame
    for i, c in enumerate(PC_SLOTS):
        if full and i < 2:  # (the graphics card's bracket is there)
            continue
        ch.box((c, 2.95, Z + 0.02), (0.62, 3.9, 0.04), "case", hit=False)
        for k in range(4):
            ch.box((c, 1.5 + k * 0.7, Z + 0.042), (0.3, 0.45, 0.01), fixed=(20, 20, 24), hit=False)
        fixed_screw_z(ch, c, 4.72, Z + 0.065, 1)
    # the front I/O, a strip across the top of its front, flush with the front panel: the power button, the reset
    # button, two USB ports, a USB-C, a headphone jack (and on a complete PC, its power light)
    fz = -Z - 0.45
    ch.box((6.3, (y0 + top) / 2, -Z - 0.225), (0.84, top - y0, 0.45), "inside")
    ch.shapes.use(SILVER).axle(ch.rel((6.29, 5.0, fz - 0.03)), 0.27, 0.06, 20, along="z")
    ch.shapes.use(spec["accent"]).axle(ch.rel((6.29, 5.0, fz - 0.06)), 0.21, 0.06, 20, along="z")
    ch.target((6.29, 5.0, fz - 0.06), (0.62, 0.62, 0.2), ("power",))
    ch.shapes.use((24, 24, 28)).axle(ch.rel((6.29, 4.3, fz - 0.03)), 0.1, 0.06, 12, along="z")
    ch.target((6.29, 4.3, fz - 0.04), (0.36, 0.36, 0.16), ("reset",))
    for y in (2.2, 2.9):
        ch.box((6.29, y, fz - 0.004), (0.2, 0.5, 0.012), fixed=(12, 12, 14), hit=False)
        ch.box((6.29, y, fz - 0.007), (0.06, 0.4, 0.012), fixed=(60, 110, 210), hit=False)
    ch.target((6.29, 2.55, fz - 0.03), (0.44, 1.3, 0.12), ("usb",))
    ch.box((6.29, 3.55, fz - 0.004), (0.1, 0.32, 0.012), fixed=(12, 12, 14), hit=False)  # USB-C
    ch.shapes.use((12, 12, 14)).axle(ch.rel((6.29, 1.5, fz - 0.004)), 0.08, 0.012, 10, along="z")  # the jack
    if full:
        light = Shapes().use((255, 255, 255), "light")
        light.box((6.29, 5.7, fz - 0.005), (0.07, 0.36, 0.012))
        board.mic["light"], board.mic["light_host"] = light, "chassis"
    # the front I/O's cables: in from the strip, along the top of the tray, through a grommet and along behind it,
    # and back out of the grommet by the bottom of the motherboard
    ch.wire([(6.3, 0.8, -6.6), (6.3, 0.8, -5.3), (6.46, 0.8, -5.3), (6.46, 0.35, -5.3), (-2.5, 0.35, -5.3),
             (-2.5, 0.35, -1.0), (-2.5, 0.66, -1.0)], 0.12, CABLE_BLACK)
    ch.box((2.6, 0.3, -4.2), (1.2, 0.14, 0.8), fixed=(40, 40, 46), hit=False)  # a fan hub, behind the tray
    ch.box((2.6, 0.38, -4.2), (1.0, 0.03, 0.6), fixed=PCB_GREEN, hit=False)
    if not full:  # a case on its own: the front I/O's plugs, bundled up on the tray with a tie, ready for a board
        ch.wire([(-2.5, 0.66, -1.0), (-2.5, 0.76, -1.0), (-2.5, 0.76, 0.6)], 0.12, CABLE_BLACK)
        ch.box((-2.5, 0.78, -0.3), (0.2, 0.18, 0.08), fixed=(26, 26, 30), hit=False)
        ch.box((-2.5, 0.77, 0.86), (0.36, 0.14, 0.5), fixed=(60, 90, 200), hit=False)  # the USB 3 plug
        ch.wire([(-2.5, 0.76, 0.2), (-2.0, 0.76, 0.2), (-2.0, 0.76, 0.5)], 0.08, CABLE_BLACK)
        for k, col in enumerate(((220, 70, 60), (240, 240, 236), (70, 160, 90), (236, 200, 80))):
            ch.box((-2.12 + k * 0.08, 0.75, 0.6), (0.07, 0.08, 0.2), fixed=col, hit=False)  # the switch and light pins
    else:  # a complete PC: its fans and filters, its front panel and right side panel, all on for good, and the
        # fans' cables through the grommets to the hub
        for x, y in PC_FANS:
            case_fan(board, ch, (x, y, -6.205))
            for sx in (-1, 1):
                for sy in (-1, 1):
                    fixed_screw_z(ch, x + sx * 1.68, y + sy * 1.68, -Z - 0.025, -1)
            ch.wire([(x - 1.7, y - 1.9, -5.85), (x - 1.7, 0.85, -5.85), (x - 1.7, 0.85, -5.3), (6.4, 0.85, -5.3),
                     (6.4, 0.25, -5.3), (3.2, 0.25, -5.3), (3.2, 0.25, -4.2)], 0.08, CABLE_BLACK)
        case_fan(board, ch, (PC_REAR_FAN[0], PC_REAR_FAN[1], 6.205))
        for sx in (-1, 1):
            for sy in (-1, 1):
                fixed_screw_z(ch, PC_REAR_FAN[0] + sx * 1.68, PC_REAR_FAN[1] + sy * 1.68, Z + 0.025, 1)
        ch.wire([(6.05, 6.0, 5.85), (6.46, 6.0, 5.85), (6.46, 0.8, 5.85), (6.46, 0.8, 5.25), (6.46, 0.25, 5.25),
                 (6.3, 0.25, 5.25), (6.3, 0.25, -4.2), (3.2, 0.25, -4.2)], 0.08, CABLE_BLACK)
        pc_filters(board, part, spec, ch)
        pc_front_panel(ch, spec)
        ch.box((0, 0.04, 0), (2 * X, 0.08, 2 * Z), "case", hit=False)  # the right side panel, underneath
        ch.box((0, 0.3, Z + 0.03), (2 * X, 0.6, 0.06), "case", hit=False)
        for x in (-4.5, 4.5):
            ch.shapes.use((44, 44, 50)).axle(ch.rel((x, 0.32, Z + 0.13)), 0.2, 0.14, 16, along="z")
    return ch


def filter_sheet(part, axis, at, u, v):
    """A dust filter: fine mesh (clogged, or clean) in a thin frame."""
    frame = (34, 34, 38)
    sheet(part, axis, at, 0.05, u, v, "filter")
    m = 0.14
    for uu, vv in (((u[0], u[0] + m), v), ((u[1] - m, u[1]), v), (u, (v[0], v[0] + m)), (u, (v[1] - m, v[1]))):
        sheet(part, axis, at, 0.062, uu, vv, None, frame, False)


def pc_filters(board, part, spec, host=None):
    """Its three dust filters: behind the front panel, on the top (it holds on by magnets), and under the power
    supply (it slides out to the front). On a case of its own, they're parts; on a complete PC, part of it."""
    made = []
    for key, name, axis, at, u, v, lift in (
            ("front_filter", "front dust filter", "z", -6.81, (-6.5, 5.75), (0.5, 6.3), (0, 0, -1)),
            ("top_filter", "top dust filter", "x", 6.73, (-4.9, 4.9), (0.7, 6.1), (1, 0, 0)),
            ("bottom_filter", "bottom dust filter", "x", -6.73, (1.7, 6.5), (0.9, 5.9), (0, 0, -1))):
        p = host or part(key, name, ["chassis"], lift=lift)
        filter_sheet(p, axis, at, u, v)
        if host is None:
            p.material = "plastic"
            made.append(p)
    return made


def pc_front_panel(p, spec):
    """The front panel: a frame round a fine mesh (you see the dust filter and the fans through it), with clips on
    its back that push into the chassis."""
    z0, z1 = -7.15, -6.86
    x0, x1, y0, y1 = -6.72, 5.86, 0.08, 6.72
    zc, d, m = (z0 + z1) / 2, z1 - z0, 0.36
    for x, y, w, h in (((x0 + x1) / 2, y0 + m / 2, x1 - x0, m), ((x0 + x1) / 2, y1 - m / 2, x1 - x0, m),
                       (x0 + m / 2, (y0 + y1) / 2, m, y1 - y0 - 2 * m), (x1 - m / 2, (y0 + y1) / 2, m, y1 - y0 - 2 * m)):
        p.box((x, y, zc), (w, h, d), "inside")
    mesh = (62, 62, 68)
    k = x0 + m + 0.3
    while k < x1 - m:
        p.box((k, (y0 + y1) / 2, z0 + 0.03), (0.04, y1 - y0 - 2 * m, 0.04), fixed=mesh, hit=False)
        k += 0.3
    k = y0 + m + 0.3
    while k < y1 - m:
        p.box(((x0 + x1) / 2, k, z0 + 0.03), (x1 - x0 - 2 * m, 0.04, 0.04), fixed=mesh, hit=False)
        k += 0.3
    for x, y in ((-6.45, 0.28), (-6.45, 6.52), (5.6, 0.28), (5.6, 6.52)):  # its clips, into the chassis
        p.box((x, y, -6.79), (0.3, 0.16, 0.14), fixed=(28, 28, 32), hit=False)
    p.target(((x0 + x1) / 2, (y0 + y1) / 2, zc), (x1 - x0, y1 - y0, d))


def pc_dust(rnd, n, x, z, y, keep_out=(), margin=0.14):
    """n specks of dust (as a dusty one has) on a flat top at height y, inside x and z, but not on what's in
    keep_out (x0, x1, z0, z1 each)."""
    def where():
        for _ in range(60):
            px, pz = rnd.uniform(*x), rnd.uniform(*z)
            if not any(a - margin < px < b + margin and c - margin < pz < d + margin for a, b, c, d in keep_out):
                return px, y, pz
        return (x[0] + x[1]) / 2, y, z[0]
    return specks_on(rnd, n, where, ("dust", "dust", "dust", "hair"))  # (no crumbs in a computer)


def build_pc(board, part, spec, rnd, extras):
    """A computer, lying on its side, glass up. A case on its own: the chassis, its right side panel (two thumb
    screws at the back), two front fans and a rear fan (four screws each), three dust filters, the front panel, the
    cover over the power supply's shroud, and the glass side panel on four thumb screws. A complete desktop PC: the
    chassis with its fans, filters and panels on for good, and inside it the power supply (four screws at the back),
    the motherboard (six screws), the CPU in its socket, the cooler on it (two screws, and its fan clipped on), two
    memory sticks, an M.2 SSD (a screw), the graphics card (two screws at its bracket), and their power cables and
    the front panel's; then the shroud's cover, and the glass."""
    full = spec["form"] == "pc_tower"
    X, Z = PC_X, PC_Z
    screws = [0]

    def screw(name, below, origin, lift):
        s = part(f"screw{screws[0]}", name, below, screw=True, origin=origin, lift=lift)
        screws[0] += 1
        return s, screws[0] - 1

    ch = pc_chassis(board, part, spec, full)
    inside = []  # (what the glass goes on over)
    if not full:
        right = part("right_panel", "right side panel", ["chassis"], lift=(0, -1, 0))
        right.box((0, 0.04, 0), (2 * X, 0.08, 2 * Z), "case")
        right.box((0, 0.3, Z + 0.03), (2 * X, 0.6, 0.06), "case")  # its flange, round the back
        right.material = "metal"
        for x in (-4.5, 4.5):
            s, i = screw("thumb screw", ["right_panel"], (x, 0.32, Z + 0.13), (0, 0, 1))
            thumb_z(s, x, 0.32, Z + 0.06, 1)
            right.target((x, 0.32, Z + 0.065), (0.3, 0.3, 0.02), ("hole", i))
        fans = []
        for k, (x, y) in enumerate(PC_FANS):
            fan = part(f"front_fan{k}", "front fan", ["chassis"])
            case_fan(board, fan, (x, y, -6.205))
            fan.wire([(x - 1.7, y - 1.9, -5.85), (x - 1.7, 0.78, -5.85), (x - 1.7, 0.78, -5.55)], 0.08,
                     CABLE_BLACK)  # its cable, and the plug on its end, lying on the tray for a board to come
            fan.box((x - 1.7, 0.76, -5.38), (0.26, 0.12, 0.34), fixed=(26, 26, 30), hit=False)
            fan.material = "plastic"
            fans.append(fan)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    px, py = x + sx * 1.68, y + sy * 1.68
                    s, i = screw("fan screw", [fan.key], (px, py, -Z - 0.025), (0, 0, -1))
                    screw_head_z(s, px, py, -Z - 0.025, -1)
                    ch.target((px, py, -Z - 0.004), (0.3, 0.3, 0.012), ("hole", i))
        front_screws = [f"screw{n}" for n in range(2, screws[0])]
        rear = part("rear_fan", "rear fan", ["chassis"])
        rx, ry = PC_REAR_FAN
        case_fan(board, rear, (rx, ry, 6.205))
        rear.wire([(rx - 1.85, ry - 1.8, 5.85), (rx - 1.85, 0.78, 5.85), (rx - 1.85, 0.78, 5.55)], 0.08, CABLE_BLACK)
        rear.box((rx - 1.85, 0.76, 5.38), (0.26, 0.12, 0.34), fixed=(26, 26, 30), hit=False)
        rear.material = "plastic"
        fans.append(rear)
        for sx in (-1, 1):
            for sy in (-1, 1):
                px, py = rx + sx * 1.68, ry + sy * 1.68
                s, i = screw("fan screw", ["rear_fan"], (px, py, Z + 0.025), (0, 0, 1))
                screw_head_z(s, px, py, Z + 0.025, 1)
                ch.target((px, py, Z + 0.004), (0.3, 0.3, 0.012), ("hole", i))
        filters = pc_filters(board, part, spec)
        filters[0].below += front_screws  # (the front filter goes on over the front fans' screws)
        bezel = part("front_panel", "front panel", ["chassis", "front_filter"], lift=(0, 0, -1))
        pc_front_panel(bezel, spec)
        bezel.material = "plastic"
        clogged = rnd.sample(filters, rnd.choice((1, 2, 2, 3)))  # (how many have clogged: it's never the same)
        for f in clogged:
            f.grimy = True
        board.special["clogged"] = len(clogged)
        inside = [f.key for f in fans]
    else:
        psu = part("psu", "power supply", ["chassis"])
        px0, px1, py0, py1, pz0, pz1 = -6.56, -3.69, 0.95, 5.85, 1.95, 6.62
        psu.box(((px0 + px1) / 2, (py0 + py1) / 2, (pz0 + pz1) / 2), (px1 - px0, py1 - py0, pz1 - pz0),
                fixed=(36, 36, 40))
        psu.box((-5.12, py1 + 0.005, 4.4), (2.2, 0.01, 2.8), fixed=(206, 206, 200), hit=False)  # its label
        for k in range(5):
            psu.box((-5.12, py1 + 0.011, 3.3 + k * 0.5), (1.6 - (k % 2) * 0.5, 0.004, 0.08), fixed=(120, 120, 120),
                    hit=False)
        for r in (2.0, 1.5, 1.0, 0.5):  # its fan's grille, underneath (it breathes in through the bottom filter)
            psu.shapes.use((150, 150, 156)).axle(psu.rel((px0 - 0.005, 3.4, 4.3)), r, 0.012, 28, along="x")
            psu.shapes.use((24, 24, 28)).axle(psu.rel((px0 - 0.006, 3.4, 4.3)), r - 0.07, 0.012, 28, along="x")
        psu.box((-5.12, 4.5, pz1 + 0.005), (2.0, 1.6, 0.01), fixed=(20, 20, 22), hit=False)  # its back: a grille,
        for k in range(6):
            psu.box((-6.0 + k * 0.36, 4.5, pz1 + 0.011), (0.04, 1.5, 0.006), fixed=(70, 70, 76), hit=False)
        psu.box((-5.5, 2.0, pz1 + 0.02), (0.5, 0.7, 0.04), fixed=(14, 14, 16), hit=False)  # the mains socket
        for dx, dy in ((-0.12, 0.12), (0.12, 0.12), (0, -0.16)):
            psu.box((-5.5 + dx, 2.0 + dy, pz1 + 0.042), (0.06, 0.12, 0.01), fixed=SILVER, hit=False)
        psu.box((-4.5, 2.0, pz1 + 0.03), (0.3, 0.46, 0.06), fixed=(54, 54, 58), hit=False)  # and the switch
        for sx, sy, w, h in ((-5.0, 2.2, 0.8, 0.6), (-4.3, 4.4, 0.6, 0.6), (-5.8, 1.4, 0.6, 0.5), (-5.9, 3.6, 0.6, 0.5),
                             (-5.0, 3.6, 0.6, 0.5), (-4.3, 3.0, 0.6, 0.5)):  # its modular sockets, on its front
            psu.box((sx, sy, pz0 - 0.01), (w, h, 0.02), fixed=(14, 14, 16), hit=False)
        psu.material = "metal"
        for x, y in ((-6.36, 1.12), (-6.36, 5.68), (-3.89, 1.12), (-3.89, 5.68)):
            s, i = screw("screw", ["psu"], (x, y, Z + 0.025), (0, 0, 1))
            screw_head_z(s, x, y, Z + 0.025, 1)
            ch.target((x, y, Z + 0.004), (0.3, 0.3, 0.012), ("hole", i))
        # the motherboard, on its standoffs
        mb = part("motherboard", "motherboard", ["chassis"])
        X0, X1, Z0, Z1, Y0, Y1 = -1.8, 6.3, -1.65, 6.45, 0.98, 1.04
        mb.box(((X0 + X1) / 2, (Y0 + Y1) / 2, (Z0 + Z1) / 2), (X1 - X0, Y1 - Y0, Z1 - Z0), fixed=(36, 40, 48))
        mb.material = "board"
        dark, white = (28, 28, 32), (236, 236, 230)

        def on(c, s, col):
            mb.box(c, s, fixed=col, hit=False)
        on((4.0, 0.935, 2.9), (2.4, 0.05, 2.4), (40, 40, 44))  # the cooler's backplate, behind it
        on((4.0, 1.07, 2.9), (1.7, 0.06, 1.7), (70, 72, 80))  # the CPU socket, and its lever
        on((4.95, 1.11, 2.9), (0.05, 0.05, 1.6), SILVER)
        for z in (0.35, 0.75):  # the memory slots, with a latch at each end
            on((3.8, 1.17, z), (4.7, 0.26, 0.2), dark)
            for x in (1.5, 6.1):
                on((x, 1.24, z), (0.1, 0.4, 0.2), (210, 210, 204))
        on((0.6, 1.2, 4.0), (0.3, 0.32, 3.0), dark)  # the graphics card's slot (PCIe x16), and a little one
        on((-0.76, 1.2, 4.95), (0.3, 0.32, 1.1), dark)
        on((1.185, 1.1, 4.02), (0.78, 0.12, 0.25), dark)  # the M.2 socket, and the standoff its end screws to
        mb.post((1.185, Y1, 1.23), 0.08, 0.09, fixed=GOLDEN, hit=False)
        on((3.5, 1.27, -1.33), (1.8, 0.46, 0.36), white)  # the 24-pin power socket
        on((6.0, 1.22, 5.0), (0.28, 0.36, 0.62), white)  # the CPU's 8-pin
        on((6.1, 1.12, 1.35), (0.12, 0.16, 0.3), white)  # the CPU fan's header
        on((5.15, 1.37, 4.72), (1.1, 0.66, 1.45), (80, 84, 92))  # the power stages' heatsink, with fins
        for k in range(5):
            on((4.7 + k * 0.22, 1.71, 4.72), (0.05, 0.02, 1.4), (110, 114, 122))
        on((-1.15, 1.2, 3.1), (0.6, 0.32, 1.0), (80, 84, 92))  # the chipset's heatsink
        on((-1.62, 1.1, -0.7), (0.2, 0.12, 0.5), dark)  # the front panel's header, and the USB 3 one
        on((-1.6, 1.12, 0.65), (0.25, 0.16, 0.7), (60, 90, 200))
        mb.post((2.2, Y1, -0.6), 0.32, 0.05, fixed=SILVER, hit=False)  # its little coin battery
        for z in (2.0, 2.5, 3.0, 3.5):  # capacitors
            mb.post((5.6, Y1, z), 0.1, 0.3, fixed=(60, 62, 70), hit=False)
        on((3.55, 1.62, 6.12), (5.1, 1.16, 1.0), (150, 152, 158))  # the ports at the back, through the I/O shield
        for y, col in ((1.25, (60, 110, 210)), (1.6, (60, 110, 210)), (1.95, (12, 12, 14))):
            for k in range(4):
                on((1.6 + k * 0.5, y, 6.625), (0.4, 0.18, 0.02), col)
        on((4.1, 1.45, 6.625), (0.5, 0.5, 0.02), (12, 12, 14))  # the network socket
        for k, col in enumerate(((120, 200, 120), (230, 120, 190), (90, 160, 230))):
            mb.shapes.use(col).axle(mb.rel((5.0 + k * 0.32, 1.7, 6.625)), 0.09, 0.02, 10, along="z")  # audio
        holed(mb, "z", 6.66, 0.02, (1.0, 6.1), (0.76, 2.3), [(1.3, 5.8, 1.05, 2.15)], None, (176, 178, 186), False)
        mb.target(((X0 + X1) / 2, (Y0 + Y1) / 2, (Z0 + Z1) / 2), (X1 - X0, 0.1, Z1 - Z0))
        mb_holes = []
        for x, z in MB_HOLES:
            mb.post((x, Y1, z), 0.15, 0.004, fixed=GOLDEN, hit=False)
            mb_holes.append((x, z))
        for x, z in mb_holes:
            s, i = screw("screw", ["motherboard"], (x, 1.1, z), (0, 1, 0))
            s.post((x, Y1, z), 0.13, 0.08, fixed=SILVER)
            for size in ((0.18, 0.008, 0.03), (0.03, 0.008, 0.18)):
                s.box((x, Y1 + 0.084, z), size, fixed=(108, 110, 120), hit=False)
            mb.target((x, Y1 + 0.02, z), (0.3, 0.04, 0.3), ("hole", i))
        # the CPU, in its socket: old paste dried on it
        cpu = part("cpu", "CPU", ["motherboard"])
        cpu.box((4.0, 1.12, 2.9), (1.25, 0.04, 1.25), fixed=(40, 110, 70))
        cpu.box((4.0, 1.17, 2.9), (1.05, 0.06, 1.05), fixed=SILVER)
        cpu.material = "board"
        old, fresh = Shapes(), Shapes()
        for _ in range(rnd.randint(9, 15)):  # dried out, crumbly and patchy, where the cooler pressed it flat
            s_ = rnd.uniform(0.14, 0.34)
            old.use(rnd.choice(((150, 150, 146), (128, 128, 126), (170, 168, 160)))).box(
                (4.0 + rnd.uniform(-0.38, 0.38), 1.2 + rnd.uniform(0.003, 0.008), 2.9 + rnd.uniform(-0.38, 0.38)),
                (s_, 0.012, s_ * rnd.uniform(0.6, 1.2)))
        fresh.use((176, 176, 172)).cylinder((4.0, 1.2, 2.9), 0.2, 0.05, 16)  # a fresh, pea-sized dot
        board.attach.append((old, "cpu", "paste_old", False))
        board.attach.append((fresh, "cpu", "paste_new", True))
        # the cooler: a copper base on the CPU, heat pipes up through a tower of fins, a crossbar its two spring
        # screws hold down; and its fan, clipped on the front of the fins
        cooler = part("cooler", "CPU cooler", ["cpu"])
        cooler.box((4.0, 1.3, 2.9), (1.2, 0.2, 1.2), fixed=COPPER)
        cooler.box((4.0, 1.45, 2.9), (0.32, 0.1, 3.1), fixed=(60, 62, 70))
        for x in (3.45, 3.82, 4.18, 4.55):
            cooler.shapes.use(COPPER).rod(cooler.rel((x, 1.38, 2.9)), cooler.rel((x, 5.76, 2.9)), 0.08)
        for k in range(28):
            cooler.box((4.0, 2.22 + k * 0.122, 2.9), (4.0, 0.025, 1.7), fixed=(196, 198, 206), hit=False)
        cooler.box((4.0, 5.68, 2.9), (4.04, 0.06, 1.74), fixed=(40, 40, 46), hit=False)  # its top cap
        cooler.box((4.0, 5.72, 2.9), (2.0, 0.02, 0.3), fixed=spec["accent"], hit=False)
        cooler.grow((4.0, 3.5, 2.9), (4.04, 4.5, 1.74))
        cooler.target((4.0, 3.9, 2.9), (4.04, 3.6, 1.74))
        cooler.target((4.0, 1.4, 2.9), (1.3, 0.3, 3.1))
        cooler.material = "metal"
        cooler_screws = []
        for z in (1.5, 4.3):
            s, i = screw("spring screw", ["cooler"], (4.0, 1.58, z), (0, 1, 0))
            s.post((4.0, 1.5, z), 0.13, 0.14, fixed=SILVER)
            s.post((4.0, 1.5, z), 0.07, 0.02, fixed=SILVER, hit=False)
            for size in ((0.18, 0.008, 0.03), (0.03, 0.008, 0.18)):
                s.box((4.0, 1.644, z), size, fixed=(108, 110, 120), hit=False)
            cooler.target((4.0, 1.51, z), (0.3, 0.03, 0.3), ("hole", i))
            cooler_screws.append(s.key)
        cfan = part("cooler_fan", "cooler fan", ["cooler", cooler_screws[0]])
        case_fan(board, cfan, (4.0, 3.6, 1.615))
        for x in (2.1, 5.9):  # its wire clips, hooked into the fins
            for y in (2.4, 5.45):
                cfan.shapes.use(SILVER).rod(cfan.rel((x, y, 1.9)), cfan.rel((x, y, 2.3)), 0.03)
        cfan.wire([(5.85, 1.75, 1.5), (6.12, 1.75, 1.5), (6.12, 1.3, 1.5), (6.12, 1.3, 1.36)], 0.06, CABLE_BLACK)
        cfan.box((6.1, 1.26, 1.35), (0.15, 0.12, 0.3), fixed=WHITE, hit=False)  # its plug, on the header
        cfan.material = "plastic"
        rams = []
        for k, z in enumerate((0.35, 0.75)):
            r = part(f"ram{k}", "memory stick", ["motherboard"])
            r.box((3.8, 1.27, z), (4.4, 0.24, 0.06), fixed=PCB_GREEN, hit=False)
            r.box((3.8, 1.85, z), (4.36, 0.9, 0.15), fixed=spec["accent"])
            r.box((3.8, 2.31, z), (4.3, 0.02, 0.06), fixed=(50, 50, 56), hit=False)
            r.material = "board"
            rams.append(r.key)
        ssd = part("ssd", "M.2 SSD", ["motherboard"], lift=(0, 0.5, -1))
        ssd.box((1.185, 1.15, 2.6), (0.73, 0.04, 2.67), fixed=(30, 30, 34))
        ssd.box((1.185, 1.175, 2.45), (0.6, 0.01, 1.7), fixed=(220, 220, 214), hit=False)
        ssd.box((1.185, 1.15, 3.97), (0.6, 0.03, 0.12), fixed=GOLDEN, hit=False)
        ssd.material = "board"
        s, i = screw("screw", ["ssd"], (1.185, 1.2, 1.23), (0, 1, 0))
        s.post((1.185, 1.17, 1.23), 0.1, 0.05, fixed=SILVER)
        mb.target((1.185, 1.175, 1.23), (0.24, 0.05, 0.24), ("hole", i))  # (under the screw's head)
        # the graphics card: its board standing in its slot, the cooler and its two fans facing down the case, a
        # backplate, its power socket on the top edge, and the bracket at the back, held by two screws
        gpu = part("gpu", "graphics card", ["motherboard"])
        gpu.box((0.6, 2.85, 3.26), (0.06, 3.4, 6.72), fixed=(30, 60, 40), hit=False)
        gpu.box((0.6, 1.25, 4.0), (0.05, 0.2, 2.8), fixed=GOLDEN, hit=False)
        gpu.box((0.665, 3.0, 3.15), (0.05, 3.1, 6.5), fixed=(48, 50, 58))
        shroud = (34, 36, 42)
        g_fans = ((4.55, 3.0), (1.75, 3.0))
        holed(gpu, "x", -0.725, 0.05, (-0.1, 6.55), (1.45, 4.6), [h for z, y in g_fans for h in fan_hole(z, y, 1.3)],
              None, shroud)
        for y, h in ((1.475, 0.05), (4.575, 0.05)):
            gpu.box((-0.1, y, 3.225), (1.3, h, 6.65), fixed=shroud)
        gpu.box((-0.1, 3.025, -0.075), (1.3, 3.1, 0.05), fixed=shroud)
        gpu.box((-0.72, 1.6, 3.225), (0.02, 0.06, 6.6), fixed=spec["accent"], hit=False)
        for k in range(42):  # its heatsink's fins, behind the fans
            gpu.box((-0.05, 3.0, 0.05 + k * 0.155), (0.9, 3.0, 0.03), fixed=(150, 152, 160), hit=False)
        for z, y in g_fans:
            fan_blades(board, gpu, (-0.62, y, z), 0.42, 1.2, 0.16, "x", 9)
        gpu.box((0.42, 4.725, 0.6), (0.28, 0.25, 0.6), fixed=BLACK, hit=False)  # its power socket, by its board
        gpu.box((0.26, 2.975, 6.72), (1.32, 3.95, 0.04), fixed=SILVER)  # its bracket
        for y in (1.6, 2.3, 3.0, 3.7):
            gpu.box((0.6, y, 6.745), (0.16, 0.5, 0.02), fixed=BLACK, hit=False)  # its screen sockets
        for k in range(4):
            gpu.box((-0.08, 1.6 + k * 0.75, 6.745), (0.3, 0.5, 0.012), fixed=(20, 20, 24), hit=False)
        gpu.material = "board"
        for x in (0.6, -0.08):
            s, i = screw("screw", ["gpu"], (x, 4.72, Z + 0.065), (0, 0, 1))
            screw_head_z(s, x, 4.72, Z + 0.065, 1)
            gpu.target((x, 4.72, Z + 0.042), (0.28, 0.28, 0.012), ("hole", i))
        # the power supply's cables: the 24-pin to the motherboard, the 8-pin up behind the tray to the CPU's, and
        # the card's; and the front panel's plugs on their headers
        atx = part("atx_cable", "24-pin power cable", ["motherboard", "psu"])
        atx.box((3.5, 1.68, -1.33), (1.82, 0.36, 0.4), fixed=BLACK)
        atx.wire([(3.5, 1.86, -1.33), (3.5, 2.2, -1.33), (3.5, 2.2, -2.2), (-5.0, 2.2, -2.2), (-5.0, 2.2, 1.6)],
                 0.42, CABLE_BLACK, hit=True)
        atx.box((-5.0, 2.2, 1.82), (0.82, 0.62, 0.26), fixed=BLACK)
        eps = part("cpu_cable", "CPU power cable", ["motherboard", "psu"])
        eps.box((6.0, 1.58, 5.0), (0.3, 0.36, 0.64), fixed=BLACK)
        eps.wire([(6.0, 1.76, 5.0), (6.0, 1.92, 5.0), (6.46, 1.92, 5.0), (6.46, 0.42, 5.0), (6.46, 0.42, 1.3),
                  (-5.8, 0.42, 1.3), (-5.8, 1.4, 1.3), (-5.8, 1.4, 1.6)], 0.24, CABLE_BLACK, hit=True)
        eps.box((-5.8, 1.4, 1.82), (0.62, 0.52, 0.26), fixed=BLACK)
        pcie = part("gpu_cable", "graphics card power cable", ["gpu", "psu"])
        pcie.box((0.42, 4.975, 0.6), (0.32, 0.25, 0.64), fixed=BLACK)
        pcie.wire([(0.42, 5.1, 0.6), (0.42, 5.25, 0.6), (-4.3, 5.25, 0.6), (-4.3, 4.4, 0.6), (-4.3, 4.4, 1.6)],
                  0.3, CABLE_BLACK, hit=True)
        pcie.box((-4.3, 4.4, 1.82), (0.62, 0.62, 0.26), fixed=BLACK)
        fp = part("front_cables", "front panel cables", ["motherboard"])
        fp.box((-1.62, 1.24, -0.7), (0.24, 0.16, 0.54), fixed=BLACK)
        fp.box((-1.6, 1.29, 0.65), (0.3, 0.18, 0.74), fixed=(60, 90, 200))
        fp.wire([(-1.62, 1.3, -0.7), (-2.5, 1.3, -0.7), (-2.5, 0.72, -0.7)], 0.1, CABLE_BLACK, hit=True)
        fp.wire([(-1.6, 1.38, 0.65), (-2.5, 1.38, 0.65), (-2.5, 1.38, -0.5), (-2.5, 0.72, -0.5)], 0.18, CABLE_BLACK,
                hit=True)
        for p in (atx, eps, pcie, fp):
            p.material = "cable"
        inside = ["psu", "cooler", "cooler_fan", "ssd", "gpu", "atx_cable", "cpu_cable", "gpu_cable",
                  "front_cables"] + rams
    cover = part("shroud_cover", "shroud cover", ["chassis"] + (["psu", "atx_cable", "cpu_cable", "gpu_cable"]
                                                                  if full else []))
    cover.box(((-X + PC_T + PC_SHROUD + PC_T / 2) / 2, 6.58, 0.175), (PC_SHROUD + PC_T / 2 - (-X + PC_T), 0.08, 11.55),
              "case")
    for k in range(7):  # vents, at its front end
        cover.box((-5.05, 6.622, -5.0 + k * 0.38), (2.3, 0.006, 0.14), fixed=(20, 20, 24), hit=False)
    cover.box((-5.05, 6.622, 3.6), (1.6, 0.006, 0.5), fixed=spec["accent"], hit=False)
    cover.material = "metal"
    glass = part("glass_panel", "glass side panel", ["chassis", "shroud_cover"] + inside)
    glass.box((0, 6.76, 0), (2 * X, 0.08, 2 * Z), fixed=(110, 126, 140))
    glass.material = "glass"
    board.special["glass"] = "glass_panel"
    for x in (-6.35, 6.35):
        for z in (-6.35, 6.35):
            s, i = screw("thumb screw", ["glass_panel"], (x, 6.86, z), (0, 1, 0))
            s.post((x, 6.8, z), 0.22, 0.11, fixed=(44, 44, 50))
            knurl(s, (x, 6.855, z), 0.225, 0.09, "y", 14, (30, 30, 34))
            s.post((x, 6.6, z), 0.06, 0.2, fixed=SILVER, hit=False)
            s.thumb = True
            glass.target((x, 6.81, z), (0.4, 0.03, 0.4), ("hole", i))
    if extras:  # dust: on the tray (or the motherboard and what's on it), on the shroud, on the fans' frames
        by_key = {p.key: p for p in board.parts}
        if not full:
            keep = [PC_CPU_CUT, (-2.95, -1.75, -1.65, 1.25), (6.1, 6.7, -6.7, 6.7)] + list(PC_GROMMETS) + [
                (x - 0.15, x + 0.15, z - 0.15, z + 0.15) for x, z in MB_HOLES] + [
                (x - 1.9, x - 1.5, -6.0, -5.1) for x, _ in PC_FANS] + [(2.0, 2.5, 5.1, 6.0)]
            board.dirt.append(Dirt(ch, pc_dust(rnd, 14, (-3.2, 6.4), (-5.6, 6.3), PC_TRAY + 0.004, keep)))
            for key, (x, y), z in (("front_fan0", PC_FANS[0], -6.205), ("front_fan1", PC_FANS[1], -6.205),
                                   ("rear_fan", PC_REAR_FAN, 6.205)):  # (on the top edge of each fan's frame)
                board.dirt.append(Dirt(by_key[key], pc_dust(rnd, 3, (x - 1.8, x + 1.8), (z - 0.32, z + 0.32),
                                                            y + 2.004)))
        else:
            keep = [(2.9, 5.1, 1.8, 4.0), (3.8, 4.2, 1.3, 4.5), (1.4, 6.2, 0.2, 0.9), (-0.8, 0.8, -0.15, 6.5),
                    (-0.95, -0.55, 4.35, 5.6), (0.78, 1.6, 1.1, 4.2), (2.55, 4.45, -1.55, -1.1), (5.8, 6.3, 4.6, 5.4),
                    (4.55, 5.75, 3.95, 5.5), (0.95, 6.15, 5.55, 6.5), (-1.5, -0.8, 2.55, 3.65), (-1.8, -1.4, -1.0, 1.05),
                    (5.98, 6.3, 1.15, 1.55), (1.85, 2.55, -0.95, -0.25), (1.95, 6.05, 1.15, 2.1), (5.45, 5.75, 1.85, 3.65)
                    ] + [(x - 0.2, x + 0.2, z - 0.2, z + 0.2) for x, z in MB_HOLES]
            board.dirt.append(Dirt(mb, pc_dust(rnd, 12, (-1.7, 6.2), (-1.55, 6.35), 1.044, keep)))
            board.dirt.append(Dirt(cooler, pc_dust(rnd, 5, (2.2, 5.8), (2.15, 3.65), 5.71, [(3.0, 5.0, 2.75, 3.05)])))
            board.dirt.append(Dirt(gpu, pc_dust(rnd, 4, (-0.6, 0.45), (1.0, 6.3), 4.601)))
            board.dirt.append(Dirt(psu, pc_dust(rnd, 5, (-6.3, -3.95), (2.2, 6.4), 5.852, [(-6.25, -3.98, 2.95, 5.85)])))
        board.dirt.append(Dirt(cover, pc_dust(rnd, 5, (-6.35, -3.75), (-5.3, 5.7), 6.624,
                                              [(-6.25, -3.85, -5.1, -2.5), (-5.9, -4.2, 3.3, 3.9)])))
    board.size = board.inner = spec["size"]
    board.height = 6.95


def build_mic(kb, spec, extras=True, seed=None):
    """A microphone of this kind, in its own colours (or a webcam, or a headset: they're made the same way)."""
    board = Board(spec)
    rnd = random.Random(seed)
    parts = board.parts

    def part(*args, **kwargs):
        parts.append(Part3D(kb, *args, **kwargs))
        return parts[-1]
    {"stage": build_stage_mic, "lav": build_lav_mic, "podcast": build_podcast_mic, "wireless": build_wireless_mic,
     "studio": build_studio_mic, "clipcam": build_clip_cam, "ballcam": build_ball_cam, "streamcam": build_stream_cam,
     "office_hs": build_headset, "gaming_hs": build_headset, "wireless_hs": build_headset, "pc_case": build_pc,
     "pc_tower": build_pc}[spec["form"]](
        board, part, spec, rnd, extras)
    for p in parts:
        p.finish()
        if p.paintable:
            p.repaint(part_colours(spec, None))
    by_key = {p.key: p for p in parts}
    if "foam" in by_key and by_key["foam"].grimy:  # grubby from years of singing: lipstick and breath
        by_key["foam"].mesh.paint(0, "foam", (150, 128, 104))
    if "light" in board.mic:
        host = board.mic.pop("light_host", "body")
        board.mic["light"] = board.mic["light"].mesh(by_key[host].root, "light", shadow=False)
        board.mic["light"].paint(0, "light", (46, 48, 54))
    for shapes, host, store, hidden in board.attach:  # bits that come and go with a part: a smudge, a loose end...
        mesh = shapes.mesh(by_key[host].root, store, shadow=False)
        if hidden:
            mesh.np.stash()
        if store in ("rgb", "flakes"):  # (one on each side)
            board.special.setdefault(store, []).append(mesh)
        else:
            board.special[store] = mesh
    for p in parts:  # dust filters: clogged grey with fluff, or clean
        if "filter" in p.tags:
            p.mesh.paint(0, "filter", FILTER_DIRTY if p.grimy else FILTER_CLEAN)
    if "glass" in board.special:  # a glass side panel: you see in through it
        np = by_key[board.special.pop("glass")].mesh.np
        np.setTransparency(TransparencyAttrib.M_alpha)
        np.setAlphaScale(0.2)
        np.setDepthWrite(False)
        np.hide(SHADOW_MASK)
    if "glow" in board.mic:  # a ring light's diffuser: unlit, until it's switched on
        board.mic["glow"] = by_key[board.mic["glow"]].mesh
        board.mic["glow"].paint(0, "glow", (196, 194, 188))
    for mesh in board.special.get("rgb", []):
        mesh.paint(0, "glow", (60, 62, 70))
    if "knots" in board.special:
        board.special["knots"] = [k.mesh(by_key["cable"].root, "knot").np for k in board.special["knots"]]
    if "crust" in board.special:
        board.special["crust"] = [c and c.mesh(by_key["body"].root, "crust").np for c in board.special["crust"]]
    board.caps, board.switches = KeySet("keycap", kb, Shapes()), KeySet("switch", kb, Shapes())
    return board


def build_product(kb, spec, extras=True, seed=None):
    """A keyboard, a mouse or a mic, whichever spec is: in a mess of its own."""
    level = random.Random(seed).choices(MESS_LEVELS, weights=(2, 3, 4, 3, 2))[0]
    _mess["level"] = level[0]
    build = {"mouse": build_mouse, "mic": build_mic, "webcam": build_mic, "headset": build_mic,
             "computer": build_mic}.get(kind_of(spec), build_keyboard)
    board = build(kb, spec, extras, seed)
    board.mess = level[1]  # (its name, for the job card)
    return board


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
    if getattr(part, "material", None):
        return part.material
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
        self.twisting = {}  # grilles and caps unscrewing by hand: part -> [how far along, coming off?, then]
        self.later = []  # things to say in a moment: (when, what)
        self.special, self.done = None, {}  # this one's own job, and how it's going
        self.knob_music = None  # the music's volume before a knob took it over, to put it back
        self.dragging = self.help_open = self.confirming = False
        self.frames, self.frame_clock, self.show_fps = 0, 0.0, False
        self.clock = 0.0
        self.cam, self.cam_target = None, Vec3(0, 0, 0)
        self.layout_aspect = window.aspect_ratio
        self.ui_hovered = None
        self.volumes, self.volume_drag = {}, None  # the volume pop-ups, and the one being dragged
        self.said = set()
        self.next_tick = self.next_warn = 0.0
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
        if kind_of(board.spec) != "keyboard":  # nothing to lay out but its screws: just the dish, in front
            self.bowl = None
            dish_at = (0, -cd / 2 - 1.7)
            if board.spec.get("special") in ("foam", "filters"):  # and the wash bowl, for its foam (or filters)
                dish_at = (1.6, -cd / 2 - 1.7)
                self.bowl = Bowl(self.tray_root, (-2.4, DESK_Y + 0.05, -cd / 2 - 1.8))
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
        tall = spec.get("height", 0) if kind_of(spec) in HEARS + ("computer",) else 0  # (a mic on a stand stands tall)
        if kind_of(spec) != "keyboard":  # (small: seen from a little further off, so it doesn't fill the screen)
            cw = max(cw, 10.5, tall * 1.25)
        if kind_of(spec) == "computer":  # (big and boxy: further off still, so it stays under the title)
            cw *= 1.6
        if where == "menu":
            target, elevation, distance, width = Vec3(0, 0.5 + tall * 0.3, 0), 24, 34, cw / 0.6
        elif where == "result":
            target, elevation, distance, width = Vec3(cw * 0.24, 0.6 + tall * 0.3, 0), 30, 34, cw / 0.52
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
        for holder in self.showcase.values():  # (whatever was on show before, put away)
            holder.stash()
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
        self.special = spec.get("special")
        # (a mouse or a mic needs no keycap or switch pullers, and has no stabilisers to lube; and some jobs want
        # a tool of their own)
        self.tools = list(TOOLS) if self.kind == "keyboard" else [t for t in TOOLS if t[0] in ("hand", "driver",
                                                                                                "brush")]
        if self.special in ("sticky", "contacts", "smudge", "paste"):
            self.tools.append(SWAB)
        elif self.special == "blower":
            self.tools.append(BLOWER)
        elif self.special == "solder":
            self.tools.append(SOLDER)
        self.done = {"swabs": {}, "knots": set(), "dpi": {0}, "shaken": 0}
        self.twisting, self.later = {}, []
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
        if self.special:  # and a moment later, its own job
            self.soon(4.5, "Its own job: " + self.how())

    def clear_play(self):
        self.give_back_music()
        self.twisting, self.later = {}, []
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
        self.card((L + 0.31, 0.37 if self.special else 0.38), (0.56, 0.2 if self.special else 0.18))
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
        self.special_star = self.special_text = None
        if self.special:  # its own job, with a star that lights up once it's done
            self.special_star = self.icon("star", (L + 0.082, 0.293), 0.026, PAPER_DARK)
            self.special_text = self.text("", (L + 0.1, 0.293), 0.85, MUTED, origin=(-0.5, 0))
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
        if self.special in FRESH:
            chips.append(FRESH[self.special])
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
        self.test_special = self.meter = self.cam_pic = None
        extra = 0.07 if self.special else 0.0  # (room for its own job's line)
        if self.kind != "keyboard":  # a row for each thing to try, with a dot that lights up once it works
            mic = self.kind in HEARS
            checks = self.test_checks()
            pic = 0.2 if self.kind == "webcam" else 0.0  # (a webcam's picture, what it sees)
            height = 0.17 + len(checks) * 0.034 + extra + (0.06 if mic else 0.0) + pic
            self.card((R - 0.21, 0.39 - height / 2), (0.38, height), group="test")
            self.text("Test it", (R - 0.382, 0.37), 1.1, COCOA, bold=True, group="test")
            self.text({"mic": "Tap it, and talk into it:", "webcam": "Smile! Try it out:",
                       "headset": "Put it on, and listen:",
                       "computer": "Plug it in, and switch it on:" if self.spec.get("form") == "pc_tower" else
                       "Try its buttons, and its fans:"}.get(self.kind, "Use your own mouse:"), (R - 0.382, 0.335),
                      0.82, MUTED, group="test")
            self.cam_pic = self.cam_flash = None
            if pic:
                self.card((R - 0.21, 0.225), (0.31, 0.179), COCOA, corner=0.008, z=0.15, shadow=False, collider=False,
                          group="test")
                self.cam_pic = self.add(Entity(parent=camera.ui, model="quad", position=(R - 0.21, 0.225, 0.12),
                                               scale=(0.3, 0.169)), "test")
                self.cam_flash = self.add(Entity(parent=camera.ui, model="quad", position=(R - 0.21, 0.225, 0.11),
                                             scale=(0.3, 0.169), color=color.rgba32(255, 255, 255, 0)), "test")
                self.cam_flash.setTransparency(TransparencyAttrib.M_alpha)
                self.preview_key = None
            for k, (check, label) in enumerate(checks):
                y = 0.29 - pic - k * 0.034
                dot = self.icon("dot", (R - 0.37, y), 0.024, PAPER_DARK, group="test")
                text = self.text(label, (R - 0.35, y), 0.9, MUTED, origin=(-0.5, 0), group="test")
                self.check_rows.append((check, dot, text))
            y = 0.29 - pic - len(checks) * 0.034 - 0.012
            if mic:  # its level meter: green is just right, honey is loud, and the red end is too loud (it clips)
                self.text("Level", (R - 0.382, y), 0.82, MUTED, origin=(-0.5, 0), group="test")
                x0, w = R - 0.31, 0.26
                self.card((x0 + w / 2, y), (w, 0.02), PAPER_DARK, corner=0.01, z=0.15, shadow=False, collider=False,
                          group="test")
                for at in (0.45, 0.75, 0.9):  # the zones' edges
                    self.card((x0 + w * at, y), (0.003, 0.03), MUTED, corner=0.001, z=0.12, shadow=False,
                              collider=False, group="test")
                self.meter = self.add(Entity(parent=camera.ui, model="quad", origin=(-0.5, 0), position=(x0, y, 0.13),
                                             scale=(0.001, 0.016), color=rgb(SAGE)), "test")
                self.meter.width, self.meter.tinted = w, SAGE
                y -= 0.05
            if self.special:
                self.test_special = self.text("", (R - 0.382, y + 0.01), 0.82, HONEY_DARK, group="test",
                                              wordwrap=31)
            self.test_count = self.knob_text = None
            self.button("Finish", (R - 0.21, 0.39 - height + 0.045), (0.2, 0.055), self.finish_test, HONEY, CREAM,
                        text_size=1.1, group="test", z=-0.05)
        else:
            self.card((R - 0.21, 0.24 - extra / 2), (0.38, 0.3 + extra), group="test")
            self.text("Test every key", (R - 0.382, 0.37), 1.1, COCOA, bold=True, group="test")
            self.text("Type on your own keyboard, or click the keys. Each one lights up and clicks, the way its "
                      "switch feels.", (R - 0.382, 0.335), 0.82, MUTED, group="test", wordwrap=34)
            self.test_count = self.text("", (R - 0.382, 0.235), 0.95, HONEY_DARK, group="test")
            self.knob_text = self.text("", (R - 0.382, 0.205), 0.85, MUTED, group="test")
            if self.special:
                self.test_special = self.text("", (R - 0.382, 0.205 if self.knob is None else 0.175), 0.82,
                                              HONEY_DARK, group="test", wordwrap=31)
            self.button("Finish", (R - 0.21, 0.135 - extra), (0.2, 0.055), self.finish_test, HONEY, CREAM,
                        text_size=1.1, group="test", z=-0.05)
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
        self.card((0, 0.0), (0.8, 0.7), CREAM, group="help")
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
        elif self.kind in ("webcam", "headset"):
            lines = ["Take it all apart, into the box. Then build it back up in",
                     "any colour, and test it: " + ("smile, and talk (hold Space)." if self.kind == "webcam" else
                                                    "an ear at a time, and talk."),
                     "",
                     "One click, one part. Pick the tool for it first:",
                     "1  Hand: lift parts off. Lenses, rings, front panels and",
                     "    ear cushions unscrew by hand, and so do thumb screws.",
                     "    Click a part in the box to hold it, then click where it goes.",
                     "2  Screwdriver: click a screw. Some hide underneath.",
                     "3  Brush: hold it down and drag it over the dust."]
            if self.special == "smudge":
                lines.append("4  Alcohol swab: click the smudged lens window.")
            elif self.special == "solder":
                lines.append("4  Soldering iron: click the loose wire, inside the left cup.")
            lines += ["",
                      "Right-click: put back what you hold.   Drag: turn it round.",
                      "Scroll: zoom.   F: flip over.   R: level.   M: music.",
                      "F11: full screen or window.   Esc: back."]
        elif self.kind == "computer":
            lines = ["Take it all apart, into the box. Then build it back up in",
                     "any colour, and test it: " + ("switch it on, and try it." if self.spec["form"] == "pc_tower"
                                                    else "its buttons, and its fans."),
                     "",
                     "One click, one part. Pick the tool for it first:",
                     "1  Hand: lift parts off. Panels, filters and cables come off",
                     "    by hand, and so do thumb screws. Click a part in the",
                     "    box to hold it, then click where it goes.",
                     "2  Screwdriver: click a screw. Some are round the back.",
                     "3  Brush: hold it down and drag it over the dust."]
            if self.special == "paste":
                lines.append("4  Alcohol swab: click the CPU, once its cooler is off.")
            if self.bowl is not None:
                lines.append("Wash bowl: click it while you hold a dust filter, to wash it.")
            lines += ["",
                      "Right-click: put back what you hold.   Drag: turn it round.",
                      "Scroll: zoom.   F: flip over.   R: level.   M: music.",
                      "F11: full screen or window.   Esc: back."]
        elif self.kind == "mic":
            lines = ["Take it all apart, into the box. Then build it back up in",
                     "any colour, and test it: tap it, and talk (hold Space).",
                     "",
                     "One click, one part. Pick the tool for it first:",
                     "1  Hand: lift parts off. Grilles, caps and collars unscrew",
                     "    by hand, and so do thumb screws. Click a part in the",
                     "    box to hold it, then click where it goes.",
                     "2  Screwdriver: click a screw. Some hide underneath.",
                     "3  Brush: hold it down and drag it over the dust."]
            if self.special == "blower":
                lines.append("4  Air blower: click to puff dust off the capsule.")
            elif self.special == "contacts":
                lines.append("4  Alcohol swab: click a crusty battery contact.")
            if self.bowl is not None:
                lines.append("Wash bowl: click it while you hold the foam, to wash it.")
            lines += ["",
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
                     "6  Lube: click a stabiliser, so its long key won't rattle."]
            if self.special == "sticky":
                lines.append("7  Alcohol swab: click the sticky switch, keycap off.")
            lines += ["Wash bowl: click it to wash the grimy keycaps in the tray.",
                      "",
                      "Right-click: put back what you hold.   Drag: turn it round.",
                      "Scroll: zoom.   F: flip over.   R: level.   M: music.",
                      "F11: full screen or window.   Esc: back."]
        self.text("\n".join(lines), (-0.36, 0.255), 0.95, COCOA, group="help")
        if self.special:  # and its own job, at the bottom
            self.text(SPECIALS[self.special][0] + ": " + self.how(), (-0.36, -0.18), 0.85, HONEY_DARK, group="help",
                      wordwrap=62)
        self.button("Got it", (0, -0.29), (0.16, 0.055), self.toggle_help, HONEY, CREAM, group="help")
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
        spotless = all(not d.left for d in self.board.dirt if not d.delicate) and not any(c.grimy for c in self.caps)
        smooth = all(s.lubed for s in self.stabs)
        if not self.offscreen:
            key = self.spec["key"]
            self.save["fixed"][key] = self.save["fixed"].get(key, 0) + 1
            if self.special and self.special_ok():
                self.save.setdefault("specials", [])
                if key not in self.save["specials"]:
                    self.save["specials"].append(key)
            write_save(self.save)
        if self.kind == "keyboard":
            self.stars = [(True, "Built"), (spotless, "Spotless"), (smooth, "Smooth"), (self.all_tested(), "All tested")]
        else:
            self.stars = [(True, "Built"), (spotless, "Spotless"), (self.all_tested(), "All tested")]
        if self.special:
            self.stars.append((self.special_ok(), SPECIALS[self.special][1]))
        self.give_back_music()
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
            x = cx + (i - (len(self.stars) - 1) / 2) * {5: 0.112, 4: 0.14}.get(len(self.stars), 0.18)
            self.icon("star", (x, 0.165), 0.08, HONEY if got else PAPER_DARK)
            self.text(what, (x, 0.105), 0.85, COCOA if got else MUTED, origin=(0, 0))
        crumbs = sum(len(d.points) - len(d.left) for d in self.board.dirt)
        lines = [f"{crumbs} crumbs and specks of dust brushed out"]
        if self.washed:
            lines.append(f"{self.washed} keycaps washed")
        if self.stabs:
            lines.append(f"{sum(s.lubed for s in self.stabs)} of {len(self.stabs)} stabilisers lubed")
        if self.kind != "keyboard":
            checks = self.test_checks()
            lines.append(f"{sum(c in self.checks for c, _ in checks)} of {len(checks)} things tested")
        else:
            lines.append(f"{len(self.tested)} of {len(self.caps)} keys tested" +
                         ("" if not self.knob else ", and the knob" if self.knob_turned else " (not the knob)"))
        if self.special:
            lines.append(SPECIALS[self.special][0] + (": done!" if self.special_ok() else ": not this time"))
        if self.found:
            lines.append(f"Found inside: a {self.found}")
        if self.kind in ("keyboard", "mouse"):  # (only keyboards and mice hide lost things)
            found = len(set(self.save.get("found", [])))
            lines.append(f"Things found so far: {found} of {len(TRINKETS)}")
        self.text("\n".join(lines), (cx - 0.25, 0.04), 1.0, COCOA)
        tip = TIPS.get(self.special) or (
            "Real repairers photograph every step, and keep each part's screws together. Keycaps in different rows "
            "are shaped differently, so they go back in the rows they came from." if self.kind == "keyboard" else
            "A mouse's screws nearly always hide under its feet, and the feet don't stick as well once they're "
            "peeled: repairers keep spare ones.")
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
        if item == "fresh battery":  # (whenever the old one's out)
            self.fresh_battery()
            return
        if item == "fresh cushions":
            self.fresh_cushions()
            return
        if item == "new battery":
            self.new_battery()
            return
        if item == "thermal paste":
            self.thermal_paste()
            return
        if self.phase == "apart":
            self.say("Take everything apart first, into the box and the trays. Then build it back up.")
            self.nope()
            return
        if item in ("keycaps", "switches"):
            self.held = item
            self.say("Click a switch to put a keycap on it, in the colour you've picked."
                     if item == "keycaps" else "Click a hole in the plate to press a switch in.")
        elif item.placed:
            self.say(f"The {item.name} is on the {self.kind}.")
        else:
            self.held = item
            more = " Or click the wash bowl to wash it first." if item.grimy else ""
            self.say(f"Click the {self.kind} where the {item.name} goes. Right-click puts it back.{more}")

    def above(self, part):
        """The parts still on that sit on this one."""
        return [q for q in self.parts if q.placed and part in q.below]

    def blocker_message(self, part, above):
        first = next((q for q in above if not q.screw), None)
        if first is None:
            screw = above[0]
            if screw.thumb and screw.lift.z > 0.5:
                return (f"Its thumb screws round the back still hold it: flip it over (F), and turn them out by hand "
                        f"({self.tool_no('hand')}).")
            if screw.thumb:
                return f"Its {screw.name} still holds it: turn it out by hand ({self.tool_no('hand')})."
            if abs(screw.lift.z) > 0.5 and self.kind == "computer":
                return (f"The {screw.name}s {'round the back' if screw.lift.z > 0 else 'on the front'} still hold it: "
                        f"undo them with the screwdriver ({self.tool_no('driver')})" +
                        (". Flip it over (F) to reach them." if screw.lift.z > 0 else "."))
            if screw.lift.y < -0.5:
                return "It's still screwed on from underneath: flip it over (F) and undo the screws (2)."
            return f"The {screw.name} still holds it: undo it with the screwdriver (2)."
        if first.key.startswith("battery") and self.kind == "mic":
            return "Take the batteries out first: never open a wireless mic with its batteries in."
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
        if part in self.twisting:
            return  # (already unscrewing)
        above = self.above(part)
        if above:
            self.say(self.blocker_message(part, above))
            self.nope()
            self.jiggle(part.root)
            return
        if part.twist:  # a grille or a cap: it unscrews first, a couple of turns by hand, then lifts off
            self.unhighlight(part)
            self.twirl(part, True, lambda: part.placed and self.lift_off(part))
            return
        self.lift_off(part)

    def twirl(self, part, out, then=None):
        """A part that screws on by hand, turning: off (out), or back on."""
        self.twisting[part] = [0.0, out, then]
        self.sounds.play("screw_out" if out else "screw_in", 0.45, pitch=0.7)

    def update_twists(self):
        for part, tw in list(self.twisting.items()):
            if part.root.isEmpty():
                del self.twisting[part]
                continue
            tw[0] = min(1.0, tw[0] + time.dt / 0.55)
            turn(part.root, part.twist, (1 if tw[1] else -1) * 720 * smooth(tw[0]))
            if tw[0] < 1:
                continue
            del self.twisting[part]
            turn(part.root, part.twist, 0)
            if tw[2]:
                tw[2]()
            if not tw[1]:
                self.after_change()

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

        def landed():
            self.sounds.play(f"put_{material(part)}", 0.65)
            if part.twist and part.placed:  # and it screws home, by hand
                self.twirl(part, False)
        self.tween(part.root, part.origin, 0.3, then=landed)
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
                self.say(f"Click on the {self.kind}, where it goes.")
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
                peel = "peel" if cover[0].key.startswith("foot") else "take"
                self.say(f"The {cover[0].name} covers it: {peel} that off first, with the hand (1).")
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
            turn(screw.root, screw.spin, turned(screw.root, screw.spin) + (-1 if undoing else 1) * 720 * time.dt)
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
            if dirt.delicate:  # a capsule's diaphragm: the brush would tear it
                if any((dirt.points[i] - point).length() < 1.0 for i in dirt.left) and self.clock >= self.next_warn:
                    self.next_warn = self.clock + 2.0
                    self.say(f"Never brush a capsule: its diaphragm is thinner than a hair. Puff it clean with the "
                             f"air blower ({self.tool_no('blower')}).", ROSE)
                    self.nope()
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
        """A click on the wash bowl: the grimy keycaps in the tray go in for a soak (or the foam in your hand)."""
        if self.washing > 0:
            return
        if self.kind in ("mic", "computer"):
            foam = self.held if isinstance(self.held, Part3D) else None
            if foam is None or not foam.grimy:
                grubby = next((p for p in self.big if p.grimy), None)
                if self.kind == "computer":
                    self.say("That filter's clean already." if foam is not None else
                             "The bowl is for the clogged dust filters: click one in the parts box to hold it, then "
                             "click the bowl." if grubby and not grubby.placed else
                             "Take the clogged dust filters off first: they're what want a wash." if grubby else
                             "The dust filters are all clean: they're ready to go back on.")
                    return
                self.say("The bowl is for the foam: click it in the parts box to hold it, then click the bowl."
                         if grubby and not grubby.placed else
                         "Take the grille off and lift the foam out first: it's what wants a wash." if grubby else
                         "The foam's clean already: it's ready to go back in.")
                return
            self.washing = WASH_TIME
            self.washing_foam = foam
            self.sounds.play("wash", 0.6)
            self.say("Into the warm, soapy water with the foam: a good squeeze, and a rinse..." if self.kind == "mic"
                     else f"Into the warm, soapy water with the {foam.name}: a swish, and a rinse...")
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
        foam = getattr(self, "washing_foam", None)
        if foam is not None:  # a mic's foam: clean, black again
            self.washing_foam = None
            foam.grimy = False
            if self.kind == "computer":  # a dust filter: clean, dark again
                foam.mesh.paint(0, "filter", FILTER_CLEAN)
                self.sounds.play("sparkle", 0.5)
                left = sum(q.grimy for q in self.big)
                if left:
                    self.say(f"Clean as new! {left} more clogged filter{'s' if left > 1 else ''} to wash.", HONEY_DARK)
                else:
                    self.complete("Every dust filter's clean: the air can flow freely through it again.")
                return
            foam.mesh.paint(0, "foam", (58, 58, 64))
            self.sounds.play("sparkle", 0.5)
            self.complete("Squeaky clean! The foam's fresh and ready to go back in.")
            return
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
        """The knob, in the test: a notch of volume up (or down), with its soft click. (A mic's gain knob turns up
        how loud it hears you.)"""
        turn(self.knob.root, self.knob.spin, turned(self.knob.root, self.knob.spin) - way * 18)
        self.sounds.play("knob", 0.6)
        if self.kind == "mic":
            self.gain = min(1.7, max(0.2, self.gain + way * 0.08))
            self.mic_try("gain")
            return
        if self.kind == "webcam":  # a webcam's focus ring: the lens nearer the sensor, or further off
            self.focus = min(1.0, max(0.0, self.focus + way * 0.05))
            if self.special == "focus" and abs(self.focus - FOCUS_AT) < 0.026:
                self.complete("Pin sharp! Every eyelash in focus.")
            return
        if self.special == "volume":  # this knob turns the music, really
            if self.knob_music is None:
                self.knob_music = (self.sounds.volume["music"], self.sounds.music_on)
                self.notch = round(self.sounds.volume["music"] * 10) if self.sounds.music_on else 5
            self.notch = min(10, max(0, self.notch + way))
            self.sounds.music_on = True
            self.sounds.set_volume("music", self.notch / 10)
            self.done["low"] = self.done.get("low") or self.notch == 0
            if self.notch == 0:
                self.say("All the way down: the music's gone quiet. Now all the way up!")
            elif self.notch == 10 and self.done["low"]:
                self.complete("All the way down, and all the way up: the knob turns the music. It works!")
        if not self.knob_turned:
            self.knob_turned = True
            if self.special != "volume":
                self.say("The knob turns, notch by notch: volume up, volume down. It works!", HONEY_DARK)
            self.check_all_tested()

    def give_back_music(self):
        """The music's volume as it was, before the knob had its turn."""
        if self.knob_music is not None:
            level, on = self.knob_music
            self.knob_music = None
            self.sounds.set_volume("music", level)
            self.sounds.set_music(on)
            if hasattr(self, "volumes"):
                self.show_volume("music")

    def all_tested(self):
        if self.kind == "mouse":
            return all(c in self.checks for c, _ in self.mouse_checks())
        if self.kind != "keyboard":
            return all(c in self.checks for c, _ in self.test_checks())
        return len(self.tested) >= len(self.caps) and (self.knob is None or self.knob_turned)

    def check_all_tested(self):
        if self.all_tested():
            self.sounds.play("fanfare", 0.6)
            still = self.special and not self.special_ok() and self.special in (
                "sum", "fn_layer", "pair", "volume", "pangram", "dpi", "gain", "focus")  # (done in the test)
            self.say("Everything works! " + ("Now its own job: " + self.how() if still else
                                             "Press Finish when you're done" + (" typing." if self.kind == "keyboard"
                                                                                 else ".")), HONEY_DARK)

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
            if name == "left" and self.special == "double_click" and not self.special_ok():  # its worn switch
                self.soon(0.07, lambda: self.sounds.play("mouse_click", 0.55, pitch=1.03))
                if "double" not in self.said:
                    self.said.add("double")
                    self.say("Click-click! One click, and it clicked twice: its left switch is worn. Next time, "
                             "bend its spring back with the top shell off.", ROSE)
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

    # -- testing a mic: tap it, and talk into it (hold Space) --

    def mic_checks(self):
        form = self.spec.get("form")
        checks = [("power", "Switch it on")] if form == "wireless" else []
        checks += [("tap", "Tap the capsule" if form == "lav" else "Tap the grille"), ("speak", "Talk: hold Space")]
        if form == "podcast":
            checks.append(("mute", "Mute it, and back"))
        return checks

    def mic_try(self, check):
        """Something tried in a mic's test: the first time it works, it's ticked off."""
        if check in self.checks or check not in dict(self.test_checks()):
            return
        self.checks[check] = True
        if self.all_tested():
            self.check_all_tested()

    def live(self):
        """Can it hear you? It's switched on, and not muted."""
        return self.mic_on and not self.muted

    def light_mic(self):
        """A mic's light: green while it can hear you, red when it's muted, dark when it's off."""
        light = self.board.mic.get("light") if self.board else None
        if light is not None:
            light.paint(0, "light", (46, 48, 54) if not self.mic_on else ROSE if self.muted else (110, 210, 120))

    def mic_click(self, part, tag):
        """A click on a mic in its test: its power switch, its mute button, its knob, or a tap on it."""
        if part is None:
            self.dragging = True
            return
        what = tag[0] if tag else None
        if what == "knot":
            self.untie(tag[1])
        elif what == "power":
            self.mic_on = not self.mic_on
            self.sounds.play("mouse_click", 0.6, pitch=0.8)
            self.light_mic()
            self.say("On! Its light glows green." if self.mic_on else "Off: its light goes dark.")
            if self.mic_on:
                self.mic_try("power")
        elif what == "mute":
            self.muted = not self.muted
            self.done["mutes"] += 1
            self.sounds.play("mouse_click", 0.6, pitch=1.1)
            self.light_mic()
            self.say("Muted: its light goes red, and it can't hear you." if self.muted else
                     "Live again: the light's green.")
            if self.done["mutes"] >= 2:
                self.mic_try("mute")
        elif part is self.knob:
            self.turn_knob(1)
        else:  # a tap on it: a thump, if it can hear you
            self.sounds.play("thump", 0.7)
            if self.live():
                self.mic_level = max(self.mic_level, min(1.0, 0.95 * self.gain + 0.1))
                self.mic_try("tap")
            else:
                self.say("Nothing on the meter: it's " + ("switched off. Click its power switch." if not self.mic_on
                                                          else "muted. Press mute again."))

    def mic_input(self, key):
        """Space, held down: you, talking into the mic."""
        if key == "space":
            self.speaking, self.voice_t, self.next_voice = True, 0.0, self.clock
            return True
        if key == "space up":
            self.speaking = False
            return True
        return False

    def update_mic_test(self):
        """Its level meter, following you as you talk (and the taps), through its gain; and its own job's bits."""
        if not (self.state == "play" and self.kind in HEARS and self.phase == "test") or self.meter is None:
            return
        dt = time.dt
        target = 0.0
        if self.speaking:
            self.voice_t += dt
            if self.clock >= self.next_voice:
                self.next_voice = self.clock + 0.8
                self.sounds.play("voice", 0.55, vary=0.04)
            syllables = abs(math.sin(self.voice_t * 7.5)) ** 0.6
            target = 0.75 * (0.55 + 0.45 * syllables) * self.gain
            cut = False
            if self.special == "contacts" and not self.special_ok() and self.live():  # crusty contacts: it cuts out
                cut = math.sin(self.clock * 5.3) * math.sin(self.clock * 13.1) > 0.25
                if cut and self.clock >= self.next_crackle:
                    self.next_crackle = self.clock + 0.35
                    self.sounds.play("rattle", 0.4, pitch=0.6, vary=0.2)
                    if "crackle" not in self.said:
                        self.said.add("crackle")
                        self.say("It crackles and cuts out: the crusty contacts. Next time, swab them clean.", ROSE)
            if not self.live():
                target = 0.0
                if "deaf" not in self.said:
                    self.said.add("deaf")
                    self.say("Nothing on the meter: it's " + ("switched off. Click its power switch." if not
                                                              self.mic_on else "muted. Press mute again."))
            elif not cut:
                self.talked += dt
                if self.talked > 0.5:
                    self.mic_try("speak")
            if cut:
                target = 0.0
        rate = 14 if target > self.mic_level else 3
        self.mic_level += (target - self.mic_level) * min(1.0, dt * rate)
        level = min(1.0, self.mic_level)
        self.meter.scale_x = max(0.001, level * self.meter.width)
        col = SAGE if level < 0.75 else HONEY if level < 0.9 else ROSE
        if self.meter.tinted != col:
            self.meter.color, self.meter.tinted = rgb(col), col
        if self.special == "gain" and self.speaking and self.live():  # where your voice sits, on average
            self.mic_avg += (target - self.mic_avg) * min(1.0, dt * 3)
            zone = "low" if self.mic_avg < 0.42 else "high" if self.mic_avg > 0.78 else "good"
            self.done["zone"] = zone
            self.good_time = self.good_time + dt if zone == "good" else 0.0
            if self.good_time > 1.2:
                self.complete(f"Gain {self.gain:.1f}: your voice sits right in the green. Not too quiet, never "
                              "clipping.")
        if self.special == "contacts" and self.mic_on and not self.special_ok():  # its light flickers, too
            light = self.board.mic.get("light")
            if light is not None:
                flicker = math.sin(self.clock * 17) * math.sin(self.clock * 6.1) > 0.3
                light.paint(0, "light", (46, 48, 54) if flicker else (110, 210, 120))

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
        reach = 1.0 + 0.35 * getattr(self, "dpi", 0)  # (faster, the higher its DPI: its light reaches further)
        self.sensor_light.setScale((3.2 + 1.2 * self.glow) * reach)
        bright = 0.25 + 0.6 * self.glow
        if self.special == "battery" and not self.special_ok():  # a flat battery: it flickers and stutters
            bright *= 0.25 if math.sin(self.clock * 23) * math.sin(self.clock * 7.3) > 0.3 else 1.0
            if speed > 0.002 and "flat" not in self.said:
                self.said.add("flat")
                self.say("It stutters and the light flickers: its battery's flat. Next time, swap in a fresh one.",
                         ROSE)
        self.sensor_light.setColorScale(1.0, 0.25, 0.22, bright)
        if self.sensor_light.isHidden():
            self.sensor_light.show()
            self.sensor_light.hide(SHADOW_MASK)
        logo = self.board.mouse.get("logo")
        if logo is not None:
            logo.paint(0, "logo", hue(self.clock * 0.2, 0.6))

    DPI = [(400, (226, 92, 80)), (800, (240, 196, 80)), (1600, (110, 200, 120)), (3200, (90, 150, 240))]

    def next_dpi(self):
        """The gaming mouse's DPI button: the next speed, and its light changes colour to show which."""
        self.dpi = (getattr(self, "dpi", 0) + 1) % len(self.DPI)
        speed, col = self.DPI[self.dpi]
        self.board.mouse["dpi"].paint(0, "light", col)
        self.sounds.play("mouse_click", 0.5, pitch=1.3)
        self.done["dpi"].add(self.dpi)
        if len(self.done["dpi"]) == len(self.DPI) and not self.special_ok():
            self.complete(f"{speed} DPI: you've tried every speed. Its light shows which it's on.")
        else:
            self.say(f"{speed} DPI: the pointer moves {'faster' if self.dpi else 'slower'}. Its light turns "
                     f"{['red', 'yellow', 'green', 'blue'][self.dpi]}.")

    # -- testing a webcam, or a headset --

    def test_checks(self):
        """What there is to try in a test, other than a keyboard's keys."""
        if self.kind == "mouse":
            return self.mouse_checks()
        if self.kind == "mic":
            return self.mic_checks()
        form = self.spec["form"]
        if form == "pc_case":
            return [("power", "Power button: press it"), ("reset", "Reset button: press it"),
                    ("usb", "Front USB: click a port"), ("fans", "Fans: give each a spin")]
        if form == "pc_tower":
            return [("power", "Power: press its button"), ("fans", "Fans spin, and one beep"),
                    ("usb", "Front USB: click a port"), ("reset", "Restart: press reset")]
        if form == "clipcam":
            return [("shutter", "Shutter: shut it, then open it"), ("speak", "Talk: hold Space"),
                    ("photo", "Photo: press P")]
        if form == "ballcam":
            return [("photo", "Photo: click its button"), ("speak", "Talk: hold Space")]
        if form == "streamcam":
            return [("light", "Light: click its button"), ("bright", "Brightness: scroll on it"),
                    ("speak", "Talk: hold Space"), ("photo", "Photo: press P")]
        checks = [("power", "Power: click its button")] if form == "wireless_hs" else []
        checks += [("left", "Left ear: click its cup"), ("right", "Right ear: click its cup"),
                   ("speak", "Talk: hold Space")]
        if form == "gaming_hs":
            checks.append(("mute", "Mute: click the mic, twice"))
        return checks + [("volume", "Volume: scroll on it")]

    def photo(self):
        """A webcam takes your picture: the card flashes white."""
        if self.shutter_closed:
            self.say("All black: its shutter's closed. Slide it open first.")
            return
        self.sounds.play("shutter", 0.7)
        self.flash_t = 0.5
        self.say("Snap! A lovely one of you.")
        self.mic_try("photo")

    def cam_click(self, part, tag):
        """A click on a webcam in its test: its snapshot button, its ring light's button, its shutter, its focus."""
        if part is None:
            self.dragging = True
            return
        what = tag[0] if tag else None
        if what == "snap":
            self.sounds.play("mouse_click", 0.5, pitch=1.1)
            self.photo()
        elif what == "light":
            self.ring_on = not self.ring_on
            self.sounds.play("mouse_click", 0.5, pitch=0.9)
            self.say("The ring light's on: a soft, even glow on your face." if self.ring_on else "Ring light off.")
            if self.ring_on:
                self.mic_try("light")
        elif part.key == "shutter":
            self.shutter_closed = not self.shutter_closed
            self.tween(part.root, part.origin + Vec3(-1.15 if self.shutter_closed else 0, 0, 0), 0.25)
            self.sounds.play("snick", 0.5)
            self.done["shuts"] += 1
            self.say("Shutter closed: it can't see a thing." if self.shutter_closed else "Open again: there you are!")
            if self.done["shuts"] >= 2:
                self.mic_try("shutter")
        elif part is self.knob:
            self.turn_knob(1)
        else:
            self.dragging = True

    def ear(self, side, part):
        """A headset's test: a chime, in one ear (if it's on, and that side works)."""
        if not self.mic_on:
            self.say("It's switched off: click its power button, on the right cup.")
            return
        cup = next((p for p in self.parts if p.key == f"{side}_cushion"), part)
        self.jiggle(cup.root)
        if side == "left" and self.special == "solder" and not self.special_ok():
            self.say("Nothing from the left side: that's the loose wire. Next time, solder it back on.", ROSE)
            return
        self.sounds.play(f"ear_{side}", self.hs_volume, vary=0.0)
        self.say(f"A soft chime, in your {side} ear only.")
        self.mic_try(side)

    def hs_click(self, part, tag):
        """A click on a headset in its test: an ear cup, its power button, its mic (to mute it)."""
        if part is None:
            self.dragging = True
            return
        if tag and tag[0] == "power":
            self.mic_click(part, tag)
        elif part.key.startswith(("left", "right")):
            self.ear("left" if part.key.startswith("left") else "right", part)
        elif part.key == "boom" and self.spec["form"] == "gaming_hs":
            self.mic_click(part, ("mute",))
        else:
            self.say("Click an ear cup to hear that side.")

    def gadget_input(self, key):
        """A webcam's or a headset's keys and wheel, in its test. True if that's all the key was for."""
        if self.kind == "webcam" and key == "p":
            self.photo()
            return True
        if key not in ("scroll up", "scroll down"):
            return False
        way = 1 if key == "scroll up" else -1
        if self.kind == "headset":
            self.hs_volume = min(1.0, max(0.1, self.hs_volume + way * 0.1))
            self.sounds.play("knob", 0.5)
            self.say(f"Volume {round(self.hs_volume * 10)} of 10.")
            self.mic_try("volume")
            return True
        if self.knob is not None and self.pick()[0] is self.knob:  # its focus ring
            self.turn_knob(way)
            return True
        if self.spec["form"] == "streamcam" and self.pick()[0] is not None:
            if not self.ring_on:
                self.say("Switch the ring light on first: its button's on top.")
                return True
            self.ring_level = min(1.0, max(0.0, self.ring_level + way * 0.1))
            self.sounds.play("knob", 0.4)
            self.mic_try("bright")
            return True
        return False

    def update_gadget_test(self):
        """A webcam's picture (and its ring light); a gaming headset's lights, round the colours."""
        if not (self.state == "play" and self.phase == "test" and self.kind in ("webcam", "headset")):
            return
        for k, mesh in enumerate(self.board.special.get("rgb", [])):
            mesh.paint(0, "glow", hue(self.clock * 0.2 + k * 0.5, 0.6))
        if self.kind != "webcam" or self.cam_pic is None:
            return
        form, ok = self.spec["form"], self.special_ok()
        flicker = form == "streamcam" and self.ring_on and not ok and \
            math.sin(self.clock * 19) * math.sin(self.clock * 7.7) > 0.35
        glow = self.board.mic.get("glow")
        if glow is not None:
            level = 0.0 if not self.ring_on or flicker else 0.6 + 0.4 * self.ring_level
            want = mix((196, 194, 188), (255, 244, 214), level)
            if getattr(self, "glow_was", None) != want:
                self.glow_was = want
                glow.paint(0, "glow", want)
        if flicker and "flicker" not in self.said:
            self.said.add("flicker")
            self.say("See it flicker? That's the loose ribbon cable. Next time, press it home.", ROSE)
        blur = 0.0
        if form == "clipcam" and not ok:
            blur = 3.5  # (through the smudge)
        elif form == "ballcam":
            blur = min(9.0, abs(self.focus - FOCUS_AT) * 22)
        bright = 1.0
        if form == "streamcam":
            bright = 0.62 if not self.ring_on or flicker else 0.85 + 0.3 * self.ring_level
        key = (self.shutter_closed, round(blur * 2) / 2, round(bright, 2))
        if key != self.preview_key:
            self.preview_key = key
            cache = ART.setdefault("previews", {})
            if key not in cache:
                cache[key] = Texture(draw_preview(key[1], key[2], key[0]), filtering="bilinear")
            self.cam_pic.texture = cache[key]
        t = getattr(self, "flash_t", 0.0)
        if t > 0:
            self.flash_t = max(0.0, t - time.dt)
            self.cam_flash.color = color.rgba32(255, 255, 255, int(255 * min(1.0, self.flash_t * 3)))

    def gadget_hint(self):
        """A word as a webcam or a headset comes apart, mostly about its own job."""
        by_key = {p.key: p for p in self.parts}
        s = self.special
        if s == "flicker" and "ribbon" not in self.said and not by_key["front_panel"].placed and \
                not self.special_ok():
            self.said.add("ribbon")
            self.say("There's the ribbon cable, at the right, beside the LED ring: its end has lifted out of its "
                     "socket. Press it home with the hand (1).", ROSE)
        elif s == "solder" and "joint" not in self.said and not by_key["left_baffle"].placed and \
                not self.special_ok():
            self.said.add("joint")
            self.say(f"See the red wire, off its pad on the little board? Touch the soldering iron "
                     f"({self.tool_no('solder')}) to it.", ROSE)
        elif s == "swollen" and "swollen" not in self.said and not by_key["right_baffle"].placed:
            self.said.add("swollen")
            self.say("There's the battery, puffed up like a pillow. Unplug its lead first, then lift it out gently: "
                     "never press on it.", ROSE)
        elif s == "swollen" and "swapped" not in self.said and not by_key["battery"].placed:
            self.said.add("swapped")
            self.say("Out it comes, for recycling. Click New battery in the parts box to fit a new one.")
        elif s == "cushions" and "cushions" not in self.said and not any(
                p.placed for p in self.parts if p.key.endswith("cushion")):
            self.said.add("cushions")
            self.say("Both old cushions are off: click Fresh cushions in the parts box.")

    def pc_hint(self):
        """A word as a computer comes apart, mostly about its own job."""
        by_key = {p.key: p for p in self.parts}
        s = self.special
        if "glass" not in self.said and not by_key["glass_panel"].placed:
            self.said.add("glass")
            self.say("The glass is off. Some screws are round the back: flip it over (F), or drag it round, to reach "
                     "them.")
        elif s == "paste" and "paste" not in self.said and not by_key["cooler"].placed and by_key["cpu"].placed and \
                not self.special_ok():
            self.said.add("paste")
            self.say(f"There's the old thermal paste on the CPU, dried out and crumbly. Wipe it off with the alcohol "
                     f"swab ({self.tool_no('swab')}), then click Thermal paste in the parts box.", ROSE)
        elif s == "filters" and "filters" not in self.said and any(not q.placed and q.grimy for q in self.big):
            self.said.add("filters")
            self.say("That filter's furry with dust! Once everything's apart, hold it (click it in the parts box), "
                     "and click the wash bowl.", ROSE)

    # -- testing a computer --

    def pc_click(self, part, tag):
        """A click on a computer in its test: its power button, its reset button, a front USB port; on a case of its
        own, a fan, for a spin by hand. (You reach in through the glass.)"""
        if part is not None and part.key == "glass_panel":
            part.placed = False
            try:
                part, tag, _ = self.pick()
            finally:
                next(q for q in self.parts if q.key == "glass_panel").placed = True
        if part is None:
            self.dragging = True
            return
        what = tag[0] if tag else None
        full = self.spec["form"] == "pc_tower"
        if what == "power":
            self.sounds.play("mouse_click", 0.5, pitch=0.8)
            if not full:
                self.say("Click! A good, firm power button. (There's nothing inside it to switch on, yet.)")
            elif self.mic_on:
                self.pc_power(False, "A press, and it shuts down: the fans whirr to a stop.")
            else:
                self.pc_power(True, "It hums to life: its fans spin up, and its light glows...")
            self.mic_try("power")
        elif what == "reset":
            self.sounds.play("mouse_click", 0.45, pitch=1.2)
            if not full:
                self.say("Click! The reset button works, too.")
                self.mic_try("reset")
            elif not self.mic_on:
                self.say("It's off: press the power button first.")
            else:
                self.pc_t, self.done["beeped"] = 0.0, False
                for key in self.fan_speed:
                    self.fan_speed[key] *= 0.4
                self.say("It restarts: the fans dip, and spin back up.")
                self.mic_try("reset")
        elif what == "usb":
            if not full:
                self.sounds.play("snick", 0.6)
                self.say("A USB stick slides snugly into the front port.")
                self.mic_try("usb")
            elif not self.mic_on:
                self.sounds.play("snick", 0.6)
                self.say("The stick goes in, but it's off: switch it on, and it'll find it.")
            else:
                self.sounds.play("usb_in", 0.6)
                self.say("Ding-dong! It's found the USB stick.")
                self.mic_try("usb")
        elif not full and part.key in ("front_fan0", "front_fan1", "rear_fan"):
            self.fan_speed[part.key] = 900.0
            self.sounds.play("fan_spin", 0.5, vary=0.05)
            spun = self.done["spun"]
            spun.add(part.key)
            left = 3 - len(spun)
            self.say("It spins freely, smooth and quiet: a good bearing." + (f" {left} more to try." if left else ""))
            if not left:
                self.mic_try("fans")
        else:
            self.say(("The fans are whirring away nicely." if self.mic_on else
                      "Press the power button, at the top of its front, to switch it on.") if full else
                     "Click a fan to give it a spin, or try its buttons at the top of its front.")
            self.dragging = True

    def pc_power(self, on, message=None):
        """A desktop PC switched on, or off."""
        self.mic_on = on
        self.pc_t = 0.0
        self.done["beeped"] = self.done["temp_said"] = False
        self.light_mic()
        self.sounds.play("pc_on" if on else "pc_off", 0.55)
        if message:
            self.say(message)

    def update_pc_test(self):
        """A computer in its test: its fans turning (spun by hand, on a case of its own; on a desktop PC, spinning up
        once it's on), the beep it starts up with, and how hot its CPU runs."""
        if not (self.state == "play" and self.phase == "test" and self.kind == "computer"):
            return
        dt, full, d = time.dt, self.spec["form"] == "pc_tower", self.done
        if full and self.mic_on:
            self.pc_t += dt
            if self.pc_t >= 1.2 and not d["beeped"]:
                d["beeped"] = True
                self.sounds.play("beep", 0.35)
                self.mic_try("fans")
            if self.pc_t >= 3.0 and not d["temp_said"]:
                d["temp_said"] = True
                if self.special_ok():
                    self.say("Beep! It's started up. Its CPU sits at 38 degrees: cool and quiet, on fresh paste.",
                             HONEY_DARK)
                else:
                    self.say("Beep! It's started up... but its CPU's at 84 degrees, and climbing.", ROSE)
            if not self.special_ok() and self.pc_t >= 7.0:
                self.pc_power(False)
                self.say("It's shut itself down: its CPU hit 99 degrees! That's the dried-out paste. Next time, wipe "
                         "it off and put fresh paste on.", ROSE)
        fans = self.board.special.get("fans", [])
        for key in {key for _, _, key in fans}:
            speed = self.fan_speed.get(key, 0.0)
            if full:
                want = 1100.0 if self.mic_on else 0.0
                speed += (want - speed) * min(1.0, dt * (1.5 if want > speed else 0.7))
            else:
                speed *= max(0.0, 1 - dt * 0.55)  # (a spin by hand, slowing)
            self.fan_speed[key] = speed
        for hub, axis, key in fans:
            if self.fan_speed[key] > 1:
                turn(hub, axis, (turned(hub, axis) + self.fan_speed[key] * dt) % 360)

    def thermal_paste(self):
        """The desktop PC: a fresh dot of thermal paste on its CPU, once the old is wiped off."""
        by_key = {p.key: p for p in self.parts}
        if self.special_ok():
            self.say("It has fresh paste on already.")
        elif by_key["cooler"].placed:
            self.say("Take the cooler off first: the paste goes between it and the CPU.")
            self.nope()
        elif not by_key["cpu"].placed:
            self.say("Put the CPU back in its socket first: the paste goes on top of it.")
            self.nope()
        elif self.done["swabs"].get("cpu", 0) < SWAB_WORK:
            self.say(f"Wipe the old, dried paste off first, with the alcohol swab ({self.tool_no('swab')}).")
            self.nope()
        else:
            self.board.special["paste_new"].np.unstash()
            self.sounds.play("lube", 0.6, pitch=0.9)
            self.complete("A pea-sized dot of fresh paste, right in the middle: the cooler will spread it thin.")

    # -- its own job --

    def tool_no(self, tool):
        """The number key for a tool, as it is for this one."""
        return next((str(i + 1) for i, (t, _) in enumerate(self.tools) if t == tool), "?")

    def how(self):
        """How its own job is done, in words, with the right tool numbers."""
        sticky = self.board.special.get("sticky") if self.board else None
        label = nice_label(self.board.keys[sticky][0]) if sticky is not None else ""
        return SPECIALS[self.special][2].format(hand=self.tool_no("hand"), swab=self.tool_no("swab"),
                                                blower=self.tool_no("blower"), solder=self.tool_no("solder"),
                                                sticky=label)

    def special_ok(self):
        """Is its own job done?"""
        if self.special == "swap":  # every switch new, all of one kind, and not the kind it came with
            styles = {s.style for s in self.switches}
            return all(s.placed for s in self.switches) and len(styles) == 1 and \
                styles != {[k[0] for k in SWITCH_KINDS].index(self.spec["switch"])}
        if self.special == "shake":
            return self.done["shaken"] >= self.shake_goal()
        return bool(self.done.get("ok"))

    def complete(self, message):
        """Its own job, done: its star lights up."""
        if self.done.get("ok"):
            return
        self.done["ok"] = True
        self.sounds.play("chime", 0.7)
        self.say(message + "  (A star for it!)", HONEY_DARK)

    def special_status(self):
        """A word on how its own job is going, for the cards."""
        s, d = self.special, self.done
        if self.special_ok():
            return "Done!"
        if s == "sum" and self.phase == "test":
            a, b = d["sum"]
            return f"{a} + {b} = {d.get('typed', '')}_   (type it, then Enter)"
        if s == "fn_layer" and self.phase == "test":
            n = len(d.get("arrows", ()))
            return f"Fn layer {'on' if d.get('layer') else 'off'}: {n} of 4 arrows" + (
                "" if d.get("layer") else " (click Fn)")
        if s == "pair" and self.phase == "test":
            return "Hold Esc down to pair..." if not d.get("hold") else f"Pairing... {min(2.0, d['hold']):.1f} s"
        if s == "pangram" and self.phase == "test":
            rest = PANGRAM[d.get("typed", 0):]
            return f"Type: {rest}"
        if s == "volume" and self.phase == "test":
            return "Down to 0, then up to 10: " + (str(getattr(self, "notch", "-")) if self.knob_music else "turn it")
        if s == "shake":
            return f"Shaken out: {d['shaken']} of {self.shake_goal()}"
        if s == "swap":
            kinds = {s_.style for s_ in self.switches if s_.placed}
            return f"{sum(s_.placed for s_ in self.switches)} of {len(self.switches)} in" + (
                ", but mixed kinds" if len(kinds) > 1 else "")
        if s in ("sticky", "contacts"):
            total = 1 if s == "sticky" else sum(c is not None for c in self.board.special["crust"])
            done = sum(n >= SWAB_WORK for n in d["swabs"].values())
            return f"{done} of {total} swabbed"
        if s == "untangle":
            return f"{len(d['knots'])} of {len(self.board.special['knots'])} knots undone"
        if s == "dpi" and self.phase == "test":
            return f"{len(d['dpi'])} of {len(self.DPI)} speeds tried"
        if s == "gain" and self.phase == "test":
            return f"Gain {self.gain:.1f}: " + {None: "hold Space and talk", "low": "too quiet: turn it up",
                                                "high": "too loud: it clips!", "good": "just right..."}[
                d.get("zone")]
        if s == "blower":
            left = sum(len(x.left) for x in self.board.dirt if x.delicate)
            return f"{left} specks on the capsule"
        if s == "smudge":
            return f"{d['swabs'].get('lens', 0)} of {SWAB_WORK} wipes"
        if s == "focus" and self.phase == "test":
            return "Turn the focus ring: scroll on it" + ("  (nearly!)" if abs(self.focus - FOCUS_AT) < 0.12 else "")
        if s == "cushions":
            off = sum(not p.placed for p in self.parts if p.key.endswith("cushion"))
            return f"{off} of 2 old cushions off" if off < 2 else "click Fresh cushions in the box"
        if s == "filters":
            total = self.board.special.get("clogged", 0)
            return f"{total - sum(q.grimy for q in self.big)} of {total} clogged filters washed"
        if s == "paste":
            n = d["swabs"].get("cpu", 0)
            return f"{n} of {SWAB_WORK} wipes of the old paste" if n < SWAB_WORK else "click Thermal paste in the box"
        return None  # (nothing to count: its name says it)

    def shake_goal(self):
        plate = [d for d in self.board.dirt if d.host.key == "plate"]
        return min(12, len(plate[0].points)) if plate else 0

    def shake(self, amount):
        """The vintage keyboard upside down and shaken: loose crumbs fall out of it, onto the mat below."""
        plate = next((d for d in self.board.dirt if d.host.key == "plate"), None)
        if plate is None or not plate.host.placed or not plate.left or self.special_ok():
            return
        self.shake_amount = min(0.2, getattr(self, "shake_amount", 0.0) + amount)
        render = application.base.render
        if self.shake_amount >= 0.05 and plate.left and self.clock >= getattr(self, "next_drop", 0.0):
            self.next_drop = self.clock + 0.12  # (a crumb at a time, rattling out)
            self.shake_amount -= 0.05
            i = random.choice(sorted(plate.left))
            plate.left.discard(i)
            p = plate.points[i]
            flyer = plate.mesh.piece(i, self.flyers, tuple(p))
            plate.mesh.move(i, None)
            w = render.getRelativePoint(plate.host.root, Point3(*p))
            self.fly(flyer, (plate.host.root, tuple(p)), (render, (w.x + random.uniform(-0.5, 0.5), DESK_Y + 0.1,
                                                                   w.z + random.uniform(-0.5, 0.5))),
                     0.5, 0.2, end_scale=0.4)
            self.sounds.play("brush", 0.25, pitch=1.6, vary=0.1)
            self.done["shaken"] += 1
            if self.special_ok():
                self.complete("Out they all came, onto the mat: the loose crumbs are shaken out!")

    def swab(self, part, tag):
        """The alcohol swab: on the sticky switch (with its keycap off), or a crusty battery contact (or a webcam's
        smudged lens window, or the dried paste on a CPU)."""
        if self.special == "paste":
            key = getattr(part, "key", None)
            if key == "cooler" or key == "cooler_fan":
                self.say("Take the cooler off first: the old paste is between it and the CPU.")
                self.nope()
                return
            if key != "cpu":
                self.say("The swab's for the CPU: the old, dried paste on top of it, under the cooler.")
                return
            n = self.done["swabs"].get("cpu", 0)
            if n >= SWAB_WORK:
                self.say("It's clean already: now click Thermal paste in the parts box.")
                return
            self.done["swabs"]["cpu"] = n + 1
            self.sounds.play("lube", 0.5, pitch=1.3)
            if n + 1 < SWAB_WORK:
                self.say("The old paste is coming away: wipe it again." if n == 0 else "Nearly clean: once more.")
                return
            self.board.special["paste_old"].np.stash()
            self.sounds.play("sparkle", 0.5)
            self.say("Shiny and clean! Now click Thermal paste in the parts box, for a fresh dot of it.", HONEY_DARK)
            return
        if self.special == "smudge":
            if not tag or tag[0] != "lens":
                self.say("The swab's for the lens window: the glass on the front, with the thumbprint on it.")
                return
            n = self.done["swabs"].get("lens", 0)
            if n >= SWAB_WORK:
                self.say("It's spotless already.")
                return
            self.done["swabs"]["lens"] = n + 1
            self.sounds.play("lube", 0.5, pitch=1.4)
            if n + 1 < SWAB_WORK:
                self.say("The smear's fading: wipe it again." if n == 0 else "Nearly clear: once more.")
                return
            self.board.special["smudge"].np.stash()
            self.sounds.play("sparkle", 0.5)
            self.complete("Crystal clear: not a smear left on the lens window.")
            return
        if self.special == "sticky":
            i = self.board.special["sticky"]
            if not isinstance(part, KeyItem) or part.kind != "switch" or part.i != i:
                self.say(f"The swab's for the sticky switch: the {nice_label(self.board.keys[i][0])} one, with the "
                         "brown spill round it.")
                return
            if self.caps[i].placed:
                self.say("Pull its keycap off first, with the keycap puller (3).")
                self.nope()
                return
            key = i
        else:
            if not tag or tag[0] != "contact":
                self.say("The swab's for the battery contacts: the crusty metal at each end of the battery bay.")
                return
            if any(p.placed for p in self.parts if p.key.startswith("battery")):
                self.say("Take the batteries out first: the contacts are under them.")
                self.nope()
                return
            key = tag[1]
            if self.board.special["crust"][key] is None:
                self.say("That contact's clean: the leak never reached it. Swab the crusty one.")
                return
        n = self.done["swabs"].get(key, 0)
        if n >= SWAB_WORK:
            self.say("That one's clean already.")
            return
        n += 1
        self.done["swabs"][key] = n
        self.sounds.play("lube", 0.5, pitch=1.3)
        if n < SWAB_WORK:
            self.say("Swab it again: work the alcohol in." if self.special == "sticky" else
                     "The crust's coming away: once more.")
            return
        if self.special == "sticky":
            self.board.special["spill"].stash()
            self.sounds.play("sparkle", 0.5)
            self.complete("The spilled drink's dissolved: that switch moves freely again.")
        else:
            self.board.special["crust"][key].stash()
            self.sounds.play("sparkle", 0.5)
            crusty = sum(c is not None for c in self.board.special["crust"])
            if sum(v >= SWAB_WORK for v in self.done["swabs"].values()) == crusty:
                self.complete(("Both contacts shine" if crusty == 2 else "The contact shines") +
                              " like new: the batteries will make a good connection.")
            else:
                self.say("One contact clean, and one to go.")

    def blow(self, part, point):
        """The air blower: a puff of air that lifts the dust off whatever it's aimed at, the capsule's too."""
        self.sounds.play("brush", 0.55, pitch=0.6, vary=0.05)
        if point is None:
            return
        blown = 0  # (off the capsule)
        for dirt in self.board.dirt:
            if not dirt.host.placed or not dirt.left:
                continue
            cover = [q for q in self.above(dirt.host) if not q.screw] if dirt.delicate else []
            if cover:  # it's under the headbasket still
                if (dirt.points[0] - point).length() < 2.5:
                    self.say(f"Take the {cover[0].name} off first: the capsule's under it.")
                continue
            for i in list(dirt.left):
                if (dirt.points[i] - point).length() < 1.1:
                    self.sweep_speck(dirt, i)
                    blown += dirt.delicate
        if blown:
            left = sum(len(d.left) for d in self.board.dirt if d.delicate)
            if left:
                self.say(f"Puff! {left} more speck{'s' if left > 1 else ''} on the capsule.")
            else:
                self.complete("Not a speck left on the diaphragm, and nothing touched it but air.")

    def untie(self, k):
        """One knot in the lav's cable, worked loose."""
        if k in self.done["knots"]:
            return
        self.done["knots"].add(k)
        self.board.special["knots"][k].stash()
        self.sounds.play("turn", 0.6, pitch=1.3)
        left = len(self.board.special["knots"]) - len(self.done["knots"])
        if left:
            self.say(f"Knot undone! {left} more to go.")
        else:
            self.complete("The cable lies smooth: not a knot left in it.")

    def fix_switch(self):
        """The office mouse's worn left switch: its spring bent back, so it clicks once again, not twice."""
        if self.done.get("ok"):
            self.say("Its left switch is fixed already.")
            return
        self.sounds.play("mouse_click", 0.6)
        self.soon(0.15, lambda: self.sounds.play("mouse_click", 0.6, pitch=1.02))
        self.complete("You bent its spring back: the left switch clicks once, crisp and clean.")

    def fresh_battery(self):
        """The travel mouse: its flat battery, swapped for a fresh one."""
        battery = next(p for p in self.parts if p.key == "mouse_battery")
        if self.special_ok():
            self.say("It has a fresh battery already.")
        elif battery.placed:
            self.say("Take the old battery out first: it's under the cover, underneath.")
            self.nope()
        else:
            self.board.special["old"].stash()
            self.board.special["fresh"].unstash()
            self.complete("In with a fresh battery! The old one goes to recycling.")

    def solder(self, part, tag):
        """The soldering iron, on the gaming headset's loose wire: heat the pad and the wire, and the solder flows."""
        if self.special != "solder":
            self.say("There's nothing to solder on this one.")
            return
        if self.special_ok():
            self.say("That joint's soldered already: shiny and solid.")
            return
        if not tag or tag[0] != "joint":
            self.say("The iron's for the loose red wire, on the little board in the left cup.")
            return
        self.sounds.play("sizzle", 0.6)
        self.board.special["loose"].np.stash()
        self.board.special["soldered"].np.unstash()
        self.complete("A shiny joint: the wire's back on its pad. The left side will play again.")

    def fresh_cushions(self):
        """The office headset: its flaking old cushions swapped for fresh ones."""
        cushions = [p for p in self.parts if p.key.endswith("cushion")]
        if self.special_ok():
            self.say("It has fresh cushions already.")
        elif any(c.placed for c in cushions):
            self.say("Take both old cushions off first: they twist off by hand.")
            self.nope()
        else:
            for mesh in self.board.special.get("flakes", []):
                mesh.np.stash()
            self.complete("Two fresh, soft cushions! The flaky old ones go in the bin.")

    def new_battery(self):
        """The wireless headphones: the swollen battery out, and a new one in."""
        battery = next(p for p in self.parts if p.key == "battery")
        if self.special_ok():
            self.say("It has its new battery already.")
        elif battery.placed:
            self.say("Take the swollen one out first: unplug its lead, then lift it out gently.")
            self.nope()
        else:
            battery.mesh.np.stash()
            self.board.special["fresh"].np.unstash()
            self.complete("A new battery, flat as it should be. The swollen one goes to battery recycling.")

    def special_click(self, part, tag):
        """A click that's for this one's own job. True if it was."""
        if (tag and tag[0] == "ribbon" or getattr(part, "key", None) == "ribbon") and self.tool == "hand" and                 self.special == "flicker" and not self.special_ok():  # (pressed home first; then it lifts out)
            self.board.special["loose"].np.stash()
            self.board.special["seated"].np.unstash()
            self.sounds.play("mouse_click", 0.6, pitch=0.9)
            self.complete("Click! The ribbon's pressed home in its socket: the light won't flicker now.")
            return True
        if tag and tag[0] == "knot" and self.tool == "hand":
            self.untie(tag[1])
            return True
        if tag and tag[0] == "left switch" and self.tool == "hand":
            self.fix_switch()
            return True
        return False

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

    def soon(self, delay, what):
        """Say something (or do something) in a moment."""
        self.later.append((self.clock + delay, what))
        self.later.sort(key=lambda w: w[0])

    def hint(self):
        """A word on what to do next, as each stage gets done."""
        if self.kind == "mouse":
            self.mouse_hint()
            return
        if self.kind == "mic":
            self.mic_hint()
            return
        if self.kind in ("webcam", "headset"):
            self.gadget_hint()
            return
        if self.kind == "computer":
            self.pc_hint()
            return
        sticky = self.board.special.get("sticky")
        if sticky is not None and "sticky" not in self.said and not self.caps[sticky].placed and \
                not self.special_ok():
            self.said.add("sticky")
            self.say(f"There's the spill: dried drink round the {nice_label(self.caps[sticky].label)} switch. Swab "
                     f"it with alcohol ({self.tool_no('swab')}) before you go on.", ROSE)
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
            self.say("Battery out: now it's safe to open." + (
                " It's flat, too: click Fresh battery in the parts box to swap it." if self.special == "battery"
                else "") + " Flip it back over (F) and lift the top shell off.")
        elif "shell" not in self.said and not by_key["top_shell"].placed:
            self.said.add("shell")
            self.say("The top shell's off! " + (
                "There's the worn left switch, at the front left of the board: click it with the hand (1) to bend "
                "its spring back." if self.special == "double_click" and not self.special_ok() else
                "Lift the scroll wheel out, and undo the board's little screw (2)."))

    def mic_hint(self):
        """A word as a mic comes apart, mostly about its own job."""
        by_key = {p.key: p for p in self.parts}
        s = self.special
        if s == "foam" and "foam" not in self.said and not by_key["grille"].placed:
            self.said.add("foam")
            self.say("Grille off! See how grubby the foam is? Lift it out (1): you'll wash it once it's all apart.")
        elif s == "contacts" and "contacts" not in self.said and \
                not any(p.placed for p in self.parts if p.key.startswith("battery")):
            self.said.add("contacts")
            self.say(f"Batteries out. See the green crust on the contacts? Swab it off ({self.tool_no('swab')}).",
                     ROSE)
        elif s == "blower" and "blower" not in self.said and not by_key["headbasket"].placed:
            self.said.add("blower")
            self.say(f"There's the gold diaphragm, and it's dusty. Puff it clean with the air blower "
                     f"({self.tool_no('blower')}): never the brush.")

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
        index = {label: i for i, (label, *_) in enumerate(self.board.keys)}
        d = self.done
        if self.special == "sum":  # a sum to do on it
            d["sum"], d["typed"] = (random.randint(3, 9), random.randint(3, 9)), ""
        elif self.special == "pangram":
            d["typed"] = 0
        elif self.special == "fn_layer":
            d["layer"], d["arrows"], d["fn"] = False, set(), index.get("Fn")
        elif self.special == "pair":
            d["hold"], d["esc"] = 0.0, index.get("Esc")
        d["stuck"] = None
        self.dpi = 0
        if "dpi" in self.board.mouse:
            self.board.mouse["dpi"].paint(0, "light", self.DPI[0][1])
            d["dpi"] = {0}
        # a mic: is it on, and can it hear you; how loud it hears you; and you, talking
        form = self.spec.get("form")
        self.mic_on, self.muted = form not in ("wireless", "wireless_hs", "pc_case", "pc_tower"), False
        self.pc_t, self.fan_speed = 0.0, {}  # a computer's
        d["spun"], d["beeped"], d["temp_said"] = set(), False, False
        self.focus, self.shutter_closed, self.ring_on, self.ring_level = 0.15, False, False, 0.5  # a webcam's
        self.hs_volume, d["shuts"] = 0.7, 0  # a headset's
        self.gain = 0.4 if self.special == "gain" else 0.8
        self.mic_level = self.mic_avg = self.talked = self.voice_t = self.good_time = 0.0
        self.speaking, self.next_voice, self.next_crackle = False, 0.0, 0.0
        d["mutes"] = 0
        self.light_mic()
        self.sounds.play("fanfare", 0.7)
        self.build_ui()
        if self.kind == "webcam":
            self.say("It's back together, and plugged in: there you are on its picture! Try it out.", HONEY_DARK)
        elif self.kind == "headset":
            self.say("It's back together! " + ("Switch it on (its button, on the right cup), then listen."
                                               if not self.mic_on else "Click an ear cup to hear that side."),
                     HONEY_DARK)
        elif self.kind == "computer":
            self.say("It's back together, and plugged in! Press its power button, at the top of its front."
                     if form == "pc_tower" else
                     "It's back together! Try its buttons and its front USB, and give each fan a spin.", HONEY_DARK)
        elif self.kind == "mic":
            self.say("It's back together! " + ("Switch it on (click its power switch), then tap it and talk."
                                               if not self.mic_on else "Tap it, and talk into it: hold Space."),
                     HONEY_DARK)
        else:
            self.say("It's back together! Type on it: every key you press lights up." if self.kind == "keyboard"
                     else "It's back together! Click, scroll and move your own mouse: this one does it too.",
                     HONEY_DARK)
        if self.special in ("sum", "fn_layer", "pair", "volume", "pangram", "dpi", "gain", "focus") and \
                not self.special_ok():
            self.soon(4.0, "Its own job: " + self.how())

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
        if self.special and not self.special_ok():
            self.special_key(i, self.board.keys[i][0])
        if done:
            if self.knob is not None and not self.knob_turned:
                self.say("Every key works! Now turn the knob: scroll on it, or click it.", HONEY_DARK)
            else:
                self.check_all_tested()

    def special_key(self, i, label):
        """A key pressed in the test, for this keyboard's own job."""
        s, d = self.special, self.done
        if s == "sum":
            a, b = d["sum"]
            if label in "0123456789" and len(d["typed"]) < 3:
                d["typed"] += label
            elif label in ("Ent", "Enter"):
                if d["typed"] == str(a + b):
                    self.complete(f"{a} + {b} = {a + b}. The sums add up!")
                else:
                    self.say(f"{a} + {b} isn't {d['typed'] or 'nothing'}: try again!", ROSE)
                    d["typed"] = ""
            elif label in ("Back", "Num", "/", "*", "-", "+", "."):
                d["typed"] = ""
        elif s == "fn_layer":
            if label == "Fn":
                self.fn_layer(not d["layer"])
            elif d["layer"] and label in "IJKL":
                d["arrows"].add(label)
                arrow = {"I": "Up", "J": "Left", "K": "Down", "L": "Right"}[label]
                if len(d["arrows"]) == 4:
                    self.fn_layer(False)
                    self.complete("All four arrows, on the Fn layer: the 60% has them after all.")
                else:
                    self.say(f"Fn + {label} is {arrow}: {4 - len(d['arrows'])} more to go.")
            elif not d["layer"] and label in "IJKL" and "fn" not in self.said:
                self.said.add("fn")
                self.say("That's just the letter. Click Fn first: then I, J, K and L are the arrows.")
        elif s == "pangram":
            want = PANGRAM[d["typed"]]
            if label.lower() == want or (label == "Space" and want == " "):
                d["typed"] += 1
                if d["typed"] == len(PANGRAM):
                    self.complete("The quick brown fox, every letter: no dead keys hiding anywhere.")
        elif s == "sticky" and i == self.board.special["sticky"]:  # the spilled drink: it sticks, and repeats
            d["stuck"] = [i, 0.9, 0.0]
            if "stuck" not in self.said:
                self.said.add("stuck")
                self.say(f"It sticks down and repeats: {label.lower() * 8}! That's the dried drink. Next time, swab "
                         "it with alcohol.", ROSE)
        elif s == "pair" and label == "Esc":
            d["hold"] = 0.001

    def fn_layer(self, on):
        """The 60%'s Fn layer: on, I, J, K and L wear the arrows; off, their own letters again."""
        self.done["layer"] = on
        legends, where = self.board.caps.meshes[1], self.board.legend_where
        for label, arrow in (("I", "Up"), ("J", "Left"), ("K", "Down"), ("L", "Right")):
            i = next(k for k, key in enumerate(self.board.keys) if key[0] == label)
            legends.show_glyph(i, where[KEY_LEGENDS[arrow] if on else label])
            self.flash[i] = 0.6
        self.sounds.play("chime" if on else "knob", 0.4)
        if on:
            self.say("Fn layer on: I, J, K and L are the arrows now. Press them!")

    def release_key(self, i):
        stuck = self.done.get("stuck")
        if stuck and stuck[0] == i:
            return  # (it's stuck down: it comes up by itself, slowly)
        if i in self.keys_down:
            self.keys_down.discard(i)
            self.board.caps.on_board(i, (0, 0, 0))
        if self.special == "pair" and i == self.done.get("esc") and not self.special_ok():
            self.done["hold"] = 0.0
            self.board.special["light"].paint(0, "light", (40, 52, 70))

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
        d = self.done
        stuck = d.get("stuck")
        if stuck:  # the sticky key, stuck down, repeating
            i = stuck[0]
            stuck[1] -= time.dt
            stuck[2] -= time.dt
            if stuck[2] <= 0:
                stuck[2] = 0.11
                self.sounds.play(f"press_{SWITCH_KINDS[self.switches[i].style][0]}", 0.45, vary=0.08)
                self.flash[i] = 0.3
            if stuck[1] <= 0:
                d["stuck"] = None
                self.release_key(i)
        if self.special == "pair" and d.get("hold") and not self.special_ok():  # Esc held down: pairing
            if d["esc"] in self.keys_down:
                d["hold"] += time.dt
                blink = int(d["hold"] * 6) % 2 == 0
                self.board.special["light"].paint(0, "light", (90, 150, 255) if blink else (40, 52, 70))
                if d["hold"] >= 2.0:
                    self.board.special["light"].paint(0, "light", (90, 150, 255))
                    self.sounds.play("sparkle", 0.6)
                    self.complete("Its light stops blinking and glows blue: paired over Bluetooth!")
            else:
                d["hold"] = 0.0

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
        if self.phase == "test" and self.kind in ("webcam", "headset") and not self.confirming and \
                self.gadget_input(key):
            return
        if self.phase == "test" and self.kind in HEARS and not self.confirming and self.mic_input(key):
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
            elif tag and tag[0] == "dpi":
                self.next_dpi()
            else:
                self.mouse_button("left", True)
                self.dragging = True  # (and a drag still turns it round)
            return
        if self.phase == "test" and self.kind == "mic":
            self.mic_click(part, tag)
            return
        if self.phase == "test" and self.kind == "webcam":
            self.cam_click(part, tag)
            return
        if self.phase == "test" and self.kind == "headset":
            self.hs_click(part, tag)
            return
        if self.phase == "test" and self.kind == "computer":
            self.pc_click(part, tag)
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
        if self.special_click(part, tag):
            return
        tool = self.tool
        screw = self.screw_under(part, tag)
        if tool == "hand" and screw is not None and screw.thumb:  # a thumb screw: it turns by hand
            self.start_turn(screw)
        elif tool == "driver":
            if screw:
                self.start_turn(screw)
            else:
                self.say(self.advice(part))
        elif tool == "swab":
            self.swab(part, tag)
        elif tool == "blower":
            self.blow(part, point)
        elif tool == "solder":
            self.solder(part, tag)
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
            return ("Thumb screws turn by hand (1), or with the screwdriver (2)." if part.thumb else
                    "Screws need the screwdriver (2): click one with it.")
        if isinstance(part, KeyItem):
            return ("Keycaps come off with the keycap puller (3)." if part.kind == "keycap" else
                    "Switches come out with the switch puller (4).")
        return "Lift parts off with the hand (1)."

    def actionable(self, part):
        """Can the tool in your hand do something to this?"""
        if part is None:
            return False
        if isinstance(part, Bowl):  # (whatever's in your hand)
            if self.kind in ("mic", "computer"):
                return isinstance(self.held, Part3D) and self.held.grimy
            return self.phase != "test" and any(not c.placed and c.grimy for c in self.caps)
        if self.phase == "test":  # the keys to press, and the knob to turn (or a mic, all of it)
            if self.kind in HEARS or self.kind == "computer":
                return isinstance(part, Part3D)
            return part is self.knob or isinstance(part, KeyItem) and part.kind == "keycap"
        if self.held is not None:
            return False
        if isinstance(part, Trinket):
            return True
        tool = self.tool
        if tool == "lube":
            return part in self.stabs and not part.lubed
        if tool == "swab":
            return isinstance(part, KeyItem) and part.kind == "switch" and \
                part.i == self.board.special.get("sticky") or self.special == "contacts" and part.key == "body" or \
                self.special == "paste" and getattr(part, "key", None) == "cpu"
        if tool == "blower":
            return isinstance(part, Part3D)
        if tool == "hand":
            return isinstance(part, Part3D) and (not part.screw or part.thumb)
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
        self.update_mic_test()
        self.update_gadget_test()
        self.update_pc_test()
        while self.later and self.clock >= self.later[0][0]:  # what was to be said, or done, in a moment
            _, what = self.later.pop(0)
            if self.state == "play":
                what() if callable(what) else self.say(what)
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
            upside_down = abs(abs((self.pitch.rotation_x + 180) % 360 - 180) - 180) < 50
            if self.special == "shake" and self.phase != "test" and upside_down:  # shaken about, upside down
                self.shake(Vec3(mouse.velocity).length() * 0.5)
        self.keep_above_desk()
        self.update_turns()
        self.update_twists()
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
            if self.kind != "keyboard":
                checks = self.test_checks()
                done, total = sum(c in self.checks for c, _ in checks), len(checks)
        else:
            done = total - on if phase == "apart" else on
        if self.special:  # its own job, on the job card (and on the test card, while it's being tested)
            ok = self.special_ok()
            status = self.special_status()
            self.set_text(self.special_text, SPECIALS[self.special][0] + (
                "  -  done!" if ok else f":  {status}" if status and phase != "test" else ""))
            for e, col in ((self.special_star, HONEY if ok else PAPER_DARK), (self.special_text,
                                                                            HONEY_DARK if ok else MUTED)):
                if getattr(e, "tinted", None) != col:
                    e.color, e.tinted = rgb(col), col
            if self.test_special is not None:
                self.set_text(self.test_special, ("Its own job: " + SPECIALS[self.special][0] + ", done!") if ok
                              else status or self.how())
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
        self.set_text(self.clean_text, (f"{self.board.mess}: {left} crumbs left" if left else "Spotless inside") +
                      found)
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
                elif item in FRESH.values():  # (until it's swapped in)
                    label, boxed, held = item[0].upper() + item[1:], not self.special_ok(), False
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
            if self.knob is not None and self.knob_text is not None:  # (a keyboard's: a mic's is its gain)
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
    every_job(shop, wait, snap)


def every_job(shop, wait, snap):
    """Every keyboard, mouse and mic taken apart and built back as a player would, each doing its own job on the
    way, then tested: so every one is checked, and has its pictures."""
    def press(label):
        i = next(k for k, key in enumerate(shop.board.keys) if key[0] == label)
        shop.press_key(i)
        shop.release_key(i)

    def act(stage):
        s, b, d = shop.special, shop.board, shop.done
        by_key = {p.key: p for p in shop.parts}
        if stage == "start" and s in ("sticky", "blower", "dpi"):  # how to play, and its own job, on the help card
            shop.toggle_help()
            snap(f"help_{shop.spec['key']}", 0.3)
            shop.toggle_help()
        if s == "shake" and stage == "start":  # upside down, and shaken
            shop.pitch.rotation_x = 180
            for _ in range(60):
                shop.shake(0.06)
                wait(0.13)
                if shop.special_ok():
                    break
            snap("job_shake", 0.3)
            shop.pitch.rotation_x = 0
        elif s == "sticky" and stage == f"keycap{b.special['sticky']}":
            snap("job_sticky", 0.6)
            for _ in range(SWAB_WORK):
                shop.swab(shop.switches[b.special["sticky"]], None)
        elif s == "double_click" and stage == "top_shell":
            shop.fix_switch()
        elif s == "battery" and stage == "mouse_battery":
            shop.fresh_battery()
        elif s == "untangle" and stage == "start":
            snap("job_knots", 1.0)
            for k in range(len(b.special["knots"])):
                shop.untie(k)
        elif s == "contacts" and stage.startswith("battery") and not any(
                p.placed for p in shop.parts if p.key.startswith("battery")):
            snap("job_contacts", 0.6)
            for k in (0, 1):
                for _ in range(SWAB_WORK):
                    shop.swab(by_key["body"], ("contact", k))
        elif s == "blower" and stage == "headbasket":
            snap("job_capsule", 0.6)
            shop.brush_at(Vec3(0, 7.75, -0.215))  # (it won't: never a brush on a capsule)
            for dirt in [x for x in b.dirt if x.delicate]:
                for i in list(dirt.left):
                    shop.blow(by_key["capsule"], dirt.points[i])
        elif s == "smudge" and stage == "start":
            snap("job_smudge", 0.6)
            for _ in range(SWAB_WORK):
                shop.swab(by_key["front_cover"], ("lens",))
        elif s == "flicker" and stage == "front_panel":
            snap("job_ribbon", 0.6)
            shop.pick_tool("hand")
            shop.special_click(by_key["ribbon"], ("ribbon",))
        elif s == "solder" and stage == "left_baffle":
            snap("job_solder", 0.6)
            shop.pick_tool("solder")
            shop.solder(by_key["control_board"], ("joint",))
            snap("job_soldered", 0.3)
        elif s == "swollen" and stage == "battery":
            snap("job_swollen", 0.3)
            shop.pick_up("new battery")
        elif s == "cushions" and stage.endswith("cushion") and not any(
                p.placed for p in shop.parts if p.key.endswith("cushion")):
            shop.pick_up("fresh cushions")
        elif s == "foam" and stage == "build":
            shop.held = by_key["foam"]
            shop.wash()
            wait(1.7)
            shop.held = None
        elif s == "paste" and stage == "cooler":
            snap("job_paste", 0.4)
            for _ in range(SWAB_WORK):
                shop.swab(by_key["cpu"], None)
            shop.pick_up("thermal paste")
            snap("job_pasted", 0.3)
        elif s == "filters" and stage == "build":
            for f in [q for q in shop.big if q.grimy]:
                shop.held = f
                shop.wash()
                wait(1.7)
            shop.held = None
        elif s == "swap" and stage == "build":
            shop.switch_kind = 1  # all brown, where it came with reds
        elif stage == "test":
            if s == "sum":
                a, c = d["sum"]
                for ch in str(a + c):
                    press(ch)
                press("Ent")
            elif s == "fn_layer":
                press("Fn")
                snap("job_fn_layer", 0.3)
                for ch in "IJKL":
                    press(ch)
            elif s == "pair":
                esc = d["esc"]
                shop.press_key(esc)
                wait(1.0)
                snap("job_pairing", 0.0)
                wait(1.3)
                shop.release_key(esc)
            elif s == "volume":
                for way in [-1] * 11 + [1] * 11:
                    shop.turn_knob(way)
            elif s == "pangram":
                for ch in PANGRAM:
                    press("Space" if ch == " " else ch.upper())
            elif s == "dpi":
                for _ in range(len(shop.DPI) - 1):
                    shop.next_dpi()
                snap("job_dpi", 0.3)
            if shop.kind == "webcam":  # every button and the shutter, a photo, and talking (and its focus)
                form = shop.spec["form"]
                if form == "clipcam":
                    shop.cam_click(by_key["shutter"], None)
                    snap("job_shutter_closed", 0.3)
                    shop.cam_click(by_key["shutter"], None)
                elif form == "ballcam":
                    snap("job_blurry", 0.3)
                    for _ in range(30):
                        if shop.special_ok():
                            break
                        shop.turn_knob(1 if shop.focus < FOCUS_AT else -1)
                    shop.cam_click(by_key["back_half"], ("snap",))
                else:
                    shop.cam_click(by_key["housing"], ("light",))
                    shop.ring_level = 0.9
                    shop.mic_try("bright")
                if form != "ballcam":
                    shop.gadget_input("p")
                shop.mic_input("space")
                wait(1.6)
                snap(f"{shop.spec['key']}_test", 0.0)
                shop.mic_input("space up")
            elif shop.kind == "headset":  # switch it on, each ear, mute, the volume, and talking
                if not shop.mic_on:
                    shop.mic_click(by_key["right_cup"], ("power",))
                shop.hs_click(by_key["left_cup"], None)
                shop.hs_click(by_key["right_cup"], None)
                if "mute" in dict(shop.test_checks()):
                    shop.hs_click(by_key["boom"], None)
                    shop.hs_click(by_key["boom"], None)
                shop.mic_try("volume")
                shop.mic_input("space")
                wait(1.6)
                snap(f"{shop.spec['key']}_test", 0.0)
                shop.mic_input("space up")
            elif shop.kind == "computer":  # its buttons, its front USB, and its fans (or switching it on)
                chassis = by_key["chassis"]
                shop.pc_click(chassis, ("power",))
                wait(2.0)
                shop.pc_click(chassis, ("usb",))
                for key in ("front_fan0", "front_fan1", "rear_fan"):
                    if key in by_key:
                        shop.pc_click(by_key[key], None)
                wait(0.5)
                snap(f"{shop.spec['key']}_test", 0.0)
                shop.pc_click(chassis, ("reset",))
                wait(1.6)
            elif shop.kind == "keyboard":
                for i in range(len(shop.caps)):
                    shop.press_key(i)
                    shop.release_key(i)
                if shop.knob is not None and not shop.knob_turned:
                    shop.turn_knob(1)
            elif shop.kind == "mouse":
                for check, _ in shop.mouse_checks():
                    shop.mouse_try(check)
            else:  # a mic: switch it on, mute it and back, tap it, and talk (with its gain set)
                body = by_key["body"] if "body" in by_key else shop.parts[0]
                if not shop.mic_on:
                    shop.mic_click(body, ("power",))
                if s == "gain":
                    for _ in range(6):
                        shop.turn_knob(1)
                if "mute" in dict(shop.mic_checks()):
                    shop.mic_click(body, ("mute",))
                    shop.mic_click(body, ("mute",))
                shop.mic_click(body, None)
                shop.mic_input("space")
                wait(2.2)
                snap(f"{shop.spec['key']}_test", 0.0)
                shop.mic_input("space up")

    for kind in ("mic", "webcam", "headset", "computer"):
        shop.show_menu()
        shop.pick_kind(kind)
        snap(f"3d_menu_{kind}s", 1.2)
    for spec in [m for m in ALL_MODELS if m.get("special")]:
        shop.start(spec)
        wait(0.3)
        if shop.kind in HEARS + ("computer",):
            snap(f"{spec['key']}_start", 1.0)
        act("start")
        for _ in range(800):  # apart: whatever's free, each with its own tool
            free = [p for p in reversed(shop.parts) if p.placed and not shop.above(p)]
            if not free:
                break
            p = free[0]
            if isinstance(p, KeyItem):
                shop.pull(p)
            elif p.twist:
                shop.take_off(p)
                wait(0.7)
            else:
                shop.lift_off(p)
            act(p.key)
        wait(0.6)
        assert shop.phase == "build", f"{spec['key']}: still {shop.phase} after taking everything off"
        if shop.kind in HEARS + ("computer",):
            snap(f"{spec['key']}_apart", 0.2)
        act("build")
        for p in shop.parts:  # and back together
            assert all(q.placed for q in p.below), f"{spec['key']}: {p.name} would go on before what it sits on"
            if isinstance(p, KeyItem):
                shop.put_key(p)
            elif p.screw:
                p.root.unstash()
                p.placed = True
                shop.dish_mesh.move(shop.screws.index(p), None)
                shop.after_change()
            else:
                shop.put_on(p)
        wait(1.0)
        assert shop.phase == "test", f"{spec['key']}: phase is {shop.phase} once it's built"
        act("test")
        wait(0.2)
        ok, tested = shop.special_ok(), shop.all_tested()
        shop.finish_test()
        if shop.kind in HEARS + ("computer",) or spec["key"] in ("tkl", "mouse_gaming"):
            snap(f"{spec['key']}_result", 1.4)
        print(f"{spec['key']:14} {SPECIALS[spec['special']][1]:14} job {'done' if ok else 'NOT DONE'},"
              f" tested {'all' if tested else 'NOT ALL'}, {len(shop.parts)} parts")
        assert ok, f"{spec['key']}: its own job ({spec['special']}) isn't done"
        assert tested or shop.kind == "keyboard", f"{spec['key']}: not everything tested"
    print("every job ok")


if __name__ == "__main__":
    main()
