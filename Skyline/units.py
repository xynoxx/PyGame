"""Units on the map, the turrets engineers build, and the HQ that trains them.

Every unit walks the same way: it finds a path round anything in the way and
swings its arms and legs as it goes. The kinds differ in size, speed, look and
what they do in a fight. (The zombies are in zombies.py.)
"""
import math
import random

from mathx import turn_toward

LOOK_EVERY = 0.2       # seconds between one shooter's looks round for zombies it can see (the
                       # line-of-sight checks are what costs; in between it keeps what it saw)

DEATH_TIME = 4.0       # seconds a fallen unit stays on the ground before it's gone


class Unit:
    NAME = "Unit"
    RADIUS = 0.35       # how much room it takes up on the map
    SPEED = 3.6         # tiles per second
    TURN_RATE = 10.0    # radians per second
    SIZE = 1.5          # drawing scale of the model
    MAX_HP = 100
    STAYS_ON_MAP = True # never pushed off the edge of the map
    strafing = False    # facing something (to shoot it) rather than where it's walking

    def __init__(self, world, x, z, team_color, team_name, owner):
        self.world = world
        self.x, self.z = x, z
        self.yaw = 0.0                  # 0 faces +Z (toward the camera at the start)
        self.team_color = team_color
        self.team_name = team_name
        self.owner = owner
        self.path = []                  # points still to walk through
        self.phase = 0.0                # walk cycle
        self.stride = 0.0               # 0 standing still .. 1 in full stride
        self.hp = self.MAX_HP
        self.dead_for = None            # seconds since it fell, or None while it's alive
        self.flash = 0.0                # a moment of red when it's hit
        self.end_yaw = None             # the way to face once it gets there (lined up), if any

    @property
    def alive(self):
        return self.dead_for is None

    @property
    def gone(self):
        """Fallen long enough ago to be taken off the map."""
        return self.dead_for is not None and self.dead_for > DEATH_TIME

    @property
    def moving(self):
        return bool(self.path)

    @property
    def destination(self):
        return self.path[-1] if self.path else None

    @property
    def tile(self):
        return int(self.x), int(self.z)

    def distance_to(self, other):
        return math.hypot(other.x - self.x, other.z - self.z)

    def move_to(self, x, z):
        """Walk to (x, z), around anything in the way. Returns where they will end up."""
        self.path = self.world.find_path(self.x, self.z, x, z, self.RADIUS)
        self.end_yaw = None
        return self.destination

    def hurt(self, damage):
        """Take a hit. True if it was the one that killed it."""
        if not self.alive:
            return False
        self.hp -= damage
        self.flash = 0.12
        if self.hp <= 0:
            self.hp = 0
            self.dead_for = 0.0
            self.path = []
            return True
        return False

    def face(self, x, z, dt):
        """Turn toward a point; True once it's facing it."""
        heading = math.atan2(x - self.x, z - self.z)
        self.yaw = turn_toward(self.yaw, heading, self.TURN_RATE * dt)
        return abs((heading - self.yaw + math.pi) % (2 * math.pi) - math.pi) < 0.15

    def update(self, dt):
        self.flash = max(0.0, self.flash - dt)
        if not self.alive:
            self.dead_for += dt
            self.stride = 0.0
            return
        step = self.SPEED * dt
        heading = None
        while self.path and step > 0:
            tx, tz = self.path[0]
            dx, dz = tx - self.x, tz - self.z
            dist = math.hypot(dx, dz)
            if dist > 1e-6:
                heading = math.atan2(dx, dz)
            if dist <= step:
                self.x, self.z = tx, tz
                self.path.pop(0)
                step -= dist
            else:
                self.x += dx / dist * step
                self.z += dz / dist * step
                step = 0
        if heading is not None and not self.strafing:
            self.yaw = turn_toward(self.yaw, heading, self.TURN_RATE * dt)
        elif not self.path and self.end_yaw is not None and not self.strafing:
            self.yaw = turn_toward(self.yaw, self.end_yaw, self.TURN_RATE * dt)   # face the way it was lined up

        target = 1.0 if self.path else 0.0
        self.stride += (target - self.stride) * min(1.0, dt * 8)
        self.phase += dt * 9.0 * max(self.stride, 0.2)

    @property
    def swing(self):
        """How far the arms and legs swing right now (radians)."""
        return math.sin(self.phase) * 0.6 * self.stride

    @property
    def bob(self):
        """How high the body bounces right now."""
        return abs(math.sin(self.phase)) * 0.05 * self.stride

    def ray_hit(self, origin, direction):
        """How far along a mouse ray (from the camera) it touches this unit, or None if it misses."""
        if not self.alive:
            return None
        cx, cy, cz = self.x, 0.6 * self.SIZE, self.z
        radius = 0.42 * self.SIZE
        ox, oy, oz = origin[0] - cx, origin[1] - cy, origin[2] - cz
        b = ox * direction[0] + oy * direction[1] + oz * direction[2]
        c = ox * ox + oy * oy + oz * oz - radius * radius
        disc = b * b - c
        if disc < 0:
            return None
        t = -b - math.sqrt(disc)
        return t if t > 0 else None


