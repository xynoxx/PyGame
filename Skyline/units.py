"""Units on the map, the turrets and trenches they make, and the HQ that trains them.

Every unit walks the same way: it finds a path round anything in the way and
swings its arms and legs as it goes. The kinds differ in size, speed, look and
what they do in a fight. What they've been told to do is in orders.py, and the
zombies are in zombies.py.
"""
import math
import random

from deaths import Fall
from deposits import SPOT, Junkyard, Warehouse
from mathx import box_hit, turn_toward
from orders import FIRE_AT_WILL, HOLD_FIRE, Move
from stores import FREE, MATERIALS, Cost, Stores, owing, plus
from world import TRENCH_DEPTH

LOOK_EVERY = 0.2       # seconds between one shooter's looks round for zombies it can see (the
                       # line-of-sight checks are what costs; in between it keeps what it saw)

DEATH_TIME = 11.5      # seconds a fallen unit stays on the ground before it's gone...
FADE_TIME = 1.5        # ...fading away over the last of them
CLIMB_SPEED = 2.5      # how fast someone steps down into a trench or climbs out, tiles a second
BOARDS = 0.03          # how high the boards on a trench's floor are

LEVEL_KILLS = (0, 60, 160, 300, 500)  # the kills a soldier needs for each level, 1 to 5 (he kills many a game)
TROOP_LONG_SHOTS = 1.25  # troops open fire out to this many times their range (unless their kind says)...
TURRET_LONG_SHOTS = 1.5  # ...and turrets this many (past their range, most shots miss)
MISS_BY = (0.1, 0.7)     # how far a shot that misses goes by the side of its target, in tiles (at random)
SHOT = Cost(bullets=1)   # what one shot uses up, from a soldier or a turret
UPKEEP = Cost(supply=50)    # what each soldier and engineer eats...
UPKEEP_TIME = 30.0          # ...every so many seconds, from the HQ's stores
HUNGRY_PACE = 0.2        # how fast one who's hungry (there wasn't the supply to feed him) walks, of his speed (80% slower)...
HUNGRY_MISS = 0.3        # ...and how much less often his shots hit, at every range (30 in a hundred fewer)


class Fighter:
    """Anything of ours that shoots: a soldier or a turret. It counts what it kills, and with
    enough kills it goes up a level, as its kind's LEVEL_KILLS says (a soldier has five levels,
    a turret ten). Each level past the first adds LEVEL_RANGE to its range and LEVEL_HITS to
    how often it hits, at every distance.
    How often a shot hits what it's aimed at goes by how far off that is: HITS is a list of
    (out to this far, this often), nearest first. A shot that misses goes by the side of its
    target and flies on, so it may yet hit another zombie behind it. It shoots past its range,
    out to LONG_SHOTS times it; out there it mostly misses (as HITS says). Each shot does
    somewhere from DAMAGE[0] to DAMAGE[1]."""
    LEVEL_KILLS = LEVEL_KILLS
    LEVEL_RANGE = 1.0
    LEVEL_HITS = 0.01
    HITS = ((math.inf, 1.0),)
    LONG_SHOTS = 1.0     # how far it shoots, against its range (1: no further than that)
    DAMAGE = (10, 10)

    @property
    def level(self):
        """1 and up, by how many it has killed."""
        return sum(self.kills >= k for k in self.LEVEL_KILLS)

    @property
    def next_level_kills(self):
        """The kills it needs for the next level, or None at the top level."""
        return self.LEVEL_KILLS[self.level] if self.level < len(self.LEVEL_KILLS) else None

    @property
    def range(self):
        """How far it shoots well: its RANGE, and more for each level."""
        return self.RANGE + self.LEVEL_RANGE * (self.level - 1)

    @property
    def long_range(self):
        """How far off it will shoot at something at all."""
        return self.range * self.LONG_SHOTS

    def hit_chance(self, distance):
        """How often its shots hit what they're aimed at, `distance` off."""
        chance = next(chance for reach, chance in self.HITS if distance <= reach)
        return min(1.0, chance + self.LEVEL_HITS * (self.level - 1))

    def damage(self):
        """What one shot does, at random."""
        return random.randint(*self.DAMAGE)

    def count_kill(self):
        """It has killed something. If that takes it up a level, it goes on the world's list of
        those who did, for the game to show."""
        before = self.level
        self.kills += 1
        if self.level > before:
            self.world.promoted.append(self)


