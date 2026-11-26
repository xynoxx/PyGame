"""The dead: zombies, and the waves they come in.

FIRST_WAVE seconds into a game, and every WAVE_TIME seconds after, a wave of
zombies comes in from beyond one edge of the map and shambles at the HQ. A
structure they find on the way (a turret, a building's walls or the HQ's,
within STRUCTURE_NOTICE) they go for first, till it's down; else they turn on any of
our troops who comes near. Each wave is bigger than the last: WAVE_SIZE zombies
in the first, and MORE_PER_WAVE more in every one after. From wave
SPITTERS_FROM_WAVE on, some of them are spitters, who spit acid from a few
tiles off. A glob that misses leaves a puddle that burns for a while.
A zombie's blow never misses. The dead don't go up in level.
"""
import math
import random

from mathx import turn_toward
from models import RIM
from units import LOOK_EVERY, Unit

FIRST_WAVE = 60.0      # seconds before the first wave
WAVE_TIME = 30.0       # and between waves after it
WAVE_SIZE = 50         # zombies in the first wave
MORE_PER_WAVE = 20     # and this many more in every wave after
SPITTERS_FROM_WAVE = 5   # from this wave on, some of each wave are spitters...
SPITTER_SHARE = (0.05, 0.20)   # ...somewhere from this share of it to this, at random
COVER_ACID = 0.2         # what acid does to someone in cover in a trench, of what it would (80% less)
STRUCTURE_NOTICE = 10.0  # how near a turret, a building or the HQ must be for the dead to find it (and go for it first)
MISS_BY = (0.5, 1.0)     # how far beside its victim a spit that's off target goes by, in tiles
BURN_TIME = 1.0          # seconds a glob of acid that comes down on a man burns him for
POOL_TIME = 4.0          # seconds a puddle of acid lasts where a spit came down on the ground...
POOL_DAMAGE = (2, 5)     # ...burning anyone standing in it this much health a second (each puddle its own)...
POOL_RADIUS = 0.5        # ...as far out as this, in tiles (less where a wall or a trench's edge stops it)
WALL_REACH = 0.1         # how near a building's or the HQ's tiles a zombie comes to strike its wall (set back on
                         # its tiles; they're blocked, so it comes as near as it can)
SIDES = ("north", "east", "south", "west")


