"""Orders: what each of the player's units has been told to do.

A unit keeps a list of orders and works through them in turn. The first is the
one it's on; holding Shift adds a new order to the end instead of replacing
them all. Most orders finish by themselves (a move once it's there, an attack
once the zombie is down, a build once it's all built). Patrol and guard go on
until another order takes their place.
"""
from collections import namedtuple

LOOK_FOR_WORK = 0.5     # seconds between a patrolling or guarding unit's looks round for something to do
PATROL_REACH = 8.0      # how far off his beat a worker on patrol goes to build or repair
GUARD_NEAR = 2.5        # how far from what he guards a guard may stand
GUARD_REACH = 10.0      # how far from it he goes after a zombie that's going for it

# Fire states: when a unit shoots without being told to. Sent after a zombie, he shoots it whatever his state.
FIRE_AT_WILL = "Fire at will"   # anything in reach
RETURN_FIRE = "Return fire"     # only zombies going for him
HOLD_FIRE = "Hold fire"         # nothing
FIRE_STATES = (FIRE_AT_WILL, RETURN_FIRE, HOLD_FIRE)

# What a unit needs to know about the battle to follow its orders, handed to it every frame:
# the zombies, every worker (to share out the work), the turrets and buildings, and the HQ.
Around = namedtuple("Around", "zombies crew structures base")


class Order:
    """Something a unit has been told to do."""
    COLOR = (1.0, 1.0, 1.0)  # the line drawn to it, for a selected unit
    halts = False            # on the way, he stops while there's a zombie he's shooting at

    def begin(self, unit):
        """It becomes the order he's on."""

    def update(self, unit, dt, around):
        """Carry it on for a moment. True once it's done."""
        return True

    def take_in(self, other, queued):
        """Can this order take in a newer one (a patrol another point, a build more sites)? If so, do."""
        return False

    def points(self):
        """Where it takes him, in order, for the line drawn to it."""
        return []

    def end_point(self):
        """Where he'll be when it's done (where the next order in the queue starts from)."""
        points = self.points()
        return points[-1] if points else None


class Move(Order):
    """Walk to a spot, round anything in the way, and face `yaw` there (if given). He shoots
    what comes in reach on the way, but doesn't stop for it."""
    COLOR = (0.45, 1.0, 0.55)

    def __init__(self, x, z, yaw=None):
        self.x, self.z = x, z
        self.yaw = yaw

    def begin(self, unit):
        unit.walk_to(self.x, self.z)
        unit.end_yaw = self.yaw

    def update(self, unit, dt, around):
        return not unit.path

    def points(self):
        return [(self.x, self.z)]


class Attack(Order):
    """Go after one zombie: close in only till it's in range and in sight, then stand and
    shoot it till it falls (soldiers only: engineers carry no gun)."""
    COLOR = (1.0, 0.35, 0.30)

    def __init__(self, zombie):
        self.zombie = zombie

    def begin(self, unit):
        unit.target = self.zombie
        unit.repath = 0.0

    def update(self, unit, dt, around):
        if not self.zombie.alive:
            return True
        unit.target = self.zombie
        unit.chase(dt)
        return False

    def points(self):
        return [(self.zombie.x, self.zombie.z)]


class Patrol(Order):
    """Walk a beat, from where he was to each point given and back to the start, again and
    again. He stops to shoot whatever comes in his range (long shots past it, he takes on the
    move). A worker on patrol also builds or repairs anything nearby that needs it, then goes
    back to his beat."""
    COLOR = (0.40, 0.70, 1.0)
    halts = True

    def __init__(self, start, point):
        self.beat = [start, point]
        self.leg = 1                    # the point he's walking to
        self.look = 0.0

    def begin(self, unit):
        unit.walk_to(*self.beat[self.leg])

    def update(self, unit, dt, around):
        if unit.busy_with_job(dt):
            if not unit.job:            # done with it: back to the beat
                unit.walk_to(*self.beat[self.leg])
            return False
        self.look -= dt
        if self.look <= 0:
            self.look = LOOK_FOR_WORK
            job = unit.find_work(around, PATROL_REACH)
            if job:
                unit.take_job(job, around.crew)
                return False
        if not unit.path:
            self.leg = (self.leg + 1) % len(self.beat)
            unit.walk_to(*self.beat[self.leg])
        return False

    def take_in(self, other, queued):
        """Shift and another patrol point: the beat goes on to it."""
        if queued and isinstance(other, Patrol):
            self.beat.append(other.beat[-1])
            return True
        return False

    def points(self):
        """Round the beat from the point he's walking to, and back to it."""
        return self.beat[self.leg:] + self.beat[:self.leg + 1]

    def end_point(self):
        return self.beat[0]