class Unit:
    RADIUS = 0.35       # how much room it takes up on the map
    walled = False      # (a building, with walls the dead spread along: see Zombie.think)
    SPEED = 3.6         # tiles per second
    TURN_RATE = 10.0    # radians per second
    SIZE = 1.5          # drawing scale of the model
    MAX_HP = 100
    STAYS_ON_MAP = True # never pushed off the edge of the map
    strafing = False    # facing something (to shoot it) rather than where it's walking
    big = False         # a tank: an oblong hull, not a round body (see tanks.Tank and keep_apart)

    def __init__(self, world, x, z):
        self.world = world
        self.x, self.z = x, z
        self.yaw = 0.0                  # 0 faces +Z (toward the camera at the start)
        self.path = []                  # points still to walk through
        self.halted = False             # standing still for now, though it has somewhere to go
        self.phase = 0.0                # walk cycle
        self.stride = 0.0               # 0 standing still .. 1 in full stride
        self.hp = self.MAX_HP
        self.dead_for = None            # seconds since it fell, or None while it's alive
        self.flash = 0.0                # a moment of red when it's hit
        self.end_yaw = None             # the way to face once it gets there (lined up), if any
        self.sink = 0.0                 # how far below the ground its feet are (down in a trench)
        self.fall = None                # how it went down, once it's killed (see deaths.py)

    @property
    def alive(self):
        return self.dead_for is None

    @property
    def gone(self):
        """Fallen long enough ago to be taken off the map."""
        return self.dead_for is not None and self.dead_for > DEATH_TIME

    @property
    def moving(self):
        return bool(self.path) and not self.halted

    @property
    def in_cover(self):
        """Standing still in a finished trench, where acid mostly splashes on the sandbags."""
        trench = self.world.trench_at(self.x, self.z)
        return self.alive and not self.moving and trench is not None and trench.built

    @property
    def dug_in(self):
        """In cover, in the middle of the trench's tile: nobody can jostle it out of there."""
        return self.in_cover and abs(self.x % 1 - 0.5) < 0.12 and abs(self.z % 1 - 0.5) < 0.12

    def rest_depth(self):
        """How far below the ground its feet come to rest where it stands (on a trench's boards)."""
        return max(0.0, self.world.floor_depth(self.x, self.z) - BOARDS)

    def settle(self, dt):
        """Step down into a trench, or climb out of one."""
        step = CLIMB_SPEED * dt
        self.sink += max(-step, min(step, self.rest_depth() - self.sink))

    def distance_to(self, other):
        return math.hypot(other.x - self.x, other.z - self.z)

    def gap(self, other):
        """How far it is from other's middle to this one's edge."""
        return self.distance_to(other) - self.RADIUS

    @property
    def bar_height(self):
        """How high over the ground its health bar goes: just over its head."""
        return 1.15 * self.SIZE - self.sink

    def holds(self, x, y, z, margin):
        """Is the point (x, y, z) in its body, or within `margin` of its side?"""
        return (math.hypot(x - self.x, z - self.z) <= self.RADIUS + margin
                and -self.sink <= y <= 1.35 * self.SIZE - self.sink)

    def spot_beside(self, unit, taken=()):
        """Where someone keeping by it (a guard) stands: a little way off, on his own side."""
        return spot_round(self, unit, 1.2, taken)

    def walk_to(self, x, z):
        """Walk to (x, z), around anything in the way."""
        self.path = self.world.find_path(self.x, self.z, x, z, self.RADIUS)
        self.end_yaw = None

    def hurt(self, damage, source=None):
        """Take a hit, from `source` (x, z) if it's known. True if it was the one that killed
        it: then it goes down, away from the blow."""
        if not self.alive:
            return False
        self.hp -= damage
        self.flash = 0.12
        if self.hp <= 0:
            self.hp = 0
            self.dead_for = 0.0
            self.path = []
            self.fall = Fall(self, source)
            return True
        return False

    def face(self, x, z, dt):
        """Turn toward a point; True once it's facing it."""
        heading = math.atan2(x - self.x, z - self.z)
        self.yaw = turn_toward(self.yaw, heading, self.TURN_RATE * dt)
        return abs((heading - self.yaw + math.pi) % (2 * math.pi) - math.pi) < 0.15

    def update(self, dt):
        self.flash = max(0.0, self.flash - dt)
        self.settle(dt)
        if not self.alive:
            self.dead_for += dt
            self.stride = 0.0
            return
        heading = self.follow_path(dt)
        if heading is not None and not self.strafing:
            self.yaw = turn_toward(self.yaw, heading, self.TURN_RATE * dt)
        elif not self.path and self.end_yaw is not None and not self.strafing:
            self.yaw = turn_toward(self.yaw, self.end_yaw, self.TURN_RATE * dt)   # face the way it was lined up

        target = 1.0 if self.moving else 0.0
        self.stride += (target - self.stride) * min(1.0, dt * 8)
        self.phase += dt * 9.0 * max(self.stride, 0.2) * self.pace / self.SPEED   # (slower, the legs swing slower)

    def follow_path(self, dt):
        """Walk along its path for a moment (not while it's halted). Returns the way it's
        walking, to turn to, or None if it isn't."""
        step = 0.0 if self.halted else self.pace * dt
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
        return heading

    @property
    def pace(self):
        """How fast it walks right now, in tiles a second."""
        return self.SPEED

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
        cx, cy, cz = self.x, 0.6 * self.SIZE - self.sink, self.z
        radius = 0.42 * self.SIZE
        ox, oy, oz = origin[0] - cx, origin[1] - cy, origin[2] - cz
        b = ox * direction[0] + oy * direction[1] + oz * direction[2]
        c = ox * ox + oy * oy + oz * oz - radius * radius
        disc = b * b - c
        if disc < 0:
            return None
        t = -b - math.sqrt(disc)
        return t if t > 0 else None


class Trooper(Unit):
    """One of ours, who takes orders (see orders.py): a soldier, an engineer or a tank. He
    works through his orders one by one, and never walks off after the dead on his own. Each
    kind costs COST to train (paid bit by bit as it's trained: see Trainer), and takes
    TRAIN_TIME seconds where it's trained (the HQ, or a vehicle factory), and uses its upkeep
    every UPKEEP_TIME from then on (Headquarters.feed): when there isn't the supply, he goes
    hungry, walks at HUNGRY_PACE of his speed, and (with a gun) hits HUNGRY_MISS less often,
    till he's fed. Acid that comes down on him burns for a moment (see burn). Only a Worker
    makes or mends things."""
    RADIUS = 0.28
    SIZE = 1.2
    TRAIN_TIME = 4.0     # seconds at the HQ
    COST = FREE
    COST_EVERY = 1.0     # (its cost given as so much every this many seconds of training, for the details)
    UPKEEP = UPKEEP      # what he uses every UPKEEP_TIME...
    LEVEL_UPKEEP = 0     # ...and how much less of its supply each level past the first (one with levels)
    armed = False        # carries a gun (see Gunner)
    job = None           # what he's making or mending (a Worker)
    working = False      # at work on it, there and then (a Worker)

    def __init__(self, *args):
        super().__init__(*args)
        self.orders = []            # what he's been told to do; the first is the one he's on
        self.target = None          # the zombie he was sent after, if any (a gunner)
        self.repath = 0.0
        self.burns = []             # [health a second, seconds left, (x, z) it came from] of acid on him
        self.hungry = False         # there wasn't the supply to feed him (see Headquarters.feed)

    @property
    def pace(self):
        return self.SPEED * (HUNGRY_PACE if self.hungry else 1.0)

    @property
    def upkeep(self):
        """What he uses every UPKEEP_TIME, at his level: his kind's UPKEEP, with LEVEL_UPKEEP
        less supply for each level past the first."""
        less = self.LEVEL_UPKEEP * (getattr(self, "level", 1) - 1)
        return Cost(max(0, self.UPKEEP.supply - less), self.UPKEEP.metal, self.UPKEEP.bullets)

    # ------------------------------------------------------------ orders

    def order(self, order, queue=False):
        """Give him an order: in place of all he's doing, or (queue) to do once the rest are done.
        An order the one before can take in (more sites to build, another patrol point) joins it."""
        if queue and self.orders:
            if not self.orders[-1].take_in(order, True):
                self.orders.append(order)
            return
        if self.orders and self.orders[0].take_in(order, False):
            return
        self.clear_doing()
        self.orders = [order]
        order.begin(self)

    def stop(self):
        """Drop every order, and stand where he is."""
        self.clear_doing()
        self.orders = []

    def clear_doing(self):
        """Leave off what the order he was on had him doing."""
        self.path = []
        self.target = None
        self.halted = False

    def plan_end(self):
        """Where he'll be once his orders are done."""
        for order in reversed(self.orders):
            point = order.end_point()
            if point:
                return point
        return self.x, self.z

    @property
    def shooting_in_range(self):
        """Standing to shoot something within his range (only a gunner can)."""
        return False

    def can_work_on(self, thing):
        """Can he make or mend it? (Only a Worker can make or mend anything.)"""
        return False

    def busy_with_job(self, dt):
        """Is he busy making or mending something, for a patrol or a guard to wait on? (A Worker.)"""
        return False

    def find_work(self, around, reach):
        """Something nearby to make or mend, for a worker on patrol (a Worker); None."""
        return None

    def obey(self, dt, around):
        """Carry on with the order he's on, and begin the next once it's done. Returns the
        order he finished just now, or None."""
        self.halted = False
        if not self.alive:
            return None
        if not self.orders:
            self.step_clear()
            return None
        order = self.orders[0]
        if order.update(self, dt, around):
            self.orders.pop(0)
            self.clear_doing()
            if self.orders:
                self.orders[0].begin(self)
            return order
        self.halted = order.halts and self.shooting_in_range      # (long shots, he takes on the move)
        return None

    def step_clear(self):
        """Standing with nothing to do where a turret's gun would swing into him: step out of
        its way. (Down in a trench, it swings over his head.)"""
        if self.path or self.sink > 0.1:
            return
        turret = self.world.gun_over(self.x, self.z, self.RADIUS)
        if turret:
            self.walk_to(*spot_round(turret, self, turret.gun_reach + self.RADIUS + 0.02))

    # ------------------------------------------------------------ acid

    def burn(self, damage, seconds, source):
        """Acid has come down on him: it burns him for `damage` in all, over `seconds`, from `source` (x, z)."""
        self.burns.append([damage / seconds, seconds, source])

    def update(self, dt):
        for burn in self.burns:
            if self.alive:
                self.hurt(burn[0] * min(dt, burn[1]), burn[2])
            burn[1] -= dt
        self.burns = [b for b in self.burns if b[1] > 0 and self.alive]
        super().update(dt)