class Zombie(Unit):
    STAYS_ON_MAP = False # they come from beyond the edge
    RADIUS = 0.3
    SPEED = 0.5
    TURN_RATE = 4.0
    SIZE = 1.25
    MAX_HP = 80          # the most one of its kind has: each has somewhere from HP_LEAST to this
    HP_LEAST = 20
    DAMAGE = (10, 15)    # a blow at one of our troops...
    WALL_DAMAGE = (5, 10)   # ...and at a turret or the HQ's walls
    HIT_TIME = 1.0       # seconds between blows
    REACH = 0.3          # how near it must be to hit, beyond its own and its victim's edge
    NOTICE = 5.0         # how near one of our troops must come to be turned on
    STEP = 2 * 0.42 * math.sin(0.45)   # how far a stride takes it, against its size (its legs, as they swing)

    def __init__(self, world, x, z, variant):
        super().__init__(world, x, z)
        self.MAX_HP = self.hp = random.randint(self.HP_LEAST, type(self).MAX_HP)   # each its own
        self.variant = variant          # which of the zombie looks
        self.cooldown = random.uniform(0.0, self.HIT_TIME)
        self.lunge = 0.0                # > 0 while it's swinging at something
        self.lean = random.uniform(-0.25, 0.25)   # each one shambles a little crooked
        self.offset = random.uniform(-1.5, 1.5)   # where along the HQ's wall it heads for
        self.victim = None              # who (or what) it's going for: a unit, a turret, the HQ or nobody
        self.found = None               # the structure it found first (a turret, a building or the HQ): it goes for that
        self.look = random.uniform(0, LOOK_EVERY)   # when it next looks round for one (staggered)
        self.detour = False             # a deposit stands between it and the HQ: it goes round (World.way_home)

    def think(self, dt, base, men, structures):
        """Pick a victim, walk at it, and hit it: first the structure it found first (a turret,
        a building or the HQ, see find_structure), till it's down; else any man who comes too
        near; else the HQ. At a building or the HQ, it goes for a spot on its nearest wall (each
        its own, so they spread along it)."""
        self.cooldown = max(0.0, self.cooldown - dt)
        self.lunge = max(0.0, self.lunge - dt)
        if not self.alive:
            return
        self.look -= dt
        if self.look <= 0:
            self.look += LOOK_EVERY
            self.find_structure(base, structures)
            self.check_way(base)
        self.victim = None
        near = [s for s in men if s.alive and self.distance_to(s) <= self.NOTICE]
        if self.found is not None and self.found.alive:
            victim = self.found
        elif near:
            victim = min(near, key=self.distance_to)
        elif base and base.alive:
            victim = base
        else:
            return
        step = self.step_round(victim, base)
        if step:                                     # going round a deposit on the way to the HQ
            self.victim = victim
            self.head_for(*step, dt)
            return
        if victim.walled:
            goal = self.wall_spot(victim)
            reach = self.RADIUS + WALL_REACH
        elif isinstance(victim, Unit) and victim.big:     # a tank: at its nearest side
            goal = victim.nearest_point(self.x, self.z)
            reach = self.RADIUS + self.REACH
        else:
            goal = (victim.x, victim.z)
            reach = self.RADIUS + victim.RADIUS + self.REACH
        self.victim = victim
        dx, dz = goal[0] - self.x, goal[1] - self.z
        dist = math.hypot(dx, dz)
        heading = math.atan2(dx, dz)
        self.yaw = turn_toward(self.yaw, heading, self.TURN_RATE * dt)
        if dist > reach:
            self.walk(dx / dist, dz / dist, dt)
        else:
            self.stride += (0.0 - self.stride) * min(1.0, dt * 6)
            if self.cooldown <= 0:
                self.cooldown = self.HIT_TIME
                self.lunge = 0.35
                victim.hurt(random.randint(*(self.DAMAGE if isinstance(victim, Unit) else self.WALL_DAMAGE)),
                            (self.x, self.z))

    def check_way(self, base):
        """Is a deposit in its way to the HQ? If so, it goes round, the way World.way_home
        shows, till it can walk straight at it."""
        x, z = base.nearest_point(self.x, self.z) if base and base.alive else (self.x, self.z)
        self.detour = self.world.deposit_between(self.x, self.z, x, z, self.RADIUS)

    def step_round(self, victim, base):
        """Where to walk next to go round a deposit, while it's after the HQ; else None."""
        return self.world.next_step_home(self.x, self.z) if victim is base and self.detour else None

    def head_for(self, x, z, dt):
        """Turn to (x, z) and shamble toward it."""
        dx, dz = x - self.x, z - self.z
        dist = max(math.hypot(dx, dz), 1e-6)
        self.yaw = turn_toward(self.yaw, math.atan2(dx, dz), self.TURN_RATE * dt)
        self.walk(dx / dist, dz / dist, dt)

    def wall_spot(self, thing):
        """Its own spot on the wall of a building or the HQ that it's off: the nearest point
        of that wall, moved along it by its offset (so the dead spread along the wall), and
        never into the building."""
        px, pz = thing.nearest_point(self.x, self.z)
        if abs(px - self.x) >= abs(pz - self.z):     # off a wall that runs along z: slide along it in z
            return thing.nearest_point(px, self.z + self.offset)
        return thing.nearest_point(self.x + self.offset, pz)

    def find_structure(self, base, structures):
        """Has it found a structure, to go for before anything else? It keeps to the first it
        found while that stands. Otherwise it finds the nearest turret or building (started:
        not a blueprint) or HQ wall within STRUCTURE_NOTICE that it can see, if there is one."""
        if self.found is not None and self.found.alive:
            return
        self.found, nearest = None, STRUCTURE_NOTICE
        for t in structures + ([base] if base and base.alive else []):
            gap = self.sight_of(t, nearest) if t.alive else None
            if gap is not None and gap <= nearest:
                self.found, nearest = t, gap

    def sight_of(self, thing, within=math.inf):
        """How far it is to a structure, if it can see it (else None): to a turret's round
        edge, with nothing in the way but the turret's own tile; or to the nearest point of a
        building's or the HQ's walls, with nothing in the way to just short of them. (Further
        than `within`, it doesn't look: None.)"""
        if not thing.walled:
            gap = self.distance_to(thing) - thing.RADIUS
            if gap > within:
                return None
            return gap if self.world.line_clear(self.x, self.z, thing.x, thing.z, (thing.i, thing.j)) else None
        x, z = thing.nearest_point(self.x, self.z)
        gap = math.hypot(x - self.x, z - self.z)
        if gap > within:
            return None
        back = min(0.05, gap) / max(gap, 1e-6)                    # (the line ends just short of the wall)
        return gap if self.world.line_clear(self.x, self.z, x - (x - self.x) * back, z - (z - self.z) * back) else None

    def walk(self, ux, uz, dt):
        """Shamble along (ux, uz); slide along a wall rather than walk into it. Its legs swing
        as fast as it goes: a stride (STEP) for every half swing, so its feet don't slide."""
        step = self.SPEED * dt
        for mx, mz in ((ux, uz), (ux, 0.0), (0.0, uz)):
            nx, nz = self.x + mx * step, self.z + mz * step
            if not self.world.hits_wall(nx, nz, self.RADIUS):
                self.x, self.z = nx, nz
                break
        self.stride += (1.0 - self.stride) * min(1.0, dt * 4)
        self.phase += dt * math.pi * self.SPEED / (self.STEP * self.SIZE)

    def update(self, dt):
        """Zombies walk by think(); this only counts the time since it fell, and the red flash."""
        self.flash = max(0.0, self.flash - dt)
        self.settle(dt)
        if not self.alive:
            self.dead_for += dt

    @property
    def swing(self):
        return math.sin(self.phase) * 0.45 * self.stride


