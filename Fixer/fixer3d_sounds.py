"""The sounds of Fixer 3D, made in code: no sound files come with the game.

You hear the tools hundreds of times in a game, so their sounds are made to be easy on the ear: short, soft and
round, like tapping things on a wooden desk. Each one is a gentle knock on a real kind of thing: anything you tap
rings at a handful of its own notes, each dying away at its own rate, so each object here is a short list of them
(a keycap's are a soft, hollow "pok", a switch's a little higher, the case's low and deep). The knock is a soft
one, so only the lower, rounder notes ring. Things sliding, like the brush, are a smooth hush of air, with no
grit in it. The sounds you hear over and over come in a few takes, each a little different, so a hundred keycaps
don't sound like one keycap a hundred times.

They're written as .wav files into a folder the first time the game runs, and loaded from there after that. They
take a few seconds to make, so the game runs this file on its own, in another process, while you play:

    python fixer3d_sounds.py FOLDER

Only the standard library is used, so it runs anywhere Python does.
"""
import math
import os
import random
import sys
import wave
from array import array

RATE = 44100  # for the sound effects
SLOW_RATE = 16000  # for the music and the rain: they're soft, so they don't need the high notes
VERSION = 4  # bump to make them all again
TAKES = 3  # how many takes there are of the sounds you hear most


def hz(note):
    """The frequency of a MIDI note number (60 is middle C)."""
    return 440 * 2 ** ((note - 69) / 12)


def blank(seconds, rate=RATE):
    return [0.0] * int(seconds * rate)


# ---- soft knocks, and a hush of air ----

def strike(width, rate=RATE):
    """A tap that rings an object: a smooth bump `width` seconds long (adding up to 1). A slow one (a millisecond
    or so) is a soft tap: it rings only the lower, rounder notes."""
    n = max(1, int(width * rate))
    bump = [0.5 - 0.5 * math.cos(2 * math.pi * (k + 0.5) / n) for k in range(n)]
    total = sum(bump)
    return [v / total for v in bump]


def ring(buf, at, push, modes, gain=1.0, detune=1.0, rate=RATE):
    """Ring an object (its notes: frequency, seconds to die away, how loud) with a push, into buf at `at` seconds.
    Each note is a resonator: pushed, it rings at its frequency and dies away, as a tapped thing does."""
    start = int(at * rate)
    room = len(buf) - start
    p = len(push)
    for freq, decay, level in modes:
        f = freq * detune
        if f >= rate * 0.45:
            continue
        w = 2 * math.pi * f / rate
        r = math.exp(-1.0 / (decay * rate))
        a1, a2 = 2 * r * math.cos(w), -r * r
        g = gain * level * math.sin(w)  # so a push that adds up to 1 rings it at about `level`
        y1 = y2 = 0.0
        for k in range(min(room, p + int(decay * 7 * rate))):
            y = a1 * y1 + a2 * y2 + (push[k] if k < p else 0.0)
            buf[start + k] += g * y
            y2, y1 = y1, y


def knock(buf, at, modes, gain=1.0, soft=0.001, detune=1.0):
    """A soft tap on something: `soft` is how long the tap lasts (longer is softer)."""
    ring(buf, at, strike(soft), modes, gain, detune)


def swish(buf, at, length, amp, seed=0, low=800, high=3000, rate=RATE):
    """A smooth hush, like a soft brush or a part sliding free: noise between `low` and `high` Hz (gently, both
    ways), swelling in and fading out over `length` seconds."""
    rnd = random.Random(seed)
    start = int(at * rate)
    n = max(0, min(len(buf) - start, int(length * rate)))
    a_hi = 1 - math.exp(-2 * math.pi * high / rate)
    a_lo = 1 - math.exp(-2 * math.pi * low / rate)
    h1 = h2 = lo = 0.0
    for k in range(n):
        h1 += a_hi * (rnd.uniform(-1, 1) - h1)
        h2 += a_hi * (h1 - h2)  # twice, for a softer top
        lo += a_lo * (h2 - lo)
        buf[start + k] += amp * math.sin(math.pi * k / n) ** 1.5 * (h2 - lo)


def warm(buf, cutoff=5000, rate=RATE):
    """Roll off the highest notes, gently: softer and cozier."""
    a = 1 - math.exp(-2 * math.pi * cutoff / rate)
    y = 0.0
    for k in range(len(buf)):
        y += a * (buf[k] - y)
        buf[k] = y
    return buf


def fade_out(buf, seconds=0.012, rate=RATE):
    """Ease the very end down to nothing, so a sound never stops with a click."""
    n = min(len(buf), int(seconds * rate))
    for k in range(n):
        buf[len(buf) - n + k] *= 1 - (k + 1) / n


