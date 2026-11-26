"""Sounds, made in code: there are no sound files.

A rifle shot is built from noise and a low tone, each fading at its own pace: a sharp crack,
the heavier report behind it, a thump, and a short echo. A tank's main gun firing is a deep
boom, and its shell bursting a duller bang with a long rumble, made the same way. Each of a few takes is made from its
own noise, and slightly higher or lower, so a burst of fire doesn't sound like one sound over
and over. Shots play quietly, and how quietly goes with the camera: loudest (and still not
loud) zoomed all the way in, quieter as it zooms out, and very low zoomed all the way out.
They're quieter, too, the further they are from where the camera looks, and come from the
left or right as they are on the screen.
"""
import array
import math
import random

import pygame

RATE = 22050           # samples a second asked of the mixer (it may give another; sounds are made for what it gives)
TAKES = 4              # how many takes of a rifle shot there are, to choose from
NEW_A_FRAME = 3        # the most shots that start sounding in one frame (a volley sounds as a few)
HEARD_TO = 40.0        # tiles from where the camera looks at which a shot can no longer be heard
LOUD_FAR = 0.01        # how loud a shot right where the camera looks is, the camera zoomed all the way out (very low)...
LOUD_NEAR = 0.08       # ...and zoomed all the way in (between, it falls away faster as the camera zooms out: see rifle_shot)
BOOM_HEARD_TO = 120.0  # tiles off at which a tank's gun, or its shell bursting, can no longer be heard...
BOOM_LOUDER = 3.0      # ...and how many times as loud as a rifle shot they are, the same distance off


def rifle_shot(rate, rng, pitch=1.0):
    """One take of a rifle shot, as samples from -1 to 1 (0.55 seconds long)."""
    n = int(rate * 0.55)
    out = []
    low = mid = tail = 0.0
    for k in range(n):
        t = k / rate
        noise = rng.uniform(-1.0, 1.0)
        mid += (noise - mid) * 0.35 * pitch          # the report: noise with its hiss taken off
        low += (noise - low) * 0.06 * pitch          # the echo: duller still
        tail += (low - tail) * 0.5
        crack = noise * math.exp(-t / 0.006)
        report = mid * math.exp(-t / 0.045) * 1.6
        thump = math.sin(2 * math.pi * 70 * pitch * t) * math.exp(-t / 0.05) * 0.7
        echo = tail * math.exp(-max(0.0, t - 0.04) / 0.16) * (1.0 if t > 0.04 else t / 0.04) * 1.4
        out.append(crack + report + thump + echo)
    peak = max(abs(v) for v in out)
    fade = int(rate * 0.02)                          # (no click at the end)
    return [v / peak * (min(1.0, (n - 1 - k) / fade)) for k, v in enumerate(out)]


def boom(rate, rng, low, length, crack):
    """A deep boom, as samples from -1 to 1, `length` seconds long: low noise (the duller, the
    lower `low` is) under a tone falling from 55 cycles a second, with `crack` of sharp noise
    at its start. A tank's gun firing has more crack; its shell bursting, more rumble."""
    n = int(rate * length)
    out = []
    rumble = 0.0
    for k in range(n):
        t = k / rate
        noise = rng.uniform(-1.0, 1.0)
        rumble += (noise - rumble) * low
        tone = math.sin(2 * math.pi * (55 - 20 * min(1.0, t / length)) * t) * math.exp(-t / 0.18)
        body = rumble * 4.0 * math.exp(-t / (length * 0.35))
        out.append(noise * crack * math.exp(-t / 0.01) + tone + body)
    peak = max(abs(v) for v in out)
    fade = int(rate * 0.05)
    return [v / peak * (min(1.0, (n - 1 - k) / fade)) for k, v in enumerate(out)]


class Sounds:
    """The game's sounds. With no sound device (or when told not to: a test run), it stays
    quiet and does nothing."""

    def __init__(self, enabled=True):
        self.ready = False
        self.started = 0                             # shots started this frame
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 2, 512)
            pygame.mixer.set_num_channels(24)
        except pygame.error:
            return
        rate, _, channels = pygame.mixer.get_init()
        rng = random.Random(7)
        self.rifle = [self.sound(rifle_shot(rate, rng, 0.94 + 0.04 * k), channels) for k in range(TAKES)]
        self.booms = {"cannon": self.sound(boom(rate, rng, 0.08, 1.3, 0.9), channels),
                      "blast": self.sound(boom(rate, rng, 0.03, 1.6, 0.4), channels)}
        self.ready = True

    @staticmethod
    def sound(samples, channels):
        """A pygame Sound from samples -1..1, as 16-bit, on every channel the mixer has."""
        data = array.array("h")
        for v in samples:
            data.extend([int(v * 26000)] * channels)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def new_frame(self):
        self.started = 0

    def rifle_shot(self, distance, pan, zoom):
        """A rifle shot `distance` tiles from where the camera looks, at `pan` (-1 the left
        edge of the screen, 1 the right), with the camera zoomed in `zoom` (0 all the way out,
        1 all the way in). It goes from LOUD_FAR to LOUD_NEAR with the square of the zoom, so
        it's quiet at the zooms a game is mostly played at and very low far out."""
        if not self.ready or self.started >= NEW_A_FRAME or distance >= HEARD_TO:
            return
        loud = (LOUD_FAR + (LOUD_NEAR - LOUD_FAR) * zoom ** 2) * (1.0 - distance / HEARD_TO) ** 2
        channel = pygame.mixer.find_channel()
        if channel is None:
            return
        self.started += 1
        pan = max(-1.0, min(1.0, pan))
        channel.set_volume(loud * min(1.0, 1.0 - pan), loud * min(1.0, 1.0 + pan))
        channel.play(random.choice(self.rifle))

    def boom(self, kind, distance, pan, zoom):
        """A tank's main gun firing ("cannon") or its shell bursting ("blast"), `distance` tiles
        from where the camera looks: as a rifle shot is heard (see rifle_shot), BOOM_LOUDER
        times as loud, and heard out to BOOM_HEARD_TO."""
        if not self.ready or distance >= BOOM_HEARD_TO:
            return
        loud = min(1.0, BOOM_LOUDER * (LOUD_FAR + (LOUD_NEAR - LOUD_FAR) * zoom ** 2)
                   * (1.0 - distance / BOOM_HEARD_TO) ** 2)
        channel = pygame.mixer.find_channel()
        if channel is None:
            return
        pan = max(-1.0, min(1.0, pan))
        channel.set_volume(loud * min(1.0, 1.0 - pan), loud * min(1.0, 1.0 + pan))
        channel.play(self.booms[kind])
