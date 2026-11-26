"""Tanks, and the vehicle factory that makes them.

A tank is one of ours, trained at a vehicle factory, that takes orders as soldiers do (move,
patrol, guard, attack, stop, fire states). It's big: an oblong hull on two tracks rather than
a round body, so it keeps others off its hull (shove, from keep_apart), finds its way with room
to turn on the spot (its RADIUS, the circle it sweeps), and the dead come at its sides. It has
three guns: a main gun in its turret that fires explosive shells, and two machine guns on the
turret roof that work as a semi-auto turret does.

Everything high on it is out of everyone's way: the main gun's barrel is higher than anyone
stands (and a turret's gun), so it swings over their heads, and the machine guns higher
still. What turns low (the turret) stays over its hull.
"""
import math
import random

from mathx import box_hit, turn_toward
from orders import FIRE_AT_WILL, HOLD_FIRE, RETURN_FIRE
from stores import Cost
from units import (HUNGRY_MISS, LEVEL_KILLS, LOOK_EVERY, SHOT, Building, Fighter, Trainer,
                   Trooper, Turret, spot_round)

WRECK_TIME = 30.0      # seconds a wrecked tank stands burnt out before it's gone...
SINK_TIME = 3.0        # ...sinking away over the last of them
LOOK_AT_MOST = 40      # the most zombies a tank checks its line of fire to, each time it looks round


def wrapped(angle):
    """An angle brought into -pi..pi."""
    return (angle + math.pi) % (2 * math.pi) - math.pi


class MachineGun:
    """One of a tank's two machine guns, each on its own mount on the turret roof and turning
    on its own. It works as a semi-auto turret does (with a semi-auto turret's damage and hit
    rates, at its first level), but faster, and with its tank's main gun's range: it turns to
    the zombie it's given and fires, a bullet a shot. What it kills counts for its tank, and it
    misses more while its tank is hungry."""
    RANGE = 30.0         # (the main gun's: 30, long shots to 40)
    LONG_SHOTS = 40 / 30
    DAMAGE = Turret.DAMAGE
    RELOAD = 0.3         # seconds between shots
    HITS = Turret.HITS
    TURN_RATE = Turret.TURN_RATE
    KICK = 0.12          # how long it's thrown back by a shot, in seconds

    def __init__(self, tank, mount, height, reach):
        self.tank = tank
        self.mount = mount          # where its post stands on the turret: (across, along) from the turret's middle
        self.height = height        # how high its barrel is
        self.reach = reach          # how far in front of its post its muzzle is
        self.turn = 0.0             # the way it faces, on the turret (0: the way the turret faces)
        self.reload = 0.0
        self.recoil = 0.0
        self.aim_at = None

    @property
    def yaw(self):
        """The way it faces, on the map."""
        return self.tank.turret_yaw + self.turn

    @property
    def place(self):
        """Where its post is, on the map: (x, z)."""
        return self.tank.on_turret(*self.mount)

    @property
    def x(self):
        return self.place[0]

    @property
    def z(self):
        return self.place[1]

    @property
    def long_range(self):
        return self.RANGE * self.LONG_SHOTS

    def hit_chance(self, distance):
        chance = next(chance for reach, chance in self.HITS if distance <= reach)
        return max(0.0, chance - (HUNGRY_MISS if self.tank.hungry else 0.0))

    def damage(self):
        return random.randint(*self.DAMAGE)

    def count_kill(self):
        self.tank.count_kill()

    def muzzle(self):
        x, z = self.place
        return (x + math.sin(self.yaw) * self.reach, self.height, z + math.cos(self.yaw) * self.reach)

    def fight(self, dt, target, stores):
        """Turn to `target` (or stay as it is, with none) and fire when it's on it, a bullet
        from `stores` a shot. True if it fired."""
        self.reload = max(-dt, self.reload - dt)     # what's left of a frame counts toward the next shot
        self.recoil = max(0.0, self.recoil - dt)
        self.aim_at = target
        if target is None:
            self.reload = max(0.0, self.reload)
            return False
        x, z = self.place
        heading = math.atan2(target.x - x, target.z - z)
        self.turn = turn_toward(self.turn, heading - self.tank.turret_yaw, self.TURN_RATE * dt)
        if abs(wrapped(heading - self.yaw)) < 0.08 and self.reload <= 0 and stores.pay(SHOT):
            self.reload += self.RELOAD
            self.recoil = self.KICK
            return True
        return False