def take(seed, v, spread=0.035):
    """Take v of a sound: its own random numbers, and the object a hair higher or lower (no two are quite alike)."""
    rnd = random.Random(seed * 31 + v)
    return rnd, 1 + rnd.uniform(-spread, spread)


# What things ring at, tapped softly: (frequency, seconds to die away, how loud)
CAP = [(640, 0.028, 1.0), (1290, 0.014, 0.3), (2150, 0.007, 0.1)]  # a keycap, hollow plastic: a round "pok"
SWITCH = [(900, 0.02, 1.0), (1830, 0.01, 0.28), (3000, 0.005, 0.08)]  # a switch: smaller, a little higher
CASE = [(220, 0.04, 1.0), (520, 0.026, 0.5), (1000, 0.014, 0.2)]  # the case: low and deep
PLATE = [(760, 0.03, 0.6), (1350, 0.022, 0.4), (2150, 0.014, 0.2)]  # the steel plate, quietened by its foam
BOARD = [(480, 0.02, 1.0), (1150, 0.012, 0.35), (2300, 0.006, 0.12)]  # a circuit board
RUBBER = [(200, 0.016, 1.0), (450, 0.01, 0.35)]
PLUG = [(1500, 0.012, 1.0), (2600, 0.007, 0.3)]  # a cable's plug
RATCHET = [(1650, 0.011, 1.0), (2800, 0.005, 0.22)]  # the screwdriver's ratchet
CLICK = [(2300, 0.008, 0.5), (3600, 0.006, 1.0), (5200, 0.004, 0.35)]  # a clicky switch's little jacket
TRAY = [(330, 0.03, 1.0), (800, 0.018, 0.45), (1500, 0.009, 0.15)]  # the wooden keycap tray
TIN = [(1250, 0.045, 0.6), (2050, 0.03, 0.3), (3200, 0.018, 0.1)]  # the switch tin (felt inside)
WOOD = [(620, 0.018, 1.0), (1710, 0.01, 0.4), (3100, 0.006, 0.15)]  # a small wooden button
BLOCK = [(380, 0.03, 1.0), (1050, 0.016, 0.45), (2300, 0.008, 0.15)]  # knocking on the desk
CERAMIC = [(1960, 0.07, 0.6), (3420, 0.045, 0.3), (5300, 0.03, 0.1)]  # a little paint pot

# The big parts, by what they're made of: (what rings, how soft a tap)
MATERIALS = {"plastic": (CASE, 0.002), "metal": (PLATE, 0.0015), "board": (BOARD, 0.0015),
             "foam": (RUBBER, 0.006), "rubber": (RUBBER, 0.003), "cable": (PLUG, 0.0009)}


# ---- keycaps and switches ----

def effect_pop(v=0):
    """A keycap pulled off: a soft "pok" as it comes free, and the stem settling just after."""
    rnd, d = take(1, v)
    b = blank(0.2)
    knock(b, 0, CAP, 1.0, 0.0011, d)
    knock(b, 0.011 + rnd.uniform(0, 0.004), SWITCH, 0.15, 0.0009, d * 1.3)
    return warm(b)


def effect_clack(v=0):
    """A keycap pushed onto its switch: a slightly deeper, firmer "tok", and the keyboard under it."""
    _, d = take(2, v)
    b = blank(0.22)
    knock(b, 0, CAP, 1.0, 0.001, d * 0.88)
    knock(b, 0, CASE, 0.3, 0.002)
    return warm(b)


def effect_snick(v=0):
    """A switch pulled out of the plate: "tu-tok", the puller taking hold and the switch coming out."""
    rnd, d = take(3, v)
    b = blank(0.25)
    knock(b, 0, SWITCH, 0.5, 0.0012, d)
    knock(b, 0.032 + rnd.uniform(0, 0.01), SWITCH, 1.0, 0.001, d * 1.12)
    return warm(b)


def effect_switch_in(v=0):
    """A switch pressed into the plate: its two clips settle in, one just after the other."""
    rnd, d = take(4, v)
    b = blank(0.22)
    knock(b, 0, SWITCH, 1.0, 0.001, d)
    knock(b, 0.008 + rnd.uniform(0, 0.003), SWITCH, 0.55, 0.001, d * 1.06)
    knock(b, 0, CASE, 0.2, 0.002)
    return warm(b)