class Gunner(Unit):
    """Anyone who carries a gun. He holds where he's put: he never walks off after the dead
    on his own, just turns and shoots any zombie in range that he can see (never through a
    wall), whatever he's doing, walking or not. Sent after one (a right click on it), he
    walks only till it's in range and in sight, then stands and shoots it till it falls."""
    RADIUS = 0.28
    SPEED = 3.2
    SIZE = 1.2
    RANGE = 10.0         # tiles
    RELOAD = 0.8         # seconds between shots
    DAMAGE = 10
    PELLETS = 1          # tracers a shot shows (a shotgun's spray)
    AIM_HOLD = 1.2       # seconds the gun stays up after a shot
    TRAIN_TIME = 4.0     # seconds at the HQ

    def __init__(self, *args):
        super().__init__(*args)
        self.target = None          # the zombie he was sent after, if any
        self.reload = 0.0
        self.aiming = 0.0           # > 0 while the gun's up
        self.aim_blend = 0.0        # 0 gun held low .. 1 up at the shoulder (for drawing)
        self.repath = 0.0
        self.look = random.uniform(0, LOOK_EVERY)   # when he next looks round (staggered, not all at once)
        self.in_sight = []          # the zombies in reach when he last looked

    def sees(self, other):
        """Is there a clear line of fire to it (no wall between)?"""
        return self.world.line_clear(self.x, self.z, other.x, other.z)

    def in_reach(self, zombie):
        """In range, and nothing in the way."""
        return self.distance_to(zombie) <= self.RANGE and self.sees(zombie)

    def attack(self, zombie):
        self.target = zombie
        self.repath = 0.0

    def move_to(self, x, z):
        self.target = None          # a move order calls off the chase
        return super().move_to(x, z)

    def fight(self, dt, zombies):
        """Shoot the zombie he was sent after if he can, else the nearest one in reach.
        Returns the zombie shot, or None."""
        self.reload = max(0.0, self.reload - dt)
        self.aiming = max(0.0, self.aiming - dt)
        self.aim_blend += ((1.0 if self.aiming > 0 else 0.0) - self.aim_blend) * min(1.0, dt * 12)
        self.strafing = False
        if not self.alive:
            return None
        if self.target and not self.target.alive:
            self.target = None

        self.look -= dt
        if self.look <= 0:                       # look round: who's in range, with nothing in the way?
            self.look += LOOK_EVERY
            self.in_sight = [z for z in zombies if z.alive and self.in_reach(z)]
        seen = [z for z in self.in_sight if z.alive and self.distance_to(z) <= self.RANGE]

        if self.target:                          # sent after one: close in only till it's in reach
            if self.target in seen:
                self.path = []
            else:
                self.repath -= dt                # it moves, so follow it afresh now and then
                if self.repath <= 0:
                    self.repath = 0.5
                    Unit.move_to(self, self.target.x, self.target.z)

        if self.target in seen:
            shoot = self.target
        elif seen:
            shoot = min(seen, key=self.distance_to)
        else:
            return None
        self.strafing = True                     # face it, even walking
        self.aiming = max(self.aiming, 0.3)
        if self.face(shoot.x, shoot.z, dt) and self.reload <= 0:
            self.reload = self.RELOAD
            self.aiming = self.AIM_HOLD
            return shoot
        return None


