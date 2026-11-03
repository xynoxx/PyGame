import array
import math
import random
import sys

import pygame

WIDTH, HEIGHT = 1000, 700
HUD_H = 44
HINT_H = 40
PANEL_X = 690  # the bench is left of this line, the panel right of it
BENCH = pygame.Rect(0, HUD_H, PANEL_X, HEIGHT - HUD_H - HINT_H)
HEAD = (300, 214)  # the middle of the fan's head: the grille, blade, spinner and motor all sit round it
GRILLE_R = 148
BLADE_R = 132
MOTOR_R = 64  # the motor's front cover
BLADE_REST = -math.pi / 2 + 0.35  # which way the blade points while it's still
BASE = pygame.Rect(115, 440, 370, 108)
PIECE_TRAY = pygame.Rect(14, 566, 470, 80)  # where the grille, blade, covers and so on wait
TRAY = pygame.Rect(494, 566, 182, 80)  # where the screws wait
STRIP = pygame.Rect(530, 478, 140, 44)  # the power strip the fan plugs into
OUTLET = (566, 500)
METER_BOX = pygame.Rect(508, 62, 164, 116)  # the multimeter, standing on the bench
# The radio lies face down on the bench, so you're looking at its back
RADIO = pygame.Rect(40, 196, 610, 330)  # its case
SPEAKER = (180, 362)  # the middle of the speaker
SPEAKER_R = 104
BOARD = pygame.Rect(318, 238, 316, 178)  # the circuit board, solder side up
BATTERY_BOX = pygame.Rect(394, 424, 172, 90)  # the battery compartment
ANTENNA_BASE = (110, 192)  # where the telescopic antenna swivels, on top of the case
ANTENNA_TIP = (360, 66)

SCREW_TIME = 0.7  # seconds of holding to undo or do up a screw
CRIMP_TIME = 0.8  # seconds of holding the crimper on a joint
DRAIN_TIME = 0.6  # seconds of holding the screwdriver across the capacitor
SPINNER_MAX = 1.5 * 2 * math.pi  # how far the spinner turns from tight to off
SHAFT_WORK = 2 * 2 * math.pi  # how far to turn the shaft to work new oil in
DRY_DRAG = 0.3  # a dry bearing turns this much for each turn of your hand
OIL_DROPS = 2  # drops of oil a dry bearing needs
TOO_MUCH_OIL = 4  # more drops than this and it drips out
SCRUB_RADIUS = 22
SCRUB_STRENGTH = 24  # dust alpha one brush stamp wipes away
GUNK_WORK = 500  # px of scrubbing to clean the old gunk off a bearing
DUST_DONE = 0.04  # the dust counts as gone once less than 4% of it is left
ANIM_TIME = 0.3  # seconds for a piece to come off or go back
WIGGLE_TIME = 0.35  # how long something wiggles when it won't budge
TEST_TIME = 3.2  # seconds a power test lasts
RESULT_DELAY = 0.5  # clicks are ignored this long after a result screen appears
MESSAGE_TIME = 2.8  # seconds a message stays on the line under the bench
HINT_TIME = 4.0  # seconds a hint glows
SHAKE_DECAY = 40
IRON_TIME = 1.2  # seconds of holding the soldering iron on a joint: heat it, feed in solder
POT_TURN = 4.7  # radians from one end of the volume control to the other (about 270°)
POT_WORK = 6 * POT_TURN  # turn it end to end and back three times to work the cleaner in
CRUST_WORK = 260  # px of scrubbing to clean the crust off one battery contact
# Par seconds for one action with each tool (a drag counts as "drag", a test as "test", turning as "twist").
# A repair's par is 20 s plus the actions a tidy repair needs; guided repairs get half as long again.
ACTION_PAR = {"hand": 1.3, "driver": 1.6, "cutters": 1.2, "crimper": 1.6, "brush": 8, "meter": 1.8, "drag": 2.6,
              "test": 4.5, "twist": 4.0, "iron": 2.2, "magnifier": 3.0}

WOOD = (150, 108, 72)
WOOD_DARK = (132, 94, 62)
MAT = (52, 96, 84)
MAT_LINE = (64, 112, 98)
SHADOW = (38, 70, 62)
BG = (22, 25, 35)
PANEL = (36, 40, 54)
CARD = (50, 55, 74)
CARD_HOT = (66, 72, 96)
HUD_BG = (26, 29, 40)
BODY = (234, 228, 212)  # the fan's cream plastic
BLADE = (128, 184, 226)
GRILLE = (204, 208, 216)
MOTOR = (84, 88, 100)
INSIDE = (38, 40, 46)
LAMINATION = (126, 130, 140)
COIL = (198, 112, 52)
BRONZE = (190, 146, 84)
GUNK = (96, 70, 34)
OIL = (240, 196, 70)
FUSE_SLEEVE = (238, 238, 232)
TAPE = (232, 200, 74)
CAP_BODY = (44, 46, 54)
SWITCH = (70, 72, 82)
TERMINAL = (236, 232, 218)
BRASS = (210, 178, 92)
CORD = (236, 236, 230)
WIRE_BROWN = (138, 84, 42)
WIRE_BLUE = (52, 96, 204)
WIRE_RED = (205, 60, 55)
WIRE_YELLOW = (222, 192, 52)
WIRE_BLACK = (44, 44, 48)
COPPER = (214, 140, 72)
METAL = (188, 190, 198)
METAL_DARK = (108, 110, 120)
HOLE = (24, 26, 30)
SCREW = (196, 198, 206)
PLUG = (238, 234, 220)
GLOW = (255, 236, 150)
TEXT = (235, 235, 240)
DIM = (150, 156, 176)
MUTED = (100, 106, 126)
GOLD = (250, 205, 60)
GREEN = (110, 220, 120)
RED = (240, 90, 80)
ACCENT = (150, 130, 240)
SKIN = (240, 204, 168)
SKIN_DARK = (170, 120, 90)
BLACK = (16, 16, 20)
WHITE = (255, 255, 255)
BOARD_GREEN = (34, 100, 64)
TRACE = (58, 134, 86)  # copper under the board's green coating
SOLDER = (206, 208, 214)
SILK = (226, 230, 220)  # the white printing on the board
CHROME = (214, 218, 228)
CRUST = (228, 234, 206)  # what leaks out of old batteries
BATTERY = (52, 128, 86)

TOOL_NAMES = {"hand": "Hand", "driver": "Screwdriver", "cutters": "Cutters", "crimper": "Crimper", "brush": "Brush",
              "meter": "Multimeter", "iron": "Soldering iron", "magnifier": "Magnifier"}
TOOL_INFO = {
    "hand": "Hand: click to unclip, lift off, pull out and push on. Hold and circle to turn things",
    "driver": "Screwdriver: hold it on a screw to undo it or do it up",
    "cutters": "Cutters: cut wires and leads, and strip the plastic off a wire's end",
    "crimper": "Crimper: hold it on a joint to squeeze a metal sleeve tight round the wires",
    "brush": "Brush: hold the button and rub to scrub off dust, old gunk or crust",
    "meter": "Multimeter: click a part to measure it (ohms for wires, fuses and speakers, µF for capacitors, volts)",
    "iron": "Soldering iron: hold it on a joint to melt solder into it (it's about 350 °C: never touch the tip)",
    "magnifier": "Magnifier: click a solder joint to look at it closely. Hairline cracks are hard to see by eye",
}
TOOL_FOR = {"twist": "hand"}  # a step that isn't a tool's own action, and the tool it needs
SUPPLY_INFO = {
    "oil": "Machine oil: a light oil made for motor bearings",
    "wd40": "WD-40: a spray that cleans and loosens things (it isn't a lasting lubricant, or for electronics)",
    "cap": "Run capacitor, {} µF 450 V",
    "fuse": "Thermal fuse, 130 °C: cuts the power if the motor overheats",
}
SUPPLY_INFO.update({
    "vinegar": "White vinegar: a mild acid that neutralises the crust leaky batteries leave",
    "cleaner": "Contact cleaner: a spray made for electronics that cleans and leaves nothing behind",
    "batteries": "Two new {} batteries, 1.5 V each",
    "antenna": "A new telescopic antenna, with its screw",
})
SUPPLY_LABELS = {"oil": "OIL", "wd40": "WD-40", "fuse": "FUSE", "vinegar": "VINEGAR", "cleaner": "CLEANER",
                 "batteries": "2 x {}", "antenna": "ANTENNA"}  # what the drawer's label says
CAP_VALUES = [1.2, 1.5, 1.8, 2.0, 2.5]  # µF: the usual sizes of fan capacitor (the drawer has a wrong one too)
# Types of fan. Desk, stand and wall fans are built round the same kind of head (a motor with a run capacitor, a
# reverse-threaded spinner, a blade and a grille), so the repairs are the same. What differs is the stand, the
# switches, the capacitor's value and the look. "box" is what holds the switch and the capacitor: a desk fan's base,
# or the control box on the others.
FAN_MODELS = [
    dict(key="desk", name="Desk fan", box="base", box_name="base",
         about="A small fan that sits on a table. Its speed keys, the capacitor and the cord are all in its base.",
         body=BODY, blade=BLADE, blades=3, width=0.44, grille=GRILLE, spiral=0.0,
         badge=(80, 140, 200), clips=(-45, 4), controls="keys", caps=[1.2, 1.5], watts=40, label="BREEZE D12"),
    dict(key="stand", name="Stand fan", box="box", box_name="control box",
         about="A tall fan on a pole, with a speed knob and a wind-up timer under its head. Lay it down to work "
               "on it.",
         body=(58, 60, 68), blade=(146, 156, 170), blades=5, width=0.27, grille=(200, 204, 214), spiral=0.9,
         badge=(236, 140, 60), clips=(-90, 6), controls="knobs", caps=[1.5, 1.8], watts=55, label="BREEZE S16"),
    dict(key="wall", name="Wall fan", box="box", box_name="control box",
         about="High on a wall, with two pull cords: one for the speed, one for the swing. Unplug it and lift it "
               "off its bracket first.",
         body=(206, 214, 222), blade=(84, 170, 164), blades=3, width=0.52, grille=(234, 236, 240), spiral=0.0,
         badge=(50, 140, 132), clips=(-90, 5), controls="cords", caps=[1.5, 2.0], watts=50, label="BREEZE W16"),
]

# What can go wrong while you work on the fan: (kind, what the result says, the lesson in it)
FAN_MISTAKES = {
    "power": ("safety", "Worked on it while it was plugged in", "Unplug it before you touch anything."),
    "open_test": ("safety", "Switched it on with covers off", "Only switch it on with every cover back on."),
    "charge": ("safety", "Touched the capacitor before draining it", "Capacitors hold a charge: drain them first."),
    "wrong_cap": ("wrong", "Fitted a capacitor with the wrong value", "Read the µF on the old one and match it."),
    "wd40": ("wrong", "Oiled the bearing with WD-40", "WD-40 cleans but dries out: use machine oil."),
    "good_part": ("wrong", "Took out or cut a part that was fine", "Measure first, and replace only what's broken."),
}
# What's wrong when the fan is switched on: (what the owner says, what you see). Worst first: a fan with no
# power can't show anything else that's wrong with it.
FAN_SYMPTOMS = {
    "unplugged": ("", "Nothing at all... it isn't plugged in!"),
    "dead": ("It just stopped working. Nothing happens at all.", "Nothing happens. No hum, no spin."),
    "cutout": ("It keeps cutting out, especially when the cable moves.", "It runs... stops... runs again."),
    "hum": ("It hums but won't turn. If I give it a push, it starts!", "It hums, but the blade just sits there."),
    "hot": ("", "It runs at the wrong speed and the motor gets hot."),
    "grind": ("", "It grinds and rattles: the motor cover holds the bearing!"),
    "noblade": ("", "The motor runs, but there's no blade on it!"),
    "wobble": ("", "The blade wobbles and rattles: the spinner is loose!"),
    "slow": ("It squeaks, and it's really slow to get going.", "Squeak... it creeps up to a slow spin."),
    "weak": ("It's noisy and hardly blows any air any more.", "It runs, but it rattles and pushes hardly any air."),
}
FAN_FAULT_SYMPTOM = {"dusty": "weak", "dry": "slow", "capacitor": "hum", "thermal": "dead", "cord": "cutout"}
FAN_LEVELS = [
    dict(title="Dusty fan", faults=["dusty"], difficulty=1,
         learn="Take the front apart safely and clean it",
         tip="Dust on the blade makes a fan weak and noisy. For a deep clean, wash the grille and blade in warm "
             "soapy water, and let them dry completely before they go back on."),
    dict(title="Squeaky fan", faults=["dry"], difficulty=2,
         learn="Feel for a dry bearing, clean it and oil it",
         tip="Use a few drops of light machine oil (sewing machine oil is fine). WD-40 cleans but doesn't last, "
             "so the squeak comes back. Too much oil drips out and collects dust."),
    dict(title="Hums but won't spin", faults=["capacitor"], difficulty=3,
         learn="Drain, measure and replace the capacitor",
         tip="If a push gets the blade going, the capacitor is the usual suspect. The new one must have the same µF "
             "value and the same or a higher voltage rating. Drain it before you touch it."),
    dict(title="Completely dead", faults=["thermal"], difficulty=4,
         learn="Find and replace a blown thermal fuse",
         tip="A thermal fuse blows when the motor overheats, often because the bearing was dry, so oil it too. Use "
             "one with the same temperature rating, and crimp it: soldering heat can blow it."),
    dict(title="Cuts out", faults=["cord"], difficulty=4,
         learn="Find the break in the cord and refit it",
         tip="Cords usually break where they bend as they go into the fan. Cut back past the damage. If the outer "
             "sheath is cracked anywhere else, replace the whole cord."),
    dict(title="Mystery fan", faults=None, difficulty=5,
         learn="No steps: test, measure, work it out",
         tip="Repair like a pro: see what it does, think about what could cause that, measure to be sure, then fix "
             "only what's actually broken."),
]
# What can go wrong while you work on the radio
RADIO_MISTAKES = {
    "power": ("safety", "Soldered or sprayed with the batteries in", "Take the batteries out first."),
    "backwards": ("wrong", "Switched on with a battery the wrong way round",
                  "Match each battery's + to the + mark: backwards can damage it."),
    "wd40": ("wrong", "Sprayed WD-40 into the electronics", "It leaves an oily film that collects dust: use contact "
                                                            "cleaner."),
    "good_part": ("wrong", "Replaced a part that was fine", "Measure first, and replace only what's broken."),
}
# What's wrong when the radio is switched on, worst first
RADIO_SYMPTOMS = {
    "nobattery": ("", "Nothing at all... there are no batteries in it!"),
    "backwards": ("", "Nothing at all: a battery is in the wrong way round!"),
    "dead": ("It won't turn on. It's been in a drawer since last year.", "Nothing happens. No sound, no light."),
    "nosound": ("The light comes on, but there's no sound. Headphones work!", "The light's on, but the speaker is "
                                                                               "silent."),
    "cutout": ("It cuts out, then comes back if I give it a tap.", "It plays... cuts out... comes back when tapped."),
    "crackle": ("It crackles and jumps when I turn the volume.", "Scratch! Crackle! The sound jumps as the volume "
                                                                "turns."),
    "fmhiss": ("AM is fine, but FM is just hiss now.", "AM plays fine, but FM is nothing but hiss."),
}
RADIO_FAULT_SYMPTOM = {"leak": "dead", "pot": "crackle", "antenna": "fmhiss", "speaker": "nosound", "joint": "cutout"}
RADIO_LEVELS = [
    dict(title="Won't turn on", faults=["leak"], difficulty=1,
         learn="Clean leaked batteries off the contacts",
         tip="Leaked battery crust is caustic: wear gloves and wash your hands after. A dab of vinegar neutralises "
             "it. Take the batteries out of anything you'll put away for months."),
    dict(title="Crackly volume", faults=["pot"], difficulty=2,
         learn="Clean a dirty volume control",
         tip="Use contact cleaner made for electronics, then turn the knob end to end a dozen times. Not WD-40 or "
             "oil: they leave a film that collects dust. If it still crackles, the control is worn out."),
    dict(title="FM is just hiss", faults=["antenna"], difficulty=2,
         learn="Test and replace a broken antenna",
         tip="AM comes in through a coil on the ferrite rod inside; FM needs the telescopic antenna. So when only "
             "FM is bad, test the antenna first. Spares screw on in the same place."),
    dict(title="No sound", faults=["speaker"], difficulty=3,
         learn="Measure the speaker and solder its wire",
         tip="A good speaker reads a little under the ohms on its label. To solder, heat the tab and the wire "
             "together, feed in a little solder, then take the iron away: 2 or 3 seconds. Work in fresh air."),
    dict(title="Cuts out when tapped", faults=["joint"], difficulty=4,
         learn="Find a cracked solder joint and reflow it",
         tip="Joints on parts that get pushed and pulled, like sockets and knobs, crack with age: look for a thin "
             "ring round the leg. Melt it again with a little fresh solder."),
    dict(title="Mystery radio", faults=None, difficulty=5,
         learn="No steps: listen, look, measure, work it out",
         tip="Listen first: only FM bad points at the antenna, crackles at a knob, silence with headphones still "
             "working at the speaker, and nothing at all at the batteries."),
]
# Types of radio. All three are battery AM/FM radios built the same way inside (a speaker, a board with a volume
# control, a telescopic antenna for FM and two batteries), so the repairs are the same. What differs is the case,
# the size of battery, the speaker and how many screws hold the back on. screws are the ones you can see on the
# back; every model hides one more under the batteries.
RADIO_MODELS = [
    dict(key="pocket", name="Pocket radio", label="POCKET RADIO", code="R-7",
         about="Small enough for a coat pocket, with a thumb wheel for the volume. It runs on two AA batteries.",
         case=(62, 64, 72), back=(80, 83, 92), trim=None, handle=False, vents="slots", cell="AA", ohms=8, watts=0.5,
         screws=[(64, 220), (626, 220), (64, 502)]),
    dict(key="outdoor", name="Outdoor radio", label="OUTDOOR RADIO", code="X-20",
         about="A tough radio for campsites, with a rubber bumper and a carry handle. Two big D batteries last "
               "for months.",
         case=(50, 54, 52), back=(66, 72, 68), trim=(236, 150, 40), handle=True, vents="holes", cell="D", ohms=8,
         watts=2, screws=[(64, 220), (626, 220), (64, 502), (626, 502)]),
    dict(key="retro", name="Retro radio", label="RETRO RADIO", code="TR-56",
         about="Looks like a 1950s set, with a wood case and a big round dial, but it's modern inside. It runs "
               "on two C batteries.",
         case=(122, 78, 46), back=(132, 104, 72), trim=None, handle=False, vents="lines", cell="C", ohms=4, watts=1,
         screws=[(64, 220), (626, 220)]),
]
# What you can learn to fix, each with its own levels: the first screen has a card for each.
PRODUCTS = [
    dict(key="fan", name="Electric fan", noun="fan", color=ACCENT, levels=FAN_LEVELS, models=FAN_MODELS,
         blurb="Dust, squeaks, capacitors, fuses and cords",
         intro="Learn to fix a real electric fan, one real problem at a time. Pick one:",
         safety="Real fans run on mains electricity. Always unplug first, and if you're not sure about a repair, "
                "ask someone qualified.",
         facts=lambda m: f"{' or '.join(f'{c:g}' for c in m['caps'])} µF  ·  {m['watts']} W  ·  {m['blades']} blades",
         same=("Inside, they're built the same way: the same kind of motor, capacitor, spinner and blade.",
               "So the repairs are the same. What changes is the stand, the switches and the capacitor's value.")),
    dict(key="radio", name="Portable radio", noun="radio", color=(236, 150, 70), levels=RADIO_LEVELS,
         models=RADIO_MODELS, blurb="Batteries, crackles, antennas and solder",
         intro="Learn to fix a real portable radio, one real problem at a time. Pick one:",
         safety="These radios run on batteries. Radios that plug into the wall have mains electricity inside: "
                "unplug them, and leave those repairs to someone qualified.",
         facts=lambda m: f"2 x {m['cell']}  ·  {m['ohms']} Ω speaker  ·  {len(m['screws']) + 1} screws",
         same=("Inside, they're built the same way: a speaker, a circuit board, a volume control and an antenna.",
               "So the repairs are the same. What changes is the case, the batteries, the speaker and the screws.")),
]