def landing(seed, v, small, big):
    """Something small set down in something: a soft tap, and a little bounce."""
    rnd, d = take(seed, v)
    b = blank(0.3)
    t, level = 0.0, 1.0
    for _ in range(2):
        knock(b, t, small, level, 0.0012, d)
        knock(b, t, big, level * 0.7, 0.0015)
        t += 0.045 + rnd.uniform(0, 0.015)
        level *= 0.3
    return warm(b)


def effect_drop_cap(v=0):  # a keycap landing in the wooden tray
    return landing(5, v, CAP, TRAY)


def effect_drop_switch(v=0):  # a switch landing in the tin
    return landing(6, v, SWITCH, TIN)


def effect_press(kind):
    """A key pressed on a switch of this kind. Red is linear: straight down, a deep "thock" at the bottom. Brown is
    tactile: a little bump on the way down first. Blue is clicky: its jacket clicks just before the bottom. Pink
    is silent: a damper takes the hit, so there's only a soft, low thud."""
    def make(v=0):
        rnd, d = take(10 + "red brown blue pink".split().index(kind), v, 0.025)
        b = blank(0.25)
        if kind == "pink":
            knock(b, 0, CAP, 0.6, 0.003, d)
            knock(b, 0, CASE, 0.5, 0.004)
            return warm(b, 3000)
        bottom = 0.0
        if kind == "blue":
            knock(b, 0, CLICK, 1.0, 0.0003, d)
            bottom = 0.013 + rnd.uniform(0, 0.003)
        elif kind == "brown":
            knock(b, 0, SWITCH, 0.3, 0.001, d)
            bottom = 0.011 + rnd.uniform(0, 0.003)
        knock(b, bottom, CAP, 1.0, 0.0012, d)
        knock(b, bottom, CASE, 0.4, 0.002)
        knock(b, bottom, PLATE, 0.12, 0.0015, d)
        return warm(b, 6000 if kind == "blue" else 5000)
    return make


# ---- the big parts, the screws, the brush ----

def effect_lift(material):
    """A big part lifted off: a soft hush as it slides free, and a gentle tap as it lets go. Foam just whispers
    off; a cable's plug comes out with a small click."""
    modes, soft = MATERIALS[material]

    def make(v=0):
        b = blank(0.35)
        if material == "cable":
            knock(b, 0, PLUG, 1.0, soft)
            return warm(b)
        swish(b, 0, 0.2 if material == "foam" else 0.14, 0.9, seed=2, low=300, high=1600)
        if material != "foam":
            knock(b, 0.11, modes, 0.5, soft)
        return warm(b, 4000)
    return make


def effect_put(material):
    """A big part set down on the keyboard: a soft tap of its own, and the case under it answers."""
    modes, soft = MATERIALS[material]

    def make(v=0):
        b = blank(0.3)
        if material == "cable":  # the plug pushed in: two small clicks as it goes home
            knock(b, 0, PLUG, 1.0, soft)
            knock(b, 0.006, PLUG, 0.5, soft, 1.08)
            return warm(b)
        knock(b, 0, modes, 1.0, soft)
        knock(b, 0, CASE, 0.15 if material == "plastic" else 0.3, 0.003)
        return warm(b, 4000 if material in ("foam", "rubber") else 5000)
    return make


def effect_screw(out):
    """The screwdriver turning a screw out (or in): the soft, steady "tk-tk-tk" of its ratchet, a little firmer at
    the start as a screw comes loose."""
    def make(v=0):
        rnd, d = take(20 + out, v, 0.02)
        b = blank(0.55)
        for k in range(5):
            t = k * 0.088 + rnd.uniform(0, 0.006)
            level = (1.0 if out and k == 0 else 0.8) * 0.93 ** k
            knock(b, t, RATCHET, level, 0.0009, d * (1.015 if k % 2 else 0.985))
            knock(b, t, CASE, level * 0.08, 0.002)
        return warm(b, 4500)
    return make


def effect_brush(v=0):
    """A stroke of a soft brush: a smooth "shff"."""
    rnd, _ = take(30, v)
    b = blank(0.28)
    swish(b, 0, 0.16 + rnd.uniform(0, 0.05), 1.0, seed=v, low=900 + rnd.uniform(0, 300), high=3200)
    return warm(b, 5000)


def effect_turn(v=0):
    """The keyboard turned over in your hands: a soft hush as it moves."""
    b = blank(0.32)
    swish(b, 0, 0.26, 1.0, seed=40, low=250, high=1200)
    return b


# ---- the screen's buttons, and the rewards ----

def effect_ui(v=0):  # a button: a small wooden one
    b = blank(0.15)
    knock(b, 0, WOOD, 1.0, 0.0009)
    return warm(b)