class Soldier(Gunner):
    """A rifleman: long reach, steady fire."""
    NAME = "Soldier"
    RANGE = 20.0
    DAMAGE = 10
    RELOAD = 0.8
    TRAIN_TIME = 4.0


class Engineer(Gunner):
    """Carries a shotgun for close work, and builds turrets. Given turrets to build (placed
    from his panel: one, or a row of them dragged out), he builds them one after another:
    each time, the one with the fewest engineers on it, nearest first, so a crew spreads
    over the work. Any other order calls him off (unfinished turrets wait; right click one
    with engineers to finish it). He still shoots anything that comes in reach, and leaves
    the work while he does."""
    NAME = "Engineer"
    SPEED = 3.0
    MAX_HP = 90
    RANGE = 10.0
    DAMAGE = 5
    RELOAD = 1.0
    PELLETS = 5
    TRAIN_TIME = 6.0
    WORK_REACH = 0.5     # how near a turret's edge he must stand to work on it

    def __init__(self, *args):
        super().__init__(*args)
        self.jobs = []              # the turrets he's to build, in the order they were laid
        self.job = None             # the one he's on now
        self.spot = None            # where he stands to work on it
        self.working = False        # at it right now (for drawing: the hammer swings)
        self.hammer = 0.0

    def build(self, turrets, crew=()):
        """Add these turrets (one, or a list) to the ones he's to build; if he's not on one
        already, go to the first. `crew`: all the engineers about (whose work and spots he
        takes into account)."""
        new = list(turrets) if isinstance(turrets, (list, tuple)) else [turrets]
        self.jobs += [t for t in new if t not in self.jobs]
        if not self.job:
            self.take_next(crew)

    def take_next(self, crew=()):
        """Pick the next turret to work on: unbuilt, the fewest engineers on it, then the nearest."""
        self.jobs = [t for t in self.jobs if t.alive and not t.built]
        self.job = None
        if not self.jobs:
            return
        workers = {id(t): sum(e.job is t for e in crew if e is not self) for t in self.jobs}
        turret = min(self.jobs, key=lambda t: (workers[id(t)], self.distance_to(t)))
        taken = [e.spot for e in crew if e is not self and e.job is turret and e.spot]
        self.spot = turret.work_spot(self, taken)
        Gunner.move_to(self, *self.spot)
        self.job = turret

    def move_to(self, x, z):
        self.jobs, self.job = [], None   # any other order calls him off the work
        return super().move_to(x, z)

    def attack(self, zombie):
        self.jobs, self.job = [], None
        super().attack(zombie)

    def work(self, dt, crew=()):
        """Build, if he's at his turret and not busy shooting. Returns True while he works."""
        self.working = False
        if not self.alive:
            return False
        if self.job and (not self.job.alive or self.job.built):
            self.take_next(crew)                     # that one's done (or gone): on to the next
        job = self.job
        if not job:
            return False
        if self.distance_to(job) > job.RADIUS + self.RADIUS + self.WORK_REACH:
            if not self.path:                        # pushed away, or not there yet: walk back to it
                Gunner.move_to(self, *(self.spot or job.work_spot(self)))
            return False
        self.path = []
        if self.strafing:                            # shooting: the work waits
            return False
        self.face(job.x, job.z, dt)
        job.begin()                                  # a blueprint no longer: the foundation goes down
        job.add_progress(dt / job.BUILD_TIME)
        self.working = True
        self.hammer += dt
        return True