class Tank(Fighter, Trooper):
    """A tank on two tracks, with a turret. It drives where it's sent, turning on its tracks
    (slowly, and slower still the more it has to turn: on the spot for a sharp turn), and
    fights as it goes:
    - Its main gun fires an explosive shell, every RELOAD seconds (LEVEL_RELOAD quicker each
      level past the first), each using SHELL from the stores. The turret turns to the nearest
      zombie it can see in its long range (or the one it was sent after); on target (HITS),
      the shell bursts on it, else BLAST and more off to its side. The blast does DAMAGE to
      everything of the dead within BLAST of it (less toward its edge; nothing to our own).
    - Its two machine guns shoot the nearest zombies they can see, as two semi-auto turrets.
    Its fire state goes for all three guns. It uses UPKEEP supply as a soldier eats his (less
    as it goes up a level, as his does).
    Wrecked, it stands burnt out for WRECK_TIME, then it's gone."""
    NAME = "Tank"
    LENGTH, WIDTH = 3.4, 2.1   # its hull on its tracks, front to back and side to side (tiles)
    TOP = 1.62                 # the top of its turret (the machine guns stand higher)
    RADIUS = math.hypot(LENGTH, WIDTH) / 2   # the circle its hull sweeps turning on the spot: the room it keeps
    SIZE = 1.0
    SPEED = 3.0
    TURN_RATE = 1.3            # radians a second, on its tracks
    MAX_HP = 500
    TRAIN_TIME = 20.0
    COST = Cost(metal=200)     # (50 metal every 5 seconds, for 20)
    COST_EVERY = 5.0
    UPKEEP = Cost(supply=100)
    LEVEL_UPKEEP = 5           # 5 supply less upkeep a level past the first
    big = True
    armed = True
    # its main gun
    RANGE = 30.0
    LONG_SHOTS = 40 / 30       # (as asked: range 30, long shots to 40)
    HITS = ((30, 1.00), (40, 0.80), (math.inf, 0.20))
    DAMAGE = (100, 200)
    LEVEL_KILLS = LEVEL_KILLS  # (five levels, as a soldier)
    LEVEL_RANGE = 0.0          # (a level makes it reload quicker and use less supply, nothing else)
    LEVEL_HITS = 0.0
    RELOAD = 6.0               # seconds to load the next shell, at level 1...
    LEVEL_RELOAD = 0.5         # ...and this much quicker each level past the first
    SHELL = Cost(bullets=30)   # what a shell uses up
    BLAST = 6.0                # how far a shell's blast reaches, in tiles
    BLAST_EDGE = 0.25          # what it does at its edge, of what it does where the shell bursts
    MISS_BY = (6.5, 9.0)       # how far beside its target a shell that's off target bursts (past the blast's reach)
    TURRET_AT = -0.1           # how far forward of the hull's middle the turret turns
    TURRET_TURN = 1.2          # how fast the turret turns, radians a second
    GUN_HEIGHT = 1.5           # the main gun's barrel: how high (over anyone's head, and a turret's gun)...
    GUN_FROM = 0.95            # ...from how far in front of the turret's middle...
    MUZZLE = 2.55              # ...to its muzzle
    KICK = 0.3                 # how long the gun runs back after a shot, in seconds
    # its machine guns: where each one's post stands on the turret (across, along from its middle), how high
    # its foot is (on the commander's cupola, on the loader's hatch), how high its barrel, how far its muzzle
    # is in front of the post. The commander's is higher than the loader's, so as they turn they pass.
    GUN_POSTS = (((0.38, -0.3), 1.74, 1.87, 0.55), ((-0.38, -0.3), 1.65, 1.71, 0.50))

    def __init__(self, world, x, z):
        super().__init__(world, x, z)
        self.fire_state = FIRE_AT_WILL
        self.turret_turn = 0.0      # the way the turret faces, on the hull (0: forward)
        self.round_way = 0          # turning the long way round (+1 or -1) because the short way's walled, or 0
        self.reload = 0.0           # seconds till the next shell is loaded
        self.recoil = 0.0
        self.look = random.uniform(0, LOOK_EVERY)
        self.kills = 0
        self.aim_at = None          # what the main gun is turned on
        self.in_reach = False       # what it was sent after is in its reach and in sight
        self.picks = []             # what the machine guns are on (the nearest, at the last look round)
        self.rolled = [0.0, 0.0]    # how far its right and left tracks have run (for drawing)
        self.guns = [MachineGun(self, mount, height, reach) for mount, _, height, reach in self.GUN_POSTS]

    # ------------------------------------------------------------ its body

    @property
    def gone(self):
        return self.dead_for is not None and self.dead_for > WRECK_TIME

    @property
    def standing(self):
        """Alive, or a wreck not yet sinking away: something others must keep off."""
        return self.dead_for is None or self.dead_for < WRECK_TIME - SINK_TIME

    @property
    def sunk(self):
        """How far a wreck has sunk into the ground, 0 to 1."""
        if self.dead_for is None:
            return 0.0
        return max(0.0, min(1.0, (self.dead_for - (WRECK_TIME - SINK_TIME)) / SINK_TIME))

    @property
    def in_cover(self):
        return False

    @property
    def dug_in(self):
        return False

    def rest_depth(self):
        """It rides over a trench on its tracks (a trench is one tile wide): it never goes down into one."""
        return 0.0

    @property
    def bar_height(self):
        return self.TOP + 0.4

    def to_hull(self, x, z):
        """A point on the map in the hull's own frame: (across, to the right; along, forward)."""
        dx, dz = x - self.x, z - self.z
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return dx * c - dz * s, dx * s + dz * c

    def from_hull(self, across, along):
        """A point in the hull's frame, on the map."""
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return self.x + across * c + along * s, self.z - across * s + along * c

    def nearest_point(self, x, z):
        """The point of its hull nearest (x, z): where the dead come at it."""
        a, b = self.to_hull(x, z)
        return self.from_hull(min(max(a, -self.WIDTH / 2), self.WIDTH / 2), min(max(b, -self.LENGTH / 2), self.LENGTH / 2))

    def gap(self, other):
        """How far it is from other's middle to its hull."""
        return math.dist(self.nearest_point(other.x, other.z), (other.x, other.z))

    def spot_beside(self, unit, taken=()):
        """Where someone keeping by it (a guard) stands: clear of it, however it turns."""
        return spot_round(self, unit, self.RADIUS + unit.RADIUS + 0.1, taken)

    def holds(self, x, y, z, margin):
        a, b = self.to_hull(x, z)
        return (abs(a) <= self.WIDTH / 2 + margin and abs(b) <= self.LENGTH / 2 + margin
                and 0.0 <= y <= self.TOP + margin)

    def ray_hit(self, origin, direction):
        """How far along a mouse ray it touches its hull or turret, or None."""
        if not self.alive:
            return None
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        ox, oz = origin[0] - self.x, origin[2] - self.z
        o = (ox * c - oz * s, origin[1], ox * s + oz * c)
        d = (direction[0] * c - direction[2] * s, direction[1], direction[0] * s + direction[2] * c)
        return box_hit(o, d, (-self.WIDTH / 2, 0.0, -self.LENGTH / 2), (self.WIDTH / 2, self.TOP, self.LENGTH / 2))

    @staticmethod
    def room_at(world, x, z, yaw):
        """Is there room for a tank's hull at (x, z), facing yaw: no wall under any of it, and
        all of it on the open part of the map?"""
        c, s = math.cos(yaw), math.sin(yaw)
        x0, z0, x1, z1 = world.open
        n_across, n_along = 6, 9
        for p in range(n_across + 1):
            a = -Tank.WIDTH / 2 + Tank.WIDTH * p / n_across
            for q in range(n_along + 1):
                b = -Tank.LENGTH / 2 + Tank.LENGTH * q / n_along
                px, pz = x + a * c + b * s, z - a * s + b * c
                if not (x0 <= px < x1 and z0 <= pz < z1) or world.is_blocked(math.floor(px), math.floor(pz)):
                    return False
        return True

    def tiles_under(self):
        """The tiles its hull stands on (for the dead to keep off as they fall)."""
        tiles = set()
        for p in range(5):
            for q in range(7):
                x, z = self.from_hull(-self.WIDTH / 2 + self.WIDTH * p / 4, -self.LENGTH / 2 + self.LENGTH * q / 6)
                tiles.add((math.floor(x), math.floor(z)))
        return tiles

    def hurt(self, damage, source=None):
        """Take a hit. True if it was the one that wrecked it: then it stops where it is, burnt out."""
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

    def follow_path(self, dt):
        """Drive along its path: it turns on its tracks toward the next point, and the more it
        has yet to turn the slower it goes (for a sharp turn, it turns on the spot), so it
        keeps to its path, which has room for it. Returns None: it has turned itself."""
        if self.halted or not self.path:
            return None
        tx, tz = self.path[0]
        dx, dz = tx - self.x, tz - self.z
        dist = math.hypot(dx, dz)
        if dist < 1e-6:
            self.path.pop(0)
            return None
        before = self.yaw
        heading = math.atan2(dx, dz)
        self.yaw = turn_toward(self.yaw, heading, self.TURN_RATE * dt)
        off = abs(wrapped(heading - self.yaw))
        step = min(dist, self.pace * dt * max(0.0, math.cos(off)) ** 4)
        self.x += dx / dist * step
        self.z += dz / dist * step
        if step >= dist:
            self.path.pop(0)
        turned = wrapped(self.yaw - before) * self.WIDTH / 2   # (turning, one track runs back and the other on)
        self.rolled[0] += step - turned
        self.rolled[1] += step + turned
        return None

    def shove(self, others, tanks):
        """Keep others off its hull: a man or a zombie on it goes off its nearest side, all at
        once (or, with a wall behind him, it gives way, if it's alive and has room). Another
        tank keeps RADIUS off it each, as two men do (see keep_apart)."""
        world = self.world
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        for u in others:
            a, b = self.to_hull(u.x, u.z)
            pa, pb = self.WIDTH / 2 + u.RADIUS - abs(a), self.LENGTH / 2 + u.RADIUS - abs(b)
            if pa <= 0 or pb <= 0:
                continue
            da, db = (math.copysign(pa + 0.001, a), 0.0) if pa < pb else (0.0, math.copysign(pb + 0.001, b))
            dx, dz = da * c + db * s, -da * s + db * c
            x, z = u.x + dx, u.z + dz
            x0, z0, x1, z1 = world.open
            on_map = not u.STAYS_ON_MAP or (x0 + u.RADIUS <= x <= x1 - u.RADIUS and z0 + u.RADIUS <= z <= z1 - u.RADIUS)
            if not u.dug_in and on_map and not world.hits_wall(x, z, u.RADIUS):
                u.x, u.z = x, z
            elif self.alive and self.room_at(world, self.x - dx, self.z - dz, self.yaw):
                self.x, self.z = self.x - dx, self.z - dz
        for t in tanks:
            dx, dz = t.x - self.x, t.z - self.z
            d = math.hypot(dx, dz)
            gap = self.RADIUS + t.RADIUS
            if d >= gap:
                continue
            if d < 1e-4:
                dx, dz, d = 1.0, 0.0, 1.0
            push = (gap - d) / 2 * 0.5
            nx, nz = dx / d * push, dz / d * push
            for tank, sx, sz in ((self, -nx, -nz), (t, nx, nz)):
                if tank.alive and self.room_at(world, tank.x + sx, tank.z + sz, tank.yaw):
                    tank.x, tank.z = tank.x + sx, tank.z + sz

    # ------------------------------------------------------------ its guns

    @property
    def turret_yaw(self):
        """The way the turret faces, on the map."""
        return self.yaw + self.turret_turn

    def on_turret(self, across, along):
        """A point on the turret (across, along from its middle, turned with it), on the map: (x, z)."""
        tx, tz = self.from_hull(0.0, self.TURRET_AT)
        c, s = math.cos(self.turret_yaw), math.sin(self.turret_yaw)
        return tx + across * c + along * s, tz - across * s + along * c

    def muzzle(self):
        x, z = self.on_turret(0.0, self.MUZZLE)
        return x, self.GUN_HEIGHT, z

    @property
    def reload_time(self):
        """How long it takes to load the next shell, at its level."""
        return self.RELOAD - self.LEVEL_RELOAD * (self.level - 1)

    def hit_chance(self, distance):
        """As Fighter.hit_chance; hungry, it hits HUNGRY_MISS less often."""
        return max(0.0, super().hit_chance(distance) - (HUNGRY_MISS if self.hungry else 0.0))

    def blast_damage(self, damage, distance):
        """What a blast that does `damage` where it bursts does `distance` from there."""
        if distance > self.BLAST:
            return 0
        return round(damage * (1.0 - (1.0 - self.BLAST_EDGE) * distance / self.BLAST))

    @property
    def shooting_in_range(self):
        return self.aim_at is not None and self.distance_to(self.aim_at) <= self.range

    def barrel_clear(self, turn):
        """Would the main gun's barrel, with the turret turned so on the hull, be clear of
        every wall? (It passes over turrets: it's higher than their guns.)"""
        world = self.world
        tx, tz = self.from_hull(0.0, self.TURRET_AT)
        yaw = self.yaw + turn
        ux, uz = math.sin(yaw), math.cos(yaw)
        d = self.GUN_FROM
        while d <= self.MUZZLE + 1e-6:
            tile = (math.floor(tx + ux * d), math.floor(tz + uz * d))
            if world.is_blocked(*tile) and not isinstance(world.structures.get(tile), Turret):
                return False
            d += 0.25
        return True

    def turn_turret(self, want, dt):
        """Turn the turret toward `want` (an angle on the hull), the short way round, or the
        long way if the barrel would hit a wall going the short way. True once it's on it."""
        step = self.TURRET_TURN * dt
        off = wrapped(want - self.turret_turn)
        if abs(off) <= step:
            new = want
        else:
            way = self.round_way or (1 if off > 0 else -1)
            new = self.turret_turn + way * step
        if self.barrel_clear(new):
            self.turret_turn = wrapped(new)
        elif not self.round_way and abs(off) > step:      # walled the short way: go round the other
            self.round_way = -1 if off > 0 else 1
        on = abs(wrapped(want - self.turret_turn)) < 0.05
        if on:
            self.round_way = 0
        return on

    def sees(self, other):
        """Is there a clear line of fire to it (no wall between)?"""
        return self.world.line_clear(self.x, self.z, other.x, other.z)

    def may_shoot(self, zombie):
        """Does its fire state let it shoot this one, unbidden?"""
        return self.fire_state == FIRE_AT_WILL or (self.fire_state == RETURN_FIRE and zombie.victim is self)

    def look_round(self, zombies):
        """What it can see, nearest first: what the main gun goes for (what it was sent after,
        if that's in reach; else the nearest its fire state lets it shoot) and what the
        machine guns go for (the two nearest in their reach, or what it was sent after)."""
        far, gun_far = self.long_range, MachineGun.RANGE * MachineGun.LONG_SHOTS
        near = [z for z in zombies if z.alive and abs(z.x - self.x) <= far and abs(z.z - self.z) <= far]
        near.sort(key=self.distance_to)
        target = self.target if self.target and self.target.alive else None
        self.in_reach = target is not None and self.distance_to(target) <= far and self.sees(target)
        main = target if self.in_reach else None
        picks = [target] if self.in_reach and self.distance_to(target) <= gun_far else []
        if self.fire_state != HOLD_FIRE:
            looked = 0
            for z in near:
                if (main and len(picks) >= 2) or looked >= LOOK_AT_MOST:
                    break
                d = self.distance_to(z)
                if d > far or (main and d > gun_far) or z is target or not self.may_shoot(z):
                    continue
                looked += 1
                if not self.sees(z):
                    continue
                main = main or z
                if d <= gun_far and len(picks) < 2:
                    picks.append(z)
        self.aim_at, self.picks = main, picks

    def chase(self, dt):
        """Close in on its target only till it's in reach (in range and in sight), then stop."""
        if self.in_reach:
            self.path = []
            return
        self.repath -= dt
        if self.repath <= 0:
            self.repath = 1.0
            self.walk_to(self.target.x, self.target.z)

    def fight(self, dt, zombies, stores):
        """Turn the turret and the machine guns on what it can see, and fire them. Returns the
        shots fired, as (what fired: the tank for its main gun, or a machine gun; at what)."""
        self.reload = max(0.0, self.reload - dt)
        self.recoil = max(0.0, self.recoil - dt)
        if not self.alive:
            return []
        if self.target and not self.target.alive:
            self.target = None
        self.look -= dt
        if self.look <= 0:
            self.look += LOOK_EVERY
            self.look_round(zombies)
        shots = []
        aim = self.aim_at
        if aim and not (aim.alive and self.distance_to(aim) <= self.long_range):
            aim = self.aim_at = None
        if aim:
            want = math.atan2(aim.x - self.x, aim.z - self.z) - self.yaw
            if self.turn_turret(want, dt) and self.reload <= 0 and stores.pay(self.SHELL):
                self.reload = self.reload_time
                self.recoil = self.KICK
                shots.append((self, aim))
        gun_far = MachineGun.RANGE * MachineGun.LONG_SHOTS
        picks = [z for z in self.picks if z.alive and self.distance_to(z) <= gun_far]
        for k, gun in enumerate(self.guns):
            target = picks[k % len(picks)] if picks else None
            if gun.fight(dt, target, stores):
                shots.append((gun, target))
        return shots