class Spitter(Zombie):
    """A bloated zombie that spits acid, from up to RANGE away: first at a structure it has
    found (a turret, or a building's or the HQ's wall: see find_structure), else at the
    nearest of our troops it can see in reach. With neither, it walks at the HQ. It hits one
    of our troops or a turret HIT_CHANCE of the time (a building's or the HQ's walls, always). On a man, the acid burns him for
    DAMAGE over BURN_TIME; on a turret or a wall, it does WALL_DAMAGE at once."""
    SPEED = 0.3
    MAX_HP = 40
    HP_LEAST = 20
    RANGE = 5.0          # tiles: it must come close
    DAMAGE = (10, 20)    # a glob that comes down on one of our troops, burning, over BURN_TIME...
    WALL_DAMAGE = (10, 15)   # ...and on a turret or the HQ's walls
    HIT_TIME = 0.5       # seconds between spits
    HIT_CHANCE = 0.6     # how often its spit is on target (at a man standing still, or a turret)
    MOUTH = 1.15         # how high it spits from

    def __init__(self, world, x, z):
        super().__init__(world, x, z, 3)
        self.aim = None                 # the man it saw last time it looked round

    def think(self, dt, base, men, structures):
        """Spit at a structure it has found (walking up to it till it's in range: it finds them
        further off than it spits), else at the nearest man in reach, else walk on at the HQ.
        Returns a new Spit, or None."""
        self.cooldown = max(0.0, self.cooldown - dt)
        self.lunge = max(0.0, self.lunge - dt)
        if not self.alive:
            return None
        self.look -= dt
        if self.look <= 0:
            self.look += LOOK_EVERY
            self.find_structure(base, structures)
            self.check_way(base)
            seen = [m for m in men if m.alive and self.distance_to(m) <= self.RANGE
                    and self.world.line_clear(self.x, self.z, m.x, m.z)]
            self.aim = min(seen, key=self.distance_to) if seen else None
        if self.found is not None and self.found.alive:
            self.victim = self.found
            if self.found.walled:
                x, z = self.found.nearest_point(self.x, self.z)
                gap = math.hypot(x - self.x, z - self.z)
            else:
                x, z = self.found.x, self.found.z
                gap = self.distance_to(self.found) - self.found.RADIUS
            if gap <= self.RANGE:
                return self.spit_at(self.found, x, z, dt, base, men)
            return self.walk_at(x, z, dt)
        if self.aim and self.aim.alive and self.distance_to(self.aim) <= self.RANGE:
            self.victim = self.aim
            return self.spit_at(self.aim, self.aim.x, self.aim.z, dt, base, men)
        self.victim = base if base and base.alive else None
        if not self.victim:
            return None
        return self.walk_at(*(self.step_round(base, base) or base.nearest_point(self.x, self.z)), dt)

    def walk_at(self, x, z, dt):
        """Turn to (x, z) and shamble toward it. Returns None (no spit)."""
        self.head_for(x, z, dt)
        return None

    def spit_at(self, victim, x, z, dt, base=None, victims=()):
        """Stand, turn to it, and spit when ready: at (x, z) on a building's or the HQ's wall,
        or at where a man or a turret stands now. HIT_CHANCE of the time it's on target; else it goes by,
        to one side (MISS_BY), and comes down beyond."""
        self.stride += (0.0 - self.stride) * min(1.0, dt * 6)
        self.yaw = turn_toward(self.yaw, math.atan2(x - self.x, z - self.z), self.TURN_RATE * dt)
        if self.cooldown > 0:
            return None
        self.cooldown = self.HIT_TIME
        self.lunge = 0.35
        mouth = (self.x + math.sin(self.yaw) * 0.3, self.MOUTH - self.sink, self.z + math.cos(self.yaw) * 0.3)
        if victim.walled:                            # a building or the HQ: its walls are too big to miss
            return Spit(mouth, (x, 1.0, z), self, base, victims)
        height = 0.75 * victim.SIZE - victim.sink if isinstance(victim, Unit) else 1.0   # his chest, or the gun
        if random.random() >= self.HIT_CHANCE:      # off target: it goes by, to one side
            dx, dz = x - self.x, z - self.z
            d = max(math.hypot(dx, dz), 1e-6)
            off = (victim.RADIUS + random.uniform(*MISS_BY)) * random.choice((-1, 1))
            x, z = x + dz / d * off, z - dx / d * off
        return Spit(mouth, (x, height, z), self, base, victims)