class Turret:
    """A semi-automatic gun on a concrete block, on one tile. Laid out, it's only a blueprint:
    it doesn't take up its tile, the dead ignore it, and it can be called off. Once an
    engineer starts on it, it's a real foundation (it fills its tile) and is built up (no use
    till it's done). Built, it turns to the nearest zombie in range it can see, and fires.
    The dead attack it if they pass near."""
    NAME = "Turret"
    RADIUS = 0.5         # its block fills its tile
    MAX_HP = 400
    RANGE = 30.0
    DAMAGE = 15
    RELOAD = 0.55        # semi-auto: a shot each time it's ready, on its target
    TURN_RATE = 3.5
    BUILD_TIME = 8.0     # seconds for one engineer (two take half as long)
    PELLETS = 1
    HEIGHT = 1.05        # the barrel's height, for tracers and the health bar

    def __init__(self, world, i, j, team_color):
        self.world = world
        self.i, self.j = i, j
        self.x, self.z = i + 0.5, j + 0.5
        self.team_color = team_color
        self.started = False        # an engineer has begun on it: no longer a blueprint
        self.progress = 0.0         # 0 just begun .. 1 built
        self.hp = self.MAX_HP * 0.1
        self.yaw = 0.0
        self.reload = 0.0
        self.recoil = 0.0
        self.flash = 0.0
        self.dead_for = None
        self.look = random.uniform(0, LOOK_EVERY)
        self.in_sight = []

    @property
    def built(self):
        return self.progress >= 1.0

    @property
    def blueprint(self):
        return self.alive and not self.started

    def begin(self):
        """An engineer starts on it: from now it fills its tile."""
        if not self.started:
            self.started = True
            self.world.set_blocked(self.i, self.j, True)

    def cancel(self):
        """Call a blueprint off (it goes at once: nothing was built)."""
        self.dead_for = 99.0

    @property
    def alive(self):
        return self.dead_for is None

    @property
    def gone(self):
        return self.dead_for is not None and self.dead_for > 1.5

    def add_progress(self, amount):
        """Building also mends: it's at full strength the moment it's done."""
        amount = min(amount, 1.0 - self.progress)
        self.progress += amount
        self.hp = min(self.MAX_HP, self.hp + self.MAX_HP * 0.9 * amount)

    def work_spot(self, engineer, others=()):
        """Where an engineer stands to work on it: beside it, on his side, but round from any
        spot another engineer has already taken (so they don't stand on each other)."""
        heading = math.atan2(engineer.x - self.x, engineer.z - self.z)
        reach = self.RADIUS + engineer.RADIUS + 0.2
        taken = [math.atan2(x - self.x, z - self.z) for x, z in others]
        for step in (0, 1, -1, 2, -2, 3, -3, 4):
            a = heading + step * 0.9
            x, z = self.x + math.sin(a) * reach, self.z + math.cos(a) * reach
            if (all(abs((a - t + math.pi) % (2 * math.pi) - math.pi) > 0.6 for t in taken)
                    and not self.world.hits_wall(x, z, engineer.RADIUS)):
                return x, z
        return self.x + math.sin(heading) * reach, self.z + math.cos(heading) * reach

    def distance_to(self, other):
        return math.hypot(other.x - self.x, other.z - self.z)

    def hurt(self, damage):
        if not self.alive:
            return False
        self.hp -= damage
        self.flash = 0.12
        if self.hp <= 0:
            self.hp = 0
            self.dead_for = 0.0
            return True
        return False

    def sees(self, other):
        return self.world.line_clear(self.x, self.z, other.x, other.z, skip=(self.i, self.j))

    def fight(self, dt, zombies):
        """Turn to the nearest zombie it can see in range and fire. Returns the zombie shot, or None."""
        self.reload = max(0.0, self.reload - dt)
        self.recoil = max(0.0, self.recoil - dt)
        self.flash = max(0.0, self.flash - dt)
        if not self.alive:
            self.dead_for += dt
            return None
        if not self.built:
            return None
        self.look -= dt
        if self.look <= 0:
            self.look += LOOK_EVERY
            self.in_sight = [z for z in zombies if z.alive and self.distance_to(z) <= self.RANGE and self.sees(z)]
        seen = [z for z in self.in_sight if z.alive and self.distance_to(z) <= self.RANGE]
        if not seen:
            return None
        target = min(seen, key=self.distance_to)
        heading = math.atan2(target.x - self.x, target.z - self.z)
        self.yaw = turn_toward(self.yaw, heading, self.TURN_RATE * dt)
        facing = abs((heading - self.yaw + math.pi) % (2 * math.pi) - math.pi) < 0.08
        if facing and self.reload <= 0:
            self.reload = self.RELOAD
            self.recoil = 0.12
            return target
        return None

    def muzzle(self):
        return (self.x + math.sin(self.yaw) * 0.78, self.HEIGHT, self.z + math.cos(self.yaw) * 0.78)

    def ray_hit(self, origin, direction, height=1.4):
        lo = (self.i, 0.0, self.j)
        hi = (self.i + 1, height, self.j + 1)
        return _box_hit(origin, direction, lo, hi)