# The panel on the right
TICKET = pygame.Rect(PANEL_X + 14, HUD_H + 12, 282, 122)
MIDDLE = pygame.Rect(PANEL_X + 14, TICKET.bottom + 10, 282, 246)  # the steps, or what you've found out
STEP_LINES = 10  # steps shown in the list at once
TOOL_RECTS = [pygame.Rect(PANEL_X + 14 + i * 48, MIDDLE.bottom + 26, 42, 36) for i in range(6)]  # 6 tools each
SUPPLY_RECTS = [pygame.Rect(PANEL_X + 14 + i * 57, TOOL_RECTS[0].bottom + 42, 52, 52) for i in range(5)]  # 5 supplies
TEST_BUTTON = pygame.Rect(PANEL_X + 14, SUPPLY_RECTS[0].bottom + 12, 90, 38)
HINT_BUTTON = pygame.Rect(PANEL_X + 110, SUPPLY_RECTS[0].bottom + 12, 90, 38)
FINISH_BUTTON = pygame.Rect(PANEL_X + 206, SUPPLY_RECTS[0].bottom + 12, 90, 38)
# The first screen, a product's levels and the result screen
CARD_RECTS = [pygame.Rect(30 + (i % 2) * 485, 112 + (i // 2) * 154, 455, 140) for i in range(6)]  # up to 6 levels
BACK_BUTTON = pygame.Rect(30, 600, 220, 42)  # from a product's levels back to the first screen
RESULT_BOX = pygame.Rect(40, 30, 920, 640)
RETRY_BUTTON = pygame.Rect(WIDTH // 2 - 230, RESULT_BOX.bottom - 56, 210, 40)
LEVELS_BUTTON = pygame.Rect(WIDTH // 2 + 20, RESULT_BOX.bottom - 56, 210, 40)


def model_rect(i, count):
    """Model i's card on the screen where you pick which type to fix."""
    left = (WIDTH - count * 280 - (count - 1) * 24) // 2
    return pygame.Rect(left + i * 304, 112, 280, 340)


def product_rect(i):
    """Product i's card on the first screen: rows of up to 4, in the middle of the screen."""
    rows = (len(PRODUCTS) + 3) // 4
    row, col = divmod(i, 4)
    across = min(4, len(PRODUCTS) - row * 4)
    left = (WIDTH - across * 210 - (across - 1) * 20) // 2
    top = 340 - (rows * 220 + (rows - 1) * 20) // 2
    return pygame.Rect(left + col * 230, top + row * 240, 210, 220)


def make_sound(freq, ms, volume=0.3, end_freq=None, wave="square"):
    """Build a sound effect in code, so the game needs no sound files.

    The pitch slides from freq to end_freq and the volume fades out.
    wave is "square" (retro beep), "sine" (soft tone) or "noise" (hiss, crash, rumble).
    """
    if not pygame.mixer.get_init():
        return None  # no audio device: the game runs silently
    rate, _, channels = pygame.mixer.get_init()
    n = max(1, rate * ms // 1000)
    end_freq = freq if end_freq is None else end_freq
    samples = array.array("h")
    phase, level = 0.0, 0.0
    for i in range(n):
        t = i / n
        step = (freq + (end_freq - freq) * t) / rate
        if wave == "noise" and int(phase + step) != int(phase):
            level = random.uniform(-1, 1)  # new random level each cycle: lower freq = deeper rumble
        phase += step
        if wave == "square":
            v = 1 if phase % 1 < 0.5 else -1
        elif wave == "sine":
            v = math.sin(2 * math.pi * phase)
        else:
            v = level
        samples.extend([int(volume * (1 - t) * 32767 * v)] * channels)
    return pygame.mixer.Sound(buffer=samples)


def make_tune(notes, note_ms, volume=0.2, wave="square"):
    """A short tune as one sound: notes are frequencies in Hz, 0 is a rest. Each note fades a little."""
    if not pygame.mixer.get_init():
        return None
    rate, _, channels = pygame.mixer.get_init()
    n = rate * note_ms // 1000
    samples = array.array("h")
    for freq in notes:
        phase, level = 0.0, 0.0
        for i in range(n):
            step = freq / rate
            if wave == "noise" and int(phase + step) != int(phase):
                level = random.uniform(-1, 1)
            phase += step
            if not freq:
                v = 0
            elif wave == "square":
                v = 1 if phase % 1 < 0.5 else -1
            elif wave == "sine":
                v = math.sin(2 * math.pi * phase)
            else:
                v = level
            samples.extend([int(volume * (1 - 0.7 * i / n) * 32767 * v)] * channels)
    return pygame.mixer.Sound(buffer=samples)


class Particle:
    """A dot that flies out and shrinks away: used for sparks, dust, oil and bits of plastic."""

    def __init__(self, x, y, vx, vy, color, life, size, gravity=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.color, self.size, self.gravity = color, size, gravity
        self.life = self.max_life = life

    def update(self, dt):
        self.life -= dt
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.life > 0

    def draw(self, surf):
        radius = self.size * self.life / self.max_life
        if radius >= 0.5:
            pygame.draw.circle(surf, self.color, (round(self.x), round(self.y)), max(1, round(radius)))


def burst(particles, x, y, color, count=12, speed=150, life=0.5, size=4, gravity=0.0):
    """Throw particles out from (x, y) in random directions."""
    for _ in range(count):
        angle = random.uniform(0, 2 * math.pi)
        v = speed * random.uniform(0.3, 1)
        particles.append(Particle(x, y, math.cos(angle) * v, math.sin(angle) * v, color,
                                  life * random.uniform(0.6, 1), size, gravity))


def shake_offset(shake):
    return round(random.uniform(-shake, shake)), round(random.uniform(-shake, shake))


class FloatText:
    """Text that drifts up and fades out, like "Tight!" over the spinner."""

    def __init__(self, text, x, y, color, life=1.0):
        self.text, self.x, self.y, self.color = text, x, y, color
        self.age, self.life = 0.0, life

    def update(self, dt):
        self.age += dt
        return self.age < self.life

    def draw(self, screen, font):
        surf = font.render(self.text, True, self.color)
        surf.set_alpha(round(255 * (1 - self.age / self.life)))
        screen.blit(surf, surf.get_rect(center=(self.x, self.y - 40 * self.age / self.life)))


class Flyer:
    """A part you took out, tumbling off the bench into the bin."""

    def __init__(self, kind, x, y):
        self.kind, self.x, self.y = kind, x, y
        self.vx, self.vy = random.uniform(-120, 120), -260
        self.life = 1.2

    def update(self, dt):
        self.life -= dt
        self.vy += 1100 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.life > 0


def shade(color, k):
    """A darker (k < 1) or lighter (k > 1) version of a color."""
    return tuple(max(0, min(255, round(c * k))) for c in color)


def wrap(font, text, width):
    """Split text into lines that fit in width pixels."""
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if font.size(test)[0] <= width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    return lines + [line]


def clock_text(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def jiggle(wiggle):
    """Sideways offset for something that's wiggling because it won't budge."""
    return round(math.sin(wiggle * 70) * 4 * min(1, wiggle / WIGGLE_TIME * 2))


def ring_point(angle, r):
    """The point r pixels from the middle of the fan's head, in direction angle (clockwise from the right)."""
    return HEAD[0] + math.cos(angle) * r, HEAD[1] + math.sin(angle) * r


def rot_rect(cx, cy, w, h, angle):
    """The corners of a w x h rectangle centered on (cx, cy) and turned by angle."""
    c, s = math.cos(angle), math.sin(angle)
    return [(cx + c * dx - s * dy, cy + s * dx + c * dy)
            for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]


def lerp(a, b, k):
    """The point k of the way from a to b."""
    return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k


def dist_to_segment(p, a, b):
    """How far point p is from the line from a to b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    k = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (a[0] + dx * k, a[1] + dy * k))


class Thing:
    """Something on the fan you can click, hold, turn or drop things on. Its zone says when you can get at it:
    see Fan.open."""

    def __init__(self, x, y, r, zone):
        self.x, self.y, self.r, self.zone = x, y, r, zone
        self.wiggle = 0.0
        self.probed = False  # tested with the multimeter

    def hit(self, pos):
        return math.dist(pos, (self.x, self.y)) <= self.r + 5

    def shape(self):
        return "circle", (self.x, self.y), self.r


class Box(Thing):
    """A Thing with a rectangular outline."""

    def __init__(self, rect, zone):
        self.rect = pygame.Rect(rect)
        super().__init__(*self.rect.center, max(self.rect.size) // 2, zone)

    def hit(self, pos):
        return self.rect.inflate(8, 8).collidepoint(pos)

    def shape(self):
        return "rect", self.rect


class Screw(Thing):
    def __init__(self, x, y):
        super().__init__(x, y, 11, "out")
        self.inserted = True
        self.angle = random.uniform(0, 90)
        self.turned = 0.0  # 0 to 1 while it's being turned, for the animation


class Clip(Thing):
    """A spring clip on the rim of the front grille."""

    def __init__(self, angle):
        super().__init__(*ring_point(angle, GRILLE_R), 10, "grille")
        self.angle = angle
        self.latched = True


class Piece:
    """Something that comes off and waits in the tray: the grille, the blade, the spinner, a cover, the cord
    clamp or the tape over the thermal fuse."""

    def __init__(self, kind, name, rect, zone, screws=(), round_=False):
        self.kind, self.name, self.zone = kind, name, zone
        self.rect = pygame.Rect(rect)
        self.screws = list(screws)
        self.round = round_
        self.on = True  # in place (plugged in, for the plug)
        self.t = 0.0  # 0 = in place, 1 = off; animated in between
        self.wiggle = 0.0
        self.image = self.thumb = None  # what it looks like, on the fan and in the tray

    def hit(self, pos):
        if self.round:
            return math.dist(pos, self.rect.center) <= self.rect.w / 2 + 4
        return self.rect.inflate(8, 8).collidepoint(pos)

    def near_home(self, pos):
        """Close enough to where it goes to drop it on."""
        if self.round:
            return math.dist(pos, self.rect.center) <= max(40, self.rect.w / 2)
        return self.rect.inflate(40, 40).collidepoint(pos)

    def shape(self):
        if self.round:
            return "circle", self.rect.center, self.rect.w // 2
        return "rect", self.rect


class Spinner(Piece):
    """The cap that holds the blade on the shaft. It's reverse-threaded, like most fans': clockwise undoes it."""

    def __init__(self):
        super().__init__("spinner", "spinner", (HEAD[0] - 17, HEAD[1] - 17, 34, 34), "front", round_=True)
        self.x, self.y = HEAD
        self.turn = 0.0  # 0 is done up tight, SPINNER_MAX is off
        self.angle = 0.0
        self.refitted = False  # put back on during this repair


class Bearing(Thing):
    """The bearing the motor's shaft turns in, at the front of the motor."""

    def __init__(self, dry):
        super().__init__(*HEAD, 14, "face")
        self.dry = dry
        self.gunk = 1.0 if dry else 0.0  # old oil gone sticky
        self.drops = 0
        self.worked = 0.0  # how far the shaft has turned since it got enough new oil

    def stiff(self):
        return self.dry and self.drops < OIL_DROPS


class Capacitor(Box):
    """The run capacitor in the base: it gives the motor the kick to start turning."""

    def __init__(self, value, faulty):
        bx, by = BASE.topleft
        super().__init__((bx + 152, by + 42, 76, 36), "base")
        self.needed = self.uf = value  # the value it should be, and the value of the one fitted
        self.present = True
        self.faulty = faulty
        self.charged = True  # it can hold a charge even unplugged, until you drain it
        self.connectors = [Thing(bx + 166, by + 27, 7, "base"), Thing(bx + 214, by + 27, 7, "base")]
        for c in self.connectors:
            c.on = True

    def measure(self):
        if not self.present:
            return "EMPTY", False
        if self.faulty:
            return f"{self.uf * 0.14:.2f} µF", False
        return f"{self.uf:g} µF", self.uf == self.needed


class Fuse(Box):
    """The thermal fuse, taped onto the motor's windings, with a crimped joint at each end."""

    def __init__(self, blown):
        hx, hy = HEAD
        super().__init__((hx - 42, hy - 35, 28, 14), "fuse")
        self.present = True
        self.blown = blown  # a blown one looks just like a good one: only the multimeter can tell
        self.leads = [Thing(hx - 48, hy - 28, 7, "fuse"), Thing(hx - 8, hy - 28, 7, "fuse")]
        for lead in self.leads:
            lead.state = "crimped"  # crimped, cut or loose (a new fuse's lead, not crimped yet)

    def measure(self):
        if not self.present:
            return "EMPTY", False
        if self.blown or any(lead.state == "cut" for lead in self.leads):
            return "OPEN", False
        if any(lead.state == "loose" for lead in self.leads):
            return "LOOSE", False
        return "0.0 Ω", True


class Cord:
    """The power cord inside the base: two wires held in a terminal block, and the spot by the clamp where it
    bends every time someone moves the fan, which is where cords break."""

    def __init__(self, damaged):
        bx, by = BASE.topleft
        self.damaged = damaged
        self.cut = False  # the damaged bit has been cut off
        self.damage = Thing(bx + 347, by + 55, 10, "cord")
        self.probe = Thing(bx + 327, by + 55, 8, "base")  # where the multimeter tests it
        self.terminals = [Screw(bx + 299, by + 40), Screw(bx + 299, by + 70)]
        self.ends = []
        for screw, color in zip(self.terminals, (WIRE_BLUE, WIRE_BROWN)):  # neutral, live
            end = Thing(bx + 315, screw.y, 7, "base")
            end.screw, end.color = screw, color
            end.state = "fitted"  # fitted (as it came), cut (plastic right to the end) or stripped
            self.ends.append(end)

    def connected(self):
        return all(end.screw.inserted and end.state != "cut" for end in self.ends)

    def measure(self):
        return ("0.1 Ω", True) if self.connected() and not self.damaged else ("OPEN", False)


def blade_points(cx, cy, angle, count=3, width=0.44):
    """The outline of each of the fan's blades: width is how broad they are at their widest."""
    blades = []
    for k in range(count):
        a = angle + k * 2 * math.pi / count
        front, back = [], []
        for i in range(13):
            t = i / 12
            r = 24 + (BLADE_R - 24) * t
            sweep = 0.22 * t
            half = 0.10 + width * math.sin(math.pi * (0.06 + 0.88 * t)) ** 0.8
            front.append((cx + math.cos(a + sweep - half) * r, cy + math.sin(a + sweep - half) * r))
            back.append((cx + math.cos(a + sweep + half) * r, cy + math.sin(a + sweep + half) * r))
        blades.append(front + back[::-1])
    return blades


class Dust:
    """Fluff caked on the grille, the blade or the motor's front: the brush wipes it away."""

    def __init__(self, radius, area, clumps):
        size = 2 * radius + 4
        self.radius = radius
        self.surf = pygame.Surface((size, size), pygame.SRCALPHA)
        self.pos = (HEAD[0] - size // 2, HEAD[1] - size // 2)
        c = size // 2
        for _ in range(clumps):
            a, r = random.uniform(0, 2 * math.pi), radius * math.sqrt(random.random())
            grey = random.randint(150, 190)
            pygame.draw.circle(self.surf, (grey, grey - 6, grey - 16, random.randint(110, 170)),
                               (c + math.cos(a) * r, c + math.sin(a) * r), random.uniform(7, 20))
        for _ in range(clumps // 5):  # strands of fluff
            a, r = random.uniform(0, 2 * math.pi), radius * math.sqrt(random.random())
            x, y = c + math.cos(a) * r, c + math.sin(a) * r
            b = random.uniform(0, math.pi)
            pygame.draw.line(self.surf, (120, 116, 108, 170), (x, y), (x + 24 * math.cos(b), y + 24 * math.sin(b)), 2)
        mask = pygame.Surface((size, size), pygame.SRCALPHA)
        area(mask, c, c)  # paints where dust can sit in solid white
        self.surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        self.full = max(1, self.count())
        self.clean = not clumps
        self.left = 0.0 if self.clean else 1.0

    def count(self):
        return pygame.mask.from_surface(self.surf, 40).count()

    def hit(self, pos):
        return math.dist(pos, HEAD) <= self.radius

    def shape(self):
        return "circle", HEAD, self.radius


def disc_area(radius):
    return lambda surf, x, y: pygame.draw.circle(surf, WHITE, (x, y), radius)


def blade_area(model):
    """Where dust can sit on this model's blade."""
    def area(surf, x, y):
        for points in blade_points(x, y, BLADE_REST, model["blades"], model["width"]):
            pygame.draw.polygon(surf, WHITE, points)
    return area


class Step:
    """One step of a tidy repair: a tool (or "drag", "twist" or "button") used on some targets, done once
    goal(target) is true for each needed one. Guided, the game walks you through them; on your own, the panel
    just ticks them off."""

    def __init__(self, tool, targets, goal, label, text, source=None, needed=None, optional=False, badge=None):
        self.tool, self.targets, self.goal = tool, list(targets), goal
        self.label, self.text = label, text
        self.source = source  # what to drag, for a "drag" step
        self.needed = needed  # the targets that must be done; None means all of them
        self.optional = optional  # you can skip it (testing first, measuring, feeling the shaft)
        self.badge = badge  # what the tag by the glow says, if not the tool's usual

    def left(self):
        return [t for t in self.targets if not self.goal(t)]

    def complete(self):
        return all(self.goal(t) for t in (self.targets if self.needed is None else self.needed))

    def par(self):
        if self.tool == "button":
            return ACTION_PAR["test"] if self.targets == ["TEST"] else ACTION_PAR["hand"]
        if self.tool in ("brush", "twist"):
            return ACTION_PAR[self.tool]
        count = len(self.targets) if self.needed is None else len(self.needed) + 1
        return ACTION_PAR[self.tool] * count


class Device:
    """Whatever's on the bench: the fan or the radio. A device has its parts, what's wrong with it, the steps of a
    tidy repair and how that's going. The game gives you the tools and asks the device what each one does to it
    (use_hand, use_driver and so on), so each device says what's real for it."""
    TOOLS = []  # its six tools, in order: keys 1-6
    SUPPLIES = []  # the five things in the drawer
    SYMPTOMS = {}  # what's wrong when it's switched on: (what the owner says, what you see), worst first
    FAULT_SYMPTOM = {}  # the symptom each fault shows
    FAULT_NAMES = {}  # each fault in words, for the mystery's result
    MISTAKES = {}  # what can go wrong while you work: (kind, what the result says, the lesson in it)
    WORKS = ""  # what the power test says when it works

    def start(self):
        """What every device keeps track of, once its parts are built."""
        self.complaint = self.SYMPTOMS[self.symptom()][0]
        self.time = 0.0
        self.tests = 0
        self.worked = False  # you've started taking it apart
        self.closed_ok = False  # tested and working with everything back on, since you last touched it
        self.finished = False
        self.hints = 0
        self.mistakes = {}  # kind: how many times
        self.found = set()  # the faults you've tracked down (felt, seen or measured)
        self.readings = []  # the multimeter's log, newest last: (what, reading, good)
        self.observations = []  # what each power test showed
        self.steps = self.plan()
        self.step = 0  # the guided repair's current step
        self.done = [False] * len(self.steps)  # steps you've done, in whatever order (on your own)
        self.undo = [s.complete() for s in self.steps]  # true from the start: steps that put something back
        # Earlier steps on the same things, which have to be done first (skippable ones don't count)
        self.before = [[j for j in range(i) if not self.steps[j].optional
                        and any(t in step.targets for t in self.steps[j].targets)]
                       for i, step in enumerate(self.steps)]
        self.par = 20 + sum(s.par() for s in self.steps)

    def touch(self):
        self.worked = True
        self.closed_ok = False

    def mistake(self, kind):
        self.mistakes[kind] = self.mistakes.get(kind, 0) + 1

    def current(self):
        return self.steps[self.step] if self.step < len(self.steps) else None

    def track(self):
        """Tick off the steps you've done, in whatever order you did them. A step that puts something back only
        counts while it stays back."""
        for i, step in enumerate(self.steps):
            if self.undo[i] or not self.done[i]:
                self.done[i] = all(self.done[j] for j in self.before[i]) and step.complete()

    def next_step(self):
        """The first step still to do; steps you can skip don't hold the list up."""
        return next((i for i, s in enumerate(self.steps) if not self.done[i] and not s.optional), len(self.steps))

    def tray_slot(self, piece):
        return pygame.Rect(PIECE_TRAY.x + 8 + self.tray_pieces.index(piece) * 65, PIECE_TRAY.y + 8, 62, 64)

    def in_tray(self, piece):
        """Waiting in the parts tray (a part that went in the bin isn't)."""
        return not piece.on and getattr(piece, "present", True)

    def moving_pieces(self):
        """The pieces that slide off to the tray and back."""
        return self.tray_pieces

    def drag_source_at(self, pos):
        """Something you can pick up and drag, whatever tool you're holding: a piece waiting in the tray."""
        for piece in self.tray_pieces:
            if self.in_tray(piece) and self.tray_slot(piece).collidepoint(pos):
                return "tray", piece
        return None

    def danger(self, doing):
        """Why doing this right now isn't safe, or None if it is."""
        return None

    def drop(self, game, source, pos):
        """You let go of something you were dragging: a supply from the drawer, or a piece from the tray going back
        where it belongs (dropped anywhere else, it goes back in the tray)."""
        kind, thing = source
        if kind == "supply":
            self.drop_supply(game, thing, pos)
            return
        if not thing.near_home(pos) or not game.allowed(thing, "drag") or not game.safe("drag"):
            return
        blocked = self.blocked(thing) or (None if self.open(thing.zone) else
                                          (thing, "Something's in the way: take it off first."))
        if blocked:
            game.wiggle(*blocked)
            return
        self.touch()
        thing.on = True
        self.refitted(game, thing)

    def blocked(self, piece):
        """Something that has to go back before this piece can: (what wiggles, why), or None."""
        return None

    def refitted(self, game, piece):
        game.play("cover")

    def wrong_supply(self, key):
        """What the guide says when you pick up the wrong thing from the drawer."""
        return "Not that one: follow the glowing outline."

    def hold_time(self, target):
        """Seconds of holding a tool on this (not a screw) to get it done."""
        return CRIMP_TIME

    def holding(self, game, target, mouse):
        """Every frame while you hold a tool on something: sparks, smoke and so on."""

    def held(self, game, target):
        """You've held the tool on it long enough."""

    def turn(self, game, thing, delta):
        """You've turned thing by delta radians (positive is clockwise) with the hand."""

    def twist_progress(self, thing):
        """How far round you've got with what you're turning, 0 to 1, for the ring round it."""
        return 0.0

    def scrub(self, game, a, b):
        """The brush moved from a to b with the button down."""

    def count_dust(self, game):
        """Now and then while you scrub: is the dust gone yet?"""

    def on_test(self, game, symptom):
        """It's just been switched on: note any mistake in doing that."""

    def test_sounds(self, symptom):
        return []

    def test_warning(self):
        """A warning for the power test's banner, or None."""
        return None

    def update_test(self, game, dt):
        """Every frame of a power test."""

    def draw_test(self, surf, game):
        """What it does on the bench during a power test."""

    def supply_info(self, key):
        return SUPPLY_INFO[key]

    def supply_label(self, key):
        return SUPPLY_LABELS[key]

    def supply_icon(self, key):
        return key

    def draw_supply(self, surf, key, pos, fonts):
        SUPPLY_BODIES[key](surf, *pos)

    def notes(self):
        """What you've found out by hand, for the mystery's notebook: (text, good)."""
        return []

    def draw_details(self, lens, to_lens, zoom):
        """Fine details only the magnifier shows, drawn on its lens: to_lens turns bench points into lens points."""


class Fan(Device):
    """The desk fan on the bench: everything you can take off, undo, measure and fix, and what's wrong with it."""
    TOOLS = ["hand", "driver", "cutters", "crimper", "brush", "meter"]
    SUPPLIES = ["oil", "wd40", "cap_a", "cap_b", "fuse"]
    SYMPTOMS = FAN_SYMPTOMS
    FAULT_SYMPTOM = FAN_FAULT_SYMPTOM
    FAULT_NAMES = {"dusty": "dust", "dry": "a dry bearing", "capacitor": "a dead capacitor",
                   "thermal": "a blown thermal fuse", "cord": "a broken cord"}
    MISTAKES = FAN_MISTAKES
    WORKS = "It works! A strong, steady breeze."

    @staticmethod
    def mystery():
        """What's wrong with a mystery fan: usually one thing, sometimes one in the head and one in the base."""
        head, base = ["dusty", "dry", "thermal"], ["capacitor", "cord"]
        if random.random() < 0.3:
            return [random.choice(head), random.choice(base)]
        return [random.choice(head + base)]

    def __init__(self, faults, model=None):
        self.faults = set(faults)
        self.model = model = model or FAN_MODELS[0]  # desk, stand or wall
        hx, hy = HEAD
        bx, by = BASE.topleft
        around = lambda r: (hx - r, hy - r, 2 * r, 2 * r)
        self.plug = Piece("plug", "plug", (OUTLET[0] - 13, OUTLET[1] - 16, 26, 32), "out")
        first, count = model["clips"]
        self.clips = [Clip(math.radians(first + k * 360 / count)) for k in range(count)]
        self.grille = Piece("grille", "front grille", around(GRILLE_R), "out", round_=True)
        self.spinner = Spinner()
        self.blade = Piece("blade", "blade", around(BLADE_R), "front", round_=True)
        self.shaft = Thing(hx, hy, 6, "core")
        self.shaft.angle = 0.0
        self.bearing = Bearing("dry" in faults)
        screws = [Screw(*ring_point(math.radians(a), 55)) for a in (-90, 30, 150)]
        self.motor_cover = Piece("motor", "motor cover", around(MOTOR_R), "core", screws, round_=True)
        self.winding = Thing(hx + 24, hy + 24, 14, "motor")
        self.fuse = Fuse("thermal" in faults)
        self.tape = Piece("tape", "tape", (hx - 56, hy - 37, 56, 18), "motor")
        screws = [Screw(x, y) for y in (by + 16, BASE.bottom - 16) for x in (bx + 16, BASE.right - 16)]
        self.base_cover = Piece("base", f"{model['box']} cover", BASE, "out", screws)
        self.switch = Box((bx + 28, by + 20, 92, 56), "base")
        needed = random.choice(model["caps"])  # what this model's label says
        values = [needed, random.choice([v for v in CAP_VALUES if v != needed])]
        self.cap = Capacitor(needed, "capacitor" in faults)
        keys = ["cap_a", "cap_b"]
        random.shuffle(keys)
        self.cap_values = dict(zip(keys, values))  # what's in the drawer: the right value and a wrong one
        self.cord = Cord("cord" in faults)
        self.clamp = Piece("clamp", "cord clamp", (bx + 336, by + 28, 22, 52), "base",
                           [Screw(bx + 347, by + 36), Screw(bx + 347, by + 72)])
        self.tray_pieces = [self.grille, self.spinner, self.blade, self.motor_cover, self.tape, self.base_cover,
                            self.clamp]
        dusty = "dusty" in faults
        self.grille_dust = Dust(GRILLE_R - 4, disc_area(GRILLE_R - 4), 70 if dusty else 0)
        self.blade_dust = Dust(BLADE_R, blade_area(model), 60 if dusty else 0)
        self.face_dust = Dust(MOTOR_R - 4, disc_area(MOTOR_R - 4), 22 if dusty else 0)
        self.dusts = [self.grille_dust, self.blade_dust, self.face_dust]
        self.things = ([self.plug, self.grille, self.spinner, self.blade, self.shaft, self.bearing, self.motor_cover,
                        self.winding, self.fuse, self.tape, self.base_cover, self.switch, self.cap, self.clamp,
                        self.cord.damage, self.cord.probe] + self.clips + self.fuse.leads + self.cap.connectors
                       + self.cord.ends + self.cord.terminals
                       + [s for p in (self.motor_cover, self.base_cover, self.clamp) for s in p.screws])
        for piece in self.tray_pieces + [self.plug]:
            piece.model = model  # so its picture is in this model's colors

        self.felt_shaft = False
        self.start()

    def open(self, zone):
        """Can you get at things in this zone right now?"""
        front = not self.grille.on
        core = front and not self.blade.on
        motor = core and not self.motor_cover.on
        base = not self.base_cover.on
        return {"out": True, "grille": self.grille.on, "front": front, "core": core,
                "face": core and self.motor_cover.on, "motor": motor, "fuse": motor and not self.tape.on,
                "base": base, "cord": base and not self.clamp.on}[zone]

    def closed(self):
        """Everything's back on that keeps fingers out of the blade and the wires."""
        return self.grille.on and self.base_cover.on and self.motor_cover.on

    def symptom(self, testing=False):
        """The worst thing wrong with the fan when it's switched on, or None if it works."""
        if testing and not self.plug.on:
            return "unplugged"
        found = set()
        fuse, cord, cap = self.fuse, self.cord, self.cap
        if not fuse.present or fuse.blown or any(lead.state == "cut" for lead in fuse.leads):
            found.add("dead")
        elif any(lead.state == "loose" for lead in fuse.leads):
            found.add("cutout")
        if not cord.connected():
            found.add("dead")
        elif cord.damaged:
            found.add("cutout")
        if not cap.present or cap.faulty or not all(c.on for c in cap.connectors):
            found.add("hum")
        elif cap.uf != cap.needed:
            found.add("hot")
        if not self.motor_cover.on:
            found.add("grind")
        if not self.blade.on:
            found.add("noblade")
        elif not self.spinner.on or self.spinner.turn > 0:
            found.add("wobble")
        if self.bearing.stiff():
            found.add("slow")
        if any(d.left > DUST_DONE for d in self.dusts):
            found.add("weak")
        return next((s for s in self.SYMPTOMS if s in found), None)

    def screws_in_reach(self):
        """The screws you can get at with the screwdriver right now."""
        found = []
        if self.base_cover.on:
            found += self.base_cover.screws
        else:
            found += self.cord.terminals
            if self.clamp.on:
                found += self.clamp.screws
        if self.open("core") and self.motor_cover.on:
            found += self.motor_cover.screws
        return found

    def loose_screws(self):
        return [s for p in (self.motor_cover, self.base_cover, self.clamp) for s in p.screws if not s.inserted] + [
            s for s in self.cord.terminals if not s.inserted]

    def issues(self):
        """Everything left undone when you finish."""
        found = []

        def add(count, one, many=""):
            if count:
                found.append(one if count == 1 else f"{count} {many}")

        add(sum(not s.inserted for p in (self.motor_cover, self.base_cover, self.clamp) for s in p.screws),
            "A screw left out", "screws left out")
        add(sum(not c.latched for c in self.clips), "A grille clip left open", "grille clips left open")
        add(not self.grille.on, "Front grille left off: fingers can reach the blade")
        add(not self.motor_cover.on, "Motor cover left off")
        add(not self.base_cover.on, f"{self.model['box'].capitalize()} cover left off: live wires showing")
        add(not self.clamp.on, "Cord clamp left off: a tug could rip the wires out")
        add(not self.tape.on, "Tape left off the fuse joints")
        b = self.bearing
        add(b.drops > TOO_MUCH_OIL, "Too much oil: it'll drip and collect dust")
        add(b.dry and b.gunk > 0, "Old gunk left on the bearing")
        add(b.dry and not b.stiff() and b.worked < SHAFT_WORK, "Oil not worked into the bearing")
        add(not self.closed_ok, "Not tested with everything back on")
        return found

    def plan(self):
        """The steps of a tidy repair, from switching it on to finishing."""
        steps = []
        faults = self.faults

        def add(tool, targets, goal, label, text, **more):
            steps.append(Step(tool, targets, goal, label, text, **more))

        clips, grille, spinner, blade, bearing = self.clips, self.grille, self.spinner, self.blade, self.bearing
        add("button", ["TEST"], lambda t: self.tests >= 1, "Switch it on", "Press TEST to see what it does",
            optional=True)
        add("hand", [self.plug], lambda p: not p.on, "Unplug it",
            "Safety first! Click the plug to pull it out of the power strip")
        if faults & {"dusty", "dry", "thermal"}:
            if "dusty" in faults:
                add("brush", [self.grille_dust], lambda d: d.clean, "Brush the grille",
                    "Pick the brush (5), hold the button and rub the dust off the grille")
            add("hand", clips, lambda c: not c.latched, f"Open {len(clips)} grille clips",
                "Click each clip on the grille's rim with the hand (1) to flip it open")
            add("hand", [grille], lambda p: not p.on, "Lift off the grille", "Click the grille to lift it off")
            if "dusty" in faults:
                add("brush", [self.blade_dust], lambda d: d.clean, "Brush the blade",
                    "Rub the fluff off the blade with the brush (5)")
            add("twist", [spinner], lambda s: not s.on, "Unscrew the spinner",
                "Hold the spinner and circle the mouse CLOCKWISE. Fan spinners are reverse-threaded!",
                badge="CLOCKWISE")
            add("hand", [blade], lambda p: not p.on, "Pull off the blade", "Click the blade to slide it off the shaft")
            if "dusty" in faults:
                add("brush", [self.face_dust], lambda d: d.clean, "Brush the motor",
                    "Rub the dust off the front of the motor")
            if "dry" in faults:
                add("twist", [self.shaft], lambda s: self.felt_shaft, "Feel the shaft",
                    "Hold the shaft in the middle and circle the mouse: does it turn freely?", optional=True,
                    badge="TURN IT")
                add("brush", [bearing], lambda b: b.gunk == 0, "Clean off the old gunk",
                    "Rub the sticky old oil off the bearing with the brush (5)")
                add("drag", [bearing], lambda b: b.drops >= OIL_DROPS, f"Add {OIL_DROPS} drops of oil",
                    f"Drag the machine oil from the drawer onto the bearing, {OIL_DROPS} times. Not WD-40!",
                    source=("supply", "oil"))
                add("twist", [self.shaft], lambda s: bearing.worked >= SHAFT_WORK, "Work the oil in",
                    "Turn the shaft round and round to work the oil into the bearing", badge="TURN IT")
            if "thermal" in faults:
                mcover, fuse, tape = self.motor_cover, self.fuse, self.tape
                n = len(mcover.screws)
                add("driver", mcover.screws, lambda s: not s.inserted, f"Undo {n} motor screws",
                    "Pick the screwdriver (2) and hold it on each screw until it comes out")
                add("hand", [mcover], lambda p: not p.on, "Lift off the motor cover",
                    "Click the motor cover with the hand (1) to lift it off")
                add("hand", [tape], lambda p: not p.on, "Peel back the tape",
                    "The thermal fuse hides under the yellow tape on the windings: click the tape to peel it off")
                add("meter", [fuse, self.winding], lambda t: t.probed, "Test the thermal fuse",
                    "Pick the multimeter (6) and click the fuse, then a winding. OPEN means no connection: blown",
                    needed=[fuse], optional=True)
                add("cutters", fuse.leads, lambda lead: lead.state == "cut", "Cut out the old fuse",
                    "Pick the cutters (3) and click both joints of the fuse")
                add("hand", [fuse], lambda f: not f.present, "Take out the old fuse",
                    "Click the old fuse with the hand (1) to take it out")
                add("drag", [fuse], lambda f: f.present, "Fit a new thermal fuse",
                    "Drag a thermal fuse from the drawer into the gap", source=("supply", "fuse"))
                add("crimper", fuse.leads, lambda lead: lead.state == "crimped", "Crimp both joints",
                    "Pick the crimper (4) and hold it on each joint. Never solder a thermal fuse: the heat can blow it")
                add("drag", [tape], lambda p: p.on, "Tape it back up",
                    "Drag the tape from the tray back over the fuse", source=("tray", tape))
                add("drag", [mcover], lambda p: p.on, "Put the motor cover back",
                    "Drag the motor cover from the tray back onto the motor", source=("tray", mcover))
                add("driver", mcover.screws, lambda s: s.inserted, f"Do up {n} motor screws",
                    "Hold the screwdriver (2) on each hole")
            add("drag", [blade], lambda p: p.on, "Put the blade back",
                "Drag the blade from the tray back onto the shaft", source=("tray", blade))
            add("drag", [spinner], lambda s: s.on, "Put the spinner on",
                "Drag the spinner from the tray onto the middle of the blade", source=("tray", spinner))
            add("twist", [spinner], lambda s: s.on and s.turn == 0, "Tighten the spinner",
                "Hold the spinner and circle the mouse ANTI-CLOCKWISE to do it up tight", badge="ANTI-CLOCKWISE")
            add("drag", [grille], lambda p: p.on, "Put the grille back",
                "Drag the grille from the tray back over the blade", source=("tray", grille))
            add("hand", clips, lambda c: c.latched, f"Close {len(clips)} clips",
                "Click each clip with the hand (1) to snap it shut")
        if faults & {"capacitor", "cord"}:
            bcover = self.base_cover
            n = len(bcover.screws)
            box, box_name = self.model["box"], self.model["box_name"]
            add("driver", bcover.screws, lambda s: not s.inserted, f"Undo {n} {box} screws",
                f"Pick the screwdriver (2) and hold it on each screw of the {box_name}")
            add("hand", [bcover], lambda p: not p.on, f"Lift off the {box} cover",
                f"Click the {box} cover with the hand (1) to lift it off")
            if "capacitor" in faults:
                cap = self.cap
                key = next(k for k, v in self.cap_values.items() if v == cap.needed)
                add("driver", [cap], lambda c: not c.charged, "Drain the capacitor",
                    "A capacitor can hold a charge. Hold the screwdriver (2) across its two terminals", badge="HOLD")
                add("meter", [cap, self.switch], lambda t: t.probed, "Measure the capacitor",
                    f"Multimeter (6): click the capacitor. Its label says {cap.needed:g} µF: is it close?",
                    needed=[cap], optional=True)
                add("hand", cap.connectors, lambda c: not c.on, "Pull off 2 connectors",
                    "Click both connectors on the capacitor's wires to pull them off")
                add("hand", [cap], lambda c: not c.present, "Take out the old capacitor",
                    "Click the capacitor with the hand (1) to take it out")
                add("drag", [cap], lambda c: c.present and c.uf == c.needed, f"Fit a new {cap.needed:g} µF one",
                    f"Drag the {cap.needed:g} µF capacitor from the drawer into the gap. Match the old label!",
                    source=("supply", key))
                add("hand", cap.connectors, lambda c: c.on, "Push the connectors on",
                    "Click both connectors to push them back on")
            if "cord" in faults:
                cord, clamp = self.cord, self.clamp
                add("driver", clamp.screws, lambda s: not s.inserted, "Undo 2 clamp screws",
                    "The clamp grips the cord where it comes in. Hold the screwdriver (2) on its screws")
                add("hand", [clamp], lambda p: not p.on, "Lift off the cord clamp", "Click the clamp to lift it off")
                add("meter", [cord.probe, self.switch], lambda t: t.probed, "Find the break",
                    "Multimeter (6): click the cord, then the switch. OPEN means a wire is broken inside",
                    needed=[cord.probe], optional=True)
                add("driver", cord.terminals, lambda s: not s.inserted, "Undo 2 terminal screws",
                    "Hold the screwdriver (2) on both screws of the white terminal block to free the wires")
                add("cutters", [cord.damage], lambda d: cord.cut, "Cut off the damaged bit",
                    "Pick the cutters (3) and click the cracked bit of cord to cut it off")
                add("cutters", cord.ends, lambda e: e.state == "stripped", "Strip both wires",
                    "Click each wire's end with the cutters (3) to strip the plastic off")
                add("driver", cord.terminals, lambda s: s.inserted, "Do up 2 terminal screws",
                    "Hold the screwdriver (2) on both terminal screws to clamp the bare wires")
                add("drag", [clamp], lambda p: p.on, "Put the clamp back",
                    "Drag the cord clamp from the tray back over the cord", source=("tray", clamp))
                add("driver", clamp.screws, lambda s: s.inserted, "Do up 2 clamp screws",
                    "Hold the screwdriver (2) on both clamp holes")
            add("drag", [bcover], lambda p: p.on, f"Put the {box} cover back",
                f"Drag the {box} cover from the tray back onto the {box_name}", source=("tray", bcover))
            add("driver", bcover.screws, lambda s: s.inserted, f"Do up {n} {box} screws",
                "Hold the screwdriver (2) on each hole")
        add("drag", [self.plug], lambda p: p.on, "Plug it back in", "Drag the plug back into the power strip",
            source=("plug", self.plug))
        add("button", ["TEST"], lambda t: self.closed_ok, "Test it", "Press TEST again: it should work now")
        add("button", ["FINISH"], lambda t: self.finished, "Finish", "Press FINISH to see how you did")
        return steps

    def hand_target(self, game, pos):
        """What the hand is over, top first: you can only reach what nothing else is covering."""
        fan = self
        found = []
        if fan.grille.on:
            found += fan.clips + [fan.grille]
        else:
            if fan.spinner.on:
                found.append(fan.spinner)
            if fan.blade.on:
                found.append(fan.blade)
            else:
                found.append(fan.shaft)
                if fan.motor_cover.on:
                    found.append(fan.motor_cover)
                elif fan.tape.on:
                    found.append(fan.tape)
                elif fan.fuse.present:
                    found.append(fan.fuse)
        if fan.base_cover.on:
            found.append(fan.base_cover)
        else:
            if fan.clamp.on:
                found.append(fan.clamp)
            found += fan.cap.connectors
            if fan.cap.present:
                found.append(fan.cap)
        hits = [thing for thing in found if thing.hit(pos)]
        step = game.step()
        wanted = [thing for thing in hits if step and thing in step.left()]  # guided: what's glowing comes first
        return (wanted or hits or [None])[0]

    def use_hand(self, game, pos):
        fan = self
        if fan.plug.on and fan.plug.hit(pos):
            if game.allowed(fan.plug):
                fan.plug.on = False
                game.power_warned = False
                game.play("unplug")
            return
        target = self.hand_target(game, pos)
        turning = target in (fan.spinner, fan.shaft)
        if target is None or not game.can(target, "twist" if turning else "hand"):
            return
        if turning:
            game.twist = [target, None]
            game.turned = game.wrong_way = 0.0
            game.update_twist(pos)
        elif isinstance(target, Clip):
            target.latched = not target.latched
            game.play("snap" if target.latched else "clip")
            if not target.latched:
                burst(game.particles, target.x, target.y, self.model["body"], 6, speed=100, life=0.3, size=2)
        elif target is fan.grille:
            latched = next((c for c in fan.clips if c.latched), None)
            if latched:
                game.wiggle(latched, "The clips are still holding it: open them first.")
            else:
                game.take_off(target)
        elif target is fan.blade:
            if fan.spinner.on:
                game.wiggle(fan.spinner, "The spinner holds the blade on: unscrew it first.")
            else:
                game.take_off(target)
        elif target in (fan.motor_cover, fan.base_cover, fan.clamp):
            if any(s.inserted for s in target.screws):
                game.wiggle(target, f"The {target.name} is still screwed down.")
            else:
                game.take_off(target)
        elif target is fan.tape:
            game.take_off(target, "peel")
        elif target is fan.fuse:
            if any(lead.state != "cut" for lead in fan.fuse.leads):
                game.wiggle(target, "It's still joined in: cut both of its joints first.")
            else:
                game.take_out(target, "fuse", not fan.fuse.blown)
                fan.fuse.present = fan.fuse.blown = False
        elif target in fan.cap.connectors:
            self.flip_connector(game, target)
        elif target is fan.cap:
            if any(c.on for c in fan.cap.connectors):
                game.wiggle(target, "Its wires are still connected: pull the connectors off first.")
            else:
                game.take_out(target, "cap", not fan.cap.faulty)
                fan.cap.present = fan.cap.faulty = fan.cap.charged = False

    def flip_connector(self, game, connector):
        cap = self.cap
        if connector.on:
            if cap.charged:  # it bites
                cap.charged = False
                self.mistake("charge")
                game.shock(connector.x, connector.y)
                game.say("Zap! The capacitor still held a charge. Drain it with the screwdriver first.", RED)
            connector.on = False
            game.play("unplug")
        elif not cap.present:
            game.wiggle(connector, "There's nothing to connect it to: fit the new capacitor first.")
        else:
            connector.on = True
            game.play("plug")

    def use_driver(self, game, pos):
        fan = self
        screw = next((s for s in fan.screws_in_reach() if s.hit(pos)), None)
        if screw:
            if game.can(screw, "driver"):
                game.hold = [screw, 0.0]
            return
        cap = fan.cap
        if fan.open("base") and cap.present and cap.hit(pos) and game.can(cap, "driver"):
            if cap.charged:
                game.hold = [cap, 0.0]
            else:
                game.floats.append(FloatText("Already drained", cap.x, cap.y - 30, WHITE))

    def use_cutters(self, game, pos):
        fan = self
        cord = fan.cord
        if fan.open("fuse"):
            for lead in fan.fuse.leads:
                if lead.state != "cut" and lead.hit(pos):
                    if game.can(lead, "cutters"):
                        lead.state = "cut"
                        game.snip(lead.x, lead.y, COPPER)
                    return
        if fan.open("cord") and not cord.cut and cord.damage.hit(pos):
            if not game.can(cord.damage, "cutters"):
                return
            if any(s.inserted for s in cord.terminals):
                game.wiggle(cord.damage, "Undo the terminal screws first, so the wires come free.")
                return
            if not cord.damaged:
                fan.mistake("good_part")
            cord.cut, cord.damaged = True, False
            for end in cord.ends:
                end.state = "cut"
            game.snip(cord.damage.x, cord.damage.y, CORD)
            game.flyers.append(Flyer("scrap", cord.damage.x, cord.damage.y))
            return
        if fan.open("base"):
            for end in cord.ends:
                if end.hit(pos) and end.state == "cut":
                    if game.can(end, "cutters"):
                        if end.screw.inserted:
                            game.wiggle(end, "Undo its terminal screw first.")
                        else:
                            end.state = "stripped"
                            game.snip(end.x, end.y, end.color)
                    return

    def use_crimper(self, game, pos):
        fan = self
        if fan.open("fuse"):
            for lead in fan.fuse.leads:
                if lead.state == "loose" and lead.hit(pos):
                    if game.can(lead, "crimper"):
                        game.hold = [lead, 0.0]
                    return

    def use_brush(self, game, pos):
        fan = self
        b = fan.bearing
        target = b if fan.open("face") and b.gunk > 0 and b.hit(pos) else self.dust_at(game, pos)
        if target is None or not game.can(target, "brush"):
            return
        game.scrub_from = pos
        self.scrub(game, pos, pos)

    def use_meter(self, game, pos):
        fan = self
        found = []
        if fan.open("fuse"):
            found.append((fan.fuse, "Thermal fuse", fan.fuse.measure))
        if fan.open("motor"):
            found.append((fan.winding, "Winding", lambda: ("86 Ω", True)))
        if fan.open("base"):
            found += [(fan.cap, "Capacitor", fan.cap.measure), (fan.cord.probe, "Cord", fan.cord.measure),
                      (fan.switch, "Switch", lambda: ("0.0 Ω", True))]
        hit = next((f for f in found if f[0].hit(pos)), None)
        if hit is None or not game.can(hit[0], "meter"):
            return
        thing, name, measure = hit
        text, good = measure()
        thing.probed = True
        fan.readings.append((name, text, good))
        if thing is fan.fuse and fan.fuse.blown:
            fan.found.add("thermal")
        elif thing is fan.cap and fan.cap.faulty:
            fan.found.add("capacitor")
        elif thing is fan.cord.probe and fan.cord.damaged:
            fan.found.add("cord")
        game.floats.append(FloatText(text, thing.x, thing.y - 30, GREEN if good else RED))
        game.play("beep" if good else "buzz")

    def drop_supply(self, game, key, pos):
        fan = self
        if key in ("oil", "wd40"):
            b = fan.bearing
            if not (fan.open("face") and b.hit(pos)) or not game.can(b, "drag"):
                return
            if key == "wd40":
                if "wd40" not in fan.mistakes:
                    fan.mistake("wd40")
                game.say("WD-40 is a cleaner, not oil: it dries out and the squeak comes back. Use machine oil.")
                burst(game.particles, b.x, b.y, (200, 220, 240), 16, speed=120, life=0.5, size=3)
                game.play("spray")
                return
            b.drops += 1
            for _ in range(5):
                game.particles.append(Particle(b.x + random.uniform(-4, 4), b.y - 6, random.uniform(-20, 20),
                                               random.uniform(20, 80), OIL, 0.5, 3, gravity=300))
            game.floats.append(FloatText(f"{b.drops} drop{'s' if b.drops > 1 else ''}", b.x, b.y - 28, OIL))
            game.play("drip")
            if b.drops == TOO_MUCH_OIL + 1:
                game.say("That's too much: extra oil drips out and collects dust.")
        elif key.startswith("cap"):
            cap = fan.cap
            if cap.present or not (fan.open("base") and cap.rect.inflate(30, 30).collidepoint(pos)) or not game.can(cap, "drag"):
                return
            cap.present, cap.faulty, cap.charged = True, False, False
            cap.uf = fan.cap_values[key]
            if cap.uf != cap.needed:
                fan.mistake("wrong_cap")
            game.floats.append(FloatText(f"{cap.uf:g} µF", cap.x, cap.y - 30, WHITE))
            game.play("place")
        else:
            fuse = fan.fuse
            if fuse.present or not (fan.open("fuse") and fuse.rect.inflate(36, 30).collidepoint(pos)) or not game.can(fuse, "drag"):
                return
            fuse.present, fuse.blown = True, False
            for lead in fuse.leads:
                lead.state = "loose"
            game.play("place")

    def turn_spinner(self, game, delta):
        s = self.spinner
        if not s.on:
            return
        before = s.turn
        s.turn = max(0.0, s.turn + delta)  # reverse-threaded: clockwise undoes it
        s.angle += s.turn - before
        game.turned += abs(s.turn - before)
        if game.turned > 0.6:
            game.turned = 0.0
            game.play("tick")
        if before == 0 and delta < 0:  # already tight, and you're still going anticlockwise
            game.wrong_way -= delta
            if game.wrong_way > 1.5:
                game.wrong_way = -100  # once per grip
                game.wiggle(s, "That's tight: it won't go any further." if s.refitted else
                            "It won't go any tighter. Fan spinners are reverse-threaded: CLOCKWISE undoes them.")
        if before > 0 and s.turn == 0:
            game.floats.append(FloatText("Tight!", s.x, s.y - 30, WHITE))
            game.play("tight")
        if s.turn >= SPINNER_MAX:
            s.on = False
            game.twist = None
            game.play("unscrew")
            if s.refitted:
                game.say("That way undoes it: turn it ANTI-CLOCKWISE to do it up.")

    def turn_shaft(self, game, delta):
        fan = self
        b = fan.bearing
        stiff = b.stiff()
        fan.shaft.angle += delta * (DRY_DRAG if stiff else 1)
        game.turned += abs(delta)
        game.sound_timer -= abs(delta)
        if game.sound_timer <= 0:
            game.sound_timer = 1.2 if stiff else 0.8
            game.play("squeak" if stiff else "tick")
        if game.turned > 3 and not fan.felt_shaft:  # you've had a good feel of it
            fan.felt_shaft = True
            if stiff:
                fan.found.add("dry")
                game.floats.append(FloatText("Stiff!", fan.shaft.x, fan.shaft.y - 30, RED))
                game.say("Stiff and squeaky: this bearing has dried out.")
            else:
                game.floats.append(FloatText("Turns freely", fan.shaft.x, fan.shaft.y - 30, GREEN))
        if b.dry and not stiff:
            before = b.worked
            b.worked += abs(delta)
            if before < SHAFT_WORK <= b.worked:
                game.floats.append(FloatText("Smooth!", fan.shaft.x, fan.shaft.y - 30, GREEN))
                game.play("clean")

    def dust_at(self, game, pos):
        """The dust you'd brush at pos: on whatever's on top there."""
        fan = self
        d = math.dist(pos, HEAD)
        if fan.grille.on:
            return fan.grille_dust if d <= GRILLE_R else None
        if fan.blade.on:
            return fan.blade_dust if d <= BLADE_R else None
        if fan.motor_cover.on and d <= MOTOR_R:
            return fan.face_dust
        return None

    def scrub(self, game, a, b):
        """Brush from a to b: wipe the dust, and scrub the old gunk off the bearing on the way."""
        fan = self
        dist = math.dist(a, b)
        busy = False
        stamps = max(1, int(dist // (SCRUB_RADIUS / 2)))
        for i in range(stamps + 1):
            x, y = a[0] + (b[0] - a[0]) * i / stamps, a[1] + (b[1] - a[1]) * i / stamps
            dust = self.dust_at(game, (x, y))
            if dust and not dust.clean:
                fan.found.add("dusty")
                dust.surf.blit(game.stamp, (x - dust.pos[0] - SCRUB_RADIUS, y - dust.pos[1] - SCRUB_RADIUS),
                               special_flags=pygame.BLEND_RGBA_SUB)
                px, py = round(x - dust.pos[0]), round(y - dust.pos[1])
                if i == stamps and dist and dust.surf.get_rect().collidepoint(px, py) and dust.surf.get_at(
                        (px, py)).a > 40:
                    game.particles.append(Particle(x, y, random.uniform(-60, 60), random.uniform(-60, 10),
                                                   (176, 170, 158), 0.6, 5))
                    busy = True
        bearing = fan.bearing
        if bearing.gunk > 0 and fan.open("face") and bearing.hit(b) and dist:
            bearing.gunk = max(0.0, bearing.gunk - dist / GUNK_WORK)
            busy = True
            if random.random() < 0.4:
                game.particles.append(Particle(b[0], b[1], random.uniform(-80, 80), random.uniform(-90, 0), GUNK,
                                               0.5, 3, gravity=300))
            if bearing.gunk == 0:
                burst(game.particles, bearing.x, bearing.y, WHITE, 14, speed=160, life=0.5, size=3)
                game.floats.append(FloatText("Clean!", bearing.x, bearing.y - 30, WHITE))
                game.play("clean")
        if busy:
            game.sound_timer -= 0.03
            if game.sound_timer <= 0:
                game.sound_timer = 0.09
                game.play("scrub")

    def count_dust(self, game):
        """How much dust is left on each layer; one counts as clean once it's nearly gone."""
        for dust in self.dusts:
            if dust.clean:
                continue
            dust.left = dust.count() / dust.full
            if dust.left < DUST_DONE:  # blow the last specks away
                dust.surf.fill((0, 0, 0, 0))
                dust.left, dust.clean = 0.0, True
                for _ in range(20):
                    a, r = random.uniform(0, 2 * math.pi), dust.radius * math.sqrt(random.random())
                    x, y = ring_point(a, r)
                    burst(game.particles, x, y, WHITE, 1, speed=60, life=0.6, size=3)
                game.floats.append(FloatText("Spotless!", HEAD[0], HEAD[1] - dust.radius - 14, WHITE, 1.4))
                game.play("clean")

    def update_test(self, game, dt):
        symptom, t = game.test_symptom, game.state_time
        target = fan_speed(symptom, t)
        ease = 0.8 if symptom == "slow" else 3.0
        game.spin_speed += (target - game.spin_speed) * min(1.0, dt * ease)
        game.spin += game.spin_speed * dt
        if symptom == "weak" and random.random() < 0.5:  # dust blown off the blade
            x, y = ring_point(random.uniform(0, 2 * math.pi), random.uniform(60, GRILLE_R))
            game.particles.append(Particle(x, y, random.uniform(-80, 80), random.uniform(-80, 20), (176, 170, 158),
                                           0.8, 4))
        if symptom == "slow" and int(t * 2.4) != int((t - dt) * 2.4):
            game.floats.append(FloatText("squeak", HEAD[0] + random.uniform(-90, 90), HEAD[1] - GRILLE_R + 10,
                                         WHITE, 0.8))
        if t > TEST_TIME:
            game.end_test()

    def powered(self):
        return self.plug.on

    def danger(self, doing):
        return "UNPLUG IT FIRST! Never work on a fan while it's plugged in." if self.plug.on else None

    def moving_pieces(self):
        return self.tray_pieces + [self.plug]

    def drag_source_at(self, pos):
        """A piece waiting in the tray, or the loose plug."""
        if not self.plug.on and plug_rect(self.plug).inflate(8, 8).collidepoint(pos):
            return "plug", self.plug
        return super().drag_source_at(pos)

    def drop(self, game, source, pos):
        kind, thing = source
        if kind == "plug":
            if thing.rect.inflate(30, 30).collidepoint(pos) and game.allowed(thing, "drag"):
                thing.on = True
                game.play("plug")
            return
        super().drop(game, source, pos)

    def blocked(self, piece):
        if piece is self.grille and not self.blade.on:
            return self.shaft, "Put the blade back on first."
        if piece is self.spinner and not self.blade.on:
            return self.shaft, "The spinner holds the blade on: put the blade back first."
        if piece is self.blade and not self.motor_cover.on:
            return self.shaft, "Put the motor cover back first: it holds the bearing the shaft turns in."
        return None

    def refitted(self, game, piece):
        if piece is self.spinner:
            piece.turn = SPINNER_MAX - 0.6  # caught on the first bit of thread: now do it up
            piece.refitted = True
        game.play("peel" if piece is self.tape else "cover")

    def wrong_supply(self, key):
        if key == "wd40":
            return "Not WD-40: it's a cleaner, not oil. Take the machine oil."
        if key.startswith("cap"):
            return f"Not that one: the old capacitor's label says {self.cap.needed:g} µF."
        return super().wrong_supply(key)

    def hold_time(self, target):
        return DRAIN_TIME if target is self.cap else CRIMP_TIME

    def holding(self, game, target, mouse):
        if target is self.cap and random.random() < 0.3:
            burst(game.particles, mouse[0], mouse[1], (180, 220, 255), 1, speed=90, life=0.25, size=2)

    def held(self, game, target):
        if target is self.cap:
            target.charged = False
            burst(game.particles, target.x, target.rect.top, (255, 240, 150), 14, speed=200, life=0.3, size=2)
            game.floats.append(FloatText("Drained", target.x, target.y - 30, WHITE))
            game.play("spark")
        else:
            target.state = "crimped"
            burst(game.particles, target.x, target.y, METAL, 6, speed=100, life=0.3, size=2)
            game.floats.append(FloatText("Crimped", target.x, target.y - 26, WHITE))
            game.play("crimp")

    def turn(self, game, thing, delta):
        if thing is self.spinner:
            self.turn_spinner(game, delta)
        else:
            self.turn_shaft(game, delta)

    def twist_progress(self, thing):
        return thing.turn / SPINNER_MAX if thing is self.spinner else self.bearing.worked / SHAFT_WORK

    def on_test(self, game, symptom):
        if self.plug.on and not self.closed():
            self.mistake("open_test")

    def test_sounds(self, symptom):
        sounds = {None: "whoosh", "noblade": "whoosh", "unplugged": "click", "dead": "click", "cutout": "cutout",
                  "hum": "hum", "hot": "hum", "grind": "grind", "wobble": "rattle", "slow": "squeaky",
                  "weak": "rattle"}
        return [sounds[symptom]]

    def test_warning(self):
        if self.plug.on and not self.closed():
            return "Careful: never switch it on with covers off!"
        return None

    def draw(self, surf, game, fonts, mouse):
        draw_fan(surf, game, fonts, mouse)

    def draw_test(self, surf, game):
        draw_fan_test(surf, game)

    def supply_info(self, key):
        if key.startswith("cap"):
            return SUPPLY_INFO["cap"].format(f"{self.cap_values[key]:g}")
        return SUPPLY_INFO[key]

    def supply_label(self, key):
        return f"{self.cap_values[key]:g}µF" if key.startswith("cap") else SUPPLY_LABELS[key]

    def supply_icon(self, key):
        return "cap" if key.startswith("cap") else key

    def draw_supply(self, surf, key, pos, fonts):
        if key.startswith("cap"):
            draw_cap(surf, *pos, self.cap_values[key], False, fonts["tiny"])
        else:
            SUPPLY_BODIES[key](surf, *pos)

    def notes(self):
        if not self.felt_shaft:
            return []
        dry = "dry" in self.found
        return [("Shaft: " + ("stiff and squeaky" if dry else "turns freely"), not dry)]


def plug_rect(plug):
    """Where the plug is drawn: in the power strip, or pulled out beside it."""
    return plug.rect.move(round(-18 * plug.t), round(40 * plug.t))


class Batteries(Piece):
    """The two batteries (AA, C or D), side by side in their compartment. They sit opposite ways round, as in most
    radios: the flat - end of each one goes against a spring."""

    def __init__(self, leaked):
        super().__init__("batteries", "batteries", BATTERY_BOX.inflate(-20, -12), "battery")
        self.leaked = leaked  # old ones that have leaked: they go in the bin
        self.present = True  # False once the leaky ones are in the bin and none are in yet
        self.reversed = [False, False]  # each one in the wrong way round?
        self.cells = [pygame.Rect(BATTERY_BOX.x + 16, BATTERY_BOX.y + 10 + i * 38, 140, 32) for i in range(2)]

    def shape(self):
        wrong = [cell for cell, back in zip(self.cells, self.reversed) if back]
        return ("rect", wrong[0]) if wrong and self.present and self.on else super().shape()


class Crust(Thing):
    """White crust that leaked out of old batteries onto a spring contact."""

    def __init__(self, x, y, leaked):
        super().__init__(x, y, 11, "contacts")
        self.crust = 1.0 if leaked else 0.0
        self.soaked = False  # vinegar dabbed on: it fizzes and softens


class Pot(Thing):
    """The volume control: a potentiometer, a carbon track inside with a wiper that slides along it. Dirt on the
    track makes it crackle as it turns. Its knurled wheel peeps over the top edge of the board."""

    def __init__(self, dirty):
        super().__init__(390, 236, 22, "inside")
        self.dirty = dirty
        self.sprayed = False  # contact cleaner in it
        self.worked = 0.0  # how far it's been turned since
        self.angle = POT_TURN / 2  # where the knob is, from 0 to POT_TURN

    def hit(self, pos):
        return pos[1] <= BOARD.top + 4 and math.dist(pos, (self.x, self.y)) <= self.r + 5  # the part you can see

    def click_point(self):
        return self.x, self.y - 10

    def crackles(self):
        return self.dirty and not (self.sprayed and self.worked >= POT_WORK)


class Antenna(Thing):
    """The telescopic antenna for FM. It swivels on top of the case, held by a screw from inside."""

    def __init__(self, broken):
        super().__init__(*ANTENNA_BASE, 9, "out")
        self.broken = broken  # broken inside: it looks fine, but the multimeter says OPEN
        self.present = True
        self.screw = Screw(110, 222)

    def hit(self, pos):
        if not self.present:
            return math.dist(pos, ANTENNA_BASE) <= 30
        return dist_to_segment(pos, ANTENNA_BASE, ANTENNA_TIP) <= 10

    def shape(self):
        return ("line", ANTENNA_BASE, ANTENNA_TIP) if self.present else ("circle", ANTENNA_BASE, 22)

    def click_point(self):
        return lerp(ANTENNA_BASE, ANTENNA_TIP, 0.3) if self.present else ANTENNA_BASE

    def measure(self):
        if not self.present:
            return "EMPTY", False
        return ("OPEN", False) if self.broken else ("0.3 Ω", True)


class Speaker(Thing):
    """The speaker, seen from behind: its magnet in the middle and two solder tabs on its frame, one wire to each.
    Wires often break off right at the tab."""

    def __init__(self, broken_wire, ohms=8, watts=0.5):
        super().__init__(*SPEAKER, 46, "inside")  # the multimeter goes on its magnet (on both its tabs, really)
        self.ohms, self.watts = ohms, watts  # what its label says
        self.tabs = [Thing(277, 326, 9, "inside"), Thing(277, 398, 9, "inside")]
        self.wire = "loose" if broken_wire else "soldered"  # the red wire: soldered on, loose, or hooked on
        self.wire_end = Thing(300, 288, 10, "inside")  # where its broken end hangs

    def measure(self):
        return f"{self.ohms * 0.92:.1f} Ω", True  # its coil: a good 8 Ω speaker reads a little under 8


class Joint(Thing):
    """A solder joint: where a part's leg comes through the board and is soldered to the copper."""

    def __init__(self, x, y):
        super().__init__(x, y, 5, "inside")
        self.cracked = False
        self.looked = False  # looked at with the magnifier


# Solder joints on the board: the volume control's legs and the headphone socket's come first, because parts that
# get pushed and pulled are the ones whose joints crack. Then the tuning capacitor, the chip and the rest.
CRACKABLE = [(378, 252), (390, 252), (402, 252), (612, 302), (612, 316), (612, 330)]
PADS = {"ANT": (334, 252), "SP+": (334, 300), "SP-": (334, 322), "ROD": (334, 404), "BAT+": (470, 404),
        "BAT-": (494, 404)}
OTHER_JOINTS = ([(506, 252), (518, 252), (530, 252), (542, 252)]
                + [(440 + i * 11, y) for y in (318, 348) for i in range(8)]
                + [(352, 372), (380, 372), (420, 390), (448, 390), (546, 298), (546, 326), (574, 372), (602, 372),
                   (566, 272), (592, 272)] + list(PADS.values()))
# Copper tracks between them, for looks
TRACES = [[(334, 252), (334, 270), (440, 270), (440, 318)], [(334, 300), (420, 300), (451, 318)],
          [(334, 322), (420, 322), (420, 348), (440, 348)], [(378, 252), (378, 290), (462, 290), (462, 318)],
          [(402, 252), (402, 280), (484, 280), (484, 318)], [(518, 252), (518, 318)], [(542, 252), (542, 262),
                                                                                        (566, 272)],
          [(612, 302), (590, 302), (590, 348), (517, 348)], [(612, 330), (596, 330), (596, 372), (602, 372)],
          [(470, 404), (470, 380), (495, 380), (495, 348)], [(494, 404), (520, 404), (546, 380), (546, 326)],
          [(334, 404), (352, 390), (352, 372)], [(380, 372), (420, 372), (420, 390)], [(448, 390), (473, 362),
                                                                                      (473, 348)],
          [(574, 372), (574, 340), (546, 326)], [(592, 272), (606, 286), (612, 302)]]


class Radio(Device):
    """A portable AM/FM radio that runs on two batteries, face down on the bench. Its back comes off to show the
    speaker, the circuit board (solder side up) and the battery compartment."""
    TOOLS = ["hand", "driver", "iron", "brush", "meter", "magnifier"]
    SUPPLIES = ["vinegar", "cleaner", "wd40", "batteries", "antenna"]
    SYMPTOMS = RADIO_SYMPTOMS
    FAULT_SYMPTOM = RADIO_FAULT_SYMPTOM
    FAULT_NAMES = {"leak": "leaked batteries", "pot": "a dirty volume control", "antenna": "a broken antenna",
                   "speaker": "a speaker wire broken off", "joint": "a cracked solder joint"}
    MISTAKES = RADIO_MISTAKES
    WORKS = "It plays! Clear sound on AM and FM."

    @staticmethod
    def mystery():
        """Usually one thing wrong; sometimes leaky batteries as well as something inside."""
        inside = ["pot", "antenna", "speaker", "joint"]
        if random.random() < 0.3:
            return ["leak", random.choice(inside)]
        return [random.choice(inside + ["leak"])]

    def __init__(self, faults, model=None):
        self.faults = set(faults)
        self.model = model = model or RADIO_MODELS[0]  # pocket, outdoor or retro
        bx, by = BATTERY_BOX.topleft
        leaked = "leak" in faults
        # The screws you can see, and one hiding under the batteries (always the last)
        screws = [Screw(x, y) for x, y in model["screws"]] + [Screw(BATTERY_BOX.centerx, by + 64)]
        self.back = Piece("back", "back", RADIO, "out", screws)
        self.door = Piece("door", "battery door", BATTERY_BOX.inflate(8, 8), "cover")
        self.batteries = Batteries(leaked)
        self.crusts = [Crust(bx + 10, by + 26, leaked), Crust(BATTERY_BOX.right - 10, by + 64, leaked)]
        self.pot = Pot("pot" in faults)
        self.antenna = Antenna("antenna" in faults)
        self.speaker = Speaker("speaker" in faults, model["ohms"], model["watts"])
        self.joints = [Joint(x, y) for x, y in CRACKABLE + OTHER_JOINTS]
        self.cracked = None
        if "joint" in faults:
            self.cracked = random.choice(self.joints[:len(CRACKABLE)])
            self.cracked.cracked = True
        self.tray_pieces = [self.back, self.door, self.batteries]
        self.things = ([self.back, self.door, self.batteries, self.pot, self.antenna, self.antenna.screw, self.speaker,
                        self.speaker.wire_end] + self.speaker.tabs + self.crusts + self.joints + screws)
        for piece in self.tray_pieces:
            piece.model = model  # so its picture is in this model's colors
        self.start()

    def open(self, zone):
        """Can you get at things in this zone right now?"""
        door = not self.door.on or not self.back.on
        empty = not (self.batteries.present and self.batteries.on)
        return {"out": True, "cover": self.back.on, "battery": door, "contacts": door and empty,
                "inside": not self.back.on}[zone]

    def closed(self):
        return self.back.on and self.door.on

    def powered(self):
        return self.batteries.present and self.batteries.on

    def danger(self, doing):
        if doing in ("iron", "spray") and self.powered():
            return "Take the batteries out first! Never solder or spray inside it with the power on."
        return None

    def symptom(self, testing=False):
        """The worst thing wrong with the radio when it's switched on, or None if it plays."""
        b = self.batteries
        if not (b.present and b.on):
            return "nobattery"
        if any(b.reversed):
            return "backwards"
        if b.leaked or any(c.crust > 0 for c in self.crusts):
            return "dead"
        found = set()
        if self.speaker.wire != "soldered":
            found.add("nosound")
        if self.cracked and self.cracked.cracked:
            found.add("cutout")
        if self.pot.crackles():
            found.add("crackle")
        a = self.antenna
        if not a.present or a.broken or not a.screw.inserted:
            found.add("fmhiss")
        return next((s for s in self.SYMPTOMS if s in found), None)

    def screws_in_reach(self):
        if not self.back.on:
            return [self.antenna.screw]
        return self.back.screws[:-1] + ([self.back.screws[-1]] if self.open("contacts") else [])

    def loose_screws(self):
        return [s for s in self.back.screws + [self.antenna.screw] if not s.inserted]

    def issues(self):
        """Everything left undone when you finish."""
        found = []

        def add(count, one, many=""):
            if count:
                found.append(one if count == 1 else f"{count} {many}")

        add(sum(not s.inserted for s in self.back.screws), "A screw left out of the back",
            "screws left out of the back")
        add(not self.back.on, "Back left off: the board and wires are open to knocks")
        add(not self.door.on, "Battery door left off: the batteries can fall out")
        add(not self.antenna.screw.inserted, "Antenna screw left out: it'll wobble and lose contact")
        add(not self.closed_ok, "Not tested with everything back on")
        return found

    def plan(self):
        """The steps of a tidy repair, from switching it on to finishing."""
        steps = []
        faults = self.faults

        def add(tool, targets, goal, label, text, **more):
            steps.append(Step(tool, targets, goal, label, text, **more))

        door, batt, back, pot, ant, spk = self.door, self.batteries, self.back, self.pot, self.antenna, self.speaker
        leak = "leak" in faults
        add("button", ["TEST"], lambda t: self.tests >= 1, "Switch it on", "Press TEST to hear what it does",
            optional=True)
        add("hand", [door], lambda p: not p.on, "Open the battery door",
            "Click the battery door with the hand (1) to slide it off")
        add("hand", [batt], lambda p: not p.on, "Take out the batteries",
            "They've leaked! Click them to take them out: they go in the bin" if leak else
            "Click the batteries to take them out: never work inside with the power in")
        if leak:
            add("drag", self.crusts, lambda c: c.soaked, "Dab vinegar on the crust",
                "Drag the vinegar from the drawer onto each crusty contact: it fizzes and softens",
                source=("supply", "vinegar"))
            add("brush", self.crusts, lambda c: c.crust == 0, "Scrub the contacts clean",
                "Pick the brush (4), hold the button and rub each contact until it shines")
        if faults - {"leak"}:
            n = len(back.screws)
            add("driver", back.screws, lambda s: not s.inserted, f"Undo {n} back screws",
                "Pick the screwdriver (2) and hold it on each screw. One hides under the batteries!")
            add("hand", [back], lambda p: not p.on, "Lift off the back", "Click the back with the hand (1) to lift it off")
            if "pot" in faults:
                add("drag", [pot], lambda p: p.sprayed, "Spray the volume control",
                    "Drag the contact cleaner from the drawer onto the volume control's wheel. Not WD-40!",
                    source=("supply", "cleaner"))
                add("twist", [pot], lambda p: p.worked >= POT_WORK, "Work the cleaner in",
                    "Hold the wheel with the hand and circle the mouse: turn it end to end, back and forth",
                    badge="TURN IT")
            if "antenna" in faults:
                add("meter", [ant], lambda a: a.probed, "Test the antenna",
                    "Multimeter (5): click the antenna. A good one reads almost 0 Ω; OPEN means it's broken inside",
                    optional=True)
                add("driver", [ant.screw], lambda s: not s.inserted, "Undo the antenna screw",
                    "Hold the screwdriver (2) on the screw in the top corner that holds the antenna on")
                add("hand", [ant], lambda a: not a.present, "Pull off the broken antenna",
                    "Click the antenna with the hand (1) to pull it off")
                add("drag", [ant], lambda a: a.present, "Fit the new antenna",
                    "Drag the new antenna from the drawer onto its corner", source=("supply", "antenna"))
                add("driver", [ant.screw], lambda s: s.inserted, "Do up the antenna screw",
                    "Hold the screwdriver (2) on the antenna's screw")
            if "speaker" in faults:
                add("meter", [spk], lambda p: p.probed, "Measure the speaker",
                    f"Multimeter (5): click the speaker. About {spk.ohms} Ω means the speaker itself is fine",
                    optional=True)
                add("hand", [spk.wire_end], lambda w: spk.wire != "loose", "Hook the wire on",
                    "Click the loose red wire to hook it back through its tab on the speaker")
                add("iron", [spk.tabs[0]], lambda t: spk.wire == "soldered", "Solder it on",
                    "Pick the soldering iron (3) and hold it on the tab: it heats the joint and melts in solder")
            if "joint" in faults:
                add("magnifier", [self.cracked], lambda j: j.looked, "Look for a cracked joint",
                    "Pick the magnifier (6): look round the legs of the volume control and the headphone socket. "
                    "Click the cracked one", optional=True)
                add("iron", [self.cracked], lambda j: not j.cracked, "Reflow the cracked joint",
                    "Hold the soldering iron (3) on it to melt it together again with fresh solder")
            add("drag", [back], lambda p: p.on, "Put the back on", "Drag the back from the tray onto the radio",
                source=("tray", back))
            add("driver", back.screws, lambda s: s.inserted, f"Do up {n} back screws",
                "Hold the screwdriver (2) on each hole, the one under the batteries too")
        if leak:
            add("drag", [batt], lambda p: p.present and p.on, "Fit 2 new batteries",
                f"Drag the new {self.model['cell']} batteries from the drawer into the compartment",
                source=("supply", "batteries"))
            add("hand", [batt], lambda p: p.present and p.on and not any(p.reversed), "Turn the bottom one round",
                "Check the marks: each + must match the + by its slot. Click the wrong one to turn it round")
        else:
            add("drag", [batt], lambda p: p.on, "Put the batteries back",
                "Drag the batteries from the tray back into the compartment", source=("tray", batt))
        add("drag", [door], lambda p: p.on, "Close the battery door", "Drag the battery door from the tray back on",
            source=("tray", door))
        add("button", ["TEST"], lambda t: self.closed_ok, "Test it", "Press TEST again: it should play now")
        add("button", ["FINISH"], lambda t: self.finished, "Finish", "Press FINISH to see how you did")
        return steps

    # ---- what each tool does to the radio ----

    def joint_at(self, pos):
        hits = [j for j in self.joints if j.hit(pos)]
        return min(hits, key=lambda j: math.dist(pos, (j.x, j.y))) if hits else None

    def crust_at(self, pos):
        if not self.open("contacts"):
            return None
        return next((c for c in self.crusts if c.crust > 0 and c.hit(pos)), None)

    def hand_target(self, game, pos):
        """What the hand is over, top first: you can only reach what nothing else is covering."""
        b, spk = self.batteries, self.speaker
        found = []
        if self.back.on and self.door.on:
            found.append(self.door)
        if self.open("battery") and b.present and b.on:
            found.append(b)
        if self.back.on:
            found.append(self.back)
        else:
            if spk.wire == "loose":
                found.append(spk.wire_end)
            found.append(self.pot)
        if self.antenna.present:
            found.append(self.antenna)
        hits = [thing for thing in found if thing.hit(pos)]
        step = game.step()
        wanted = [thing for thing in hits if step and thing in step.left()]  # guided: what's glowing comes first
        return (wanted or hits or [None])[0]

    def use_hand(self, game, pos):
        target = self.hand_target(game, pos)
        if target is None or not game.can(target, "twist" if target is self.pot else "hand"):
            return
        b = self.batteries
        if target is self.pot:
            game.twist = [target, None]
            game.turned = game.wrong_way = 0.0
            game.update_twist(pos)
        elif target is self.door:
            game.take_off(target, "slide")
        elif target is self.back:
            if not any(s.inserted for s in target.screws):
                game.take_off(target)
            elif not any(s.inserted for s in target.screws[:-1]):
                game.wiggle(target, "Still stuck? Radios often hide a screw in the battery compartment: look under "
                                    "the batteries.")
            else:
                game.wiggle(target, "The back is still screwed on.")
        elif target is b:
            if any(b.reversed):  # put the wrong one right
                i = b.reversed.index(True)
                b.reversed[i] = False
                game.floats.append(FloatText("Turned round", b.cells[i].centerx, b.cells[i].y - 8, WHITE))
                game.play("place")
                return
            game.power_warned = False
            if b.leaked:  # straight in the bin
                b.present = b.on = False
                b.t = 1.0
                self.found.add("leak")
                burst(game.particles, b.rect.centerx, b.rect.centery, CRUST, 14, speed=130, life=0.5, size=3)
                game.flyers.append(Flyer("old_batteries", b.rect.centerx, b.rect.centery))
                game.play("toss")
            else:
                game.take_off(b, "pick")
        elif target is self.speaker.wire_end:
            self.speaker.wire = "hooked"
            self.found.add("speaker")
            tab = self.speaker.tabs[0]
            game.floats.append(FloatText("Hooked on", tab.x, tab.y - 24, WHITE))
            game.play("clip")
        elif target is self.antenna:
            a = self.antenna
            if a.screw.inserted:
                game.wiggle(a, "A screw inside the top corner holds it: take the back off and undo that first.")
            else:
                game.take_out(a, "antenna", not a.broken)
                a.present = a.broken = False

    def use_driver(self, game, pos):
        screw = next((s for s in self.screws_in_reach() if s.hit(pos)), None)
        if screw and game.can(screw, "driver"):
            game.hold = [screw, 0.0]

    def use_iron(self, game, pos):
        if not self.open("inside"):
            return
        spk, tab = self.speaker, self.speaker.tabs[0]
        if tab.hit(pos):
            if spk.wire == "loose":
                game.wiggle(spk.wire_end, "Hook the wire through its tab first, so it can't move while the solder "
                                          "sets.")
            elif spk.wire == "soldered":
                game.floats.append(FloatText("Already soldered", tab.x, tab.y - 24, WHITE))
            elif game.can(tab, "iron"):
                game.hold = [tab, 0.0]
            return
        joint = self.joint_at(pos)
        if joint and game.can(joint, "iron"):
            game.hold = [joint, 0.0]

    def use_brush(self, game, pos):
        crust = self.crust_at(pos)
        if crust is None or not game.can(crust, "brush"):
            return
        game.scrub_from = pos
        self.scrub(game, pos, pos)

    def use_meter(self, game, pos):
        found = []
        b = self.batteries
        if self.open("battery") and b.present and b.on:
            found.append((b, "Batteries", self.battery_reading))
        if self.open("inside"):
            found += [(self.speaker, "Speaker", self.speaker.measure), (self.antenna, "Antenna", self.antenna.measure)]
        hit = next((f for f in found if f[0].hit(pos)), None)
        if hit is None or not game.can(hit[0], "meter"):
            return
        thing, name, measure = hit
        text, good = measure()
        thing.probed = True
        self.readings.append((name, text, good))
        if thing is self.antenna and self.antenna.broken:
            self.found.add("antenna")
        elif thing is b and b.leaked:
            self.found.add("leak")
        x, y = (thing.rect.centerx, thing.rect.y) if thing is b else thing.click_point() if thing is self.antenna \
            else (thing.x, thing.y - 30)
        game.floats.append(FloatText(text, x, y, GREEN if good else RED))
        game.play("beep" if good else "buzz")

    def battery_reading(self):
        """Two 1.5 V cells in a row: about 3 V when they're good. One backwards cancels the other out."""
        b = self.batteries
        if b.leaked:
            return "0.4 V", False
        if any(b.reversed):
            return "0.0 V", False
        return "3.1 V", True

    def use_magnifier(self, game, pos):
        if not self.open("inside"):
            return
        joint = self.joint_at(pos)
        if joint is None or not game.can(joint, "magnifier"):
            return
        joint.looked = True
        if joint.cracked:
            self.found.add("joint")
            game.floats.append(FloatText("Cracked!", joint.x, joint.y - 24, RED))
            game.say("There: a hairline ring all round the leg. That joint is what cuts out.")
            game.play("buzz")
        else:
            game.floats.append(FloatText("Looks fine", joint.x, joint.y - 24, GREEN))
            game.play("tick")

    def drop_supply(self, game, key, pos):
        if key == "vinegar":
            crust = next((c for c in self.crusts if self.open("contacts") and c.hit(pos)), None)
            if crust is None or not game.can(crust, "drag"):
                return
            if crust.crust == 0:
                game.floats.append(FloatText("Clean already", crust.x, crust.y - 24, WHITE))
                return
            crust.soaked = True
            for _ in range(14):  # it fizzes
                game.particles.append(Particle(crust.x + random.uniform(-8, 8), crust.y + random.uniform(-8, 8),
                                               random.uniform(-15, 15), random.uniform(-60, -20), WHITE, 0.6, 2))
            game.floats.append(FloatText("Fizz!", crust.x, crust.y - 24, WHITE))
            game.play("fizz")
        elif key in ("cleaner", "wd40"):
            pot = self.pot
            if not (self.open("inside") and pot.hit(pos)) or not game.can(pot, "drag", doing="spray"):
                return
            burst(game.particles, pot.x, pot.y - 10, (220, 230, 240), 16, speed=120, life=0.5, size=3)
            game.play("spray")
            if key == "wd40":
                if "wd40" not in self.mistakes:
                    self.mistake("wd40")
                game.say("WD-40 leaves an oily film in there that collects dust. Use contact cleaner.")
                return
            pot.sprayed = True
            if pot.dirty:
                self.found.add("pot")
            game.floats.append(FloatText("Sprayed", pot.x, pot.y - 34, WHITE))
        elif key == "batteries":
            b = self.batteries
            if not (self.open("battery") and BATTERY_BOX.inflate(20, 20).collidepoint(pos)):
                return
            if b.present:
                game.say("There are batteries in it already." if b.on else
                         "The old ones are fine: put them back from the tray.")
                return
            if not game.can(b, "drag"):
                return
            b.present = b.on = True
            b.t, b.leaked = 0.0, False
            b.reversed = [False, True]  # both dropped in the same way: one of them is wrong
            game.play("place")
        elif key == "antenna":
            a = self.antenna
            if math.dist(pos, ANTENNA_BASE) > 60:
                return
            if a.present:
                game.say("There's an antenna on it already: take the old one off first.")
                return
            if not game.can(a, "drag"):
                return
            a.present, a.broken = True, False
            game.play("place")

    def blocked(self, piece):
        if piece is self.door and not self.back.on:
            return self.door, "Put the back on first: the battery door slides into it."
        return None

    def refitted(self, game, piece):
        game.play({"door": "slide", "batteries": "place"}.get(piece.kind, "cover"))

    def wrong_supply(self, key):
        if key == "wd40":
            return "Not WD-40: it leaves an oily film. Take the contact cleaner."
        return super().wrong_supply(key)

    def supply_info(self, key):
        return SUPPLY_INFO[key].format(self.model["cell"]) if key == "batteries" else SUPPLY_INFO[key]

    def supply_label(self, key):
        return SUPPLY_LABELS[key].format(self.model["cell"]) if key == "batteries" else SUPPLY_LABELS[key]

    def hold_time(self, target):
        return IRON_TIME

    def holding(self, game, target, mouse):
        if random.random() < 0.35:  # a wisp of smoke from the flux in the solder
            game.particles.append(Particle(target.x + random.uniform(-3, 3), target.y - 4, random.uniform(-12, 12),
                                           random.uniform(-70, -40), (200, 200, 206), 0.9, 3))
        if game.sound_timer <= 0:
            game.sound_timer = 0.4
            game.play("sizzle")

    def held(self, game, target):
        if target is self.speaker.tabs[0]:
            self.speaker.wire = "soldered"
            text = "Soldered!"
        else:
            target.cracked = False
            text = "Reflowed"
        burst(game.particles, target.x, target.y, SOLDER, 8, speed=80, life=0.4, size=2)
        game.floats.append(FloatText(text, target.x, target.y - 24, WHITE))
        game.play("clean")

    def turn(self, game, thing, delta):
        """Turning the volume control: it stops at each end, so you go back and forth."""
        pot = self.pot
        before, worked = pot.angle, pot.worked
        pot.angle = max(0.0, min(POT_TURN, pot.angle + delta))
        moved = abs(pot.angle - before)
        if pot.sprayed:
            pot.worked += moved
        game.turned += moved
        if game.turned > 0.5:
            game.turned = 0.0
            game.play("tick")
        if not moved:  # against the end stop
            game.wrong_way += abs(delta)
            if game.wrong_way > 1.0:
                game.wrong_way = -100  # once per end
                game.floats.append(FloatText("End: now back the other way", pot.x, pot.y - 34, WHITE, 0.9))
        else:
            game.wrong_way = 0.0
        if pot.dirty and worked < POT_WORK <= pot.worked:
            game.floats.append(FloatText("Smooth!", pot.x, pot.y - 34, GREEN))
            game.play("clean")

    def twist_progress(self, thing):
        return self.pot.worked / POT_WORK

    def scrub(self, game, a, b):
        crust = self.crust_at(b)
        dist = math.dist(a, b)
        if crust is None or not dist:
            return
        if not crust.soaked:
            if game.message_time <= 0:
                game.say("It's rock hard. Dab some vinegar on it first to soften it.")
            return
        crust.crust = max(0.0, crust.crust - dist / CRUST_WORK)
        if random.random() < 0.4:
            game.particles.append(Particle(b[0], b[1], random.uniform(-70, 70), random.uniform(-80, 0), CRUST, 0.5, 3,
                                           gravity=300))
        game.sound_timer -= 0.03
        if game.sound_timer <= 0:
            game.sound_timer = 0.09
            game.play("scrub")
        if crust.crust == 0:
            burst(game.particles, crust.x, crust.y, WHITE, 12, speed=140, life=0.5, size=3)
            game.floats.append(FloatText("Shiny!", crust.x, crust.y - 26, WHITE))
            game.play("clean")

    # ---- testing ----

    def on_test(self, game, symptom):
        if symptom == "backwards" and "backwards" not in self.mistakes:
            self.mistake("backwards")

    def test_sounds(self, symptom):
        return {None: ["music"], "crackle": ["music", "crackle"], "fmhiss": ["hiss"],
                "cutout": ["music_cut"]}.get(symptom, ["click"])

    def update_test(self, game, dt):
        t = game.state_time
        if game.test_symptom == "crackle" and int(t * 4) != int((t - dt) * 4) and random.random() < 0.7:
            game.floats.append(FloatText("crk!", self.pot.x + random.uniform(-30, 30), RADIO.top - 14, WHITE, 0.6))
            burst(game.particles, self.pot.x, RADIO.top + 2, (255, 240, 160), 5, speed=120, life=0.25, size=2)

    def draw(self, surf, game, fonts, mouse):
        draw_radio(surf, game, fonts)

    def draw_test(self, surf, game):
        draw_radio_test(surf, game)

    def draw_details(self, lens, to_lens, zoom):
        if not self.open("inside"):
            return
        w, h = lens.get_size()
        for joint in self.joints:
            x, y = to_lens((joint.x, joint.y))
            if not (-20 < x < w + 20 and -20 < y < h + 20):
                continue
            if joint.cracked:  # a dull, grainy joint with a hairline ring round the leg
                pygame.draw.circle(lens, (168, 170, 174), (x, y), round(4.6 * zoom))
                pygame.draw.circle(lens, (56, 56, 62), (x, y), round(2.4 * zoom), 2)
                rnd = random.Random(joint.x * 31 + joint.y)
                for _ in range(10):
                    a, r = rnd.uniform(0, 2 * math.pi), rnd.uniform(2.8, 4.4) * zoom
                    pygame.draw.circle(lens, (130, 132, 138), (x + math.cos(a) * r, y + math.sin(a) * r), 1)
            else:  # a good joint: smooth and shiny
                pygame.draw.circle(lens, WHITE, (x - 1.6 * zoom, y - 1.6 * zoom), max(1, round(0.7 * zoom)))

    def notes(self):
        found = []
        if "speaker" in self.found:
            found.append(("Speaker wire: broken off its tab", False))
        if self.cracked and self.cracked.looked:
            found.append(("A solder joint: cracked right round", False))
        return found


DEVICES = {"fan": Fan, "radio": Radio}  # each product's key, and the class for what goes on the bench


class Game:
    def __init__(self):
        self.muted = False
        self.sounds = {
            "tick": make_sound(1500, 18, 0.12),
            "unscrew": make_sound(700, 70, 0.25, end_freq=1400, wave="sine"),
            "tight": make_sound(320, 90, 0.25, end_freq=200),
            "cover": make_sound(500, 160, 0.2, end_freq=200, wave="noise"),
            "unplug": make_sound(1500, 40, 0.2, end_freq=700),
            "plug": make_sound(700, 40, 0.2, end_freq=1500),
            "clip": make_sound(900, 50, 0.22, end_freq=1700),
            "snap": make_sound(1700, 40, 0.22, end_freq=900),
            "peel": make_sound(1800, 220, 0.1, end_freq=600, wave="noise"),
            "clunk": make_sound(150, 120, 0.3, end_freq=90),
            "zap": make_sound(3000, 260, 0.3, end_freq=400, wave="noise"),
            "spark": make_sound(3200, 120, 0.18, end_freq=900, wave="noise"),
            "snip": make_sound(2400, 35, 0.2, end_freq=1800),
            "crimp": make_sound(420, 80, 0.25, end_freq=200),
            "beep": make_sound(1900, 90, 0.15),
            "buzz": make_sound(180, 220, 0.18),
            "scrub": make_sound(2600, 40, 0.05, end_freq=1600, wave="noise"),
            "clean": make_sound(900, 260, 0.2, end_freq=2200, wave="sine"),
            "pick": make_sound(500, 60, 0.18, end_freq=800, wave="sine"),
            "place": make_sound(900, 50, 0.2, end_freq=500),
            "nope": make_sound(220, 140, 0.18, end_freq=150),
            "toss": make_sound(400, 200, 0.15, end_freq=120, wave="noise"),
            "drip": make_sound(1400, 90, 0.18, end_freq=500, wave="sine"),
            "spray": make_sound(5000, 300, 0.08, end_freq=3000, wave="noise"),
            "squeak": make_sound(2000, 120, 0.07, end_freq=2500, wave="sine"),
            "fizz": make_sound(6000, 500, 0.06, end_freq=3000, wave="noise"),
            "sizzle": make_sound(5000, 350, 0.07, end_freq=2500, wave="noise"),
            "slide": make_sound(900, 120, 0.15, end_freq=500, wave="noise"),
            "step": make_tune([1320, 1760], 60, 0.1, "sine"),
            "hint": make_tune([880, 1320], 60, 0.1, "sine"),
            "cheer": make_tune([1047, 1319, 1568, 2093], 70, 0.15),
            "fail": make_tune([392, 330, 262], 160, 0.15),
            # What a power test sounds like
            "whoosh": make_sound(170, 3000, 0.12, end_freq=260, wave="noise"),
            "click": make_sound(1500, 25, 0.2),
            "hum": make_sound(110, 3000, 0.06),
            "rattle": make_tune([90, 0, 70, 110, 0, 80, 0, 100, 60, 0, 90, 0, 70, 110, 0, 80], 110, 0.18, "noise"),
            "grind": make_sound(60, 2600, 0.25, end_freq=50, wave="noise"),
            "squeaky": make_tune([1900, 0, 0, 0, 2100, 0, 0, 0, 1800, 0, 0, 0, 2000, 0, 0, 0], 120, 0.06, "sine"),
            "cutout": make_tune([180, 180, 0, 0, 200, 0, 180, 180, 180, 0, 0, 190, 190, 0], 140, 0.12, "noise"),
            "music": make_tune([523, 659, 784, 659, 698, 880, 784, 659, 587, 698, 659, 523, 587, 659], 210, 0.12,
                               "sine"),
            "music_cut": make_tune([523, 659, 784, 0, 0, 0, 698, 880, 0, 0, 659, 587, 0, 523], 210, 0.12, "sine"),
            "hiss": make_sound(4000, 3000, 0.05, wave="noise"),
            "crackle": make_tune([2600, 0, 0, 3400, 0, 0, 0, 2200, 0, 3000, 0, 0, 2800, 0, 0, 0, 3600, 0, 2400, 0, 0,
                                  3000, 0, 0], 120, 0.16, "noise"),
        }
        self.stamp = pygame.Surface((SCRUB_RADIUS * 2, SCRUB_RADIUS * 2), pygame.SRCALPHA)  # wipes dust away
        pygame.draw.circle(self.stamp, (0, 0, 0, SCRUB_STRENGTH), (SCRUB_RADIUS, SCRUB_RADIUS), SCRUB_RADIUS)
        self.state = "products"  # products, models, levels, bench, test, result
        self.state_time = 0.0
        self.clock = 0.0  # seconds since the game started, for pulsing glows
        self.shake = 0.0
        self.sound_timer = 0.0
        self.product = PRODUCTS[0]  # what you're learning to fix
        self.model = None  # which type of it, for a product that has types (a desk fan, a pocket radio...)
        self.level = 0  # which of its levels
        self.guided = True
        self.device = None  # what's on the bench: a Fan, a Radio...
        self.result = None
        self.message, self.message_color, self.message_time = "", GOLD, 0.0
        self.reset_bench()

    def start_level(self, level, guided):
        self.level, self.guided = level, guided
        device = DEVICES[self.product["key"]]
        self.device = device(self.level_info()["faults"] or device.mystery(), self.model)
        if guided:
            self.device.par *= 1.5  # no rush while you're learning
        self.reset_bench()
        self.set_state("bench")

    def level_info(self):
        """The level you're on: its title, faults, tip and so on."""
        return self.product["levels"][self.level]

    def reset_bench(self):
        self.tool = "hand"
        self.hold = None  # [target, progress] while you hold a tool on something
        self.twist = None  # [thing, last angle of the mouse round it] while you turn something with the hand
        self.turned = self.wrong_way = 0.0  # how far you've turned, and turned the wrong way, this time
        self.scrub_from = None  # last brush position while scrubbing
        self.dust_timer = 0.0
        self.drag = None  # what you're dragging: ("supply", key), ("tray", piece) or ("plug", plug)
        self.message_time = self.hint_time = 0.0
        self.hint_step = None
        self.power_warned = False  # already told off for working on it with the power on (until it's off)
        self.test_symptom = None
        self.spin = self.spin_speed = 0.0  # the fan blade's turn (degrees) and speed during a test
        self.particles, self.floats, self.flyers = [], [], []

    def play(self, name):
        sound = self.sounds.get(name)
        if sound and not self.muted:
            sound.play()

    def toggle_sound(self):
        self.muted = not self.muted
        if self.muted and pygame.mixer.get_init():
            pygame.mixer.stop()

    def set_state(self, state):
        if self.state == "test" and pygame.mixer.get_init():
            pygame.mixer.stop()  # cut the test sound if you leave the test early
        self.state, self.state_time = state, 0.0

    def say(self, text, color=GOLD):
        self.message, self.message_color, self.message_time = text, color, MESSAGE_TIME

    def step(self):
        """The guided repair's current step (None when you're on your own)."""
        return self.device.current() if self.guided else None

    def wiggle(self, thing, why=None):
        """It won't budge: something else is still holding it."""
        thing.wiggle = WIGGLE_TIME
        self.play("clunk")
        if why:
            self.say(why)

    def allowed(self, target, action=None):
        """Guided, only the glowing things respond, and only to the right tool."""
        if not self.guided:
            return True
        step = self.step()
        if step is None:
            return False
        action = action or self.tool
        if target in step.left() and step.tool == action:
            return True
        need, tools = TOOL_FOR.get(step.tool, step.tool), self.device.TOOLS
        if target in step.left() and need in tools and need != self.tool:
            self.say(f"Use the {TOOL_NAMES[need].lower()} ({tools.index(need) + 1}) for this.")
        else:
            self.say("Not that yet: follow the glowing outline.")
        return False

    def safe(self, doing=None):
        """Is it safe to do this now? The device knows what isn't: working on a fan while it's plugged in, say, or
        soldering a radio with its batteries in."""
        warning = self.device.danger(doing or self.tool)
        if warning is None:
            return True
        if not self.power_warned:  # it counts once, until you've made it safe
            self.power_warned = True
            self.device.mistake("power")
        self.say(warning, RED)
        self.shake = 5
        self.play("nope")
        return False

    def can(self, target, action=None, doing=None):
        """May you work on this right now? Checks the guide, then safety, and notes that you've started."""
        if not self.allowed(target, action) or not self.safe(doing or action):
            return False
        self.device.touch()
        return True

    # ---- input ----

    def press(self, pos):
        if self.state == "products":
            self.press_products(pos)
        elif self.state == "models":
            self.press_models(pos)
        elif self.state == "levels":
            self.press_levels(pos)
        elif self.state == "test":
            self.end_test()  # skip the rest of the test
        elif self.state == "result":
            if self.state_time > RESULT_DELAY:
                if RETRY_BUTTON.collidepoint(pos):
                    self.start_level(self.level, self.guided)
                elif LEVELS_BUTTON.collidepoint(pos):
                    self.set_state("levels")
        else:
            self.press_bench(pos)

    def press_products(self, pos):
        for i, product in enumerate(PRODUCTS):
            if product_rect(i).collidepoint(pos):
                self.product, self.model = product, None
                self.set_state("models" if product.get("models") else "levels")

    def press_models(self, pos):
        if BACK_BUTTON.collidepoint(pos):
            self.set_state("products")
            return
        models = self.product["models"]
        for i, model in enumerate(models):
            if model_rect(i, len(models)).collidepoint(pos):
                self.model = model
                self.set_state("levels")

    def press_levels(self, pos):
        if BACK_BUTTON.collidepoint(pos):
            self.set_state("models" if self.model else "products")
            return
        for i, level in enumerate(self.product["levels"]):
            guided, solo = card_buttons(i, level)
            if guided and guided.collidepoint(pos):
                self.start_level(i, True)
            elif solo.collidepoint(pos):
                self.start_level(i, False)

    def press_bench(self, pos):
        dev = self.device
        for tool, rect in zip(dev.TOOLS, TOOL_RECTS):
            if rect.collidepoint(pos):
                self.tool = tool
                return
        for key, rect in zip(dev.SUPPLIES, SUPPLY_RECTS):
            if rect.collidepoint(pos):
                self.start_drag(("supply", key))
                return
        if TEST_BUTTON.collidepoint(pos):
            self.test()
        elif HINT_BUTTON.collidepoint(pos):
            self.hint()
        elif FINISH_BUTTON.collidepoint(pos):
            self.finish()
        elif BENCH.collidepoint(pos):
            source = dev.drag_source_at(pos)
            if source:
                self.start_drag(source)
            else:
                getattr(dev, "use_" + self.tool)(self, pos)

    def key(self, key):
        """1-6 pick a tool, T tests, H gives a hint, R tries again after a repair; Enter goes on."""
        go_on = key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
        if self.state == "bench":
            tools = self.device.TOOLS
            if pygame.K_1 <= key < pygame.K_1 + len(tools):
                self.tool = tools[key - pygame.K_1]
            elif key == pygame.K_t:
                self.test()
            elif key == pygame.K_h:
                self.hint()
        elif self.state == "test" and go_on:
            self.end_test()
        elif self.state == "result" and self.state_time > RESULT_DELAY:
            if key == pygame.K_r:
                self.start_level(self.level, self.guided)
            elif go_on:
                self.set_state("levels")

    def back(self):
        """Esc: one screen back (a repair to its levels, the levels to the types or the first screen); returns
        False on the first screen, to quit the game."""
        if self.state == "products":
            return False
        self.drag = self.hold = self.twist = None
        if self.state == "levels":
            self.set_state("models" if self.model else "products")
        elif self.state == "models":
            self.set_state("products")
        else:
            self.set_state("levels")
        return True

    def wheel(self, step):
        if self.state == "bench":
            tools = self.device.TOOLS
            self.tool = tools[(tools.index(self.tool) + step) % len(tools)]

    def start_drag(self, source):
        if self.guided:
            step = self.step()
            if not (step and step.tool == "drag" and step.source == source):
                kind, key = source
                if step and step.tool == "drag" and kind == "supply" and step.source[0] == "supply":
                    self.say(self.device.wrong_supply(key))
                else:
                    self.say("Not that yet: follow the glowing outline.")
                self.play("nope")
                return
        self.drag = source
        self.play("pick")

    def release(self, pos):
        self.stop_hold()
        self.twist = None
        self.scrub_from = None
        if self.drag:
            source, self.drag = self.drag, None
            self.device.drop(self, source, pos)

    # ---- what the tools do, the same on every device ----

    def take_off(self, piece, sound="cover"):
        piece.on = False
        self.play(sound)

    def take_out(self, part, kind, was_fine):
        if was_fine:
            self.device.mistake("good_part")  # that one was fine
        self.flyers.append(Flyer(kind, part.x, part.y))
        self.play("toss")

    def shock(self, x, y):
        self.shake = 9
        burst(self.particles, x, y, (255, 240, 120), 18, speed=320, life=0.35, size=3)
        burst(self.particles, x, y, (130, 200, 255), 10, speed=220, life=0.3, size=2)
        self.floats.append(FloatText("ZAP!", x, y - 30, (255, 240, 120)))
        self.play("zap")

    def snip(self, x, y, color):
        self.play("snip")
        burst(self.particles, x, y, color, 4, speed=150, life=0.4, size=2, gravity=600)

    def stop_hold(self):
        if self.hold and isinstance(self.hold[0], Screw):
            self.hold[0].turned = 0.0  # a screw you let go of part-way drops back
        self.hold = None

    def update_hold(self, dt, mouse):
        target, progress = self.hold
        if not target.hit(mouse):
            self.stop_hold()  # slipped off: hold it again to start over
            return
        self.sound_timer -= dt
        if isinstance(target, Screw):
            progress += dt / SCREW_TIME
            undoing = target.inserted
            target.angle += (-1 if undoing else 1) * 540 * dt / SCREW_TIME
            target.turned = progress if undoing else 1 - progress
            if self.sound_timer <= 0:
                self.sound_timer = 0.07
                self.play("tick")
        else:
            progress += dt / self.device.hold_time(target)
            self.device.holding(self, target, mouse)
        self.hold[1] = progress
        if progress < 1:
            return
        self.hold = None
        if isinstance(target, Screw):
            target.inserted = not target.inserted
            target.turned = 0.0
            self.play("tight" if target.inserted else "unscrew")
        else:
            self.device.held(self, target)

    def update_twist(self, mouse):
        thing, last = self.twist
        if math.dist(mouse, (thing.x, thing.y)) < 8:
            return  # too close to the middle to tell which way you're going
        angle = math.atan2(mouse[1] - thing.y, mouse[0] - thing.x)
        self.twist[1] = angle
        if last is not None:
            delta = (angle - last + math.pi) % (2 * math.pi) - math.pi  # positive is clockwise on screen
            self.device.turn(self, thing, delta)

    # ---- testing, hints and finishing ----

    def test(self):
        dev = self.device
        step = self.step()
        if self.guided and not (step and step.targets == ["TEST"]):
            self.say("Not that yet: follow the glowing outline.")
            self.play("nope")
            return
        dev.tests += 1
        symptom = dev.symptom(testing=True)
        self.test_symptom = symptom
        dev.on_test(self, symptom)
        if symptom is None and dev.closed():
            dev.closed_ok = True
        dev.observations.append("It works!" if symptom is None else dev.SYMPTOMS[symptom][1])
        self.spin = self.spin_speed = 0.0
        self.set_state("test")
        for name in dev.test_sounds(symptom):
            self.play(name)

    def end_test(self):
        self.spin = self.spin_speed = 0.0
        self.set_state("bench")

    def hint(self):
        """On your own, a hint lights up the next step for a few seconds (and counts against you)."""
        dev = self.device
        if self.guided:
            return
        i = 0 if dev.tests == 0 and not dev.worked else dev.next_step()
        if i >= len(dev.steps):
            return
        dev.hints += 1
        self.hint_step, self.hint_time = i, HINT_TIME
        self.play("hint")

    def finish(self):
        dev = self.device
        step = self.step()
        if self.guided and not (step and step.targets == ["FINISH"]):
            self.say("Not that yet: follow the glowing outline.")
            self.play("nope")
            return
        dev.finished = True
        symptom = dev.symptom()
        works = symptom is None
        issues = dev.issues()
        safety = sum(n for k, n in dev.mistakes.items() if dev.MISTAKES[k][0] == "safety")
        wrong = sum(n for k, n in dev.mistakes.items() if dev.MISTAKES[k][0] == "wrong")
        hints, solo = dev.hints, not self.guided
        clean = not safety and not wrong and not issues
        stars = 1 + clean + (solo and not hints) if works else 0
        late = max(0.0, dev.time - dev.par)
        score = (100 - 15 * safety - 8 * wrong - 5 * len(issues) - (8 * hints if solo else 0)
                 - min(20, round(20 * late / dev.par)))
        required = [done for done, s in zip(dev.done, dev.steps) if not s.optional]
        if not works:  # still broken: credit only for how far you got
            score = min(score, 40) * sum(required) / len(required)
        score = max(0, min(100, round(score)))
        self.result = dict(guided=self.guided, fixed=works, time=round(dev.time, 1), par=dev.par, score=score,
                           stars=stars, symptom=symptom, issues=issues, safety=safety, wrong=wrong, hints=hints,
                           mistakes=dict(dev.mistakes), faults=sorted(dev.faults))
        self.set_state("result")
        self.play("cheer" if works else "fail")

    def update(self, dt, mouse):
        self.clock += dt
        self.state_time += dt
        self.shake = max(0.0, self.shake - SHAKE_DECAY * dt)
        self.message_time = max(0.0, self.message_time - dt)
        self.hint_time = max(0.0, self.hint_time - dt)
        self.particles = [p for p in self.particles if p.update(dt)]
        self.floats = [f for f in self.floats if f.update(dt)]
        self.flyers = [f for f in self.flyers if f.update(dt)]
        if self.state not in ("bench", "test"):
            return
        dev = self.device
        for piece in dev.moving_pieces():  # slide things off and back on
            target, step = (0.0 if piece.on else 1.0), dt / ANIM_TIME
            piece.t = min(target, piece.t + step) if piece.t < target else max(target, piece.t - step)
        for thing in dev.things:
            if thing.wiggle:
                thing.wiggle = max(0.0, thing.wiggle - dt)
        dev.time += dt
        if self.state == "test":
            dev.update_test(self, dt)
            if self.state_time > TEST_TIME:
                self.end_test()
            return
        if self.hold:
            self.update_hold(dt, mouse)
        if self.twist:
            self.update_twist(mouse)
        if self.scrub_from:
            if mouse != self.scrub_from:
                dev.scrub(self, self.scrub_from, mouse)
                self.scrub_from = mouse
            self.dust_timer -= dt
            if self.dust_timer <= 0:
                self.dust_timer = 0.12
                dev.count_dust(self)
        dev.track()
        if self.hint_step is not None and dev.done[self.hint_step]:
            self.hint_time = 0.0  # you've done what the hint showed
        step = self.step()
        if step and step.complete():  # the guided repair moves on by itself
            dev.step += 1
            self.message_time = 0
            self.play("step")

    def hint_line(self, mouse):
        """The line under the bench: a message, the step to do, or what the thing under the mouse is."""
        if self.message_time > 0:
            return self.message, self.message_color
        dev = self.device
        step = self.step() or (dev.steps[self.hint_step] if self.hint_time > 0 else None)
        if step:
            text = step.text if step.text.endswith(("!", ".", "?")) else step.text + "."
            if self.guided:
                return f"Step {dev.step + 1} of {len(dev.steps)}: {text}", TEXT
            return f"Hint: {text}", GOLD
        if self.guided:
            return "", TEXT
        for tool, rect in zip(dev.TOOLS, TOOL_RECTS):
            if rect.collidepoint(mouse):
                return TOOL_INFO[tool], DIM
        for key, rect in zip(dev.SUPPLIES, SUPPLY_RECTS):
            if rect.collidepoint(mouse):
                return dev.supply_info(key), DIM
        return f"{TOOL_NAMES[self.tool]}  ·  1-6 or wheel: change tool  ·  H: hint  ·  Esc: back to the levels", DIM

def fan_speed(symptom, t):
    """How fast the blade should be turning, in degrees a second, t seconds into a power test."""
    if symptom in (None, "noblade"):
        return 1500
    if symptom == "cutout":
        return 1400 if t % 1.1 < 0.55 else 0
    return {"hot": 650, "wobble": 1100, "slow": 220, "weak": 600, "grind": 140}.get(symptom, 0)


def card_buttons(i, level):
    """The GUIDED and ON MY OWN buttons on level i's card (a mystery has no guided one)."""
    rect = CARD_RECTS[i]
    solo = pygame.Rect(rect.right - 132, rect.bottom - 40, 118, 30)
    guided = pygame.Rect(solo.x - 126, solo.y, 118, 30) if level["faults"] else None
    return guided, solo


# ---- drawing ----

def draw_text(surf, font, text, pos, color=TEXT, anchor="center"):
    img = font.render(text, True, color)
    rect = img.get_rect(**{anchor: pos})
    surf.blit(img, rect)
    return rect


def draw_star(surf, x, y, r, filled):
    points = [(x + math.cos(-math.pi / 2 + i * math.pi / 5) * (r if i % 2 == 0 else r * 0.45),
               y + math.sin(-math.pi / 2 + i * math.pi / 5) * (r if i % 2 == 0 else r * 0.45)) for i in range(10)]
    pygame.draw.polygon(surf, GOLD if filled else (80, 84, 100), points)


def draw_button(surf, font, rect, text, color, mouse, live=True):
    fill = (shade(color, 1.2) if rect.collidepoint(mouse) else color) if live else CARD
    pygame.draw.rect(surf, fill, rect, border_radius=10)
    draw_text(surf, font, text, rect.center, TEXT if live else DIM)


def make_bench():
    """The wooden bench and the green cutting mat, drawn once."""
    surf = pygame.Surface(BENCH.size)
    surf.fill(WOOD)
    for y in range(30, BENCH.h, 64):
        pygame.draw.line(surf, WOOD_DARK, (0, y), (BENCH.w, y), 2)
    mat = surf.get_rect().inflate(-24, -24)
    pygame.draw.rect(surf, MAT, mat, border_radius=12)
    for x in range(mat.left + 30, mat.right, 30):
        pygame.draw.line(surf, MAT_LINE, (x, mat.top + 4), (x, mat.bottom - 5))
    for y in range(mat.top + 30, mat.bottom, 30):
        pygame.draw.line(surf, MAT_LINE, (mat.left + 4, y), (mat.right - 5, y))
    return surf


def draw_screw(surf, x, y, angle, lift=0.0):
    r = 10 + 3 * lift  # a screw being undone rises out of its hole
    pygame.draw.circle(surf, (50, 50, 56), (x + 2 + 3 * lift, y + 3 + 4 * lift), r)
    pygame.draw.circle(surf, SCREW, (x, y), r)
    pygame.draw.circle(surf, METAL_DARK, (x, y), r, 2)
    for a in (angle, angle + 90):  # the cross slot
        dx, dy = math.cos(math.radians(a)) * (r - 3), math.sin(math.radians(a)) * (r - 3)
        pygame.draw.line(surf, METAL_DARK, (x - dx, y - dy), (x + dx, y + dy), 3)
    pygame.draw.circle(surf, WHITE, (x - r * 0.4, y - r * 0.45), 2)


def draw_screws(surf, screws, turning, dx=0, post=None):
    """Screws in their holes, or the empty holes once they're out."""
    for screw in screws:
        if screw.inserted or screw is turning:
            draw_screw(surf, screw.x + dx, screw.y, screw.angle, screw.turned)
        else:
            if post:
                pygame.draw.circle(surf, post, (screw.x + dx, screw.y), 10)
            pygame.draw.circle(surf, HOLE, (screw.x + dx, screw.y), 5)


def draw_blade(surf, cx, cy, angle, model=None):
    model = model or FAN_MODELS[0]
    color, count = model["blade"], model["blades"]
    for points in blade_points(cx, cy, angle, count, model["width"]):
        pygame.draw.polygon(surf, color, points)
        pygame.draw.polygon(surf, shade(color, 0.72), points, 2)
    for k in range(count):  # a shine along each blade
        a = angle + k * 2 * math.pi / count + 0.08
        pygame.draw.line(surf, shade(color, 1.18), (cx + math.cos(a) * 40, cy + math.sin(a) * 40),
                         (cx + math.cos(a + 0.12) * 104, cy + math.sin(a + 0.12) * 104), 3)
    pygame.draw.circle(surf, shade(model["body"], 0.62), (cx, cy), 29)
    pygame.draw.circle(surf, shade(model["body"], 0.86), (cx, cy), 27)


def draw_spinner(surf, x, y, angle, model=None):
    body = (model or FAN_MODELS[0])["body"]
    pygame.draw.circle(surf, shade(body, 0.5), (x + 2, y + 3), 17)
    pygame.draw.circle(surf, shade(body, 0.9), (x, y), 16)
    for k in range(8):  # the grip
        a = angle + k * math.pi / 4
        pygame.draw.circle(surf, shade(body, 0.62), (x + math.cos(a) * 13, y + math.sin(a) * 13), 3)
    pygame.draw.circle(surf, body, (x, y), 9)
    pygame.draw.circle(surf, WHITE, (x - 3, y - 4), 3)


def draw_grille(surf, x, y, model=None):
    """The front grille: rings of wire held by spokes, straight or curving round in a spiral."""
    model = model or FAN_MODELS[0]
    wire, spiral = model["grille"], model["spiral"]
    for color, dx, dy in ((shade(wire, 0.42), 2, 3), (wire, 0, 0)):  # its shadow, then the wire itself
        cx, cy = x + dx, y + dy
        for r in (42, 70, 98, 124):
            pygame.draw.circle(surf, color, (cx, cy), r, 2)
        for k in range(28):
            a = k * 2 * math.pi / 28
            points = [(cx + math.cos(a + spiral * t) * (32 + 112 * t), cy + math.sin(a + spiral * t) * (32 + 112 * t))
                      for t in (i / 8 for i in range(9))]
            pygame.draw.lines(surf, color, False, points, 2)
        pygame.draw.circle(surf, color, (cx, cy), GRILLE_R - 2, 5)
    body = model["body"]
    pygame.draw.circle(surf, shade(body, 0.7), (x, y), 33)
    pygame.draw.circle(surf, body, (x, y), 31)
    for r in (8, 15, 22):  # the maker's badge: a little breeze
        pygame.draw.arc(surf, model["badge"], (x - r, y - r, 2 * r, 2 * r), 0.4, 2.4, 3)


def draw_clip(surf, clip, model=None):
    body = (model or FAN_MODELS[0])["body"]
    dx = jiggle(clip.wiggle)
    if clip.latched:  # flat along the rim
        x, y = ring_point(clip.angle, GRILLE_R)
        pygame.draw.polygon(surf, shade(body, 0.55), rot_rect(x + dx, y, 22, 12, clip.angle + math.pi / 2))
        pygame.draw.polygon(surf, shade(body, 1.15) if sum(body) < 300 else body,
                            rot_rect(x + dx, y, 15, 5, clip.angle + math.pi / 2))
    else:  # flipped out, sticking away from the rim
        x, y = ring_point(clip.angle, GRILLE_R + 9)
        points = rot_rect(x + dx, y, 12, 22, clip.angle + math.pi / 2)
        pygame.draw.polygon(surf, shade(body, 1.05), points)
        pygame.draw.polygon(surf, shade(body, 0.55) if sum(body) > 300 else shade(body, 1.6), points, 2)


def draw_fan_stand(surf, model):
    """What holds the head up: a desk fan's neck, a stand fan's pole, or a wall fan's bracket arm."""
    hx, hy = HEAD
    body = model["body"]
    top, height = hy + 50, BASE.top - hy - 46
    if model["key"] == "stand":
        pygame.draw.rect(surf, (40, 40, 44), (hx - 7, BASE.bottom - 4, 18, 16))  # the pole, going on down
        pygame.draw.rect(surf, METAL, (hx - 9, BASE.bottom - 4, 18, 16))
        pygame.draw.rect(surf, METAL, (hx - 9, top, 18, height))
        pygame.draw.line(surf, WHITE, (hx - 4, top), (hx - 4, top + height), 2)
        pygame.draw.rect(surf, body, (hx - 20, hy + GRILLE_R - 4, 40, 32), border_radius=8)  # the tilt joint
        pygame.draw.circle(surf, shade(body, 1.6), (hx + 28, hy + GRILLE_R + 12), 9)
    elif model["key"] == "wall":
        pygame.draw.rect(surf, shade(body, 0.8), (hx - 22, top, 44, height), border_radius=6)  # the bracket arm
        pygame.draw.rect(surf, shade(body, 0.6), (hx - 22, top, 44, height), 2, border_radius=6)
        for y in (hy + GRILLE_R + 22, top + height - 18):
            pygame.draw.circle(surf, METAL_DARK, (hx, y), 6)  # its hinge bolts
            pygame.draw.circle(surf, METAL, (hx, y), 4)
    else:
        pygame.draw.rect(surf, shade(body, 0.82), (hx - 14, top, 28, height))
        pygame.draw.rect(surf, shade(body, 0.62), (hx - 14, top, 28, height), 2)
        pygame.draw.circle(surf, shade(body, 0.72), (hx + 18, hy + GRILLE_R + 26), 10)


def draw_pull_cords(surf, model):
    """A wall fan's two pull cords, out of the side of its control box and down onto the bench."""
    for i, end in enumerate(((60, 512), (88, 540))):
        start = (BASE.x + 2, BASE.y + 44 + i * 22)
        pygame.draw.lines(surf, (240, 240, 232), False, [start, (start[0] - 18, start[1] + 12), end], 2)
        pygame.draw.ellipse(surf, shade(model["badge"], 0.7), (end[0] - 6, end[1] + 1, 12, 18))
        pygame.draw.ellipse(surf, model["badge"], (end[0] - 5, end[1], 10, 16))


def draw_motor_cover(surf, x, y):
    pygame.draw.circle(surf, shade(MOTOR, 0.7), (x, y), MOTOR_R)
    pygame.draw.circle(surf, MOTOR, (x, y), MOTOR_R - 3)
    for k in range(3):  # vents between the screws
        a = math.radians(-30 + k * 120)
        for r in (28, 36):
            pygame.draw.arc(surf, shade(MOTOR, 0.6), (x - r, y - r, 2 * r, 2 * r), -a - 0.6, -a + 0.6, 3)
    pygame.draw.circle(surf, shade(MOTOR, 1.25), (x, y), 20)
    pygame.draw.circle(surf, shade(MOTOR, 0.8), (x, y), 20, 2)


def draw_motor_inside(surf, fan, turning):
    """The motor with its front cover off: the steel ring, the copper windings, the rotor and the thermal fuse."""
    hx, hy = HEAD
    pygame.draw.circle(surf, INSIDE, HEAD, MOTOR_R - 2)
    pygame.draw.circle(surf, LAMINATION, HEAD, 60, 12)
    for k in range(24):
        a = k * math.pi / 12
        pygame.draw.line(surf, shade(LAMINATION, 0.7), ring_point(a, 49), ring_point(a, 59), 2)
    for k in range(4):  # the windings
        x, y = ring_point(math.radians(45 + 90 * k), 34)
        coil = pygame.Rect(0, 0, 30, 24)
        coil.center = (x, y)
        pygame.draw.ellipse(surf, shade(COIL, 0.7), coil.inflate(2, 2))
        pygame.draw.ellipse(surf, COIL, coil)
        for i in range(-2, 3):
            pygame.draw.line(surf, shade(COIL, 0.8), (x + i * 5, y - 9), (x + i * 5 + 2, y + 9), 1)
    pygame.draw.circle(surf, (70, 72, 80), HEAD, 20)
    for k in range(6):
        a = k * math.pi / 3
        pygame.draw.line(surf, (96, 98, 108), ring_point(a, 8), ring_point(a + 0.4, 19), 2)
    for i, color in enumerate((WIRE_RED, WIRE_YELLOW, WIRE_BLACK)):  # the motor's wires, down to the base
        pygame.draw.line(surf, color, (hx - 6 + i * 6, hy + 44), (hx - 6 + i * 6, hy + MOTOR_R), 3)
    draw_screws(surf, fan.motor_cover.screws, turning, post=shade(MOTOR, 0.9))
    fuse = fan.fuse
    for lead, coil_end in zip(fuse.leads, ((hx - 40, hy - 14), (hx - 16, hy - 14))):
        pygame.draw.line(surf, COPPER, (lead.x, lead.y), coil_end, 2)  # the winding's wire up to the joint
        draw_joint(surf, lead, fuse.present)
    if fuse.present:
        dx = jiggle(fuse.wiggle)
        body = fuse.rect.inflate(-4, -4).move(dx, 0)
        pygame.draw.line(surf, METAL, (fuse.leads[0].x + 4 + dx, fuse.y), (fuse.leads[1].x - 4 + dx, fuse.y), 2)
        pygame.draw.rect(surf, FUSE_SLEEVE, body, border_radius=4)
        pygame.draw.rect(surf, shade(FUSE_SLEEVE, 0.7), body, 1, border_radius=4)
        pygame.draw.rect(surf, (60, 60, 70), (body.x + 6, body.y, 3, body.h))


def draw_joint(surf, lead, fuse_in):
    """One end of the thermal fuse: crimped in a metal sleeve, twisted loose, or cut."""
    x, y = lead.x + jiggle(lead.wiggle), lead.y
    if lead.state == "crimped":
        pygame.draw.rect(surf, shade(METAL, 0.7), (x - 7, y - 5, 14, 10), border_radius=3)
        pygame.draw.rect(surf, METAL, (x - 6, y - 4, 12, 8), border_radius=3)
        pygame.draw.line(surf, METAL_DARK, (x - 1, y - 4), (x - 1, y + 3), 2)
    elif lead.state == "loose" and fuse_in:
        pygame.draw.rect(surf, shade(METAL, 0.85), (x - 6, y - 4, 12, 8), 1, border_radius=3)
        pygame.draw.circle(surf, COPPER, (x, y), 3)
    else:  # cut: a stub of wire
        pygame.draw.circle(surf, COPPER, (x, y), 2)


def draw_bearing(surf, b):
    x, y = b.x, b.y
    pygame.draw.circle(surf, shade(BRONZE, 0.7), (x, y), 14)
    pygame.draw.circle(surf, BRONZE, (x, y), 12)
    pygame.draw.circle(surf, shade(BRONZE, 0.6), (x, y), 8)
    if b.gunk > 0:  # sticky brown crust
        for k in range(8):
            a = k * math.pi / 4 + 0.3
            pygame.draw.circle(surf, GUNK, (x + math.cos(a) * 10, y + math.sin(a) * 10), max(1, round(5 * b.gunk)))
    if b.drops:
        sheen = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.circle(sheen, (*OIL, min(200, 70 * b.drops)), (20, 20), 15, 4)
        surf.blit(sheen, (x - 20, y - 20))
    if b.drops > TOO_MUCH_OIL:  # it's dripping
        pygame.draw.line(surf, OIL, (x + 6, y + 12), (x + 7, y + 40), 3)
        pygame.draw.circle(surf, OIL, (x + 7, y + 42), 4)


def draw_shaft(surf, shaft):
    x, y, a = shaft.x, shaft.y, shaft.angle
    pygame.draw.circle(surf, shade(METAL, 0.6), (x, y), 7)
    pygame.draw.circle(surf, METAL, (x, y), 6)
    dx, dy = math.cos(a) * 5, math.sin(a) * 5  # the flat on the shaft that the blade grips
    pygame.draw.line(surf, METAL_DARK, (x - dx - dy * 0.6, y - dy + dx * 0.6), (x + dx - dy * 0.6, y + dy + dx * 0.6), 2)


def draw_tape(surf, rect):
    pygame.draw.rect(surf, TAPE, rect, border_radius=3)
    pygame.draw.rect(surf, shade(TAPE, 0.75), rect, 1, border_radius=3)
    for x in range(rect.left + 8, rect.right - 2, 9):
        pygame.draw.line(surf, shade(TAPE, 1.12), (x, rect.top + 3), (x - 5, rect.bottom - 4), 2)


def draw_base_cover(surf, rect, font, model=None):
    """The cover over the switch and the capacitor: a desk fan's base with its speed keys, a stand fan's control
    box with a speed knob and a timer, or a wall fan's with a speed window (its pull cords come out of the side)."""
    model = model or FAN_MODELS[0]
    body, dark = model["body"], sum(model["body"]) < 300
    pygame.draw.rect(surf, body, rect, border_radius=16)
    pygame.draw.rect(surf, shade(body, 1.5 if dark else 0.75), rect, 3, border_radius=16)
    for i in range(5):  # vents
        pygame.draw.rect(surf, shade(body, 1.35 if dark else 0.72), (rect.x + 36, rect.y + 34 + i * 9, 56, 5),
                         border_radius=2)
    ink = (200, 202, 210) if dark else (90, 90, 100)
    if model["controls"] == "keys":
        for i in range(4):  # the speed keys
            key = pygame.Rect(rect.x + 118 + i * 30, rect.y + 34, 26, 32)
            pygame.draw.rect(surf, shade(body, 0.6), key.move(0, 3), border_radius=5)
            pygame.draw.rect(surf, WHITE if i else (230, 120, 100), key, border_radius=5)
            if font:
                draw_text(surf, font, str(i), key.center, (90, 90, 100))
    elif model["controls"] == "knobs":
        pygame.draw.circle(surf, (120, 30, 26), (rect.x + 104, rect.y + 50), 5)  # the pilot light, off
        for i, (name, turn) in enumerate((("SPEED", -2.4), ("TIMER", -1.2))):
            cx, cy = rect.x + 140 + i * 72, rect.y + 48
            for k in range(4):  # the marks round the knob
                a = -2.4 + k * 0.9
                pygame.draw.circle(surf, ink, (cx + math.cos(a) * 29, cy + math.sin(a) * 29), 2)
            pygame.draw.circle(surf, (24, 24, 28), (cx + 2, cy + 3), 22)
            pygame.draw.circle(surf, (214, 216, 222), (cx, cy), 22)
            pygame.draw.circle(surf, (160, 162, 172), (cx, cy), 22, 2)
            pygame.draw.line(surf, (60, 62, 70), (cx, cy), (cx + math.cos(turn) * 18, cy + math.sin(turn) * 18), 4)
            if font:
                draw_text(surf, font, name, (cx, cy + 38), ink)
    else:  # pull cords: a window shows which speed it's on
        window = pygame.Rect(rect.x + 116, rect.y + 34, 116, 34)
        pygame.draw.rect(surf, (40, 44, 50), window, border_radius=6)
        for i in range(4):
            if font:
                draw_text(surf, font, str(i), (window.x + 18 + i * 27, window.centery),
                          (240, 120, 100) if i == 0 else (180, 186, 196))
        if font:
            draw_text(surf, font, "SPEED  SWING", (rect.x + 64, rect.bottom - 22), ink)
    sticker = pygame.Rect(rect.x + 252, rect.y + 32, 86, 44)
    pygame.draw.rect(surf, (248, 246, 238), sticker, border_radius=5)
    pygame.draw.rect(surf, (200, 196, 186), sticker, 1, border_radius=5)
    if font:
        draw_text(surf, font, model["label"], (sticker.centerx, sticker.y + 13), (70, 110, 170))
        draw_text(surf, font, f"230V~ {model['watts']}W", (sticker.centerx, sticker.y + 30), (120, 120, 128))


def draw_clamp(surf, rect):
    pygame.draw.rect(surf, (54, 56, 64), rect, border_radius=5)
    pygame.draw.rect(surf, (90, 92, 102), rect, 2, border_radius=5)
    for y in range(rect.top + 18, rect.bottom - 16, 5):
        pygame.draw.line(surf, (40, 42, 48), (rect.left + 4, y), (rect.right - 5, y), 1)


def draw_cap(surf, x, y, value, faulty, font=None):
    """A run capacitor: a black box with its value on the label."""
    body = pygame.Rect(0, 0, 76, 36)
    body.center = (x, y)
    pygame.draw.rect(surf, shade(CAP_BODY, 0.6), body.move(2, 3), border_radius=6)
    pygame.draw.rect(surf, CAP_BODY, body, border_radius=6)
    if faulty:  # it's swelled a little
        pygame.draw.ellipse(surf, shade(CAP_BODY, 1.6), (body.x + 10, body.y - 3, body.w - 20, 10))
    pygame.draw.rect(surf, (120, 124, 136), body, 1, border_radius=6)
    for tx in (x - 18, x + 18):  # its two terminals
        pygame.draw.rect(surf, BRASS, (tx - 3, body.top - 4, 6, 6))
    if font:
        draw_text(surf, font, f"{value:g}µF", (x, y - 6), WHITE)
        draw_text(surf, font, "450V~", (x, y + 8), (170, 172, 184))


def draw_base_inside(surf, fan, font, turning):
    """The base with its cover off: the speed switch, the capacitor and where the cord comes in."""
    bx, by = BASE.topleft
    body = fan.model["body"]
    pygame.draw.rect(surf, shade(body, 0.8), BASE, border_radius=16)
    pygame.draw.rect(surf, INSIDE, BASE.inflate(-12, -12), border_radius=12)
    for screw in fan.base_cover.screws:  # the posts the cover screws go into
        pygame.draw.circle(surf, shade(body, 0.6), (screw.x, screw.y), 10)
        pygame.draw.circle(surf, HOLE, (screw.x, screw.y), 4)
    grommet = (HEAD[0], by + 12)
    cap = fan.cap
    # The motor's wires come down the neck: two to the capacitor's connectors, the rest to the switch
    for i, color in enumerate((WIRE_RED, WIRE_YELLOW)):
        c = cap.connectors[i]
        pygame.draw.lines(surf, color, False, [(grommet[0] - 4 + 8 * i, grommet[1]), (c.x, grommet[1] + 6),
                                               (c.x, c.y - 4)], 3)
    for i, color in enumerate((WIRE_BLACK, WIRE_RED, WIRE_YELLOW)):
        x = fan.switch.rect.x + 20 + i * 22
        pygame.draw.lines(surf, color, False, [grommet, (grommet[0] - 20 - i * 4, by + 16 + i * 2),
                                               (x, by + 16 + i * 2), (x, fan.switch.rect.top)], 3)
    pygame.draw.circle(surf, (24, 24, 28), grommet, 9)
    pygame.draw.circle(surf, (70, 70, 80), grommet, 9, 2)
    # The cord's neutral wire runs up to the motor, its live one round to the switch
    t1, t2 = fan.cord.terminals
    pygame.draw.lines(surf, WIRE_BLUE, False, [(t1.x - 16, t1.y), (bx + 270, t1.y), (bx + 270, by + 9),
                                               (grommet[0] + 6, by + 9)], 3)
    pygame.draw.lines(surf, WIRE_BROWN, False, [(t2.x - 16, t2.y), (bx + 270, t2.y), (bx + 270, by + 92),
                                                (fan.switch.rect.right - 14, by + 92),
                                                (fan.switch.rect.right - 14, fan.switch.rect.bottom)], 3)
    # The speed switch: piano keys, a rotary switch with a timer, or pull-cord switches
    sw = fan.switch.rect
    controls = fan.model["controls"]
    pygame.draw.rect(surf, SWITCH, sw, border_radius=6)
    pygame.draw.rect(surf, shade(SWITCH, 1.4), sw, 2, border_radius=6)
    if controls == "keys":
        for i in range(4):
            pygame.draw.rect(surf, (226, 226, 220), (sw.x + 10 + i * 20, sw.y + 10, 14, 20), border_radius=3)
    elif controls == "knobs":
        pygame.draw.circle(surf, (36, 36, 40), (sw.x + 26, sw.y + 22), 17)  # the rotary speed switch
        pygame.draw.circle(surf, (90, 92, 100), (sw.x + 26, sw.y + 22), 17, 2)
        pygame.draw.circle(surf, (190, 192, 200), (sw.x + 68, sw.y + 22), 15)  # the clockwork timer
        pygame.draw.circle(surf, (130, 132, 140), (sw.x + 68, sw.y + 22), 15, 2)
        pygame.draw.line(surf, (90, 92, 100), (sw.x + 68, sw.y + 22), (sw.x + 68, sw.y + 11), 2)
    else:
        for x, r, y in ((sw.x + 28, 17, BASE.y + 44), (sw.x + 70, 12, BASE.y + 66)):  # the pull-cord switches
            pygame.draw.line(surf, (240, 240, 232), (x, sw.y + 22), (BASE.x + 2, y), 2)  # out to its cord
            pygame.draw.circle(surf, (226, 226, 220), (x, sw.y + 22), r)
            pygame.draw.circle(surf, (160, 160, 152), (x, sw.y + 22), r - 6, 2)
    for i in range(4):
        pygame.draw.circle(surf, BRASS, (sw.x + 17 + i * 20, sw.bottom - 10), 4)
    # The terminal block, the cord and its two wires
    block = pygame.Rect(bx + 282, by + 24, 34, 62)
    pygame.draw.rect(surf, TERMINAL, block, border_radius=4)
    pygame.draw.rect(surf, shade(TERMINAL, 0.7), block, 1, border_radius=4)
    cord = fan.cord
    sheath_end = bx + 332
    for end in cord.ends:
        start = (sheath_end, BASE.y + 55 + (-4 if end is cord.ends[0] else 4))
        tip = (end.x, end.y) if end.screw.inserted else (end.x + 8, end.y + (3 if end.y > start[1] else -3))
        pygame.draw.line(surf, shade(end.color, 0.7), start, tip, 7)
        pygame.draw.line(surf, end.color, start, tip, 5)
        if end.state == "cut":
            pygame.draw.circle(surf, shade(end.color, 0.5), tip, 3)  # cut flush: still plastic right to the end
        else:  # bare copper, under the screw if it's done up
            reach = end.screw.x if end.screw.inserted else tip[0] - 9
            pygame.draw.line(surf, COPPER, tip, (reach, tip[1]), 3)
    draw_screws(surf, cord.terminals, turning, post=shade(TERMINAL, 0.8))
    pygame.draw.line(surf, shade(CORD, 0.6), (sheath_end, by + 55), (BASE.right - 4, by + 55), 14)
    pygame.draw.line(surf, CORD, (sheath_end, by + 55), (BASE.right - 4, by + 55), 11)
    if cord.damaged:  # cracked sheath, with broken copper showing
        d = cord.damage
        pygame.draw.lines(surf, (60, 50, 40), False, [(d.x - 9, d.y - 5), (d.x - 3, d.y + 1), (d.x + 2, d.y - 4),
                                                      (d.x + 8, d.y + 4)], 2)
        for dx in (-4, 1, 5):
            pygame.draw.line(surf, COPPER, (d.x + dx, d.y + 1), (d.x + dx + 2, d.y - 5), 1)
    for screw in fan.clamp.screws:  # the clamp's posts
        pygame.draw.circle(surf, shade(body, 0.6), (screw.x, screw.y), 9)
        pygame.draw.circle(surf, HOLE, (screw.x, screw.y), 4)
    # The capacitor, with a lead from each terminal to a connector
    for c, tx in zip(cap.connectors, (cap.x - 18, cap.x + 18)):
        if cap.present:
            pygame.draw.line(surf, (226, 226, 220), (tx, cap.rect.top - 2), (c.x, c.y + 4), 3)
        lift = 0 if c.on else -8
        x = c.x + jiggle(c.wiggle)
        if cap.present and not c.on:
            pygame.draw.rect(surf, METAL, (x - 3, c.y - 2, 6, 7))  # the bare spade
        pygame.draw.rect(surf, (60, 110, 200), (x - 7, c.y - 6 + lift, 14, 11), border_radius=3)
        pygame.draw.rect(surf, (120, 160, 230), (x - 7, c.y - 6 + lift, 14, 11), 1, border_radius=3)
    if cap.present:
        draw_cap(surf, cap.x + jiggle(cap.wiggle), cap.y, cap.uf, cap.faulty, font)
    else:  # the empty bracket
        pygame.draw.rect(surf, (90, 92, 102), cap.rect, 2, border_radius=6)


def draw_strip(surf, lit):
    """The power strip on the bench."""
    pygame.draw.rect(surf, (40, 40, 44), STRIP.move(3, 4), border_radius=10)
    pygame.draw.rect(surf, (236, 236, 230), STRIP, border_radius=10)
    pygame.draw.rect(surf, (180, 180, 176), STRIP, 2, border_radius=10)
    for x in (OUTLET[0], OUTLET[0] + 58):
        pygame.draw.circle(surf, (210, 210, 204), (x, OUTLET[1]), 15)
        for dx in (-5, 5):
            pygame.draw.rect(surf, (40, 40, 44), (x + dx - 2, OUTLET[1] - 6, 4, 12), border_radius=1)
    rocker = pygame.Rect(STRIP.right - 22, STRIP.centery - 11, 13, 22)
    pygame.draw.rect(surf, (255, 96, 80) if lit else (130, 40, 36), rocker, border_radius=3)


def draw_cord_and_plug(surf, fan, dragging, mouse):
    plug = fan.plug
    rect = pygame.Rect(plug.rect)
    rect.center = mouse if dragging else plug_rect(plug).center
    rect.x += jiggle(plug.wiggle)
    start = (BASE.right - 4, BASE.y + 55)
    points = [start, (start[0] + 26, start[1]), (rect.x - 6, rect.centery)]
    pygame.draw.lines(surf, shade(CORD, 0.6), False, points, 12)
    pygame.draw.lines(surf, CORD, False, points, 8)
    pygame.draw.rect(surf, (40, 40, 44), rect.move(2, 3), border_radius=5)
    pygame.draw.rect(surf, PLUG, rect, border_radius=5)
    pygame.draw.rect(surf, shade(PLUG, 0.7), rect, 1, border_radius=5)
    for i in range(3):
        pygame.draw.line(surf, shade(PLUG, 0.78), (rect.x + 6, rect.y + 8 + i * 7), (rect.right - 7, rect.y + 8 + i * 7),
                         2)


def piece_image(piece, fonts):
    """What a piece looks like on its own, drawn once, with a small copy for the tray."""
    if piece.image is None:
        w, h = piece.rect.size
        pad = 8 if piece.round else 0
        image = pygame.Surface((w + pad, h + pad), pygame.SRCALPHA)
        c = ((w + pad) // 2, (h + pad) // 2)
        model = getattr(piece, "model", None)
        if piece.kind == "grille":
            draw_grille(image, *c, model)
        elif piece.kind == "blade":
            draw_blade(image, *c, BLADE_REST, model)
        elif piece.kind == "spinner":
            draw_spinner(image, *c, 0, model)
        elif piece.kind == "motor":
            draw_motor_cover(image, *c)
        elif piece.kind == "tape":
            draw_tape(image, image.get_rect())
        elif piece.kind == "base":
            draw_base_cover(image, image.get_rect(), fonts["tiny"], model)
        elif piece.kind == "back":
            draw_radio_back(image, image.get_rect(), fonts["tiny"], model)
        elif piece.kind == "door":
            draw_battery_door(image, image.get_rect(), fonts["tiny"], model)
        elif piece.kind == "batteries":
            for i, cell in enumerate(piece.cells):
                draw_cell(image, cell.move(-piece.rect.x, -piece.rect.y), i == 0, False, fonts["tiny"],
                          (model or RADIO_MODELS[0])["cell"])
        else:
            draw_clamp(image, image.get_rect())
        piece.image = image
        scale = min(56 / image.get_width(), 56 / image.get_height(), 1)
        piece.thumb = pygame.transform.smoothscale(image, (max(1, round(image.get_width() * scale)),
                                                           max(1, round(image.get_height() * scale))))
    return piece.image


def draw_moving(surf, piece, slot, fonts):
    """A piece on its way to the tray (or back), or waiting in it. Returns False if it's in place instead."""
    image = piece_image(piece, fonts)
    if piece.t <= 0:
        return False
    if piece.t >= 1:
        surf.blit(piece.thumb, piece.thumb.get_rect(center=slot))
        return True
    k = piece.t
    size = (round(image.get_width() + (piece.thumb.get_width() - image.get_width()) * k),
            round(image.get_height() + (piece.thumb.get_height() - image.get_height()) * k))
    home = piece.rect.center
    center = (home[0] + (slot[0] - home[0]) * k, home[1] + (slot[1] - home[1]) * k)
    scaled = pygame.transform.smoothscale(image, size)
    surf.blit(scaled, scaled.get_rect(center=center))
    return True


def draw_in_place(surf, piece, fonts, shadow=True):
    image = piece_image(piece, fonts)
    rect = image.get_rect(center=piece.rect.center).move(jiggle(piece.wiggle), 0)
    if shadow and not piece.round:
        pygame.draw.rect(surf, (20, 30, 28), piece.rect.move(jiggle(piece.wiggle) + 3, 4), border_radius=6)
    surf.blit(image, rect)


def draw_rotated_dust(surf, dust, degrees, offset=(0, 0)):
    if dust.clean:
        return
    image = pygame.transform.rotate(dust.surf, -degrees) if degrees else dust.surf
    surf.blit(image, image.get_rect(center=(HEAD[0] + offset[0], HEAD[1] + offset[1])))


def draw_fan(surf, game, fonts, mouse):
    """The fan, from the front, with whatever's been taken off it."""
    fan, turning = game.device, game.hold[0] if game.hold and isinstance(game.hold[0], Screw) else None
    hx, hy = HEAD
    testing = game.state == "test"
    jitter = (0, 0)
    if testing and game.test_symptom in ("wobble", "grind"):
        jitter = (round(3 * math.sin(game.state_time * 47)), round(3 * math.cos(game.state_time * 39)))
    model = fan.model
    draw_fan_stand(surf, model)
    # The back of the head: the rear grille and the motor
    pygame.draw.circle(surf, shade(model["body"], 0.6), HEAD, GRILLE_R, 4)
    for r in (60, 90, 118):
        pygame.draw.circle(surf, (96, 100, 110), HEAD, r, 1)
    for k in range(20):
        a = k * math.pi / 10
        pygame.draw.line(surf, (96, 100, 110), ring_point(a, 70), ring_point(a, GRILLE_R - 2), 1)
    pygame.draw.circle(surf, shade(MOTOR, 0.6), HEAD, MOTOR_R + 8)
    if fan.motor_cover.t > 0:
        draw_motor_inside(surf, fan, turning)
        if fan.tape.t == 0:
            draw_in_place(surf, fan.tape, fonts, shadow=False)
    draw_moving(surf, fan.tape, fan.tray_slot(fan.tape).center, fonts)
    if not draw_moving(surf, fan.motor_cover, fan.tray_slot(fan.motor_cover).center, fonts):
        draw_in_place(surf, fan.motor_cover, fonts)
        draw_screws(surf, fan.motor_cover.screws, turning)
        draw_bearing(surf, fan.bearing)
        draw_rotated_dust(surf, fan.face_dust, 0)
    draw_shaft(surf, fan.shaft)
    blade = fan.blade
    if not draw_moving(surf, blade, fan.tray_slot(blade).center, fonts):
        spin = game.spin if testing else 0
        draw_blade(surf, hx + jitter[0] + jiggle(blade.wiggle), hy + jitter[1], BLADE_REST + math.radians(spin),
                   model)
        draw_rotated_dust(surf, fan.blade_dust, spin, jitter)
    s = fan.spinner
    if not draw_moving(surf, s, fan.tray_slot(s).center, fonts):
        spin = game.spin if testing else 0
        draw_spinner(surf, hx + jitter[0] + jiggle(s.wiggle), hy + jitter[1], s.angle + math.radians(spin), model)
    if not draw_moving(surf, fan.grille, fan.tray_slot(fan.grille).center, fonts):
        draw_in_place(surf, fan.grille, fonts)
        draw_rotated_dust(surf, fan.grille_dust, 0)
        for clip in fan.clips:
            draw_clip(surf, clip, model)
    # The base
    if fan.base_cover.t > 0:
        draw_base_inside(surf, fan, fonts["tiny"], turning)
        if fan.clamp.t == 0:
            draw_in_place(surf, fan.clamp, fonts)
            draw_screws(surf, fan.clamp.screws, turning)
    draw_moving(surf, fan.clamp, fan.tray_slot(fan.clamp).center, fonts)
    if not draw_moving(surf, fan.base_cover, fan.tray_slot(fan.base_cover).center, fonts):
        draw_in_place(surf, fan.base_cover, fonts)
        draw_screws(surf, fan.base_cover.screws, turning)
    if model["controls"] == "cords":
        draw_pull_cords(surf, model)
    draw_strip(surf, fan.plug.on)
    draw_cord_and_plug(surf, fan, game.drag == ("plug", fan.plug), mouse)


def draw_trays(surf, dev, font):
    """The parts tray, and the little tray for screws."""
    loose = dev.loose_screws()
    for tray, name, empty in ((PIECE_TRAY, "PARTS TRAY", not any(dev.in_tray(p) for p in dev.tray_pieces)),
                              (TRAY, "SCREWS", not loose)):
        pygame.draw.rect(surf, (88, 92, 104), tray, border_radius=14)
        pygame.draw.rect(surf, (120, 124, 136), tray.inflate(-10, -10), border_radius=10)
        if empty:
            draw_text(surf, font, name, tray.center, (100, 104, 116))
    for i, screw in enumerate(loose):
        draw_screw(surf, TRAY.x + 18 + (i % 7) * 24, TRAY.y + 18 + (i // 7) * 23, 25 * i + 10)


def draw_meter(surf, dev, fonts):
    """The multimeter on the bench, showing its last reading."""
    r = METER_BOX
    pygame.draw.rect(surf, (30, 40, 36), r.move(4, 5), border_radius=14)
    pygame.draw.rect(surf, (236, 186, 40), r, border_radius=14)
    pygame.draw.rect(surf, (60, 62, 70), r.inflate(-10, -10), border_radius=10)
    lcd = pygame.Rect(r.x + 14, r.y + 14, r.w - 28, 44)
    pygame.draw.rect(surf, (172, 194, 150), lcd, border_radius=4)
    ink = (36, 48, 36)
    if dev.readings:
        name, text, _ = dev.readings[-1]
        draw_text(surf, fonts["big"], text, (lcd.right - 8, lcd.centery + 1), ink, "midright")
        label = name.upper()
    else:
        draw_text(surf, fonts["big"], "- - -", lcd.center, shade(ink, 2.5))
        label = "MULTIMETER"
    draw_text(surf, fonts["tiny"], label, (r.centerx, lcd.bottom + 10), (200, 200, 210))
    dial = (r.centerx, r.bottom - 26)
    pygame.draw.circle(surf, (30, 30, 34), dial, 15)
    pygame.draw.line(surf, (220, 220, 226), dial, (dial[0] + 9, dial[1] - 9), 3)
    for dx, color in ((-48, BLACK), (48, (200, 50, 50))):  # the probe sockets
        pygame.draw.circle(surf, color, (dial[0] + dx, dial[1]), 6)


def draw_dragged(surf, game, mouse, fonts):
    """A supply or a piece from the tray, in your hand."""
    kind, thing = game.drag
    if kind == "supply":
        game.device.draw_supply(surf, thing, mouse, fonts)
    elif kind == "tray":
        image = piece_image(thing, fonts).copy()
        image.set_alpha(220)
        surf.blit(image, image.get_rect(center=mouse))


def draw_oil(surf, x, y):
    """A little bottle of machine oil with a long spout."""
    pygame.draw.polygon(surf, (200, 60, 50), [(x - 3, y - 10), (x + 3, y - 10), (x + 1, y - 26), (x - 1, y - 26)])
    pygame.draw.rect(surf, shade(OIL, 0.7), (x - 10, y - 10, 20, 26), border_radius=5)
    pygame.draw.rect(surf, OIL, (x - 9, y - 9, 18, 24), border_radius=5)
    pygame.draw.rect(surf, (50, 90, 160), (x - 9, y - 1, 18, 8))


def draw_wd40(surf, x, y):
    """A spray can."""
    pygame.draw.rect(surf, (40, 80, 170), (x - 9, y - 14, 18, 32), border_radius=4)
    pygame.draw.rect(surf, (240, 210, 60), (x - 9, y - 4, 18, 8))
    pygame.draw.rect(surf, (200, 50, 45), (x - 6, y - 20, 12, 7), border_radius=2)
    pygame.draw.line(surf, (200, 50, 45), (x + 5, y - 18), (x + 18, y - 22), 2)


def draw_new_fuse(surf, x, y):
    pygame.draw.line(surf, METAL, (x - 22, y), (x + 22, y), 2)
    pygame.draw.rect(surf, FUSE_SLEEVE, (x - 12, y - 5, 24, 10), border_radius=4)
    pygame.draw.rect(surf, (60, 60, 70), (x - 6, y - 5, 3, 10))


def draw_old_cap(surf, x, y):
    draw_cap(surf, x, y, 0, True)


def draw_scrap(surf, x, y):
    """The bit of cord you cut off."""
    pygame.draw.line(surf, shade(CORD, 0.6), (x - 12, y), (x + 12, y), 12)
    pygame.draw.line(surf, CORD, (x - 12, y), (x + 12, y), 9)
    pygame.draw.line(surf, COPPER, (x - 3, y + 2), (x + 3, y - 3), 2)


def draw_vinegar(surf, x, y):
    """A bottle of white vinegar."""
    pygame.draw.rect(surf, (226, 230, 232), (x - 9, y - 12, 18, 28), border_radius=5)
    pygame.draw.rect(surf, (226, 230, 232), (x - 4, y - 20, 8, 9))
    pygame.draw.rect(surf, (200, 60, 50), (x - 5, y - 24, 10, 5), border_radius=2)
    pygame.draw.rect(surf, (236, 196, 80), (x - 9, y - 2, 18, 9))


def draw_cleaner(surf, x, y):
    """A can of contact cleaner, with a thin straw to aim it."""
    pygame.draw.rect(surf, (60, 150, 210), (x - 9, y - 14, 18, 32), border_radius=4)
    pygame.draw.rect(surf, WHITE, (x - 9, y - 3, 18, 6))
    pygame.draw.rect(surf, (30, 30, 34), (x - 5, y - 20, 10, 7), border_radius=2)
    pygame.draw.line(surf, (210, 60, 50), (x + 5, y - 18), (x + 22, y - 24), 2)


def draw_new_batteries(surf, x, y):
    for dy in (-10, 2):
        draw_cell(surf, pygame.Rect(x - 16, y + dy, 32, 10), True, False)


def draw_old_batteries(surf, x, y):
    for dy in (-10, 2):
        draw_cell(surf, pygame.Rect(x - 16, y + dy, 32, 10), True, True)


def draw_folded_antenna(surf, x, y):
    """A telescopic antenna, pushed in."""
    pygame.draw.line(surf, shade(CHROME, 0.6), (x - 18, y + 10), (x + 16, y - 10), 6)
    pygame.draw.line(surf, CHROME, (x - 18, y + 9), (x + 16, y - 11), 4)
    pygame.draw.circle(surf, CHROME, (x + 17, y - 11), 3)
    pygame.draw.circle(surf, (150, 150, 160), (x - 18, y + 10), 4)


SUPPLY_BODIES = {"oil": draw_oil, "wd40": draw_wd40, "fuse": draw_new_fuse, "vinegar": draw_vinegar,
                 "cleaner": draw_cleaner, "batteries": draw_new_batteries, "antenna": draw_folded_antenna}
FLYER_BODIES = {"cap": draw_old_cap, "fuse": draw_new_fuse, "scrap": draw_scrap, "old_batteries": draw_old_batteries,
                "antenna": draw_folded_antenna}


def draw_cell(surf, rect, plus_right, leaked, font=None, size="AA"):
    """One battery (size AA, C or D), lying down: a green wrapper, and a metal cap with a button at its + end."""
    pygame.draw.rect(surf, shade(BATTERY, 0.55), rect.move(1, 2), border_radius=rect.h // 3)
    pygame.draw.rect(surf, BATTERY, rect, border_radius=rect.h // 3)
    pygame.draw.rect(surf, shade(BATTERY, 1.3), (rect.x + 4, rect.y + rect.h // 6, rect.w - 8, max(2, rect.h // 6)),
                     border_radius=2)  # the shine
    cap_w = max(4, rect.w // 7)
    cap = pygame.Rect(rect.right - cap_w if plus_right else rect.x, rect.y, cap_w, rect.h)
    pygame.draw.rect(surf, METAL, cap, border_radius=rect.h // 3)
    nub = pygame.Rect(0, 0, max(2, rect.w // 30), rect.h // 2)
    nub.center = (cap.right if plus_right else cap.left, rect.centery)
    pygame.draw.rect(surf, METAL, nub)
    if font:
        draw_text(surf, font, f"{size} 1.5V", rect.center, WHITE)
        draw_text(surf, font, "+", (cap.x - 8 if plus_right else cap.right + 8, rect.centery), WHITE)
    if leaked:  # crust where it's leaked, at both ends
        rnd = random.Random(rect.x * 3 + rect.y)
        for end in (rect.left, rect.right):
            for _ in range(5):
                pygame.draw.circle(surf, CRUST, (end + rnd.uniform(-3, 3), rect.y + rnd.uniform(0, rect.h)),
                                   rnd.uniform(1.5, rect.h / 6))


def draw_crust(surf, crust):
    """Crust on a contact: white and lumpy, wet and fizzing once vinegar's on it."""
    if crust.crust <= 0:
        return
    rnd = random.Random(crust.x * 7 + crust.y)  # the same lumps every frame
    color = (206, 220, 198) if crust.soaked else CRUST
    for _ in range(9):
        x, y = crust.x + rnd.uniform(-8, 8), crust.y + rnd.uniform(-11, 11)
        pygame.draw.circle(surf, color, (x, y), rnd.uniform(2.5, 5.5) * (0.4 + 0.6 * crust.crust))
    if crust.soaked:
        for _ in range(3):
            pygame.draw.circle(surf, WHITE, (crust.x + rnd.uniform(-8, 8), crust.y + rnd.uniform(-10, 10)), 2, 1)


def draw_battery_box(surf, dev, fonts, turning):
    """The battery compartment: a spring at each slot's - end, a flat contact at its + end, and the marks that
    say which way round each battery goes."""
    box = BATTERY_BOX
    pygame.draw.rect(surf, (24, 24, 28), box, border_radius=8)
    pygame.draw.rect(surf, shade(dev.model["case"], 0.8), box, 2, border_radius=8)
    if dev.back.on:
        draw_screws(surf, [dev.back.screws[-1]], turning)  # the one hiding under the batteries
    b = dev.batteries
    for i, cell in enumerate(b.cells):
        plus_right = i == 0
        pygame.draw.rect(surf, (34, 34, 40), cell.inflate(4, 4), 1, border_radius=8)
        minus_x = cell.left - 3 if plus_right else cell.right + 3
        plus_x = cell.right + 3 if plus_right else cell.left - 3
        points = [(minus_x + (3 if k % 2 else -3), cell.top + 4 + k * 4) for k in range(7)]  # the spring
        pygame.draw.lines(surf, METAL, False, points, 2)
        pygame.draw.rect(surf, METAL, (plus_x - 2, cell.centery - 8, 4, 16))  # the flat contact
        for text, x in (("+", plus_x + (-12 if plus_right else 12)), ("-", minus_x + (12 if plus_right else -12))):
            draw_text(surf, fonts["small"], text, (x, cell.centery), (90, 92, 102))
    for crust in dev.crusts:
        draw_crust(surf, crust)
    if b.present and b.on and b.t == 0:
        for i, cell in enumerate(b.cells):
            plus_right = (i == 0) != b.reversed[i]
            draw_cell(surf, cell.move(jiggle(b.wiggle), 0), plus_right, b.leaked, fonts["tiny"], dev.model["cell"])
        for crust in dev.crusts:
            if b.leaked:
                draw_crust(surf, crust)


def draw_speaker(surf, spk, font):
    """The speaker from behind: its frame and paper cone, the magnet in the middle, two tabs on the rim."""
    x, y = SPEAKER
    r = SPEAKER_R
    pygame.draw.circle(surf, (22, 22, 24), (x + 3, y + 4), r + 2)
    pygame.draw.circle(surf, (70, 62, 52), (x, y), r - 3)  # the paper cone
    for rr in (r - 26, r - 48):
        pygame.draw.circle(surf, (58, 52, 44), (x, y), rr, 2)
    for k in range(4):  # the frame's spokes
        a = math.radians(45 + 90 * k)
        pygame.draw.line(surf, (150, 152, 160), (x + math.cos(a) * 44, y + math.sin(a) * 44),
                         (x + math.cos(a) * r, y + math.sin(a) * r), 8)
    pygame.draw.circle(surf, (150, 152, 160), (x, y), r, 7)  # the rim
    pygame.draw.circle(surf, (28, 28, 32), (x, y), 46)  # the magnet
    pygame.draw.circle(surf, (96, 98, 108), (x, y), 46, 3)
    pygame.draw.circle(surf, (120, 122, 132), (x, y), 14)
    draw_text(surf, font, f"{spk.ohms}Ω {spk.watts:g}W", (x, y + 28), (170, 172, 180))
    for i, tab in enumerate(spk.tabs):
        pygame.draw.rect(surf, (200, 190, 150), (tab.x - 7, tab.y - 5, 14, 10), border_radius=2)
        pygame.draw.circle(surf, (40, 40, 44), (tab.x - 2, tab.y), 2)
        if i == 1 or spk.wire == "soldered":  # a blob of solder holding the wire
            pygame.draw.circle(surf, SOLDER, (tab.x, tab.y), 6)
            pygame.draw.circle(surf, WHITE, (tab.x - 2, tab.y - 2), 1)


def draw_pot(surf, pot):
    """The volume control: a metal can with a knurled wheel, its top half showing over the board."""
    x, y = pot.x, pot.y
    pygame.draw.circle(surf, (20, 20, 24), (x + 2, y + 3), 24)
    pygame.draw.circle(surf, (150, 152, 160), (x, y), 24)
    for k in range(18):  # the knurls, which turn with it
        a = pot.angle + k * math.pi / 9
        pygame.draw.line(surf, (104, 106, 116), (x + math.cos(a) * 19, y + math.sin(a) * 19),
                         (x + math.cos(a) * 24, y + math.sin(a) * 24), 2)
    pygame.draw.circle(surf, METAL, (x, y), 17)
    pygame.draw.rect(surf, (26, 26, 30), (x - 9, y - 12, 18, 4), border_radius=2)  # the gap into its track
    if pot.dirty and not pot.sprayed:
        for dx in (-6, 0, 5):
            pygame.draw.circle(surf, (110, 90, 60), (x + dx, y - 14), 2)
    if pot.sprayed:
        pygame.draw.circle(surf, (200, 226, 244), (x - 7, y - 7), 3)


def draw_board(surf, dev, font):
    """The circuit board, solder side up: green coating over copper tracks, and a silver joint for every leg."""
    pygame.draw.rect(surf, (18, 50, 32), BOARD.move(3, 4), border_radius=6)
    pygame.draw.rect(surf, BOARD_GREEN, BOARD, border_radius=6)
    for points in TRACES:
        pygame.draw.lines(surf, TRACE, False, points, 5)
    pygame.draw.rect(surf, SILK, (432, 308, 94, 50), 1, border_radius=3)
    for text, pos in (("IC1", (479, 333)), ("VOL", (390, 266)), ("TUNE", (524, 266)), ("PHONES", (588, 316)),
                      ("SP+", (354, 300)), ("SP-", (354, 322)), ("ANT", (356, 252)), ("BAT+", (470, 392)),
                      ("BAT-", (514, 392)), ("ROD", (356, 404))):
        draw_text(surf, font, text, pos, SILK)
    for joint in dev.joints:
        x, y = joint.x + jiggle(joint.wiggle), joint.y
        pygame.draw.circle(surf, (170, 130, 70), (x, y), 7)  # the copper pad
        pygame.draw.circle(surf, (178, 180, 184) if joint.cracked else SOLDER, (x, y), 5)
        pygame.draw.circle(surf, (128, 130, 136), (x, y), 2)  # the leg's end
        if joint.cracked:  # a hairline ring: hard to see without the magnifier
            pygame.draw.circle(surf, (156, 158, 164), (x, y), 3, 1)
        else:
            pygame.draw.circle(surf, WHITE, (x - 2, y - 2), 1)


def draw_antenna(surf, ant):
    """The telescopic antenna, pulled out and swung up, or the empty socket where it goes."""
    bx, by = ANTENNA_BASE
    pygame.draw.circle(surf, (40, 40, 46), (bx, by + 4), 12)
    if not ant.present:
        pygame.draw.circle(surf, (24, 24, 28), (bx, by), 5)
        return
    dx = jiggle(ant.wiggle)
    for k in range(5):  # five sections, thinner towards the tip
        p1 = lerp(ANTENNA_BASE, ANTENNA_TIP, k / 5)
        p2 = lerp(ANTENNA_BASE, ANTENNA_TIP, (k + 1) / 5)
        p1, p2 = (p1[0] + dx, p1[1]), (p2[0] + dx, p2[1])
        width = 8 - k
        pygame.draw.line(surf, shade(CHROME, 0.5), (p1[0] + 2, p1[1] + 3), (p2[0] + 2, p2[1] + 3), width)
        pygame.draw.line(surf, CHROME, p1, p2, width)
        pygame.draw.circle(surf, shade(CHROME, 0.75), p1, width // 2 + 1)
    pygame.draw.circle(surf, CHROME, (ANTENNA_TIP[0] + dx, ANTENNA_TIP[1]), 4)
    pygame.draw.circle(surf, (150, 150, 160), (bx + dx, by), 7)  # the swivel


def draw_radio_back(surf, rect, font, model=None):
    """The back cover: vents over the speaker, the label, and the hole the battery door slides into."""
    model = model or RADIO_MODELS[0]
    back = model["back"]
    pygame.draw.rect(surf, back, rect, border_radius=26)
    if model["key"] == "retro":  # wood grain
        rnd = random.Random(7)
        for _ in range(16):
            y, bend = rect.y + rnd.uniform(12, rect.h - 12), rnd.uniform(-6, 6)
            points = [(rect.x + 16 + k * (rect.w - 32) / 8, y + bend * math.sin(k * 0.9)) for k in range(9)]
            pygame.draw.lines(surf, shade(back, rnd.uniform(0.86, 0.94)), False, points, 2)
    pygame.draw.rect(surf, shade(back, 0.72), rect, 3, border_radius=26)
    sx, sy = SPEAKER[0] - RADIO.x + rect.x, SPEAKER[1] - RADIO.y + rect.y
    vent = shade(back, 0.55)
    if model["vents"] == "slots":
        for row in range(-5, 6):
            for col in range(-5, 6):
                if row * row + col * col <= 24:
                    pygame.draw.rect(surf, vent, (sx + col * 17 - 5, sy + row * 17 - 2, 10, 4), border_radius=2)
    elif model["vents"] == "holes":
        for row in range(-5, 6):
            for col in range(-5, 6):
                if row * row + col * col <= 24:
                    pygame.draw.circle(surf, vent, (sx + col * 17, sy + row * 17), 5)
    else:  # long slots right across, like an old set's
        for row in range(-4, 5):
            half = math.sqrt(92 ** 2 - (row * 20) ** 2)
            pygame.draw.rect(surf, vent, (sx - half, sy + row * 20 - 3, 2 * half, 6), border_radius=3)
    label = pygame.Rect(rect.x + 330, rect.y + 24, 230, 84)
    pygame.draw.rect(surf, (238, 236, 226), label, border_radius=6)
    for i, (text, color) in enumerate(((f"AM / FM {model['label']}", (40, 40, 52)),
                                       (f"MODEL {model['code']}   3V DC (2 x {model['cell']})", DIM),
                                       ("FM 88-108 MHz", DIM), ("AM 530-1600 kHz", DIM))):
        draw_text(surf, font, text, (label.x + 12, label.y + 12 + i * 18), color, "topleft")
    hole = BATTERY_BOX.move(rect.x - RADIO.x, rect.y - RADIO.y)
    pygame.draw.rect(surf, shade(back, 0.6), hole.inflate(12, 12), 3, border_radius=12)
    surf.fill((0, 0, 0, 0), hole)


def draw_battery_door(surf, rect, font, model=None):
    model = model or RADIO_MODELS[0]
    back = model["back"]
    pygame.draw.rect(surf, shade(back, 1.08), rect, border_radius=10)
    pygame.draw.rect(surf, shade(back, 0.7), rect, 2, border_radius=10)
    for i in range(6):  # ridges to grip
        x = rect.x + 12 + i * 7
        pygame.draw.line(surf, shade(back, 0.7), (x, rect.y + 16), (x, rect.bottom - 16), 2)
    cx = rect.right - 34
    pygame.draw.polygon(surf, shade(back, 0.6), [(cx - 10, rect.centery - 10), (cx - 10, rect.centery + 10),
                                                 (cx + 6, rect.centery)])  # slide it this way
    draw_text(surf, font, "OPEN", (cx - 4, rect.centery + 24), shade(back, 0.6))
    draw_text(surf, font, f"2 x {model['cell']}  1.5V", (rect.centerx, rect.y + 14), shade(back, 0.6))


def draw_radio_inside(surf, dev, fonts, turning):
    """Inside the radio, with its back off."""
    inner = RADIO.inflate(-16, -16)
    pygame.draw.rect(surf, (34, 35, 40), inner, border_radius=20)
    # The AM antenna: a coil on a ferrite rod, along the bottom
    pygame.draw.rect(surf, (44, 44, 50), (84, 482, 222, 16), border_radius=7)
    for x in range(150, 216, 3):
        pygame.draw.line(surf, COPPER, (x, 481), (x + 1, 498), 2)
    for x in (108, 280):
        pygame.draw.rect(surf, (90, 92, 100), (x, 478, 10, 24), border_radius=3)
    pygame.draw.lines(surf, COPPER, False, [(182, 482), (182, 474), (318, 474), (334, 404)], 1)
    draw_speaker(surf, dev.speaker, fonts["tiny"])
    # The parts that poke over the board's top edge: the volume control, the tuning capacitor, the headphone socket
    draw_pot(surf, dev.pot)
    pygame.draw.circle(surf, (58, 60, 68), (520, 228), 28)
    pygame.draw.rect(surf, (226, 226, 218), (498, 212, 44, 40), border_radius=4)
    pygame.draw.circle(surf, (170, 170, 164), (520, 228), 8)
    draw_board(surf, dev, fonts["tiny"])
    pygame.draw.rect(surf, (22, 22, 26), (620, 290, 22, 50), border_radius=4)  # the headphone socket, at the edge
    pygame.draw.circle(surf, (60, 60, 66), (636, 315), 6)
    # Wires: the speaker's, the antenna's and the batteries'
    spk = dev.speaker
    sp_plus, sp_minus = PADS["SP+"], PADS["SP-"]
    if spk.wire == "loose":
        end = (spk.wire_end.x + jiggle(spk.wire_end.wiggle), spk.wire_end.y)
        pygame.draw.lines(surf, WIRE_RED, False, [sp_plus, (316, 304), end], 3)
        pygame.draw.circle(surf, COPPER, end, 3)  # its broken end
    else:
        pygame.draw.lines(surf, WIRE_RED, False, [sp_plus, (300, 300), (spk.tabs[0].x, spk.tabs[0].y)], 3)
    pygame.draw.lines(surf, WIRE_BLACK, False, [sp_minus, (300, 340), (284, 392), (spk.tabs[1].x, spk.tabs[1].y)], 3)
    for tab in spk.tabs:
        if tab is spk.tabs[1] or spk.wire == "soldered":
            pygame.draw.circle(surf, SOLDER, (tab.x, tab.y), 6)
            pygame.draw.circle(surf, WHITE, (tab.x - 2, tab.y - 2), 1)
    screw = dev.antenna.screw
    pygame.draw.lines(surf, WIRE_YELLOW, False, [(screw.x + 6, screw.y + 6), (150, 234), (300, 234), PADS["ANT"]], 2)
    pygame.draw.line(surf, WIRE_RED, PADS["BAT+"], (PADS["BAT+"][0], BATTERY_BOX.top + 2), 3)
    pygame.draw.line(surf, WIRE_BLACK, PADS["BAT-"], (PADS["BAT-"][0], BATTERY_BOX.top + 2), 3)
    draw_screws(surf, [screw], turning, post=(60, 62, 70))


def draw_radio_case(surf, model):
    """The radio's case, face down: and its carry handle, rubber bumper or feet, for the models that have them."""
    case, trim = model["case"], model["trim"]
    if model["handle"]:  # folded up over the top edge; its lower half hides behind the case
        handle = pygame.Rect(244, 152, 244, 80)
        pygame.draw.rect(surf, (28, 30, 32), handle.move(4, 6), 16, border_radius=28)
        pygame.draw.rect(surf, shade(case, 1.25), handle, 16, border_radius=28)
        pygame.draw.line(surf, shade(case, 1.7), (274, 156), (458, 156), 2)
        for x in range(300, 440, 14):  # the grip
            pygame.draw.line(surf, shade(case, 0.8), (x, 154), (x, 164), 2)
    if model["key"] == "retro":  # little feet on its bottom edge
        for x in (110, 530):
            pygame.draw.rect(surf, (40, 30, 24), (x, RADIO.bottom - 6, 50, 14), border_radius=5)
    if trim:  # a rubber bumper all round
        bumper = RADIO.inflate(18, 18)
        pygame.draw.rect(surf, (28, 30, 32), bumper.move(4, 6), border_radius=34)
        pygame.draw.rect(surf, trim, bumper, border_radius=34)
        pygame.draw.rect(surf, shade(trim, 0.7), bumper, 3, border_radius=34)
    else:
        pygame.draw.rect(surf, (28, 30, 32), RADIO.move(4, 6), border_radius=26)
    pygame.draw.rect(surf, case, RADIO, border_radius=26)
    pygame.draw.rect(surf, shade(case, 0.7), RADIO, 3, border_radius=26)


def draw_radio(surf, game, fonts):
    """The radio, face down on the bench, with whatever's been taken off it."""
    dev = game.device
    turning = game.hold[0] if game.hold and isinstance(game.hold[0], Screw) else None
    draw_radio_case(surf, dev.model)
    if dev.back.t > 0:
        draw_radio_inside(surf, dev, fonts, turning)
    draw_battery_box(surf, dev, fonts, turning)
    back, door, b = dev.back, dev.door, dev.batteries
    if not draw_moving(surf, back, dev.tray_slot(back).center, fonts):
        draw_in_place(surf, back, fonts, shadow=False)
        draw_screws(surf, back.screws[:-1], turning)
    if not draw_moving(surf, door, dev.tray_slot(door).center, fonts):
        draw_in_place(surf, door, fonts, shadow=False)
    if b.present and b.t > 0:
        draw_moving(surf, b, dev.tray_slot(b).center, fonts)
    draw_antenna(surf, dev.antenna)  # on top of the case, outside


def radio_playing(symptom, t):
    if symptom in (None, "crackle"):
        return True
    return symptom == "cutout" and t % 1.4 < 0.8


def draw_note(surf, x, y, alpha):
    """A music note."""
    color = (*GOLD, alpha)
    pygame.draw.ellipse(surf, color, (x - 6, y - 4, 12, 9))
    pygame.draw.line(surf, color, (x + 5, y), (x + 5, y - 22), 2)
    pygame.draw.line(surf, color, (x + 5, y - 22), (x + 12, y - 15), 3)


def draw_radio_test(surf, game):
    """The radio in a power test: sound off the speaker and notes floating up, or hiss, or nothing at all."""
    symptom, t = game.test_symptom, game.state_time
    x, y = SPEAKER[0] - BENCH.x, SPEAKER[1] - BENCH.y
    layer = pygame.Surface(BENCH.size, pygame.SRCALPHA)
    if radio_playing(symptom, t):
        for k in range(3):  # sound coming off the speaker in rings
            phase = (t * 1.2 + k / 3) % 1
            pygame.draw.circle(layer, (255, 255, 255, round(120 * (1 - phase))), (x, y),
                               round(SPEAKER_R * 0.5 + phase * 90), 3)
        for k in range(4):  # notes floating up
            phase = (t * 0.5 + k / 4) % 1
            draw_note(layer, x - 60 + k * 40 + 10 * math.sin(t * 3 + k), RADIO.top - BENCH.y - 10 - phase * 110,
                      round(230 * (1 - phase)))
    elif symptom == "fmhiss":
        for _ in range(70):  # static
            a, r = random.uniform(0, 2 * math.pi), SPEAKER_R * math.sqrt(random.random())
            pygame.draw.circle(layer, (255, 255, 255, random.randint(60, 170)),
                               (x + math.cos(a) * r, y + math.sin(a) * r), 1)
    surf.blit(layer, BENCH.topleft)


def draw_lens(surf, game, mouse):
    """The magnifier: what's under it, bigger, with the fine details you can't see by eye."""
    r, zoom = 46, 2.5
    src = pygame.Rect(0, 0, round(2 * r / zoom), round(2 * r / zoom))
    src.center = mouse
    src = src.clip(BENCH)
    if src.w < 4 or src.h < 4:
        return
    view = pygame.transform.smoothscale(surf.subsurface(src).copy(), (round(src.w * zoom), round(src.h * zoom)))
    lens = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
    left, top = r - (mouse[0] - src.x) * zoom, r - (mouse[1] - src.y) * zoom
    lens.blit(view, (left, top))
    game.device.draw_details(lens, lambda p: (left + (p[0] - src.x) * zoom, top + (p[1] - src.y) * zoom), zoom)
    mask = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
    pygame.draw.circle(mask, WHITE, (r, r), r)
    lens.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(lens, (mouse[0] - r, mouse[1] - r))
    pygame.draw.line(surf, (120, 80, 50), (mouse[0] + r * 0.72, mouse[1] + r * 0.72),
                     (mouse[0] + r * 0.72 + 30, mouse[1] + r * 0.72 + 30), 9)  # the handle
    pygame.draw.circle(surf, (40, 40, 46), mouse, r + 3, 5)
    pygame.draw.circle(surf, (190, 194, 206), mouse, r + 1, 2)


def make_icon(draw_body):
    """A small picture of a supply for the drawer."""
    big = pygame.Surface((120, 80), pygame.SRCALPHA)
    draw_body(big, 60, 40)
    box = big.get_bounding_rect()
    scale = min(34 / box.w, 28 / box.h)
    return pygame.transform.smoothscale(big.subsurface(box), (round(box.w * scale), round(box.h * scale)))


def draw_fan_head(surf, x, y, model):
    """A fan's head from the front, whole: for the pictures on the cards."""
    pygame.draw.circle(surf, (58, 62, 78), (x, y), GRILLE_R)  # the inside of the head, behind the blade
    pygame.draw.circle(surf, MOTOR, (x, y), MOTOR_R)
    draw_blade(surf, x, y, BLADE_REST, model)
    draw_grille(surf, x, y, model)


def draw_desk_icon(surf, x, y, model):
    hx, hy = x, y - 50
    body = model["body"]
    pygame.draw.rect(surf, shade(body, 0.82), (hx - 14, hy + 120, 28, 84))  # the neck
    pygame.draw.rect(surf, shade(body, 0.62), (hx - 14, hy + 120, 28, 84), 3)
    base = pygame.Rect(hx - 120, hy + 196, 240, 54)
    pygame.draw.rect(surf, shade(body, 0.7), base.move(0, 5), border_radius=22)
    pygame.draw.rect(surf, body, base, border_radius=22)
    for i in range(4):  # the speed keys
        pygame.draw.rect(surf, WHITE if i else (230, 120, 100), (base.x + 70 + i * 26, base.y + 14, 20, 24),
                         border_radius=5)
    draw_fan_head(surf, hx, hy, model)


def draw_stand_icon(surf, x, y, model):
    hx, hy = x, y - 130
    body = model["body"]
    pygame.draw.ellipse(surf, shade(body, 0.6), (hx - 130, y + 232, 260, 44))  # the round base
    pygame.draw.ellipse(surf, body, (hx - 130, y + 226, 260, 44))
    pygame.draw.rect(surf, METAL, (hx - 10, hy + 160, 20, y + 250 - hy - 160))  # the pole
    pygame.draw.line(surf, WHITE, (hx - 4, hy + 160), (hx - 4, y + 246), 3)
    box = pygame.Rect(hx - 56, hy + 150, 112, 62)  # the control box, with its speed knob and timer
    pygame.draw.rect(surf, body, box, border_radius=12)
    for k in range(2):
        pygame.draw.circle(surf, (214, 216, 222), (box.x + 32 + k * 48, box.centery), 16)
    draw_fan_head(surf, hx, hy, model)


def draw_wall_icon(surf, x, y, model):
    hx, hy = x, y - 40
    body = model["body"]
    plate = pygame.Rect(hx - 44, hy - 228, 88, 70)  # the bracket screwed to the wall, and the arm the fan hangs on
    pygame.draw.rect(surf, shade(body, 0.6), (hx - 12, plate.bottom - 6, 24, 80))
    pygame.draw.rect(surf, shade(body, 0.75), plate, border_radius=10)
    for dx in (-24, 24):
        pygame.draw.circle(surf, METAL_DARK, (hx + dx, plate.y + 20), 7)
        pygame.draw.circle(surf, METAL, (hx + dx, plate.y + 20), 5)
    box = pygame.Rect(hx - 70, hy + 128, 140, 64)  # the control box, under the motor
    pygame.draw.rect(surf, shade(body, 0.7), box.move(0, 5), border_radius=14)
    pygame.draw.rect(surf, body, box, border_radius=14)
    for i, dx in enumerate((-30, 30)):  # the pull cords
        top = (hx + dx, box.bottom)
        pygame.draw.line(surf, (240, 240, 232), top, (hx + dx, box.bottom + 90 + i * 20), 4)
        pygame.draw.ellipse(surf, model["badge"], (hx + dx - 9, box.bottom + 86 + i * 20, 18, 28))
    draw_fan_head(surf, hx, hy, model)


def draw_front_antenna(surf, base, tip):
    """A radio's telescopic antenna from the front, pulled out: for the pictures on the cards."""
    pygame.draw.line(surf, CHROME, base, tip, 8)
    pygame.draw.circle(surf, CHROME, tip, 9)


def draw_dial(surf, rect, needle):
    """A tuning dial window: a cream scale with its marks, and the red needle needle of the way along."""
    pygame.draw.rect(surf, (240, 232, 206), rect, border_radius=8)
    for k in range(9):
        lx = rect.x + 12 + k * (rect.w - 24) / 8
        pygame.draw.line(surf, (90, 84, 70), (lx, rect.y + 12), (lx, rect.y + (rect.h // 2 if k % 2 else rect.h // 3)),
                         3)
    nx = rect.x + 12 + needle * (rect.w - 24)
    pygame.draw.line(surf, (220, 60, 50), (nx, rect.y + 6), (nx, rect.bottom - 6), 5)


def draw_holes(surf, cx, cy, r, color, gap=13, size=4):
    """A round speaker grille of holes."""
    n = int(r // gap)
    for row in range(-n, n + 1):
        for col in range(-n, n + 1):
            if math.hypot(row * gap, col * gap) <= r - size:
                pygame.draw.circle(surf, color, (cx + col * gap, cy + row * gap), size)


def draw_pocket_icon(surf, x, y, model):
    """A pocket radio from the front: tall and slim, with a wrist strap and thumb wheels on its side."""
    case = model["case"]
    body = pygame.Rect(0, 0, 210, 320)
    body.center = (x, y + 60)
    draw_front_antenna(surf, (body.right - 30, body.top + 8), (body.left + 4, body.top - 170))
    pygame.draw.ellipse(surf, (40, 40, 46), (body.x - 34, body.bottom - 44, 66, 104), 7)  # the wrist strap
    for k in range(2):  # the thumb wheels, peeping out of its side
        wheel = pygame.Rect(body.right - 8, body.y + 70 + k * 64, 18, 48)
        pygame.draw.rect(surf, (150, 152, 160), wheel, border_radius=6)
        for i in range(5):
            ry = wheel.y + 7 + i * 8
            pygame.draw.line(surf, (96, 98, 108), (wheel.x + 4, ry), (wheel.right - 2, ry), 2)
    pygame.draw.rect(surf, (24, 24, 28), body.move(5, 8), border_radius=30)
    pygame.draw.rect(surf, case, body, border_radius=30)
    pygame.draw.rect(surf, shade(case, 1.6), body, 5, border_radius=30)
    draw_dial(surf, pygame.Rect(body.x + 24, body.y + 28, body.w - 48, 64), 0.55)
    gx, gy = body.centerx, body.y + 204
    pygame.draw.circle(surf, (36, 38, 44), (gx, gy), 80)
    draw_holes(surf, gx, gy, 76, (110, 114, 126))
    pygame.draw.circle(surf, (110, 220, 120), (body.x + 32, body.y + 112), 5)  # the power light


def draw_outdoor_icon(surf, x, y, model):
    """An outdoor radio from the front: wide, with a rubber bumper all round and a big carry handle."""
    case, trim = model["case"], model["trim"]
    body = pygame.Rect(0, 0, 380, 230)
    body.center = (x, y + 60)
    draw_front_antenna(surf, (body.right - 46, body.top + 8), (body.left + 84, body.top - 170))
    handle = pygame.Rect(body.x + 70, body.top - 62, body.w - 140, 110)
    pygame.draw.rect(surf, shade(case, 1.3), handle, 18, border_radius=34)
    pygame.draw.rect(surf, (24, 24, 28), body.move(5, 8), border_radius=44)
    pygame.draw.rect(surf, trim, body, border_radius=44)  # the rubber bumper
    pygame.draw.rect(surf, shade(trim, 0.7), body, 4, border_radius=44)
    inner = body.inflate(-34, -34)
    pygame.draw.rect(surf, case, inner, border_radius=22)
    gx, gy = inner.x + 96, inner.centery
    pygame.draw.circle(surf, (32, 34, 36), (gx, gy), 84)
    draw_holes(surf, gx, gy, 80, (96, 104, 100), gap=14, size=5)
    draw_dial(surf, pygame.Rect(inner.x + 200, inner.y + 22, inner.w - 222, 62), 0.35)
    for k in range(2):  # big knobs you can turn with gloves on
        kx = inner.x + 226 + k * 70
        pygame.draw.circle(surf, (30, 32, 34), (kx, inner.bottom - 46), 26)
        pygame.draw.circle(surf, trim, (kx, inner.bottom - 46), 26, 5)


def draw_retro_icon(surf, x, y, model):
    """A retro radio from the front: a wood case, a cloth speaker grille with gold bars, and a big round dial."""
    case = model["case"]
    body = pygame.Rect(0, 0, 360, 240)
    body.center = (x, y + 60)
    draw_front_antenna(surf, (body.right - 40, body.top + 8), (body.left + 70, body.top - 160))
    for fx in (body.x + 40, body.right - 90):  # its feet
        pygame.draw.rect(surf, (40, 30, 24), (fx, body.bottom - 10, 50, 24), border_radius=6)
    pygame.draw.rect(surf, (24, 24, 28), body.move(5, 8), border_radius=48)
    pygame.draw.rect(surf, case, body, border_radius=48)
    rnd = random.Random(3)
    for _ in range(9):  # wood grain
        gy = body.y + rnd.uniform(14, body.h - 14)
        pygame.draw.line(surf, shade(case, 0.85), (body.x + 30, gy), (body.right - 30, gy + rnd.uniform(-5, 5)), 2)
    pygame.draw.rect(surf, shade(case, 1.35), body, 5, border_radius=48)
    cloth = pygame.Rect(body.x + 28, body.y + 30, 170, body.h - 60)
    pygame.draw.rect(surf, (214, 196, 150), cloth, border_radius=18)
    for k in range(5):  # gold bars over the cloth
        bx = cloth.x + 22 + k * 31
        pygame.draw.line(surf, GOLD, (bx, cloth.y + 10), (bx, cloth.bottom - 10), 5)
    pygame.draw.rect(surf, GOLD, cloth, 4, border_radius=18)
    dx, dy = body.right - 88, body.y + 96
    pygame.draw.circle(surf, (240, 232, 206), (dx, dy), 60)
    for k in range(13):  # the scale round the dial
        a = math.radians(150 + k * 20)
        pygame.draw.line(surf, (90, 84, 70), (dx + math.cos(a) * 44, dy + math.sin(a) * 44),
                         (dx + math.cos(a) * 54, dy + math.sin(a) * 54), 3)
    pygame.draw.line(surf, (220, 60, 50), (dx, dy), (dx + math.cos(-1.1) * 50, dy + math.sin(-1.1) * 50), 4)
    pygame.draw.circle(surf, GOLD, (dx, dy), 60, 5)
    pygame.draw.circle(surf, GOLD, (dx, dy), 8)
    for kx in (dx - 38, dx + 38):  # the volume and tuning knobs
        pygame.draw.circle(surf, (236, 228, 204), (kx, body.bottom - 32), 17)
        pygame.draw.circle(surf, GOLD, (kx, body.bottom - 32), 17, 3)


MODEL_ICONS = {"desk": draw_desk_icon, "stand": draw_stand_icon, "wall": draw_wall_icon,
               "pocket": draw_pocket_icon, "outdoor": draw_outdoor_icon, "retro": draw_retro_icon}


def make_model_icon(model, size=(240, 158)):
    """A picture of a whole fan or radio of this type, drawn big and shrunk to fit size."""
    big = pygame.Surface((440, 640), pygame.SRCALPHA)
    MODEL_ICONS[model["key"]](big, 220, 300, model)
    box = big.get_bounding_rect()
    scale = min(size[0] / box.w, size[1] / box.h)
    return pygame.transform.smoothscale(big.subsurface(box), (round(box.w * scale), round(box.h * scale)))


def draw_fan_icon(surf, x, y):
    """The fan's card on the first screen: a stand fan, a desk fan and a wall fan side by side."""
    for model, dx, height in ((FAN_MODELS[1], -190, 400), (FAN_MODELS[2], 190, 330), (FAN_MODELS[0], 0, 300)):
        icon = make_model_icon(model, (400, height))
        surf.blit(icon, icon.get_rect(midbottom=(x + dx, y + 200)))


def draw_radio_icon(surf, x, y):
    """The radio's card on the first screen: a retro radio, an outdoor radio and a pocket radio side by side."""
    for model, dx, height in ((RADIO_MODELS[2], -200, 250), (RADIO_MODELS[1], 200, 290), (RADIO_MODELS[0], 0, 260)):
        icon = make_model_icon(model, (400, height))
        surf.blit(icon, icon.get_rect(midbottom=(x + dx, y + 200)))


PRODUCT_ICONS = {"fan": draw_fan_icon, "radio": draw_radio_icon}  # each product's picture: a new one needs one here


def make_product_icon(key):
    big = pygame.Surface((720, 520), pygame.SRCALPHA)
    PRODUCT_ICONS[key](big, 360, 260)
    box = big.get_bounding_rect()
    scale = min(170 / box.w, 96 / box.h)
    return pygame.transform.smoothscale(big.subsurface(box), (round(box.w * scale), round(box.h * scale)))


def gadget_glow_shape(target):
    """Where a step's target is: ("circle", center, radius) or ("rect", rect)."""
    if target == "TEST":
        return "rect", TEST_BUTTON
    if target == "FINISH":
        return "rect", FINISH_BUTTON
    return target.shape()


def draw_glow(surf, shape, t):
    """A soft, pulsing outline around something to work on, with a crisp white edge."""
    pulse = 0.5 + 0.5 * math.sin(t * 6)
    if shape[0] == "circle":
        _, (x, y), r = shape
        box = pygame.Rect(0, 0, 2 * r + 44, 2 * r + 44)
        box.center = (round(x), round(y))
        glow = pygame.Surface(box.size, pygame.SRCALPHA)
        middle = (box.w // 2, box.h // 2)
        for i in range(5):
            pygame.draw.circle(glow, (*GLOW, round((70 + 90 * pulse) * (1 - i / 5))), middle, r + 4 + i * 3, 3)
        pygame.draw.circle(glow, (255, 255, 255, 235), middle, r + 2, 2)
    elif shape[0] == "line":
        _, a, b = shape
        box = pygame.Rect(min(a[0], b[0]), min(a[1], b[1]), abs(a[0] - b[0]), abs(a[1] - b[1])).inflate(44, 44)
        glow = pygame.Surface(box.size, pygame.SRCALPHA)
        la, lb = (a[0] - box.x, a[1] - box.y), (b[0] - box.x, b[1] - box.y)
        for i in reversed(range(5)):  # widest and faintest first
            pygame.draw.line(glow, (*GLOW, round((70 + 90 * pulse) * (1 - i / 5))), la, lb, 8 + i * 6)
        pygame.draw.line(glow, (255, 255, 255, 235), la, lb, 2)
    else:
        rect = shape[1]
        box = rect.inflate(44, 44)
        glow = pygame.Surface(box.size, pygame.SRCALPHA)
        local = pygame.Rect(22, 22, rect.w, rect.h)
        for i in range(5):
            pygame.draw.rect(glow, (*GLOW, round((70 + 90 * pulse) * (1 - i / 5))),
                             local.inflate(8 + i * 6, 8 + i * 6), 3, border_radius=8 + i * 3)
        pygame.draw.rect(glow, (255, 255, 255, 235), local.inflate(4, 4), 2, border_radius=8)
    surf.blit(glow, box)


def draw_badge(surf, font, text, shape, t):
    """A tag by the glowing outline saying how to do the step: HOLD, CLICK, RUB, DRAG or which way to turn."""
    if shape[0] == "circle":
        _, (x, y), r = shape
        x, y = x + r * 0.7 + 10, y - r * 0.7 - 8
    elif shape[0] == "line":
        x, y = shape[2][0] + 12, shape[2][1] + 4
    else:
        x, y = shape[1].right + 6, shape[1].top - 4
    img = font.render(text, True, BLACK)
    rect = img.get_rect(midleft=(round(x), round(y + 3 * math.sin(t * 5))))
    rect.clamp_ip(pygame.Rect(8, 8, WIDTH - 16, HEIGHT - 16))
    pygame.draw.rect(surf, GLOW, rect.inflate(12, 6), border_radius=9)
    surf.blit(img, rect)


def draw_turn_arrow(surf, x, y, r, clockwise, t):
    """A circling arrow round the spinner or the shaft, showing which way to turn it."""
    sign = 1 if clockwise else -1
    start = sign * t * 2.5
    points = [(x + math.cos(start + sign * k * 0.12) * r, y + math.sin(start + sign * k * 0.12) * r)
              for k in range(40)]
    pygame.draw.lines(surf, GLOW, False, points, 4)
    end = start + sign * 39 * 0.12
    tip = (x + math.cos(end) * r, y + math.sin(end) * r)
    ahead = end + sign * 0.5
    side = (math.cos(end), math.sin(end))
    head = (x + math.cos(ahead) * r, y + math.sin(ahead) * r)
    pygame.draw.polygon(surf, GLOW, [head, (tip[0] + side[0] * 9, tip[1] + side[1] * 9),
                                     (tip[0] - side[0] * 9, tip[1] - side[1] * 9)])


BADGES = {"driver": "HOLD", "crimper": "HOLD", "iron": "HOLD", "brush": "RUB", "drag": "DRAG",
          "magnifier": "LOOK"}  # anything else is "CLICK"


def step_source(game, step):
    """Where a drag step starts: the drawer, the tray or the loose plug."""
    kind, thing = step.source
    if kind == "supply":
        return "rect", SUPPLY_RECTS[game.device.SUPPLIES.index(thing)]
    if kind == "tray":
        return "rect", game.device.tray_slot(thing)
    return "rect", plug_rect(thing)


def draw_guide(surf, game, fonts, step):
    """The glowing outlines for a step: the tool to pick up, what to drag, and what to work on."""
    t = game.clock
    need, tools = TOOL_FOR.get(step.tool, step.tool), game.device.TOOLS
    if need in tools and game.tool != need:
        shape = ("rect", TOOL_RECTS[tools.index(need)])
        draw_glow(surf, shape, t)
        draw_badge(surf, fonts["tiny"], f"PRESS {tools.index(need) + 1}", shape, t)
        return
    shapes = [gadget_glow_shape(target) for target in step.left()]
    if step.tool == "drag" and game.drag is None:
        shapes.insert(0, step_source(game, step))
    for shape in shapes:
        draw_glow(surf, shape, t)
    if step.tool == "twist" and step.left():
        target = step.left()[0]
        draw_turn_arrow(surf, target.x, target.y, 34, step.badge != "ANTI-CLOCKWISE", t)
    if shapes:
        draw_badge(surf, fonts["tiny"], step.badge or BADGES.get(step.tool, "CLICK"), shapes[0], t)


def draw_steps(surf, game, fonts):
    """The steps of a tidy repair. Guided: the one you're on. On your own: ticked off as you do them, in any
    order, with a dash for one you skipped."""
    dev, box = game.device, MIDDLE
    pygame.draw.rect(surf, CARD, box, border_radius=8)
    total = len(dev.steps)
    if game.guided:
        current = min(dev.step, total)
        done = [i < current for i in range(total)]
    else:
        current, done = dev.next_step(), dev.done
    draw_text(surf, fonts["tiny"], "GUIDED REPAIR" if game.guided else "REPAIR STEPS", (box.x + 12, box.y + 9),
              GOLD if game.guided else DIM, "topleft")
    draw_text(surf, fonts["tiny"], f"{sum(done)} / {total} done", (box.right - 12, box.y + 9), DIM, "topright")
    bar = pygame.Rect(box.x + 12, box.y + 26, box.w - 24, 6)
    pygame.draw.rect(surf, PANEL, bar, border_radius=3)
    pygame.draw.rect(surf, GREEN, (bar.x, bar.y, bar.w * sum(done) / total, bar.h), border_radius=3)
    first = max(0, min(current - 3, total - STEP_LINES))
    for i in range(first, min(total, first + STEP_LINES)):
        step, y = dev.steps[i], box.y + 40 + (i - first) * 19
        if done[i]:
            pygame.draw.lines(surf, GREEN, False, [(box.x + 15, y + 8), (box.x + 19, y + 12), (box.x + 26, y + 3)], 3)
            draw_text(surf, fonts["small"], step.label, (box.x + 34, y), (110, 116, 136), "topleft")
        elif i == current:
            pygame.draw.rect(surf, CARD_HOT, (box.x + 6, y - 2, box.w - 12, 19), border_radius=5)
            pygame.draw.polygon(surf, GOLD, [(box.x + 15, y + 2), (box.x + 24, y + 7), (box.x + 15, y + 12)])
            draw_text(surf, fonts["small"], step.label, (box.x + 34, y), GOLD, "topleft")
        elif i < current:  # a step you skipped (you can still do it)
            pygame.draw.line(surf, (200, 150, 90), (box.x + 15, y + 7), (box.x + 25, y + 7), 3)
            draw_text(surf, fonts["small"], step.label, (box.x + 34, y), (150, 130, 110), "topleft")
        else:
            draw_text(surf, fonts["tiny"], str(i + 1), (box.x + 20, y + 2), (90, 96, 116), "midtop")
            draw_text(surf, fonts["small"], step.label, (box.x + 34, y), DIM, "topleft")


def draw_findings(surf, game, fonts):
    """A mystery has no step list: instead, a notebook of what the tests and the multimeter have shown."""
    dev, box = game.device, MIDDLE
    pygame.draw.rect(surf, CARD, box, border_radius=8)
    draw_text(surf, fonts["tiny"], "WHAT YOU'VE FOUND OUT", (box.x + 12, box.y + 9), GOLD, "topleft")
    lines = []
    for i, text in enumerate(dev.observations):
        lines.append((f"Test {i + 1}: {text}", GREEN if text == "It works!" else RED))
    for name, text, good in dev.readings:
        lines.append((f"{name}: {text}", GREEN if good else RED))
    lines += [(text, GREEN if good else RED) for text, good in dev.notes()]
    if not lines:
        lines = [("Nothing yet. Press TEST to see what it does, then open it up, look and measure.", DIM)]
    rows = []
    for text, color in lines:
        rows += [(line, color) for line in wrap(fonts["small"], text, box.w - 24)]
    rows = rows[-10:]  # newest at the bottom
    for i, (line, color) in enumerate(rows):
        draw_text(surf, fonts["small"], line, (box.x + 12, box.y + 30 + i * 18), color, "topleft")
    draw_text(surf, fonts["tiny"], "Stuck? H shows the next step (costs points)", (box.x + 12, box.bottom - 18), DIM,
              "topleft")


def draw_panel(surf, game, fonts, icons, tool_icons, mouse):
    dev, step = game.device, game.step()
    pygame.draw.rect(surf, PANEL, (PANEL_X, HUD_H, WIDTH - PANEL_X, HEIGHT - HUD_H))
    x = TICKET.x + 12
    pygame.draw.rect(surf, (240, 236, 222), TICKET, border_radius=8)
    pygame.draw.rect(surf, (206, 196, 176), TICKET, 2, border_radius=8)
    level = game.level_info()
    mode = "GUIDED" if game.guided else "MYSTERY" if level["faults"] is None else "ON MY OWN"
    draw_text(surf, fonts["tiny"], f"LEVEL {game.level + 1}  ·  {mode}", (x, TICKET.y + 8), (130, 120, 108), "topleft")
    draw_text(surf, fonts["font"], level["title"], (x, TICKET.y + 22), (40, 40, 52), "topleft")
    for i, line in enumerate(wrap(fonts["small"], f'"{dev.complaint}"', TICKET.w - 24)[:3]):
        draw_text(surf, fonts["small"], line, (x, TICKET.y + 46 + i * 17), (70, 66, 62), "topleft")
    slips = sum(dev.mistakes.values())
    draw_text(surf, fonts["small"], f"Mistakes {slips}  Hints {dev.hints}", (x, TICKET.bottom - 22),
              (190, 70, 60) if slips else (40, 130, 70), "topleft")
    late = dev.time > dev.par
    draw_text(surf, fonts["small"], f"{clock_text(dev.time)} / {clock_text(dev.par)}",
              (TICKET.right - 12, TICKET.bottom - 22), (190, 70, 60) if late else (40, 130, 70), "topright")

    if level["faults"] is None:
        draw_findings(surf, game, fonts)
    else:
        draw_steps(surf, game, fonts)

    draw_text(surf, fonts["tiny"], "TOOLS   1-6", (x - 12, TOOL_RECTS[0].y - 15), DIM, "topleft")
    for i, (tool, rect) in enumerate(zip(dev.TOOLS, TOOL_RECTS)):
        active = tool == game.tool
        pygame.draw.rect(surf, CARD_HOT if active or rect.collidepoint(mouse) else CARD, rect, border_radius=7)
        if active:
            pygame.draw.rect(surf, GOLD, rect, 2, border_radius=7)
        surf.blit(tool_icons[tool], tool_icons[tool].get_rect(center=rect.center))
        draw_text(surf, fonts["tiny"], str(i + 1), (rect.right - 4, rect.y + 2), DIM, "topright")
    draw_text(surf, fonts["small"], TOOL_NAMES[game.tool], (x - 12, TOOL_RECTS[0].bottom + 4), GOLD, "topleft")

    draw_text(surf, fonts["tiny"], "DRAWER", (x - 12, SUPPLY_RECTS[0].y - 15), DIM, "topleft")
    for key, rect in zip(dev.SUPPLIES, SUPPLY_RECTS):
        pygame.draw.rect(surf, CARD_HOT if rect.collidepoint(mouse) else CARD, rect, border_radius=7)
        icon = icons[dev.supply_icon(key)]
        surf.blit(icon, icon.get_rect(center=(rect.centerx, rect.y + 20)))
        draw_text(surf, fonts["tiny"], dev.supply_label(key), (rect.centerx, rect.bottom - 9), GOLD)

    for rect, text, target, color in ((TEST_BUTTON, "TEST", "TEST", (60, 110, 190)),
                                      (HINT_BUTTON, "HINT", "HINT", (120, 96, 190)),
                                      (FINISH_BUTTON, "FINISH", "FINISH", (56, 150, 90))):
        if target == "HINT":
            live = not game.guided
        else:
            live = not game.guided or (step is not None and step.targets == [target])
        draw_button(surf, fonts["font"], rect, text, color, mouse, live)
    draw_text(surf, fonts["tiny"], "T test   H hint   N sound   Esc levels", (x - 12, TEST_BUTTON.bottom + 12), DIM,
              "topleft")


def draw_hud(surf, game, fonts):
    pygame.draw.rect(surf, HUD_BG, (0, 0, WIDTH, HUD_H))
    mid = HUD_H // 2
    draw_text(surf, fonts["big"], "FIXER", (16, mid), GOLD, "midleft")
    draw_text(surf, fonts["font"], game.model["name"] if game.model else game.product["name"], (130, mid), DIM,
              "midleft")
    draw_text(surf, fonts["font"], f"Level {game.level + 1}: {game.level_info()['title']}", (360, mid), TEXT,
              "midleft")
    if game.muted:
        draw_text(surf, fonts["small"], "sound off (N)", (WIDTH - 16, mid), DIM, "midright")

def draw_hint_line(surf, game, fonts, mouse):
    rect = pygame.Rect(0, HEIGHT - HINT_H, PANEL_X, HINT_H)
    pygame.draw.rect(surf, HUD_BG, rect)
    text, color = game.hint_line(mouse)
    lines = wrap(fonts["small"], text, PANEL_X - 32)[:2]
    for i, line in enumerate(lines):
        draw_text(surf, fonts["small"], line, (16, rect.centery + (i - (len(lines) - 1) / 2) * 17), color, "midleft")


def draw_fan_test(surf, game):
    """What the fan does in a power test: a breeze off the blade, a buzzing motor, heat coming off it."""
    fan, symptom, t = game.device, game.test_symptom, game.state_time
    if game.spin_speed > 900 and fan.blade.on:  # a breeze coming off the blade
        air = pygame.Surface(BENCH.size, pygame.SRCALPHA)
        strength = min(1.0, (game.spin_speed - 900) / 500) * (0.4 if symptom == "weak" else 1)
        for k in range(14):
            a = math.radians(-200 + k * 16) + 0.15 * math.sin(t * 2 + k)
            phase = (t * 1.6 + k * 0.37) % 1
            r1 = GRILLE_R + 8 + phase * 70
            p1, p2 = ring_point(a, r1), ring_point(a, r1 + 24)
            pygame.draw.line(air, (255, 255, 255, round(150 * (1 - phase) * strength)),
                             (p1[0] - BENCH.x, p1[1] - BENCH.y), (p2[0] - BENCH.x, p2[1] - BENCH.y), 3)
        surf.blit(air, BENCH.topleft)
    if symptom in ("hum", "hot") and t % 0.2 < 0.1:  # the motor buzzing
        for side in (-1, 1):
            for r in (20, 30):
                x = HEAD[0] + side * (GRILLE_R + 8)
                pygame.draw.arc(surf, WHITE, (x - r, HEAD[1] - r, 2 * r, 2 * r), -0.7 if side > 0 else 2.44,
                                0.7 if side > 0 else 3.84, 2)
    if symptom == "hot":  # heat shimmering off the motor
        for k in range(3):
            x = HEAD[0] - 40 + k * 40
            points = [(x + 6 * math.sin(t * 6 + y * 0.1 + k), HEAD[1] - MOTOR_R - 8 - y) for y in range(0, 44, 4)]
            pygame.draw.lines(surf, (255, 150, 90), False, points, 2)


def draw_test(surf, game, fonts):
    """A power test: the device works (or doesn't) on the bench, and a banner says what it does."""
    dev, symptom, t = game.device, game.test_symptom, game.state_time
    dev.draw_test(surf, game)
    banner = pygame.Rect(14, PIECE_TRAY.y - 6, PANEL_X - 28, 92)
    pygame.draw.rect(surf, (20, 22, 30), banner, border_radius=14)
    pygame.draw.rect(surf, (60, 64, 84), banner, 2, border_radius=14)
    draw_text(surf, fonts["small"], "POWER TEST", (banner.centerx, banner.y + 16), DIM)
    if t > 0.8:
        works = symptom is None
        text = dev.WORKS if works else dev.SYMPTOMS[symptom][1]
        draw_text(surf, fonts["font"], text, (banner.centerx, banner.y + 42), GREEN if works else RED)
        warning = dev.test_warning()
        if warning:
            draw_text(surf, fonts["small"], warning, (banner.centerx, banner.y + 64), GOLD)
    bar = pygame.Rect(banner.centerx - 150, banner.bottom - 12, 300, 5)
    pygame.draw.rect(surf, CARD, bar, border_radius=3)
    pygame.draw.rect(surf, DIM, (bar.x, bar.y, bar.w * min(1, t / TEST_TIME), bar.h), border_radius=3)

def draw_bench(surf, game, fonts, art, mouse):
    dev, step = game.device, game.step()
    surf.blit(art["bench"], BENCH.topleft)
    draw_trays(surf, dev, fonts["small"])
    draw_meter(surf, dev, fonts)
    dev.draw(surf, game, fonts, mouse)
    surf.set_clip(BENCH)
    for flyer in game.flyers:
        FLYER_BODIES[flyer.kind](surf, round(flyer.x), round(flyer.y))
    surf.set_clip(None)
    for p in game.particles:
        p.draw(surf)
    draw_panel(surf, game, fonts, art["icons"], art["tool_icons"], mouse)
    guide = step or (dev.steps[game.hint_step] if game.hint_time > 0 else None)
    if game.state == "bench" and guide:
        draw_guide(surf, game, fonts, guide)
    if game.state == "bench" and game.twist:  # how far round you've turned it
        thing = game.twist[0]
        k = dev.twist_progress(thing)
        ring = pygame.Rect(0, 0, 56, 56)
        ring.center = (thing.x, thing.y)
        if k > 0:
            pygame.draw.arc(surf, GOLD, ring, math.pi / 2 - 2 * math.pi * min(1, k), math.pi / 2, 4)
    for f in game.floats:
        f.draw(surf, fonts["small"])
    draw_hud(surf, game, fonts)
    draw_hint_line(surf, game, fonts, mouse)
    if game.state == "test":
        draw_test(surf, game, fonts)

    # The cursor: the tool you're holding over the bench, or what you're dragging
    on_bench = game.state == "bench" and BENCH.collidepoint(mouse)
    pygame.mouse.set_visible(not on_bench and not game.drag)
    if game.drag:
        draw_dragged(surf, game, mouse, fonts)
    elif on_bench:
        if game.tool == "brush":
            pygame.draw.circle(surf, (230, 230, 230), mouse, SCRUB_RADIUS, 1)
        if game.tool == "magnifier":
            draw_lens(surf, game, mouse)
        else:
            draw_tool(surf, game.tool, *mouse, busy=pygame.mouse.get_pressed()[0])
        if game.hold:
            ring = pygame.Rect(0, 0, 50, 50)
            ring.center = mouse
            pygame.draw.arc(surf, GOLD, ring, math.pi / 2 - 2 * math.pi * min(1, game.hold[1]), math.pi / 2, 4)


def draw_tool(surf, tool, x, y, busy=False):
    """A tool with its working tip at (x, y) and its handle up and to the right."""
    if tool == "hand":
        reach = 7 if busy else 13  # fingers curl up while grabbing
        for i in range(4):
            finger = pygame.Rect(x + i * 6, y + 13 - reach + (3 if i in (0, 3) else 0), 6, reach + 6)
            pygame.draw.rect(surf, SKIN, finger, border_radius=3)
            pygame.draw.rect(surf, SKIN_DARK, finger, 1, border_radius=3)
        pygame.draw.ellipse(surf, SKIN, (x - 9, y + 15, 14, 8))
        pygame.draw.ellipse(surf, SKIN_DARK, (x - 9, y + 15, 14, 8), 1)
        palm = pygame.Rect(x - 1, y + 13, 26, 17)
        pygame.draw.rect(surf, SKIN, palm, border_radius=7)
        pygame.draw.rect(surf, SKIN_DARK, palm, 1, border_radius=7)
    elif tool == "driver":
        pygame.draw.line(surf, METAL, (x, y), (x + 17, y - 17), 4)
        pygame.draw.line(surf, (200, 60, 50), (x + 17, y - 17), (x + 33, y - 33), 11)
        pygame.draw.circle(surf, (200, 60, 50), (x + 33, y - 33), 5)
    elif tool == "cutters":
        pivot = (x + 11, y - 11)
        pygame.draw.line(surf, METAL, (x, y), pivot, 5)
        pygame.draw.line(surf, METAL_DARK, (x + 2, y), pivot, 1)
        for end in ((x + 36, y - 20), (x + 20, y - 36)):
            pygame.draw.line(surf, (210, 60, 50), pivot, end, 7)
        pygame.draw.circle(surf, METAL, pivot, 4)
    elif tool == "crimper":  # pliers with a notched jaw that squeezes a sleeve flat
        pivot = (x + 12, y - 12)
        pygame.draw.line(surf, METAL_DARK, (x, y), pivot, 8)
        pygame.draw.circle(surf, METAL, (x + 3, y - 3), 3)
        for end in ((x + 40, y - 22), (x + 22, y - 40)):
            pygame.draw.line(surf, (240, 200, 40), pivot, end, 7)
            pygame.draw.circle(surf, BLACK, end, 3)
        pygame.draw.circle(surf, METAL, pivot, 4)
    elif tool == "brush":
        pygame.draw.line(surf, (160, 110, 60), (x + 7, y - 7), (x + 30, y - 30), 7)
        pygame.draw.line(surf, METAL, (x + 4, y - 4), (x + 10, y - 10), 11)
        pygame.draw.circle(surf, (236, 214, 160), (x, y), 8)
        for a in range(0, 360, 60):
            a = math.radians(a)
            pygame.draw.line(surf, (190, 160, 110), (x, y), (x + 7 * math.cos(a), y + 7 * math.sin(a)), 1)
    elif tool == "iron":  # a soldering iron: hot tip, metal barrel, heat-proof handle, cable
        pygame.draw.line(surf, METAL_DARK, (x, y), (x + 10, y - 10), 3)
        pygame.draw.circle(surf, (255, 150, 60), (x, y), 2)
        pygame.draw.line(surf, METAL, (x + 10, y - 10), (x + 22, y - 22), 6)
        pygame.draw.line(surf, (60, 110, 200), (x + 22, y - 22), (x + 40, y - 40), 10)
        pygame.draw.lines(surf, (40, 40, 44), False, [(x + 40, y - 40), (x + 46, y - 46), (x + 52, y - 44)], 3)
    elif tool == "magnifier":  # a lens on a handle (over the bench it's drawn as a working lens instead)
        pygame.draw.circle(surf, (170, 210, 240), (x + 12, y - 12), 11)
        pygame.draw.circle(surf, (40, 40, 46), (x + 12, y - 12), 12, 3)
        pygame.draw.line(surf, (120, 80, 50), (x + 21, y - 21), (x + 36, y - 36), 6)
    else:  # the multimeter's probe
        pygame.draw.line(surf, (120, 30, 30), (x + 30, y - 30), (x + 44, y - 24), 2)
        pygame.draw.line(surf, METAL, (x, y), (x + 11, y - 11), 2)
        pygame.draw.line(surf, (210, 50, 50), (x + 11, y - 11), (x + 30, y - 30), 7)


def make_tool_icon(tool):
    """A small picture of a tool for its button."""
    big = pygame.Surface((64, 64), pygame.SRCALPHA)
    draw_tool(big, tool, *((20, 16) if tool == "hand" else (10, 54)))
    box = big.get_bounding_rect()
    scale = min(28 / box.w, 28 / box.h, 1)
    return pygame.transform.smoothscale(big.subsurface(box), (round(box.w * scale), round(box.h * scale)))


def draw_check(surf, x, y, ok):
    pygame.draw.circle(surf, GREEN if ok else (90, 94, 110), (x, y), 9)
    if ok:
        pygame.draw.lines(surf, BLACK, False, [(x - 4, y), (x - 1, y + 4), (x + 5, y - 4)], 2)
    else:
        pygame.draw.line(surf, BLACK, (x - 4, y), (x + 4, y), 2)


def draw_products(surf, game, fonts, art, mouse):
    """The first screen: a card for each thing you can learn to fix."""
    surf.fill(BG)
    draw_text(surf, fonts["big"], "FIXER", (30, 22), GOLD, "topleft")
    draw_text(surf, fonts["font"], "Repair school", (150, 31), TEXT, "topleft")
    draw_text(surf, fonts["small"], "What do you want to learn to fix? Pick one:", (30, 72), DIM, "topleft")
    for i, product in enumerate(PRODUCTS):
        rect = product_rect(i)
        hot = rect.collidepoint(mouse)
        pygame.draw.rect(surf, CARD_HOT if hot else CARD, rect, border_radius=14)
        pygame.draw.rect(surf, product["color"], (rect.x, rect.y, rect.w, 7), border_top_left_radius=14,
                         border_top_right_radius=14)
        if hot:
            pygame.draw.rect(surf, product["color"], rect, 2, border_radius=14)
        window = pygame.Rect(rect.x + 12, rect.y + 18, rect.w - 24, 108)
        pygame.draw.rect(surf, PANEL, window, border_radius=10)
        icon = art["products"][product["key"]]
        surf.blit(icon, icon.get_rect(center=window.center))
        draw_text(surf, fonts["font"], product["name"], (rect.centerx, rect.y + 142), TEXT)
        for k, line in enumerate(wrap(fonts["tiny"], product["blurb"], rect.w - 24)[:2]):
            draw_text(surf, fonts["tiny"], line, (rect.centerx, rect.y + 163 + k * 14), DIM)
        kinds = f"{len(product['models'])} types  ·  " if product.get("models") else ""
        draw_text(surf, fonts["tiny"], f"{kinds}{len(product['levels'])} levels", (rect.centerx, rect.bottom - 18),
                  MUTED)
    draw_text(surf, fonts["small"], "More things to fix are on the way.",
              (WIDTH // 2, product_rect(len(PRODUCTS) - 1).bottom + 28), MUTED)
    draw_text(surf, fonts["small"], "N sound   Esc quit", (30, 621), DIM, "midleft")


def draw_models(surf, game, fonts, art, mouse):
    """Pick which type to fix: a desk, stand or wall fan, or a pocket, outdoor or retro radio."""
    surf.fill(BG)
    product = game.product
    models = product["models"]
    draw_text(surf, fonts["big"], "FIXER", (30, 22), GOLD, "topleft")
    draw_text(surf, fonts["font"], product["name"], (150, 31), TEXT, "topleft")
    draw_text(surf, fonts["small"], f"Which kind of {product['noun']} do you want to fix? Pick one:", (30, 72), DIM,
              "topleft")
    for i, model in enumerate(models):
        rect = model_rect(i, len(models))
        hot = rect.collidepoint(mouse)
        pygame.draw.rect(surf, CARD_HOT if hot else CARD, rect, border_radius=14)
        pygame.draw.rect(surf, product["color"], (rect.x, rect.y, rect.w, 7), border_top_left_radius=14,
                         border_top_right_radius=14)
        if hot:
            pygame.draw.rect(surf, product["color"], rect, 2, border_radius=14)
        window = pygame.Rect(rect.x + 12, rect.y + 18, rect.w - 24, 172)
        pygame.draw.rect(surf, PANEL, window, border_radius=10)
        icon = art["models"][model["key"]]
        surf.blit(icon, icon.get_rect(center=window.center))
        draw_text(surf, fonts["font"], model["name"], (rect.centerx, rect.y + 210), TEXT)
        for k, line in enumerate(wrap(fonts["small"], model["about"], rect.w - 28)[:5]):
            draw_text(surf, fonts["small"], line, (rect.x + 14, rect.y + 228 + k * 17), DIM, "topleft")
        draw_text(surf, fonts["tiny"], product["facts"](model), (rect.centerx, rect.bottom - 18), GOLD)
    for k, line in enumerate(product["same"]):
        draw_text(surf, fonts["small"], line, (WIDTH // 2, 486 + k * 20), DIM)
    draw_button(surf, fonts["font"], BACK_BUTTON, "BACK (Esc)", (70, 90, 150), mouse)


def draw_levels(surf, game, fonts, mouse):
    """A product's levels, each with its GUIDED and ON MY OWN buttons."""
    surf.fill(BG)
    product = game.product
    device = DEVICES[product["key"]]
    draw_text(surf, fonts["big"], "FIXER", (30, 22), GOLD, "topleft")
    draw_text(surf, fonts["font"], game.model["name"] if game.model else product["name"], (150, 31), TEXT, "topleft")
    draw_text(surf, fonts["small"], product["intro"], (30, 72), DIM, "topleft")
    for i, level in enumerate(product["levels"]):
        rect = CARD_RECTS[i]
        pygame.draw.rect(surf, CARD_HOT if rect.collidepoint(mouse) else CARD, rect, border_radius=12)
        pygame.draw.rect(surf, product["color"], (rect.x, rect.y, 7, rect.h), border_top_left_radius=12,
                         border_bottom_left_radius=12)
        pygame.draw.circle(surf, PANEL, (rect.x + 34, rect.y + 28), 17)
        draw_text(surf, fonts["font"], str(i + 1), (rect.x + 34, rect.y + 28), GOLD)
        title = draw_text(surf, fonts["font"], level["title"], (rect.x + 60, rect.y + 18), TEXT, "topleft")
        for k in range(5):  # how hard it is
            pygame.draw.circle(surf, GOLD if k < level["difficulty"] else (80, 84, 100),
                               (title.right + 16 + k * 13, title.centery), 4)
        if level["faults"]:
            quote = f'"{device.SYMPTOMS[device.FAULT_SYMPTOM[level["faults"][0]]][0]}"'
        else:
            quote = '"Something\'s wrong with it... but what?"'
        for k, line in enumerate(wrap(fonts["small"], quote, rect.w - 76)[:2]):
            draw_text(surf, fonts["small"], line, (rect.x + 60, rect.y + 44 + k * 17), DIM, "topleft")
        draw_text(surf, fonts["tiny"], wrap(fonts["tiny"], "Learn: " + level["learn"], rect.w - 74)[0],
                  (rect.x + 60, rect.y + 82), TEXT, "topleft")
        guided, solo = card_buttons(i, level)
        if guided:
            draw_button(surf, fonts["small"], guided, "GUIDED", (70, 90, 150), mouse)
        draw_button(surf, fonts["small"], solo, "ON MY OWN", (56, 150, 90), mouse)
    draw_button(surf, fonts["font"], BACK_BUTTON, "BACK (Esc)", (70, 90, 150), mouse)
    for k, line in enumerate(wrap(fonts["small"], product["safety"], WIDTH - 300)):
        draw_text(surf, fonts["small"], line, (270, 604 + k * 17), DIM, "topleft")


def draw_result(surf, game, fonts, mouse):
    dim(surf, alpha=225)
    r, dev, level = game.result, game.device, game.level_info()
    box = RESULT_BOX
    pygame.draw.rect(surf, PANEL, box, border_radius=16)
    pygame.draw.rect(surf, GREEN if r["fixed"] else RED, box, 2, border_radius=16)
    mode = "Guided" if r["guided"] else "On my own"
    draw_text(surf, fonts["big"], "FIXED!" if r["fixed"] else "STILL BROKEN", (box.centerx, box.y + 34),
              GREEN if r["fixed"] else RED)
    draw_text(surf, fonts["small"], f"Level {game.level + 1}: {level['title']}  ·  {mode}", (box.centerx, box.y + 66),
              DIM)
    if not level["faults"]:
        draw_text(surf, fonts["small"], "The problem was: " + " and ".join(dev.FAULT_NAMES[f] for f in r["faults"]),
                  (box.centerx, box.y + 86), GOLD)
    for i in range(3):
        draw_star(surf, box.centerx - 50 + i * 50, box.y + 118, 18, i < r["stars"])

    # Left: how this repair went
    x, y = box.x + 36, box.y + 156
    draw_text(surf, fonts["small"], "THIS REPAIR", (x, y), DIM, "topleft")
    checks = [("It works", r["fixed"]), ("Safe and tidy: no mistakes, nothing left undone",
                                         r["fixed"] and not r["safety"] and not r["wrong"] and not r["issues"]),
              ("On your own, no hints", r["fixed"] and not r["guided"] and not r["hints"])]
    for i, (text, ok) in enumerate(checks):
        draw_check(surf, x + 9, y + 34 + i * 24, ok)
        draw_text(surf, fonts["small"], text, (x + 26, y + 34 + i * 24), TEXT if ok else DIM, "midleft")
    y += 112
    on_time = r["time"] <= r["par"]
    draw_text(surf, fonts["font"], f"Time {clock_text(r['time'])}", (x, y), TEXT, "topleft")
    draw_text(surf, fonts["small"], "inside the target time" if on_time else f"target {clock_text(r['par'])}",
              (x + 130, y + 2), GREEN if on_time else DIM, "topleft")
    draw_text(surf, fonts["font"], f"Score {r['score']}", (x, y + 26), TEXT, "topleft")
    draw_text(surf, fonts["small"], "out of 100", (x + 130, y + 28), DIM, "topleft")
    if r["guided"] and r["fixed"]:
        note = "Now try it ON MY OWN: no glowing outlines this time, just the list of steps."
        for i, line in enumerate(wrap(fonts["small"], note, 400)):
            draw_text(surf, fonts["small"], line, (x, y + 70 + i * 18), GOLD, "topleft")

    # Right: what to watch next time
    x, y = box.x + 486, box.y + 156
    draw_text(surf, fonts["small"], "WHAT TO WATCH NEXT TIME", (x, y), DIM, "topleft")
    lines = []
    if not r["fixed"]:
        lines.append((f"Switched on, it still does this: {dev.SYMPTOMS[r['symptom']][1]}", RED))
    for kind, n in r["mistakes"].items():
        lines.append((dev.MISTAKES[kind][1] + (f" (x{n})" if n > 1 else "") + ". " + dev.MISTAKES[kind][2], RED))
    lines += [(issue, GOLD) for issue in r["issues"]]
    if r["hints"]:
        lines.append((f"Used {r['hints']} hint{'s' if r['hints'] > 1 else ''}", DIM))
    if not lines:
        lines = [("Nothing! A clean, careful repair.", GREEN)]
    rows = []
    for text, color in lines:
        rows += [(line, color) for line in wrap(fonts["small"], text, 400)]
    if len(rows) > 16:
        rows = rows[:15] + [("...and more", DIM)]
    for i, (line, color) in enumerate(rows):
        draw_text(surf, fonts["small"], line, (x, y + 24 + i * 18), color, "topleft")

    tip = pygame.Rect(box.x + 30, box.bottom - 126, box.w - 60, 60)
    pygame.draw.rect(surf, (44, 50, 68), tip, border_radius=10)
    draw_text(surf, fonts["tiny"], f"REAL {game.product['noun'].upper()} TIP", (tip.x + 14, tip.y + 8), GOLD, "topleft")
    for i, line in enumerate(wrap(fonts["small"], level["tip"], tip.w - 28)[:2]):
        draw_text(surf, fonts["small"], line, (tip.x + 14, tip.y + 24 + i * 17), TEXT, "topleft")
    live = game.state_time > RESULT_DELAY
    draw_button(surf, fonts["font"], RETRY_BUTTON, "TRY AGAIN (R)", (70, 90, 150), mouse, live)
    draw_button(surf, fonts["font"], LEVELS_BUTTON, "LEVELS (Enter)", (56, 150, 90), mouse, live)


def dim(surf, rect=None, alpha=170):
    rect = rect or surf.get_rect()
    overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
    overlay.fill((10, 12, 18, alpha))
    surf.blit(overlay, rect.topleft)


def draw(surf, game, fonts, art, mouse):
    if game.state == "products":
        pygame.mouse.set_visible(True)
        draw_products(surf, game, fonts, art, mouse)
    elif game.state == "models":
        pygame.mouse.set_visible(True)
        draw_models(surf, game, fonts, art, mouse)
    elif game.state == "levels":
        pygame.mouse.set_visible(True)
        draw_levels(surf, game, fonts, mouse)
    else:
        draw_bench(surf, game, fonts, art, mouse)
        if game.state == "result":
            pygame.mouse.set_visible(True)
            draw_result(surf, game, fonts, mouse)


def make_art():
    """Everything drawn once at the start: the bench, and the icons for tools, supplies and products."""
    icons = {key: make_icon(body) for key, body in SUPPLY_BODIES.items()}
    icons["cap"] = make_icon(lambda s, x, y: draw_cap(s, x, y, 0, False))
    return dict(bench=make_bench(), tool_icons={tool: make_tool_icon(tool) for tool in TOOL_NAMES}, icons=icons,
                products={product["key"]: make_product_icon(product["key"]) for product in PRODUCTS},
                models={model["key"]: make_model_icon(model) for product in PRODUCTS
                        for model in product.get("models", [])})


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Fixer: repair school")
    canvas = pygame.Surface((WIDTH, HEIGHT))  # drawn here, then shown shifted by the screen shake
    clock = pygame.time.Clock()
    fonts = {
        "tiny": pygame.font.SysFont("consolas", 12, bold=True),
        "small": pygame.font.SysFont("consolas", 15, bold=True),
        "font": pygame.font.SysFont("consolas", 18, bold=True),
        "big": pygame.font.SysFont("consolas", 30, bold=True),
        "huge": pygame.font.SysFont("consolas", 64, bold=True),
    }
    art = make_art()
    game = Game()

    while True:
        dt = min(clock.tick(60) / 1000, 1 / 30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if not game.back():
                        pygame.quit()
                        sys.exit()
                elif event.key == pygame.K_n:
                    game.toggle_sound()
                else:
                    game.key(event.key)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.press(event.pos)
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                game.release(event.pos)
            if event.type == pygame.MOUSEWHEEL:
                game.wheel(-event.y)

        mouse = pygame.mouse.get_pos()
        game.update(dt, mouse)
        draw(canvas, game, fonts, art, mouse)
        screen.fill(BLACK)
        screen.blit(canvas, shake_offset(game.shake))
        pygame.display.flip()


if __name__ == "__main__":
    main()