class Gunner(Fighter, Trooper):
    """A trooper with a gun. Whatever he's doing, walking or not, he turns and shoots any
    zombie in reach that he can see (never through a wall), as far as his fire state lets
    him: out to his long range, though past his range most of his shots miss (see Fighter).
    His magazine holds MAGAZINE rounds: once it's empty he changes it, which takes
    MAGAZINE_TIME, his gun down; and with nothing left in reach he changes one that isn't
    full, so he starts the next fight with a full one. Each level past the first, he carries
    LEVEL_ROUNDS more a magazine and changes it LEVEL_CHANGE quicker (see magazine and
    change_time). (Turrets are fed by belt, and never stop.)"""
    RANGE = 10.0         # tiles
    LONG_SHOTS = TROOP_LONG_SHOTS
    RELOAD = 0.8         # seconds between shots
    MAGAZINE = 30        # rounds in a magazine at level 1...
    MAGAZINE_TIME = 5.0  # ...and seconds to change it for a full one
    LEVEL_ROUNDS = 5     # each level past the first: this many more rounds a magazine...
    LEVEL_CHANGE = 0.5   # ...and this many seconds quicker to change it
    AIM_HOLD = 1.2       # seconds the gun stays up after a shot
    armed = True

    def __init__(self, *args):
        super().__init__(*args)
        self.fire_state = FIRE_AT_WILL
        self.aim_at = None          # the zombie he's shooting at right now, if any
        self.reload = 0.0
        self.aiming = 0.0           # > 0 while the gun's up
        self.aim_blend = 0.0        # 0 gun carried across his chest .. 1 up to fire (for drawing)
        self.look = random.uniform(0, LOOK_EVERY)   # when he next looks round (staggered, not all at once)
        self.in_sight = []          # the zombies in reach (his long range) when he last looked
        self.seen = []              # those still standing and in his range now
        self.kills = 0              # what he has killed (see Fighter)
        self.rounds = self.magazine # rounds left in his magazine
        self.changing = 0.0         # > 0 while he changes magazines: the seconds left

    @property
    def shooting_in_range(self):
        return self.aim_at in self.seen

    @property
    def magazine(self):
        """How many rounds a full magazine of his holds, at his level."""
        return self.MAGAZINE + self.LEVEL_ROUNDS * (self.level - 1)

    @property
    def change_time(self):
        """How long he takes to change magazines, at his level."""
        return self.MAGAZINE_TIME - self.LEVEL_CHANGE * (self.level - 1)

    def hit_chance(self, distance):
        """As Fighter.hit_chance; hungry, he hits HUNGRY_MISS less often."""
        return max(0.0, super().hit_chance(distance) - (HUNGRY_MISS if self.hungry else 0.0))

    def chase(self, dt):
        """Close in on his target only till it's in reach (in range and in sight), then stand."""
        if self.target in self.seen:
            self.path = []
            return
        self.repath -= dt                # it moves, so follow it afresh now and then
        if self.repath <= 0:
            self.repath = 0.5
            self.walk_to(self.target.x, self.target.z)

    def sees(self, other):
        """Is there a clear line of fire to it (no wall between)?"""
        return self.world.line_clear(self.x, self.z, other.x, other.z)

    def fight(self, dt, zombies, stores):
        """Shoot the zombie he was sent after if he can, else whatever his fire state lets him:
        the nearest in reach (out to his long range), the nearest going for him, or nothing.
        Each shot uses a bullet from `stores`: with none left, he aims but can't fire. Each
        takes a round from his magazine; while he changes it, he turns to his target but
        can't fire, his gun down. Returns the zombie shot, or None."""
        self.reload = max(-dt, self.reload - dt)     # what's left of a frame counts toward the next shot
        if self.changing > 0:
            self.changing = max(0.0, self.changing - dt)
            if self.changing == 0.0:
                self.rounds = self.magazine
        self.aiming = 0.0 if self.changing else max(0.0, self.aiming - dt)
        self.aim_blend += ((1.0 if self.aiming > 0 else 0.0) - self.aim_blend) * min(1.0, dt * 12)
        self.strafing = False
        self.aim_at = None
        if not self.alive:
            return None
        if self.target and not self.target.alive:
            self.target = None

        far, near = self.long_range, self.range  # (worked out once, not once a zombie)
        self.look -= dt
        if self.look <= 0:                       # look round: who's in range, with nothing in the way?
            self.look += LOOK_EVERY
            self.in_sight = [z for z in zombies if z.alive and self.distance_to(z) <= far and self.sees(z)]
        reach = [z for z in self.in_sight if z.alive and self.distance_to(z) <= far]
        self.seen = [z for z in reach if self.distance_to(z) <= near]

        if self.target in reach:
            shoot = self.target
        elif self.fire_state == HOLD_FIRE:
            shoot = None
        else:
            free = reach if self.fire_state == FIRE_AT_WILL else [z for z in reach if z.victim is self]
            shoot = min(free, key=self.distance_to, default=None)
        if shoot:
            self.aim_at = shoot
            self.strafing = True                 # face it, even walking
            if self.changing:                    # changing magazines: his gun stays down
                self.face(shoot.x, shoot.z, dt)
            else:
                self.aiming = max(self.aiming, 0.3)
                if self.face(shoot.x, shoot.z, dt) and self.reload <= 0 and stores.pay(SHOT):
                    self.reload += self.RELOAD
                    self.aiming = self.AIM_HOLD
                    self.rounds -= 1
                    if self.rounds == 0:
                        self.changing = self.change_time
                    return shoot
        elif not self.changing and self.rounds < self.magazine:   # nothing in reach: a full magazine for the next
            self.changing = self.change_time
        self.reload = max(0.0, self.reload)      # (no shot this frame: nothing carries over)
        return None