class Spit:
    """A glob of acid in flight, in a low arc, at the spot its spitter aimed for: where its
    victim stood when it spat (or beside him, if it's off target), or a spot on a building's
    or the HQ's wall. It doesn't follow anyone, so someone on the move may be gone by the time it gets
    there. It burns whoever of our troops it comes down on, its victim or anyone else in its
    way (in cover in a trench, the sandbags take most of it: COVER_ACID), and any turret,
    building or HQ wall it runs into. Meeting nothing, it flies on past the spot, falling,
    and splashes on the ground."""
    SPEED = 15.0         # tiles a second
    ARC = 1.3            # how high it rises over its line of flight, at most
    GLOB = 0.1           # how big it is: it comes down on anyone within this of their edge

    def __init__(self, start, goal, spitter, base, victims):
        self.start, self.goal = start, goal
        self.spitter = spitter          # who spat it (its damage is his kind's)
        self.world = spitter.world
        self.base = base
        self.victims = victims          # the units and turrets it might come down on
        self.length = max(0.5, math.dist(start, goal))
        self.flown = 0.0                # 0 just spat .. 1 at the spot aimed for (and on, falling)
        self.pos = start
        self.struck = None              # what it came down on: a unit, a turret, the HQ, or nothing
        self.landed = False

    def fly(self, dt):
        """Move it along. True once it has come down: on someone, on a wall, or on the ground."""
        a, b = self.start, self.goal
        self.flown += self.SPEED * dt / self.length
        t = self.flown
        x, z = a[0] + (b[0] - a[0]) * t, a[2] + (b[2] - a[2]) * t
        y = a[1] + (b[1] - a[1]) * t + 4 * self.ARC * t * (1 - t)
        self.pos = (x, y, z)
        for v in self.victims:
            if isinstance(v, Unit) and v.alive and self.on(v):
                self.struck = v
                break
        else:
            self.struck = self.wall_at(x, y, z)
        floor = -self.world.floor_depth(x, z) + 0.05
        if self.struck is None and y <= floor:
            self.pos = (x, floor, z)                  # on the ground
        self.landed = self.struck is not None or y <= floor
        return self.landed

    def on(self, unit):
        """Is the glob in his body now (or the tank: see Unit.holds)?"""
        return unit.holds(*self.pos, self.GLOB)

    def wall_at(self, x, y, z):
        """The turret, building or HQ whose tile the glob is in and lower than its top, or None."""
        i, j = math.floor(x), math.floor(z)
        if not (0 <= i < self.world.size and 0 <= j < self.world.size and self.world.is_blocked(i, j)):
            return None
        structure = self.world.structures.get((i, j))
        if structure:
            return structure if structure.alive and y < structure.TOP else None
        hq = self.base.hq if self.base else None
        if hq and hq.i <= i < hq.i + hq.w and hq.j <= j < hq.j + hq.d and y < self.base.TOP:
            return self.base
        return None

    def land(self):
        """It has come down: burn what it came down on (in cover, COVER_ACID of it). Returns where it splashed."""
        v = self.struck
        if v is None:
            return self.pos
        source = (self.start[0], self.start[2])
        if isinstance(v, Unit):
            v.burn(random.randint(*self.spitter.DAMAGE) * (COVER_ACID if v.in_cover else 1.0), BURN_TIME, source)
        else:
            v.hurt(random.randint(*self.spitter.WALL_DAMAGE), source)
        return self.pos


