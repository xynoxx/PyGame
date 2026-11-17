"""The dead: zombies, and the waves they come in.

Every WAVE_TIME seconds a wave of zombies comes in from beyond one edge of the
map and shambles at the HQ. They beat on its walls, and turn on
anyone (or any turret) that comes near. Each wave is bigger than the last:
WAVE_SIZE zombies in the first, and MORE_PER_WAVE more in every one after.
"""
import math
import random

from mathx import turn_toward
from units import Unit

WAVE_TIME = 30.0       # seconds between waves (and before the first)
WAVE_SIZE = 10         # zombies in the first wave
MORE_PER_WAVE = 10     # and this many more in every wave after
SIDES = ("north", "east", "south", "west")


class Zombie(Unit):
    NAME = "Zombie"
    STAYS_ON_MAP = False # they come from beyond the edge
    RADIUS = 0.3
    SPEED = 1.5
    TURN_RATE = 4.0
    SIZE = 1.25
    MAX_HP = 100
    DAMAGE = 10          # a blow
    HIT_TIME = 1.0       # seconds between blows
    REACH = 0.35         # how near it must be to hit, beyond its own and its victim's edge
    NOTICE = 2.5         # how near a soldier must come to be turned on

    def __init__(self, world, x, z, variant, owner="the dead"):
        super().__init__(world, x, z, (0.5, 0.2, 0.15), "The dead", owner)
        self.variant = variant          # which of the zombie looks
        self.cooldown = random.uniform(0.0, self.HIT_TIME)
        self.lunge = 0.0                # > 0 while it's swinging at something
        self.lean = random.uniform(-0.25, 0.25)   # each one shambles a little crooked
        self.offset = random.uniform(-1.5, 1.5)   # where along the HQ's wall it heads for

    def think(self, dt, base, victims):
        """Pick a victim (whoever's too near: a soldier, an engineer or a turret; else the HQ),
        walk at it, and hit it."""
        self.cooldown = max(0.0, self.cooldown - dt)
        self.lunge = max(0.0, self.lunge - dt)
        if not self.alive:
            return
        near = [s for s in victims if s.alive and self.distance_to(s) <= self.NOTICE]
        if near:
            victim = min(near, key=self.distance_to)
            goal = (victim.x, victim.z)
            reach = self.RADIUS + victim.RADIUS + self.REACH
        elif base and base.alive:
            victim = base
            hq = base.hq
            # head for a spot on the nearest wall, each zombie its own, so they spread along it
            gx, gz = base.nearest_point(self.x + self.offset, self.z + self.offset)
            goal = (min(max(gx, hq.i), hq.i + hq.w), min(max(gz, hq.j), hq.j + hq.d))
            reach = self.RADIUS + self.REACH
        else:
            return
        dx, dz = goal[0] - self.x, goal[1] - self.z
        dist = math.hypot(dx, dz)
        heading = math.atan2(dx, dz)
        self.yaw = turn_toward(self.yaw, heading, self.TURN_RATE * dt)
        if dist > reach:
            self.walk(dx / dist, dz / dist, dt)
        else:
            self.stride += (0.0 - self.stride) * min(1.0, dt * 6)
            if self.cooldown <= 0:
                victim.hurt(self.DAMAGE)
                self.cooldown = self.HIT_TIME
                self.lunge = 0.35

    def walk(self, ux, uz, dt):
        """Shamble along (ux, uz); slide along a wall rather than walk into it."""
        step = self.SPEED * dt
        for mx, mz in ((ux, uz), (ux, 0.0), (0.0, uz)):
            nx, nz = self.x + mx * step, self.z + mz * step
            if not self.world.hits_wall(nx, nz, self.RADIUS):
                self.x, self.z = nx, nz
                break
        self.stride += (1.0 - self.stride) * min(1.0, dt * 4)
        self.phase += dt * 5.0

    def update(self, dt):
        """Zombies walk by think(); this only counts down the fall and the red flash."""
        self.flash = max(0.0, self.flash - dt)
        if not self.alive:
            self.dead_for += dt

    @property
    def swing(self):
        return math.sin(self.phase) * 0.45 * self.stride


class Waves:
    """Counts down to each wave, and brings it in from beyond one edge of the map."""

    def __init__(self, world, seed=None):
        self.world = world
        self.rng = random.Random(seed)
        self.number = 0                 # waves come so far
        self.left = WAVE_TIME           # seconds until the next

    def update(self, dt):
        """Returns (side, zombies) when a wave arrives, else None."""
        self.left -= dt
        if self.left > 0:
            return None
        self.left += WAVE_TIME
        self.number += 1
        return self.spawn()

    def spawn(self):
        n, rng = self.world.size, self.rng
        side = rng.choice(SIDES)
        middle = rng.uniform(n * 0.25, n * 0.75)
        zombies = []
        count = WAVE_SIZE + MORE_PER_WAVE * (self.number - 1)
        spread = 12 + count * 0.15                  # a big wave comes on a wider front
        for _ in range(count):
            along = middle + rng.uniform(-spread, spread)
            out = rng.uniform(2.0, 7.0)             # straggling, not in a line
            x, z = {"north": (along, -out), "south": (along, n + out),
                    "west": (-out, along), "east": (n + out, along)}[side]
            zombie = Zombie(self.world, x, z, rng.randrange(3))
            zombie.yaw = math.atan2(n / 2 - x, n / 2 - z)
            zombies.append(zombie)
        return side, zombies