class Worker(Trooper):
    """A trooper who can also make things, and mend them. His orders give him jobs: a turret
    or a trench to make, or a turret to repair. He goes to his own spot beside the job, round
    from anyone else on it, and works at it (more hands make faster work: see Site.do_work).
    A worker with a gun still shoots anything that comes in reach (as far as his fire state
    lets him), and leaves the work while he does."""
    WORK_REACH = 0.5     # how near a job's edge he must stand to work on it

    def __init__(self, *args):
        super().__init__(*args)
        self.job = None             # what he's making or mending now
        self.spot = None            # where he stands to work on it
        self.working = False        # at it right now (for drawing: the tool swings)
        self.hammer = 0.0

    def can_work_on(self, thing):
        """Can he make or mend this?"""
        return False

    def clear_doing(self):
        super().clear_doing()
        self.job = self.spot = None
        self.working = False

    def obey(self, dt, around):
        self.working = False
        return super().obey(dt, around)

    def take_job(self, job, crew):
        """Go to a job: to his own spot beside it, round from anyone else's on it, and from
        anyone standing by it."""
        taken = [e.spot for e in crew if e is not self and e.job is job and e.spot]
        taken += [(e.x, e.z) for e in crew if e is not self and e.job is not job and not e.moving and job.gap(e) < 1.0]
        self.job = job
        self.spot = job.spot_beside(self, taken)
        self.walk_to(*self.spot)

    def work(self, dt, taking_down=False):
        """Work on his job, if he's at it and not busy shooting: build it if it's unfinished,
        else repair it; or (taking_down) take it down. He lends it a hand this frame
        (Site.lend_hand), and it does the work of all its hands at once (Site.do_work)."""
        job = self.job
        if self.path or job.gap(self) > self.RADIUS + self.WORK_REACH:
            if not self.path:                        # pushed away: walk back to it
                self.walk_to(*(self.spot or job.spot_beside(self)))
            return                                   # (and he walks all the way to his spot)
        if self.strafing:                            # shooting: the work waits
            return
        self.face(*job.nearest_point(self.x, self.z), dt)
        job.lend_hand("down" if taking_down else "mend" if job.built else "build")
        self.working = True
        self.hammer += dt

    def busy_with_job(self, dt):
        """On patrol or guard: carry on with the job he took up there, if any. True if he had
        one (he drops it once it needs no more work)."""
        if not self.job:
            return False
        if self.job.needs_work:
            self.work(dt)
        else:
            self.job = self.spot = None
            self.working = False
        return True

    def find_work(self, around, reach):
        """The nearest thing within reach that he can make or mend, and that needs it."""
        things = around.structures + list(self.world.trenches.values())
        jobs = [t for t in things if self.can_work_on(t) and t.needs_work and t.gap(self) <= reach]
        return min(jobs, key=self.distance_to, default=None)


class Soldier(Worker, Gunner):
    """A rifleman with a modern rifle that fires fully automatic, from a magazine.
    He carries a shovel, and digs trenches."""
    NAME = "Soldier"
    SPEED = 3.0
    MAX_HP = 50
    RANGE = 20.0
    LONG_SHOTS = 1.5     # (as asked: range 20, long shots to 30)
    DAMAGE = (5, 10)
    RELOAD = 1 / 15      # fifteen shots a second
    HITS = ((5, 1.00), (20, 0.80), (30, 0.60), (math.inf, 0.10))
    LEVEL_RANGE = 0.0    # a level: 2% more hits at every range, 5 more rounds a magazine, half a second
    LEVEL_HITS = 0.02    # quicker to change it (Gunner), and 5 supply less upkeep
    LEVEL_UPKEEP = 5
    TRAIN_TIME = 2.0
    COST = Cost(supply=100)   # (50 supply a second, for 2 seconds)

    def can_work_on(self, thing):
        return isinstance(thing, Trench)


class Engineer(Worker):
    """He carries no gun. He builds turrets (semi-auto and full-auto), bullet factories,
    salvage cranes and loading dock posts, and repairs them."""
    NAME = "Engineer"
    SPEED = 3.0
    MAX_HP = 30
    TRAIN_TIME = 5.0
    COST = Cost(supply=50)    # (10 supply a second, for 5 seconds)

    def can_work_on(self, thing):
        return isinstance(thing, Structure)


class Site:
    """Something workers make on one tile. Laid out, it's only a blueprint: it lasts while
    a worker has it in his orders, and it can be called off. Once a worker starts on it,
    it's real, and it's finished bit by bit. One worker alone takes BUILD_TIME; each one more
    adds MORE_HANDS of one worker's pace (so a crew is faster, but not by as much again for
    every man). The same goes for repairing it and taking it down."""
    RADIUS = 0.5         # it fills its tile
    BUILD_TIME = 8.0     # seconds for one worker
    MORE_HANDS = 1.0     # what each worker past the first adds, of one worker's pace
    COST = FREE          # what it costs to make, paid bit by bit as it's made (see pay_for)...
    COST_EVERY = 10.0    # ...given as so much every this many seconds, for one worker (for the details)
    coming_down = False  # an engineer has orders to take it down (only a structure can be)

    def __init__(self, world, i, j):
        self.world = world
        self.i, self.j = i, j
        self.x, self.z = i + 0.5, j + 0.5
        self.started = False        # a worker has begun on it: no longer a blueprint
        self.progress = 0.0         # 0 just begun .. 1 finished
        self.dead_for = None
        self.hands = {}             # this frame: how many are at each kind of work on it ("build", "mend", "down")
        self.paid = FREE            # what's been paid for it so far
        self.short = None           # the material there wasn't enough of to go on building it, last frame
        self.build_rate = 0.0       # how fast it was built last frame (of all of it, a second)

    @property
    def built(self):
        return self.progress >= 1.0

    @property
    def blueprint(self):
        return self.alive and not self.started

    def begin(self):
        self.started = True

    def cancel(self):
        """Call a blueprint off (it goes at once: nothing was made)."""
        self.dead_for = 99.0

    @property
    def alive(self):
        return self.dead_for is None

    @property
    def gone(self):
        return self.dead_for is not None and self.dead_for > 1.5

    def add_progress(self, amount):
        self.progress = min(1.0, self.progress + amount)

    def lend_hand(self, task):
        """A worker is at it this frame: building it ("build"), repairing it ("mend") or taking
        it down ("down")."""
        self.hands[task] = self.hands.get(task, 0) + 1

    def pay_for(self, amount, stores):
        """Pay out of `stores` what building `amount` more of it costs (its share of COST, each
        material rounded up), if there's enough. True if it was paid, or costs nothing (or
        there are no stores to pay from: work done outside a game)."""
        owed = owing(self.COST, min(1.0, self.progress + amount), self.paid)
        if not any(owed) or stores is None:
            return True
        if not stores.pay(owed):
            self.short = stores.short_of(owed)
            return False
        self.paid = plus(self.paid, owed)
        return True

    def do_work(self, dt, stores=None):
        """The work done on it this frame, by however many lent a hand: one alone does dt of
        BUILD_TIME, and each one more adds MORE_HANDS of that. Building is paid for as it
        goes, out of `stores` (see pay_for): with too little to pay for the next of it, the
        building waits (and, not yet begun, it stays a blueprint)."""
        self.short, self.build_rate = None, 0.0
        for task, n in self.hands.items():
            amount = dt / self.BUILD_TIME * (1 + self.MORE_HANDS * (n - 1))
            if task == "build":
                if not self.pay_for(amount, stores):
                    continue
                self.begin()                         # laid out no longer: the work has started
                self.add_progress(amount)
                self.build_rate = amount / dt
            elif task == "mend":
                self.mend(amount)
            else:
                self.take_down(amount)
        self.hands = {}

    def mend(self, amount):
        """Repair `amount` of it (1: from nothing to whole). Only a structure needs it."""

    def take_down(self, amount):
        """Take `amount` of it down (1: all of it). Only a structure can be."""

    @property
    def needs_work(self):
        return self.alive and not self.built

    def gap(self, other):
        """How far it is from other's middle to this one's edge."""
        return self.distance_to(other) - self.RADIUS

    def spot_beside(self, worker, taken=()):
        """Where a worker stands to work on it (or a guard to guard it): beside it."""
        return spot_round(self, worker, self.RADIUS + worker.RADIUS + 0.2, taken)

    def nearest_point(self, x, z):
        """The point on its tile nearest to (x, z): where a worker beside it faces."""
        return min(max(x, self.i), self.i + 1), min(max(z, self.j), self.j + 1)

    def distance_to(self, other):
        return math.hypot(other.x - self.x, other.z - self.z)