class AcidPool:
    """A puddle of acid where a spit came down on the ground, missing everyone. For POOL_TIME
    seconds it burns anyone standing in it (his feet in it, at its level: not someone down in
    a trench beside it), somewhere in POOL_DAMAGE a second (each puddle its own). It spreads POOL_RADIUS,
    or less where a wall stands, where open ground ends at a trench's hole, or where a
    trench's floor ends at its earth walls (with no room even for a small one, there's none)."""

    def __init__(self, world, x, y, z):
        self.x, self.z = x, z
        self.floor = y - 0.05                         # the ground it lies on (Spit comes down 0.05 over it)
        self.burning = random.randint(*POOL_DAMAGE)   # health a second
        self.age = 0.0
        self.radius = self.room(world)

    def room(self, world):
        """How far it can spread without running into a wall, over a hole, or into the earth
        (0 if it can't spread even 0.1)."""
        x, z = self.x, self.z
        trench = world.trench_at(x, z)
        r = POOL_RADIUS
        while r >= 0.1 - 1e-9:
            if world.hits_wall(x, z, r):
                pass
            elif trench and trench.started:           # on its floor: keep inside its walls
                i, j = trench.i + RIM, trench.j + RIM
                if min(x - i, i + 1 - 2 * RIM - x, z - j, j + 1 - 2 * RIM - z) >= r:
                    return r
            elif not any(world.trenches.get((a, b)) and world.trenches[a, b].started
                         and (x - min(max(x, a), a + 1)) ** 2 + (z - min(max(z, b), b + 1)) ** 2 < r * r
                         for a in range(math.floor(x - r), math.floor(x + r) + 1)
                         for b in range(math.floor(z - r), math.floor(z + r) + 1)):
                return r
            r -= 0.05
        return 0.0

    def burn(self, dt, men):
        """Burn anyone standing in it, and age. True once it has dried up."""
        self.age += dt
        for m in men:
            if (m.alive and math.hypot(m.x - self.x, m.z - self.z) <= self.radius + 0.1
                    and abs(-m.sink - self.floor) < 0.25):
                m.hurt(self.burning * dt * (COVER_ACID if m.in_cover else 1.0), (self.x, self.z))
        return self.age >= POOL_TIME


class Waves:
    """Counts down to each wave, and brings it in from beyond one edge of the open part of the map."""

    def __init__(self, world):
        self.world = world
        self.number = 0                 # waves come so far
        self.left = FIRST_WAVE          # seconds until the next

    def update(self, dt):
        """Returns (side, zombies) when a wave arrives, else None."""
        self.left -= dt
        if self.left > 0:
            return None
        self.left += WAVE_TIME
        self.number += 1
        return self.spawn()

    def size(self, number):
        """How many zombies come in wave `number` (the first is 1)."""
        return WAVE_SIZE + MORE_PER_WAVE * (number - 1)

    def spawn(self):
        """A wave, beyond one edge of the open part of the map, along its middle half."""
        x0, z0, x1, z1 = self.world.open
        side = random.choice(SIDES)
        lo, hi = (x0, x1) if side in ("north", "south") else (z0, z1)
        middle = random.uniform(lo + (hi - lo) * 0.25, lo + (hi - lo) * 0.75)
        zombies = []
        count = self.size(self.number)
        spitters = round(count * random.uniform(*SPITTER_SHARE)) if self.number >= SPITTERS_FROM_WAVE else 0
        spitting = set(random.sample(range(count), spitters))   # which of them spit (taken from the wave, not added)
        spread = 12 + count * 0.15                  # a big wave comes on a wider front
        for k in range(count):
            along = middle + random.uniform(-spread, spread)
            out = random.uniform(2.0, 7.0)             # straggling, not in a line
            x, z = {"north": (along, z0 - out), "south": (along, z1 + out),
                    "west": (x0 - out, along), "east": (x1 + out, along)}[side]
            zombie = Spitter(self.world, x, z) if k in spitting else Zombie(self.world, x, z, random.randrange(3))
            zombie.yaw = math.atan2((x0 + x1) / 2 - x, (z0 + z1) / 2 - z)
            zombies.append(zombie)
        return side, zombies