def effect_hover(v=0):  # the mouse over a button: the faintest tick
    b = blank(0.08)
    knock(b, 0, [(2000, 0.005, 1.0), (3400, 0.003, 0.3)], 1.0, 0.0006)
    return warm(b)


def effect_paint(v=0):  # a colour picked: a tap on a little paint pot
    b = blank(0.4)
    knock(b, 0, CERAMIC, 1.0, 0.0008)
    return warm(b)


def effect_nope(v=0):  # that won't work: two soft knocks on the desk, the second lower
    b = blank(0.4)
    knock(b, 0, BLOCK, 1.0, 0.0015)
    knock(b, 0.13, BLOCK, 0.8, 0.0015, 0.84)
    return warm(b)


def tone(buf, at, freq, decay, amp, rate=RATE, attack=0.002, partials=((1, 1.0),), length=None):
    """Add a note to buf: a sine wave (and overtones) starting at `at` seconds and dying away over about `decay`."""
    start = int(at * rate)
    n = max(0, min(len(buf) - start, int((length if length else decay * 6) * rate)))
    step = 2 * math.pi / rate
    phases = [0.0] * len(partials)
    for k in range(n):
        t = k / rate
        env = amp * (t / attack if t < attack else 1.0) * math.exp(-t / decay)
        s = 0.0
        for j, (mult, a) in enumerate(partials):
            phases[j] += step * freq * mult
            s += a * math.sin(phases[j])
        buf[start + k] += env * s


def pad(buf, at, length, freq, amp, rate):
    """A soft held note that swells in and fades out, two voices a hair apart so it shimmers."""
    start = int(at * rate)
    n = max(0, min(len(buf) - start, int(length * rate)))
    w1 = 2 * math.pi * freq / rate
    w2 = w1 * 1.004
    for k in range(n):
        t = k / rate
        env = amp * min(1.0, t / 0.6, (length - t) / 0.8)
        buf[start + k] += env * (math.sin(w1 * k) + 0.5 * math.sin(w2 * k))


def bells(notes, gap, decay=0.5, amp=0.35):
    b = blank(gap * len(notes) + decay * 5)
    for i, note in enumerate(notes):
        tone(b, i * gap, hz(note), decay, amp, attack=0.004, partials=((1, 1), (2, 0.25), (3.01, 0.08)))
    return b


def whoosh(seconds=0.3, amp=0.5, seed=13, bright=0.25):
    """Air: noise whose brightness swells and falls."""
    rnd = random.Random(seed)
    b = blank(seconds)
    low = 0.0
    n = len(b)
    for k in range(n):
        s = k / n
        low += (0.03 + bright * math.sin(math.pi * s)) * (rnd.uniform(-1, 1) - low)
        b[k] = amp * math.sin(math.pi * s) ** 1.5 * low
    return b


def effect_swap(v=0):  # the showcase changing keyboard
    b = whoosh(0.22, 0.35, seed=15)
    tone(b, 0.05, hz(84), 0.12, 0.12, partials=((1, 1), (2, 0.2)))
    return b


def effect_fanfare(v=0):  # it's back together
    b = bells([67, 72, 76, 79, 84, 88], 0.075, 0.7, 0.3)
    for note in (60, 64, 67, 72):
        tone(b, 0.5, hz(note), 0.9, 0.12, attack=0.01, partials=((1, 1), (2, 0.2)))
    return b


# name: (how to make it, how many takes)
EFFECTS = {
    "pop": (effect_pop, TAKES), "clack": (effect_clack, TAKES), "snick": (effect_snick, TAKES),
    "switch_in": (effect_switch_in, TAKES), "drop_cap": (effect_drop_cap, TAKES),
    "drop_switch": (effect_drop_switch, TAKES), "brush": (effect_brush, TAKES),
    **{f"press_{kind}": (effect_press(kind), TAKES) for kind in ("red", "brown", "blue", "pink")},
    **{f"lift_{m}": (effect_lift(m), 1) for m in MATERIALS},
    **{f"put_{m}": (effect_put(m), 1) for m in MATERIALS},
    "screw_out": (effect_screw(True), 2), "screw_in": (effect_screw(False), 2),
    "turn": (effect_turn, 1), "ui": (effect_ui, 1), "hover": (effect_hover, 1), "paint": (effect_paint, 1),
    "nope": (effect_nope, 1), "swap": (effect_swap, 1), "fanfare": (effect_fanfare, 1),
    "chime": (lambda v=0: bells([72, 76, 79, 84], 0.09), 1),
    "sparkle": (lambda v=0: bells([88, 91, 95, 100], 0.05, 0.25, 0.22), 1),
}