class Trench(Site):
    """One tile of trench, dug by soldiers. It goes down a spadeful at a time. Anyone can walk
    through it, and the dead ignore it; whoever stands still in a finished one is in cover."""
    NAME = "Trench"
    BUILD_TIME = 5.0     # seconds for one soldier...
    MORE_HANDS = 0.5     # ...and each one more digs half as fast again as one
    STAGES = 5           # spadefuls: how many depths it's drawn at on its way down

    @property
    def stage(self):
        """How many spadefuls are out, 0 for a blueprint."""
        return min(self.STAGES, math.ceil(self.progress * self.STAGES) + 1) if self.started else 0

    @property
    def depth(self):
        return TRENCH_DEPTH * self.stage / self.STAGES

    def begin(self):
        if not self.started:
            self.started = True
            self.world.trench_changes += 1

    def add_progress(self, amount):
        before = self.stage, self.built      # full depth comes before the boards and sandbags go in
        super().add_progress(amount)
        if (self.stage, self.built) != before:
            self.world.trench_changes += 1

    def cancel(self):
        super().cancel()
        del self.world.trenches[self.i, self.j]

    def fill(self):
        """A turret or a building goes up over it: it's filled in, dug or not."""
        self.cancel()
        self.world.trench_changes += 1


class Structure(Site):
    """Something engineers build that stands on its tiles and the dead attack: a turret (one
    tile) or a building (W by D tiles from its corner tile i, j). Laid out, it's only a
    blueprint: it doesn't take up its tiles, the dead ignore it, and it can be called off.
    Once an engineer starts on it, it's a real foundation (it fills its tiles, and units on
    them step off) and is built up, no use till it's done; it has health as it goes up. It
    can be repaired, taken down (building in reverse) or wrecked."""
    W = D = 1            # how many tiles it takes up, across (x) and deep (z)
    MAX_HP = 500
    TOP = 1.4            # how high its walls stand (where spit comes down on it, and the mouse finds it)
    MORE_HANDS = 0.2     # each engineer more builds a fifth as fast again as one
    in_cover = False     # acid always finds it
    moving = False
    walled = False       # (a building has walls the dead spread along; a turret is gone round)

    def __init__(self, world, i, j):
        super().__init__(world, i, j)
        self.x, self.z = i + self.W / 2, j + self.D / 2
        self.hp = self.MAX_HP * 0.1
        self.flash = 0.0

    @property
    def tiles(self):
        return [(i, j) for i in range(self.i, self.i + self.W) for j in range(self.j, self.j + self.D)]

    def begin(self):
        """An engineer starts on it: from now it fills its tiles (a trench there is filled in)."""
        if not self.started:
            self.started = True
            for tile in self.tiles:
                trench = self.world.trenches.get(tile)
                if trench:
                    trench.fill()
                self.world.set_blocked(*tile, True)
                self.world.structures[tile] = self

    def clear_tiles(self):
        """It's gone (wrecked, or taken down to nothing): its tiles are free again."""
        for tile in self.tiles:
            self.world.set_blocked(*tile, False)
            del self.world.structures[tile]

    @property
    def needs_work(self):
        """Unfinished, or hurt (and not coming down)."""
        return self.alive and not self.coming_down and (not self.built or self.hp < self.MAX_HP)

    def add_progress(self, amount):
        """Building also mends: it's at full strength the moment it's done."""
        amount = min(amount, 1.0 - self.progress)
        super().add_progress(amount)
        self.hp = min(self.MAX_HP, self.hp + self.MAX_HP * 0.9 * amount)

    def mend(self, amount):
        """Engineers repair it, as fast as they'd build it: one makes it whole from nothing in BUILD_TIME."""
        self.hp = min(self.MAX_HP, self.hp + self.MAX_HP * amount)

    def take_down(self, amount):
        """Engineers take it down, building in reverse: it shrinks (no longer built, so it's of
        no use), and once the last of it is gone, so is it."""
        self.progress = max(0.0, self.progress - amount)
        self.hp = min(self.hp, self.MAX_HP * (0.1 + 0.9 * self.progress))
        if self.progress <= 0.0:
            self.cancel()

    def cancel(self):
        """It goes at once, with no wreck (a blueprint called off, or the last of it taken
        down), and its tiles are free again."""
        if self.started:
            self.clear_tiles()
        super().cancel()

    def hurt(self, damage, source=None):
        """Take a hit (from wherever: it stands where it is). True if it wrecked it."""
        if not self.alive:
            return False
        self.hp -= damage
        self.flash = 0.12
        if self.hp <= 0:
            self.hp = 0
            self.dead_for = 0.0
            if self.started:                                  # wrecked: its tiles are free again
                self.clear_tiles()
            return True
        return False

    def nearest_point(self, x, z):
        """The point on its tiles nearest to (x, z): where a worker beside it faces."""
        return min(max(x, self.i), self.i + self.W), min(max(z, self.j), self.j + self.D)

    def ray_hit(self, origin, direction):
        """How far along a mouse ray it touches it, or None."""
        return box_hit(origin, direction, (self.i, 0.0, self.j), (self.i + self.W, self.TOP, self.j + self.D))