class VehicleFactory(Building, Trainer):
    """A vehicle factory: a tall steel shed on W by D tiles, with a door wide enough for a
    tank in its front, and a lower workshop along one side. Built, it trains tanks (one at a
    time, from a queue, as the HQ trains men). A tank comes out of its door and drives to its
    rally point; while something's in the way of the door, the next waits inside."""
    NAME = "Vehicle factory"
    W, D = 7, 5
    MAX_HP = 500
    TOP = 2.3            # its walls (its roof's ridge stands higher)
    BUILD_TIME = 90.0
    COST = Cost(supply=1000, metal=500)
    TRAINS = (Tank,)
    DOOR_X = 2.7         # how far along its front (from its corner) its door's middle is

    def __init__(self, world, i, j):
        super().__init__(world, i, j)
        x = i + self.DOOR_X
        self.start_training((x, j + self.D + Tank.LENGTH / 2 + 0.15), (x, j + self.D + 7.0))
        self.blocked = False        # a tank is ready, but something's in the way of the door

    @property
    def ready(self):
        """Built and standing, and not being taken down: it can train."""
        return self.alive and self.built and not self.coming_down

    def door_clear(self):
        """Is there room for a tank to come out of the door?"""
        return Tank.room_at(self.world, *self.door, self.facing)

    def train_step(self, dt, stores):
        """Train, while it's ready; a tank that's done waits inside while the door's blocked."""
        self.train_rate = 0.0
        if not self.ready:
            return None
        self.blocked = bool(self.queue) and self.training + dt / self.queue[0].TRAIN_TIME >= 1.0 and not self.door_clear()
        if self.blocked:
            return None
        return super().train_step(dt, stores)