def files(name):
    """The files a sound's takes are kept in (one name for a sound with only one take)."""
    takes = EFFECTS[name][1]
    return [name] if takes == 1 else [f"{name}~{k}" for k in range(takes)]


ALL_FILES = [f for name in EFFECTS for f in files(name)]


# ---- the music and the rain ----

def make_rain(rate=SLOW_RATE, seconds=16.0):
    """Soft rain on a window: a hush of noise, a low rumble, and drops; it loops without a seam."""
    rnd = random.Random(21)
    n, fade = int(seconds * rate), int(1.0 * rate)
    buf = [0.0] * (n + fade)
    low = rumble = 0.0
    for k in range(len(buf)):
        x = rnd.uniform(-1, 1)
        low += 0.18 * (x - low)
        rumble = rumble * 0.996 + x * 0.012
        buf[k] = (low * 0.35 + rumble * 0.9) * (0.8 + 0.2 * math.sin(2 * math.pi * k / rate / 6.3))
    for _ in range(int(seconds * 22)):
        tone(buf, rnd.uniform(0, seconds + 0.9), rnd.uniform(1800, 4600), rnd.uniform(0.003, 0.009),
             rnd.uniform(0.03, 0.12), rate=rate)
    for k in range(fade):  # what comes after the end fades in over the start, so the loop joins up
        a = k / fade
        buf[k] = buf[k] * a + buf[n + k] * (1 - a)
    return buf[:n]


def make_music(rate=SLOW_RATE):
    """A slow, gentle loop: a soft pad and bass under a music-box tune that wanders round the chords."""
    beat = 60 / 70
    bar = 4 * beat
    chords = [(41, (53, 57, 60, 64)), (40, (52, 55, 59, 62)), (38, (50, 53, 57, 60)), (36, (48, 52, 55, 59)),
              (41, (53, 57, 60, 64)), (40, (52, 55, 59, 62)), (38, (50, 53, 57, 62)), (43, (50, 55, 59, 62))]
    n = int(len(chords) * bar * rate)
    buf = [0.0] * (n + 3 * rate)
    rnd = random.Random(11)
    tune = [72, 74, 76, 79, 81, 84]
    for i, (root, chord) in enumerate(chords):
        t0 = i * bar
        tone(buf, t0, hz(root), 1.2, 0.2, rate, attack=0.01, partials=((1, 1), (2, 0.3)), length=bar)
        tone(buf, t0 + 2 * beat, hz(root + 12), 0.7, 0.07, rate, attack=0.01, length=2 * beat)
        for note in chord:
            pad(buf, t0, bar + 0.8, hz(note), 0.03, rate)
        in_chord = {c % 12 for c in chord}
        for slot in range(8):
            if rnd.random() < (0.6 if slot % 2 == 0 else 0.22):
                pool = [m for m in tune if m % 12 in in_chord] if rnd.random() < 0.75 else tune
                tone(buf, t0 + slot * beat / 2, hz(rnd.choice(pool or tune)), 0.5, 0.12, rate, attack=0.003,
                     partials=((1, 1), (2, 0.16), (3, 0.05)), length=2.0)
    for k in range(n, len(buf)):  # the notes still ringing at the end ring on over the start
        buf[k - n] += buf[k]
    buf = buf[:n]
    for delay, gain in ((int(0.37 * rate), 0.28), (int(0.61 * rate), 0.16)):  # a soft echo, wrapping round too
        src = buf[:]
        for k in range(n):
            buf[k] += gain * src[k - delay]
    return buf


# ---- writing them out ----

def path(folder, name):
    return os.path.join(folder, f"{name}.wav")


def write_wav(file, samples, rate=RATE, peak=0.9):
    top = max(1e-9, max(abs(s) for s in samples))
    scale = peak / top * 32767
    data = array("h", (int(s * scale) for s in samples))
    part = file + ".part"  # written whole, then renamed: the game never loads half a file
    with wave.open(part, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())
    os.replace(part, file)


def make_effects(folder):
    """Make any sound effects not made yet (a few seconds the first time, nothing after that)."""
    os.makedirs(folder, exist_ok=True)
    for name, (make, _) in EFFECTS.items():
        for v, file in enumerate(files(name)):
            if not os.path.exists(path(folder, file)):
                samples = make(v)
                fade_out(samples)
                write_wav(path(folder, file), samples)


def make_ambience(folder):
    os.makedirs(folder, exist_ok=True)
    for name, make in (("rain", make_rain), ("music", make_music)):
        if not os.path.exists(path(folder, name)):
            write_wav(path(folder, name), make(), SLOW_RATE, peak=0.8)


if __name__ == "__main__":
    make_effects(sys.argv[1])
    make_ambience(sys.argv[1])