def _box_hit(origin, direction, lo, hi):
    """How far along a ray it enters a box (lo and hi corners), or None if it misses."""
    near, far = 0.0, math.inf
    for k in range(3):
        if abs(direction[k]) < 1e-9:
            if not lo[k] <= origin[k] <= hi[k]:
                return None
            continue
        t0 = (lo[k] - origin[k]) / direction[k]
        t1 = (hi[k] - origin[k]) / direction[k]
        near, far = max(near, min(t0, t1)), min(far, max(t0, t1))
    return near if near <= far else None


def keep_apart(units, world):
    """Nudge units that stand on each other apart, never into a wall."""
    units = [u for u in units if u.alive]
    for k, a in enumerate(units):
        for b in units[k + 1:]:
            dx, dz = b.x - a.x, b.z - a.z
            gap = a.RADIUS + b.RADIUS
            d2 = dx * dx + dz * dz
            if d2 >= gap * gap:
                continue
            d = math.sqrt(d2)
            if d < 1e-4:                       # right on top of each other: pick a side
                dx, dz, d = math.cos(k), math.sin(k), 1.0
            push = (gap - d) / 2 * 0.5         # half the overlap each, a little at a time
            nx, nz = dx / d * push, dz / d * push
            for unit, sx, sz in ((a, -nx, -nz), (b, nx, nz)):
                x, z = unit.x + sx, unit.z + sz
                if world.hits_wall(x, z, unit.RADIUS):
                    continue
                if unit.STAYS_ON_MAP and not (unit.RADIUS <= x <= world.size - unit.RADIUS
                                              and unit.RADIUS <= z <= world.size - unit.RADIUS):
                    continue
                unit.x, unit.z = x, z


def formation(n, x, z, spacing=1.0):
    """Spots for n units round (x, z), in a square block, nearest the middle first."""
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    spots = [(x + (c - (cols - 1) / 2) * spacing, z + (r - (rows - 1) / 2) * spacing)
             for r in range(rows) for c in range(cols)]
    spots.sort(key=lambda s: (s[0] - x) ** 2 + (s[1] - z) ** 2)
    return spots[:n]


def line_formation(n, a, b, coming_from, spacing=1.0):
    """Spots for n units along the line from a to b (points on the ground), in rows if it's
    too short for them all, and the way they should face: square to the line, away from
    where they're coming from. Returns (spots, yaw), the front row first."""
    (ax, az), (bx, bz) = a, b
    length = math.hypot(bx - ax, bz - az)
    ux, uz = ((bx - ax) / length, (bz - az) / length) if length > 1e-6 else (1.0, 0.0)
    nx, nz = -uz, ux                                   # square to the line...
    mx, mz = (ax + bx) / 2, (az + bz) / 2
    if (mx - coming_from[0]) * nx + (mz - coming_from[1]) * nz < 0:
        nx, nz = -nx, -nz                              # ...facing away from where they come from
    per_row = max(1, min(n, int(length / spacing) + 1))
    gap = length / (per_row - 1) if per_row > 1 else 0.0
    spots = []
    for row in range(math.ceil(n / per_row)):
        count = min(per_row, n - row * per_row)
        start = (per_row - count) * gap / 2            # a short last row stands in the middle
        bx0, bz0 = ax - nx * row * spacing, az - nz * row * spacing   # rows go back, behind the line
        for k in range(count):
            d = start + k * gap if per_row > 1 else length / 2
            spots.append((bx0 + ux * d, bz0 + uz * d))
    return spots, math.atan2(nx, nz)