class Turret(Structure, Fighter):
    """A semi-automatic gun on a concrete block, on one tile. Built, it turns to the nearest
    zombie it can see and fires, out to its long range (past its range, most of its shots
    miss), each shot using a bullet. The dead attack it if they find it."""
    NAME = "Semi-auto turret"
    MAX_HP = 100
    RANGE = 30.0
    LONG_SHOTS = TURRET_LONG_SHOTS
    DAMAGE = (10, 20)
    RELOAD = 0.6         # semi-auto: a shot each time it's ready, on its target
    HITS = ((5, 1.00), (15, 0.99), (20, 0.90), (30, 0.80), (math.inf, 0.30))
    TURN_RATE = 3.5
    BUILD_TIME = 30.0    # seconds for one engineer (each one more a fifth as fast again as one)
    COST = Cost(metal=150)   # (50 metal every 10 seconds, for 30)
    LEVEL_KILLS = (0, 20, 50, 100, 200, 350, 550, 800, 1100, 1500)   # ten levels
    LEVEL_HITS = 0.02
    HEIGHT = 1.05        # the barrel's height, where tracers start
    MUZZLE = 0.78        # how far in front of the post its muzzle is
    KICK = 0.12          # how long the gun is thrown back by a shot, in seconds
    ready = True         # it can fire (a minigun must spin up first)

    def __init__(self, world, i, j):
        super().__init__(world, i, j)
        self.yaw = 0.0
        self.reload = 0.0
        self.recoil = 0.0
        self.look = random.uniform(0, LOOK_EVERY)
        self.in_sight = []
        self.kills = 0

    def begin(self):
        """An engineer starts on it: from now it fills its tile, and its gun will swing round over it."""
        if not self.started:
            super().begin()
            self.world.guns[self.i, self.j] = self

    def clear_tiles(self):
        super().clear_tiles()
        del self.world.guns[self.i, self.j]

    @property
    def gun_reach(self):
        """How far from its middle the gun reaches as it turns (its muzzle, and a little)."""
        return self.MUZZLE + 0.08

    def sees(self, other):
        return self.world.line_clear(self.x, self.z, other.x, other.z, skip=(self.i, self.j))

    def fight(self, dt, zombies, stores):
        """Turn to the nearest zombie it can see within its long range, and fire, a bullet from
        `stores` a shot (with none left, it can't). Returns the zombie shot, or None."""
        self.reload = max(-dt, self.reload - dt)     # what's left of a frame counts toward the next shot
        self.recoil = max(0.0, self.recoil - dt)
        self.flash = max(0.0, self.flash - dt)
        if not self.alive:
            self.dead_for += dt
            return None
        if not self.built:
            return None
        far = self.long_range                    # (worked out once, not once a zombie)
        self.look -= dt
        if self.look <= 0:
            self.look += LOOK_EVERY
            self.in_sight = [z for z in zombies if z.alive and self.distance_to(z) <= far and self.sees(z)]
        seen = [z for z in self.in_sight if z.alive and self.distance_to(z) <= far]
        if not seen:
            return None
        target = min(seen, key=self.distance_to)
        heading = math.atan2(target.x - self.x, target.z - self.z)
        self.yaw = turn_toward(self.yaw, heading, self.TURN_RATE * dt)
        facing = abs((heading - self.yaw + math.pi) % (2 * math.pi) - math.pi) < 0.08
        if facing and self.reload <= 0 and self.ready and stores.pay(SHOT):
            self.reload += self.RELOAD
            self.recoil = self.KICK
            return target
        return None

    def muzzle(self):
        return (self.x + math.sin(self.yaw) * self.MUZZLE, self.HEIGHT, self.z + math.cos(self.yaw) * self.MUZZLE)

    def spot_beside(self, worker, taken=()):
        """Beside it, but clear of the gun when it turns his way."""
        return spot_round(self, worker, self.gun_reach + worker.RADIUS + 0.02, taken)


class MinigunTurret(Turret):
    """A fully automatic turret, a minigun with six turning barrels: it fires far faster,
    reaches further, turns faster and stands up to more than a semi-auto turret, but it costs
    far more, takes longer to build, and goes through bullets twenty a second. It shakes as
    it fires, so it hits less often close up. Its barrels must spin up before it fires, and
    keep turning for a moment after."""
    NAME = "Full-auto turret"
    MAX_HP = 500
    RANGE = 40.0
    DAMAGE = (5, 15)
    RELOAD = 0.05        # twenty shots a second
    HITS = ((10, 0.90), (30, 0.80), (40, 0.70), (80, 0.20), (math.inf, 0.10))
    TURN_RATE = 5.0
    BUILD_TIME = 100.0
    COST = Cost(metal=1000)  # (100 metal every 10 seconds, for 100)
    MUZZLE = 0.86
    KICK = 0.02
    SPIN_UP = 0.4        # seconds from still to firing speed
    SPIN_DOWN = 1.5      # seconds from firing speed to still
    BARREL_SPEED = 40.0  # radians a second at firing speed

    def __init__(self, world, i, j):
        super().__init__(world, i, j)
        self.spin = 0.0             # 0 barrels still .. 1 at firing speed
        self.barrels = 0.0          # how far round they've turned (for drawing)

    @property
    def ready(self):
        return self.spin >= 1.0

    def fight(self, dt, zombies, stores):
        """Spin up while there's something to shoot at, and run down when there isn't."""
        far = self.long_range                    # (worked out once, not once a zombie)
        busy = (self.alive and self.built
                and any(z.alive and self.distance_to(z) <= far for z in self.in_sight))
        change = dt / self.SPIN_UP if busy else -dt / self.SPIN_DOWN
        self.spin = max(0.0, min(1.0, self.spin + change))
        self.barrels += self.spin * self.BARREL_SPEED * dt
        return super().fight(dt, zombies, stores)


class Building(Structure):
    """Something engineers put up on W by D tiles (not a turret). The dead go for its walls as
    they do for the HQ's."""
    BUILD_TIME = 40.0    # seconds for one engineer (each one more a fifth as fast again as one)
    walled = True
    working = False      # (one that makes something works, once it's built: see Maker)

    def update(self, dt, stores):
        """Count the time since it was wrecked. (A Maker makes what it makes, too.) True if it
        ran out of work just now."""
        self.flash = max(0.0, self.flash - dt)
        if not self.alive:
            self.dead_for += dt
        return False

    def gap(self, other):
        """How far it is from other's middle to its walls (its tiles' edge)."""
        return math.dist(self.nearest_point(other.x, other.z), (other.x, other.z))

    def spot_beside(self, unit, taken=()):
        """Where someone stands by its walls (to build or repair it, or to guard it): the
        nearest spot to him of those all the way round (not in a wall: none on a deposit's
        side), but not by a spot someone else has taken."""
        out = unit.RADIUS + 0.05
        spots = []
        for k in range(self.W):
            spots += [(self.i + k + 0.5, self.j - out), (self.i + k + 0.5, self.j + self.D + out)]
        for k in range(self.D):
            spots += [(self.i - out, self.j + k + 0.5), (self.i + self.W + out, self.j + k + 0.5)]
        free = [s for s in spots if all(math.dist(s, t) > 0.6 for t in taken)
                and not self.world.hits_wall(*s, unit.RADIUS) and not self.world.gun_over(*s, unit.RADIUS)] or spots
        return min(free, key=lambda s: math.dist(s, (unit.x, unit.z)))


class Maker(Building):
    """A building that makes something: once it's built, MAKES every MAKE_TIME seconds while
    it's working, each batch using up INPUT from the stores. While there isn't the INPUT, or
    there's no room in the stores for what it makes, or the player has switched it off (`on`),
    it waits (and uses nothing)."""
    MAKES = FREE
    INPUT = FREE         # what each batch uses up from the stores
    MAKE_TIME = 10.0

    def __init__(self, world, i, j):
        super().__init__(world, i, j)
        self.making = 0.0           # seconds toward the next batch
        self.on = True              # switched on (the player can switch it off, and on again)

    @property
    def working(self):
        """Built and standing (and with something to work on)."""
        return self.alive and self.built

    def can_make(self, stores):
        """Can it get on with its batch: is there what the batch uses, and room for what it makes?"""
        return not stores.short_of(self.INPUT) and not any(stores.full(name) for name, amount in zip(MATERIALS, self.MAKES)
                                                             if amount)

    def update(self, dt, stores):
        """Make what it makes, while it's working, into `stores` (waiting, its batch where it
        got to, while it can't: see can_make); count the time since it was wrecked. True if
        it ran out of work just now."""
        self.flash = max(0.0, self.flash - dt)
        if not self.alive:
            self.dead_for += dt
            return False
        if not self.working:
            return False
        if self.on and self.can_make(stores):
            self.making = min(self.MAKE_TIME, self.making + dt)
        while self.making >= self.MAKE_TIME and self.working and self.on and self.can_make(stores):
            self.making -= self.MAKE_TIME
            self.make(stores)
        if not self.working:
            self.making = 0.0
            return True
        return False

    def make(self, stores):
        """One batch is done: what it used out of the stores, and what it made into them."""
        stores.pay(self.INPUT)
        stores.add(self.MAKES)