class Guard(Order):
    """Stay by one of your units, a turret, a building or the HQ, and look after it: go after
    any zombie that's going for it (a soldier), help with its work (a worker guarding a worker
    of his own kind), and repair it when it's hurt (an engineer guarding a turret or a building)."""
    COLOR = (0.35, 0.90, 0.85)

    def __init__(self, thing):
        self.thing = thing
        self.spot = None                # where he stands by it
        self.look = 0.0

    def update(self, unit, dt, around):
        thing = self.thing
        if not thing.alive:
            return True
        if unit.busy_with_job(dt):
            return False
        self.look -= dt
        looked = self.look <= 0
        if looked:
            self.look = LOOK_FOR_WORK
            attackers = [z for z in around.zombies
                         if z.alive and z.victim is thing and thing.gap(z) <= GUARD_REACH]
            if attackers and unit.armed and unit.fire_state == FIRE_AT_WILL:
                unit.target = min(attackers, key=unit.distance_to)
            elif unit.can_work_on(getattr(thing, "job", None)):   # (only a worker has a job)
                unit.take_job(thing.job, around.crew)        # help him with what he's making
                return False
            elif unit.can_work_on(thing) and thing.needs_work:
                unit.take_job(thing, around.crew)            # build it, or repair it
                return False
        if unit.target and unit.target.alive:
            unit.chase(dt)
            return False
        unit.target = None
        if thing.gap(unit) > GUARD_NEAR and (looked or not unit.path):
            taken = [e.orders[0].spot for e in around.crew if e is not unit and e.orders
                     and isinstance(e.orders[0], Guard) and e.orders[0].thing is thing and e.orders[0].spot]
            self.spot = thing.spot_beside(unit, taken)
            unit.walk_to(*self.spot)                         # off to it, or it has moved on: keep up
        return False

    def points(self):
        return [(self.thing.x, self.thing.z)]


class Remove(Order):
    """Take a turret or a building down (engineers only), a bit at a time: it takes as long as
    building it. It's of no use from the first blow, and once the last of it is gone its
    tiles are free again."""
    COLOR = (1.0, 0.45, 0.35)

    def __init__(self, structure):
        self.structure = structure

    def update(self, unit, dt, around):
        if not self.structure.alive:
            return True
        if unit.job is not self.structure:
            unit.take_job(self.structure, around.crew)
        unit.work(dt, taking_down=True)
        return False

    def points(self):
        return [(self.structure.x, self.structure.z)]


class Build(Order):
    """Make a list of things (turrets, buildings or trenches), one after another: each time the
    unfinished one with the fewest others on it, the nearest first, so a crew spreads over
    the work. He leaves the work while he shoots."""
    COLOR = (1.0, 0.84, 0.47)

    def __init__(self, sites):
        self.sites = list(sites)        # still to make
        self.laid = list(sites)         # all it was given
        self.site = None                # the one he's on

    def update(self, unit, dt, around):
        self.sites = [s for s in self.sites if s.alive and not s.built and not s.coming_down]
        if unit.job not in self.sites:
            unit.job = None
            if not self.sites:
                return True
            others = {id(s): sum(e.job is s for e in around.crew if e is not unit) for s in self.sites}
            unit.take_job(min(self.sites, key=lambda s: (others[id(s)], unit.distance_to(s))), around.crew)
        self.site = unit.job
        unit.work(dt)
        return False

    def take_in(self, other, queued):
        """More sites laid out while he's building: they join the work he's on."""
        if isinstance(other, Build):
            new = [s for s in other.sites if s not in self.sites]
            self.sites += new
            self.laid += new
            return True
        return False

    def points(self):
        site = self.site if self.site in self.sites else self.sites[0] if self.sites else None
        return [(site.x, site.z)] if site else []


class Repair(Order):
    """Repair a turret or a building till it's whole again (engineers only; the HQ repairs itself)."""
    COLOR = (1.0, 0.84, 0.47)

    def __init__(self, thing):
        self.thing = thing

    def update(self, unit, dt, around):
        if not self.thing.needs_work:
            return True
        if unit.job is not self.thing:
            unit.take_job(self.thing, around.crew)
        unit.work(dt)
        return False

    def points(self):
        return [(self.thing.x, self.thing.z)]