def send_to_spots(units, spots, yaw=None):
    """Send each unit to its own spot, the nearest spots to whoever's nearest; then face yaw."""
    left = list(units)
    for sx, sz in spots:
        unit = min(left, key=lambda u: (u.x - sx) ** 2 + (u.z - sz) ** 2)
        left.remove(unit)
        unit.move_to(sx, sz)
        unit.end_yaw = yaw


def order_move(units, x, z):
    """Send units to (x, z) together, in a square block round it."""
    send_to_spots(units, formation(len(units), x, z))


def order_line(units, a, b):
    """Line units up along the line from a to b, facing away from where they are now."""
    cx = sum(u.x for u in units) / len(units)
    cz = sum(u.z for u in units) / len(units)
    spots, yaw = line_formation(len(units), a, b, (cx, cz))
    send_to_spots(units, spots, yaw)


class Headquarters:
    """The HQ as it plays: its health, what it's training, how far along, and where new units gather."""
    TRAINS = (Soldier, Engineer)
    MAX_HP = 1500

    def __init__(self, world, hq, team_color, team_name, owner):
        self.world = world
        self.hq = hq
        self.team_color = team_color
        self.team_name = team_name
        self.owner = owner
        self.hp = self.MAX_HP
        self.flash = 0.0
        self.queue = []                # the kinds waiting to be trained, in order; the first is in training
        self.progress = 0.0            # how far along the one in training is, 0 to 1
        self.door = (hq.i + hq.w / 2, hq.j + hq.d + 0.4)
        self.rally = (hq.i + hq.w / 2, hq.j + hq.d + 3.0)
        self.trained = 0

    @property
    def alive(self):
        return self.hp > 0

    def hurt(self, damage):
        self.hp = max(0, self.hp - damage)
        self.flash = 0.12

    def nearest_point(self, x, z, margin=0.0):
        """The point on (or just outside, by margin) the HQ's walls nearest to (x, z)."""
        hq = self.hq
        return (min(max(x, hq.i - margin), hq.i + hq.w + margin),
                min(max(z, hq.j - margin), hq.j + hq.d + margin))

    def queued(self, kind):
        return sum(k is kind for k in self.queue)

    def train(self, kind):
        """Add one to the queue (there's no limit)."""
        self.queue.append(kind)

    def cancel(self, kind):
        """Take the last of that kind off the queue (if it was the one in training, the next starts afresh)."""
        for k in range(len(self.queue) - 1, -1, -1):
            if self.queue[k] is kind:
                del self.queue[k]
                if k == 0:
                    self.progress = 0.0
                return True
        return False

    def update(self, dt):
        """Train; returns a new unit when one is ready, already walking to the rally point."""
        self.flash = max(0.0, self.flash - dt)
        if not self.queue or not self.alive:
            return None
        kind = self.queue[0]
        self.progress += dt / kind.TRAIN_TIME
        if self.progress < 1.0:
            return None
        self.progress = 0.0
        self.queue.pop(0)
        unit = kind(self.world, *self.door, self.team_color, self.team_name, self.owner)
        spots = formation(9, *self.rally)              # gather round the rally point, not on one spot
        unit.move_to(*spots[self.trained % len(spots)])
        self.trained += 1
        return unit

    def ray_hit(self, origin, direction, height=2.7):
        """How far along a mouse ray it touches the HQ's walls or roof, or None."""
        hq = self.hq
        return _box_hit(origin, direction, (hq.i, 0.0, hq.j), (hq.i + hq.w, height, hq.j + hq.d))