class RadarStation(Building):
    """A radar station: a big dish on a pedestal, on a round concrete deck. It makes nothing:
    once it's built, the whole map is open (World.open_all), for good."""
    NAME = "Radar station"
    W = D = 6
    MAX_HP = 3000
    TOP = 1.6            # its pedestal (its dish turns higher, out of reach)
    BUILD_TIME = 120.0
    COST = Cost(supply=10000, metal=5000)


class Factory(Maker):
    """A bullet factory: a small brick works, W by D tiles (smaller than the HQ), anywhere
    there's room. Built, it makes bullets out of supply and metal for as long as it stands,
    but not while the stores are full of bullets."""
    NAME = "Bullet factory"
    W, D = 4, 3
    MAX_HP = 200
    TOP = 1.3            # its hall's walls (its chimneys stand higher)
    BUILD_TIME = 30.0
    COST = Cost(metal=150)   # (50 metal every 10 seconds, for 30)
    MAKES = Cost(bullets=200)
    INPUT = Cost(supply=40, metal=10)
    MAKE_TIME = 10.0


class Extractor(Maker):
    """A building that strips a deposit (deposits.py): it goes up on the deposit's building
    spot, beside it, its back to it, and makes what the deposit holds while any is left.
    Once the deposit's stripped, it stands idle (it can be taken down)."""
    W = D = SPOT
    DEPOSIT = None       # the kind of deposit it goes up beside

    def __init__(self, world, deposit):
        super().__init__(world, *deposit.spot)
        self.deposit = deposit

    @property
    def working(self):
        return super().working and not self.deposit.emptied

    def make(self, stores):
        """Take a batch from the deposit, as much as there is left of it."""
        name = self.deposit.MATERIAL
        got = self.deposit.take(getattr(self.MAKES, name))
        stores.add(Cost(**{name: got}))


class SalvageCrane(Extractor):
    """A salvage crane beside a junkyard: a crane on tracks with a long arm and a magnet. It
    lifts the wrecked cars out over the fence, one at a time, and drops each into the baler
    beside it, which crushes it into blocks of metal."""
    NAME = "Salvage crane"
    DEPOSIT = Junkyard
    MAX_HP = 400
    TOP = 1.0            # its tracks and cab (its arm stands higher, out of reach)
    COST = Cost(supply=400, metal=200)   # (100 supply and 50 metal every 10 seconds, for 40)
    MAKES = Cost(metal=Junkyard.PER_CAR)
    MAKE_TIME = 30.0     # a car each time


class LoadingDock(Extractor):
    """A loading dock post at a warehouse: a truck backed up to its middle bay, a forklift,
    sandbags round it and a floodlight. Crates pile up beside the truck, and every MAKE_TIME
    seconds a load goes to the stores."""
    NAME = "Loading dock post"
    DEPOSIT = Warehouse
    MAX_HP = 400
    TOP = 1.45           # the truck
    COST = Cost(supply=400, metal=200)   # (100 supply and 50 metal every 10 seconds, for 40)
    MAKES = Cost(supply=500)
    MAKE_TIME = 10.0


def spot_round(thing, unit, reach, taken=()):
    """A spot `reach` from thing's middle on unit's side, but round from any spot someone
    else has taken (so they don't stand on each other), and clear of walls and guns."""
    heading = math.atan2(unit.x - thing.x, unit.z - thing.z)
    angles = [math.atan2(x - thing.x, z - thing.z) for x, z in taken]
    for step in (0, 1, -1, 2, -2, 3, -3, 4):
        a = heading + step * 0.9
        x, z = thing.x + math.sin(a) * reach, thing.z + math.cos(a) * reach
        if (all(abs((a - t + math.pi) % (2 * math.pi) - math.pi) > 0.6 for t in angles)
                and not thing.world.hits_wall(x, z, unit.RADIUS) and not thing.world.gun_over(x, z, unit.RADIUS)):
            return x, z
    return thing.x + math.sin(heading) * reach, thing.z + math.cos(heading) * reach


def keep_apart(units, world):
    """Nudge units that stand on each other apart, never into a wall (nor ours out of the open
    part of the map). Only those on the same or a neighbouring tile can overlap (nobody but a
    tank is a tile across), so each is checked against those alone, in the order they're
    listed: with hundreds of the dead about, checking every pair took too long. A tank (or its
    wreck) keeps everyone near it off its hull, and other tanks off it (Tank.shove)."""
    hulls = [u for u in units if u.big and u.standing]
    units = [u for u in units if u.alive and not u.big]
    tiles = {}
    for k, u in enumerate(units):
        tiles.setdefault((math.floor(u.x), math.floor(u.z)), []).append(k)
    for k, a in enumerate(units):
        i, j = math.floor(a.x), math.floor(a.z)
        near = sorted(n for di in (-1, 0, 1) for dj in (-1, 0, 1) for n in tiles.get((i + di, j + dj), ()) if n > k)
        for b in (units[n] for n in near):
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
                if unit.dug_in:
                    continue
                x, z = unit.x + sx, unit.z + sz
                if world.hits_wall(x, z, unit.RADIUS):
                    continue
                x0, z0, x1, z1 = world.open
                if unit.STAYS_ON_MAP and not (x0 + unit.RADIUS <= x <= x1 - unit.RADIUS
                                              and z0 + unit.RADIUS <= z <= z1 - unit.RADIUS):
                    continue
                unit.x, unit.z = x, z
    for k, tank in enumerate(hulls):
        reach = math.ceil(tank.LENGTH / 2) + 1
        i, j = math.floor(tank.x), math.floor(tank.z)
        near = [units[n] for di in range(-reach, reach + 1) for dj in range(-reach, reach + 1)
                for n in tiles.get((i + di, j + dj), ())]
        tank.shove(near, hulls[k + 1:])


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


def send_to_spots(units, spots, make=None, queue=False):
    """Give each unit its own spot, the nearest spots to whoever's nearest (to where he'll be
    once his other orders are done, if this one is queued after them), and the order
    make(unit, x, z) for it: by default, a move there."""
    left = list(units)
    for sx, sz in spots:
        unit = min(left, key=lambda u: math.dist(u.plan_end() if queue else (u.x, u.z), (sx, sz)))
        left.remove(unit)
        unit.order(make(unit, sx, sz) if make else Move(sx, sz), queue)


class Trainer:
    """What trains units (the HQ, a vehicle factory): the kinds waiting to be trained, in
    order (the first is in training), how far along that one is, the door they come out of
    and the rally point where they gather."""
    TRAINS = ()

    def start_training(self, door, rally, facing=0.0):
        self.queue = []                # the kinds waiting to be trained, in order; the first is in training
        self.training = 0.0            # how far along the one in training is, 0 to 1 (not `progress`: a building's how far it's built)
        self.door = door               # where a new one comes out...
        self.facing = facing           # ...facing this way
        self.rally = rally             # where they gather
        self.trained = 0
        self.paid = FREE               # what's been paid for the one in training so far
        self.train_rate = 0.0          # how fast it was trained last frame (of a unit, a second; 0 waiting)

    def queued(self, kind):
        return sum(k is kind for k in self.queue)

    def enqueue(self, kind):
        """Add one to the queue (it's paid for as it's trained: see train_step)."""
        self.queue.append(kind)
        return True

    def dequeue(self, kind, stores):
        """Take the last of that kind off the queue (if it was the one in training, what's
        been paid for it goes back into `stores`, and the next starts afresh). False if
        there were none of that kind on it."""
        for k in range(len(self.queue) - 1, -1, -1):
            if self.queue[k] is kind:
                del self.queue[k]
                if k == 0:
                    stores.add(self.paid)
                    self.paid, self.training = FREE, 0.0
                return True
        return False

    def train_step(self, dt, stores):
        """Train for a moment, paying as it goes out of `stores` (its kind's COST, a share at a
        time: with too little for the next of it, it waits, and costs nothing). Returns a new
        unit when one is ready, already on its way to the rally point, or None."""
        self.train_rate = 0.0
        if not self.queue:
            return None
        kind = self.queue[0]
        amount = dt / kind.TRAIN_TIME
        owed = owing(kind.COST, min(1.0, self.training + amount), self.paid)
        if any(owed) and not stores.pay(owed):
            return None
        self.paid = plus(self.paid, owed)
        self.training += amount
        self.train_rate = amount / dt
        if self.training < 1.0:
            return None
        self.training, self.paid = 0.0, FREE
        self.queue.pop(0)
        unit = kind(self.world, *self.door)
        unit.yaw = self.facing
        room = max(1.0, 2 * kind.RADIUS + 0.4)         # (a tank needs more room than a man)
        spots = formation(9, *self.rally, room)        # gather round the rally point, not on one spot
        unit.order(Move(*spots[self.trained % len(spots)]))
        self.trained += 1
        return unit


class Headquarters(Trainer):
    """The HQ as it plays: its health, what it's training, how far along, where new units
    gather, and the stores of materials (see stores.py). It repairs itself, and makes some of
    each material as time goes by (INCOME); bullet factories make more bullets."""
    TRAINS = (Soldier, Engineer)
    MAX_HP = 1000
    REPAIR_TIME = 600.0  # seconds it takes to make itself whole from nothing
    INCOME = ((Cost(supply=1000), 30.0), (Cost(metal=100), 30.0), (Cost(bullets=500), 30.0))   # (made, every so many seconds)
    TOP = 3.13           # how high its walls stand (as models.HQ_TOP: four storeys), where spit comes down on it
    in_cover = False     # acid always finds its walls
    walled = True

    def __init__(self, world, hq):
        self.world = world
        self.hq = hq
        self.hp = self.MAX_HP
        self.flash = 0.0
        self.stores = Stores()
        self.making = [0.0] * len(self.INCOME)   # seconds toward the next of each kind of income
        self.feeding = 0.0             # seconds toward feeding the troops again (UPKEEP_TIME)
        self.start_training((hq.i + hq.w / 2, hq.j + hq.d + 0.4), (hq.i + hq.w / 2, hq.j + hq.d + 3.0))

    @property
    def alive(self):
        return self.hp > 0

    @property
    def x(self):
        return self.hq.i + self.hq.w / 2

    @property
    def z(self):
        return self.hq.j + self.hq.d / 2

    def hurt(self, damage, source=None):
        """Take a hit (from wherever: the HQ stands where it is)."""
        self.hp = max(0, self.hp - damage)
        self.flash = 0.12

    def nearest_point(self, x, z):
        """The point on the HQ's tiles nearest to (x, z)."""
        hq = self.hq
        return min(max(x, hq.i), hq.i + hq.w), min(max(z, hq.j), hq.j + hq.d)

    def gap(self, other):
        """How far it is from other's middle to the HQ's walls."""
        return math.dist(self.nearest_point(other.x, other.z), (other.x, other.z))

    def spot_beside(self, unit, taken=()):
        """Where someone stands by the walls (to repair them, or to guard them): the nearest
        spot to him of those all the way round, but not by a spot someone else has taken.
        As near the slab as he can stand, for the walls are set back on it."""
        hq, out = self.hq, unit.RADIUS + 0.05
        spots = []
        for k in range(hq.w):                      # the walls facing -Z and +Z
            spots += [(hq.i + k + 0.5, hq.j - out), (hq.i + k + 0.5, hq.j + hq.d + out)]
        for k in range(hq.d):                      # and those facing -X and +X
            spots += [(hq.i - out, hq.j + k + 0.5), (hq.i + hq.w + out, hq.j + k + 0.5)]
        free = [s for s in spots if all(math.dist(s, t) > 0.6 for t in taken)
                and not self.world.gun_over(*s, unit.RADIUS)] or spots
        return min(free, key=lambda s: math.dist(s, (unit.x, unit.z)))

    def feed(self, dt, troops):
        """Feed the troops (the living soldiers, engineers and tanks, oldest first): every
        UPKEEP_TIME, each one's upkeep from the stores. One there isn't enough left for goes
        hungry; between times, a hungry one is fed as soon as there's enough for him. Returns
        how many went hungry just now (at a feeding), or 0."""
        if not self.alive:
            return 0
        self.feeding += dt
        if self.feeding >= UPKEEP_TIME:
            self.feeding -= UPKEEP_TIME
            for trooper in troops:
                trooper.hungry = not self.stores.pay(trooper.upkeep)
            return sum(t.hungry for t in troops)
        for trooper in troops:
            if trooper.hungry and self.stores.pay(trooper.upkeep):
                trooper.hungry = False
        return 0

    def train(self, kind):
        """Add one to the queue (paid for as it's trained)."""
        return self.enqueue(kind)

    def cancel(self, kind):
        """Take the last of that kind off the queue, and get back what it cost. False if there
        were none of that kind on it."""
        return self.dequeue(kind, self.stores)

    def update(self, dt):
        """Make materials, repair itself, and train; returns a new unit when one is ready,
        already walking to the rally point."""
        self.flash = max(0.0, self.flash - dt)
        if not self.alive:
            return None
        for k, (made, every) in enumerate(self.INCOME):
            self.making[k] += dt
            while self.making[k] >= every:
                self.making[k] -= every
                self.stores.add(made)
        self.hp = min(self.MAX_HP, self.hp + self.MAX_HP / self.REPAIR_TIME * dt)
        return self.train_step(dt, self.stores)

    def ray_hit(self, origin, direction):
        """How far along a mouse ray it touches the HQ's walls or roof (and the railing round it), or None."""
        hq = self.hq
        return box_hit(origin, direction, (hq.i, 0.0, hq.j), (hq.i + hq.w, self.TOP + 0.25, hq.j + hq.d))
