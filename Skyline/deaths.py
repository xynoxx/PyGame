"""How the dead fall, and how they lie.

When a unit or a zombie is killed, a Fall is picked for it there and then: it goes down away
from the blow that killed it, turning as it goes so it lands on its back or on its face, with
its arms flung out and its legs apart, each time a little differently. With a wall in the way
it turns to fall where there's room, or slumps down against the wall. In a trench it lies
along the trench if it runs far enough, or sits with its back to the earth.

A Pose then works out, from the corners of the body's model, how the body, arms and legs lie
at each moment of the fall so that they come to rest on the ground: nothing floats, and
nothing goes into the ground. A soldier with a pack on lies propped up a little on it.

Bodies keep off each other if they can. One that can't falls onto the bodies already there
and rests on top of them: tilted as it settles, as low as it can, its arms and legs draped
over whatever is under them (the world keeps a map of how high the dead lie, World.tops).
"""
import math
import random

import mathx
from world import TOP_CELL

FALL_REACH = 1.3       # how far from his feet a fallen body reaches (head and arms), in body heights
BODY_ROOM = 0.3        # how wide a strip a fallen body needs, each side of its middle, in tiles
HIP_Y = 0.42           # the hips' height in the models, where the legs hang from
SHOULDER_Y = 0.80      # and the shoulders'
TRENCH_ARMS = 0.08     # lying along a trench (one tile wide): how far his arms come out from his sides
WALL_GAP = 0.02        # sitting in a trench: how near his back comes to the earth wall, in tiles
GUN_DROP = 0.35        # seconds a dropped gun takes to reach the ground
SAMPLE = 0.1           # how far apart the points are, on a part's surfaces, that it rests on (model)
TOP_SAMPLE = 0.05      # and the closer points a lying body marks the map with, for others to rest on
SETTLE = (-0.25, 0.0, 0.25)   # lying on bodies: the tilts tried, each way, to settle lowest
PILE_TRIES = 4         # lying on bodies: the most ways of going down tried, before taking the last


def turn_between(a, b):
    """The shortest turn from angle a to angle b."""
    return (b - a + math.pi) % (2 * math.pi) - math.pi


class Fall:
    """How someone goes down, picked the moment he's killed. `source` is where the killing
    blow came from (x, z), or None. It keeps a list of ways he could go down, the likeliest
    first (see lay_out): fall away from the blow, arms and legs flung out; the same, tucked
    in; fall another way; and last, slump where he is."""

    def __init__(self, unit, source):
        self.world = unit.world
        self.size = unit.SIZE
        self.start = (unit.x, unit.z)
        self.time = random.uniform(0.5, 0.8)          # seconds to reach the ground
        self.yaw_from = unit.yaw                      # (the way his body faced)
        self.lean = random.uniform(0.12, 0.3)         # sitting: how far back he leans
        self.tilt = random.uniform(-0.15, 0.15)       # and to one side
        self.gun_side = random.choice((-1, 1))        # which side his gun would rather land on
        self.gun_turn = random.uniform(-0.6, 0.6)
        self.pose = None                              # worked out when it's first drawn
        self.gun_rest = None                          # and where his gun lands: (x, y, z, turn) in his pose's frame
        self.rest_parts = None                        # once he's at rest: (how far he'd sunk, his parts' matrices)
        self.rests_on = set()                         # the bodies he lies on top of
        self.top_cells = ()                           # where he's marked on the map of how high the dead lie
        self.tiles = ()                               # the tiles he lies on, once he's laid out
        if source and math.hypot(unit.x - source[0], unit.z - source[1]) > 1e-6:
            self.away = math.atan2(unit.x - source[0], unit.z - source[1])
        else:
            self.away = random.uniform(-math.pi, math.pi)
        self.flung = ([random.uniform(1.0, 2.5), random.uniform(1.0, 2.5)],
                      (random.uniform(0.04, 0.28), random.uniform(0.04, 0.28)))
        self.take(next(self.options()))

    def options(self, others=()):
        """The ways he might go down, the likeliest first: (style, the yaw he ends at, arms,
        legs, the wall behind him). He keeps off the tiles other bodies lie on, and those
        `others` stand on: in a trench he'd rather sit; in the open, he lies across one only
        if there's no other way."""
        tucked = ([0.1, 0.1], (0.03, 0.03))
        x, z = self.start
        own = (math.floor(x), math.floor(z))
        self.keep_off = (set(self.world.bodies) | set(others)) - {own}
        reach = FALL_REACH * self.size
        trench = self.world.trench_at(x, z)
        if trench and trench.started:                 # in a trench: lie along it if it runs far enough...
            ways = sorted((math.atan2(dx, dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))),
                          key=lambda h: abs(turn_between(self.away, h)))
            for heading in ways:
                if self.room(x, z, heading, reach, in_trench=True):
                    yield (*self.lie(heading), [TRENCH_ARMS, TRENCH_ARMS], tucked[1], None)
            yield self.sit_in_trench(trench)                          # ...else sit against the earth
            return
        for keep_off in (True, False):
            for turn in (0.0, 0.5, -0.5, 1.0, -1.0, 1.6, -1.6, math.pi):
                heading = self.away + turn
                if self.room(x, z, heading, reach, keep_off=keep_off):
                    yield (*self.lie(heading), *self.flung, None)
                    yield (*self.lie(heading), *tucked, None)
        yield ("slump", self.away + math.pi, *tucked, None)           # walled in: against the wall

    def take(self, option):
        """Go down this way (one of the options)."""
        self.style, self.yaw_to, arms, self.legs, self.wall = option
        self.arms = list(arms)

    def lie(self, heading):
        """Falling toward `heading`: on his face if he was facing that way, else on his back.
        Returns (style, the yaw he ends at)."""
        if abs(turn_between(self.yaw_from, heading)) <= math.pi / 2:
            return "front", heading
        return "back", heading + math.pi

    def clear(self, x, z, in_trench=False, keep_off=True):
        """Is there room for a fallen body here? In the open: no wall, and no hole in the
        ground. In a trench: still in the trench. And (keep_off) no other body there."""
        if keep_off and (math.floor(x), math.floor(z)) in self.keep_off:
            return False
        trench = self.world.trench_at(x, z)
        dug = trench is not None and trench.started
        if in_trench:
            return dug
        return not dug and not self.world.hits_wall(x, z, BODY_ROOM)

    def room(self, x, z, heading, reach, in_trench=False, keep_off=True):
        """Is there room along this line to fall this way and lie full length? (A rough look:
        lay_out checks the pose itself.)"""
        return all(self.clear(x + math.sin(heading) * d, z + math.cos(heading) * d, in_trench, keep_off)
                   for d in (0.3 + 0.25 * k for k in range(int(reach / 0.25))))

    def sit_in_trench(self, trench):
        """Sitting in a trench, his back to the earth wall nearest the way he was knocked (his
        Pose slides him back to it). Returns the option."""
        earth = []
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            beside = self.world.trenches.get((trench.i + dx, trench.j + dz))
            if not (beside and beside.started):
                earth.append((dx, dz))
        if not earth:                                 # trench all round: he sits where he is
            return "slump", self.away + math.pi, [0.1, 0.1], (0.03, 0.03), None
        dx, dz = min(earth, key=lambda d: abs(turn_between(self.away, math.atan2(*d))))
        return "slump", math.atan2(-dx, -dz), [0.1, 0.1], (0.03, 0.03), ((dx, dz), (trench.x, trench.z))


def lay_out(unit, shape, arm_start, others=()):
    """How a dead unit comes to lie: the first of its Fall's options whose pose fits where it
    fell (no part in a wall, over a hole, or in the earth round a trench), else the last
    (or, on a pile of the dead, the last of PILE_TRIES).
    `others`: the tiles others stand on (or are falling on), to keep off if it can."""
    f = unit.fall
    floor = -unit.rest_depth()
    piled = 0
    for option in f.options(others):
        f.take(option)
        pose = Pose(f, shape, arm_start, floor)
        if pose.fits(unit.x, unit.z, floor):
            break
        piled += pose.ground.uneven
        if piled >= PILE_TRIES:                       # (on a pile, each try is dear: take this one)
            break
    f.tiles = pose.tiles(unit.x, unit.z, floor)       # other bodies keep off these, till he's gone
    unit.world.add_body(f.tiles)
    tops = pose.surface(unit.x, unit.z, floor)
    f.rests_on = pose.rests_on(tops, floor)           # the bodies he lies on: he fades when they do
    f.top_cells = unit.world.add_tops(unit, tops)     # others may rest on him
    return pose


def corners(builder):
    """The corners of a model (each box's, once), from the MeshBuilder it was built with."""
    data = builder.data
    return list({(round(data[k], 4), round(data[k + 1], 4), round(data[k + 2], 4)) for k in range(0, len(data), 9)})


def lowest(m, points):
    """The lowest height of these points, moved by matrix m."""
    return min(m[1] * x + m[5] * y + m[9] * z + m[13] for x, y, z in points)


def surface(boxes, step):
    """Points over the faces of these boxes (each its 8 corners, as MeshBuilder keeps them),
    about `step` apart, leaving out those inside another of the boxes (they can't touch anything)."""
    out = set()
    for c in boxes:
        for face in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)):
            a, b, d, e = (c[k] for k in face)      # a parallelogram: a, b, d, e in turn round it
            nu = max(1, math.ceil(math.dist(a, b) / step))
            nv = max(1, math.ceil(math.dist(a, e) / step))
            for i in range(nu + 1):
                for j in range(nv + 1):
                    u, v = i / nu, j / nv
                    out.add(tuple(round(a[k] + (b[k] - a[k]) * u + (e[k] - a[k]) * v, 4) for k in range(3)))
    spans = [([min(c[k] for c in box) for k in range(3)], [max(c[k] for c in box) for k in range(3)]) for box in boxes]
    return [p for p in out if not any(all(lo[k] + 1e-3 < p[k] < hi[k] - 1e-3 for k in range(3)) for lo, hi in spans)]


class Ground:
    """What a fallen body comes to rest on: the floor where it fell (the ground, or a trench's
    boards), and the tops of any bodies already lying there. Heights here are in the body's
    model units, up from the floor, along its final pose's frame."""

    def __init__(self, fall, floor):
        self.world, self.floor, self.size = fall.world, floor, fall.size
        x, z = fall.start
        self.frame = mathx.chain(mathx.translate(x, floor, z), mathx.rot_y(fall.yaw_to), mathx.scale(fall.size))
        reach = FALL_REACH * fall.size + 0.6
        self.uneven = self.world.tops_near(x, z, reach)
        self.heights = self.world.heights_near(x, z, reach) if self.uneven else {}   # cell: how high the dead lie

    def clearance(self, m, corners, samples):
        """How far above what's under it the lowest of a part's points comes (m moves the part
        into the pose's frame). On bare floor its corners tell; over bodies, its surface does."""
        if not self.uneven:
            return lowest(m, corners)
        m = mathx.mul(self.frame, m)
        heights, floor, cell = self.heights.get, self.floor, TOP_CELL
        worst = math.inf
        for x, y, z in samples:
            wx = m[0] * x + m[4] * y + m[8] * z + m[12]
            wy = m[1] * x + m[5] * y + m[9] * z + m[13]
            wz = m[2] * x + m[6] * y + m[10] * z + m[14]
            gap = wy - max(floor, heights((math.floor(wx / cell), math.floor(wz / cell)), floor))
            if gap < worst:
                worst = gap
        return worst / self.size


class Shape:
    """The corners of the parts of someone's model: the body, a leg, an arm, and the gun he
    carries (or None), and where his shoulders are (out from his middle, and forward of it). Also points over each part's
    surfaces: to rest it on other bodies (`rests`), and to mark where it lies (`tops`)."""

    def __init__(self, parts, gun=None, shoulder=0.29, shoulder_z=0.0):
        self.body, self.leg, self.arm = (corners(p) for p in parts)
        self.boxes = dict(zip(("body", "leg", "arm"), (p.boxes for p in parts)))
        if gun:
            self.boxes["gun"] = gun.boxes
        self.rests = {name: surface(boxes, SAMPLE) for name, boxes in self.boxes.items()}
        self.tops = {name: surface(boxes, TOP_SAMPLE) for name, boxes in self.boxes.items()}
        self.gun = corners(gun) if gun else None
        self.shoulder, self.shoulder_z = shoulder, shoulder_z
        self.gun_half = -min(x for x, _, _ in self.gun) if gun else 0.0   # half its width: its height lying on its side
        self.gun_middle = (min(z for _, _, z in self.gun) + max(z for _, _, z in self.gun)) / 2 if gun else 0.0


def limb(pivot, swing, tilt):
    """Where a limb hangs from its pivot, swung out sideways (from hanging straight down) and
    tilted forward or back."""
    return mathx.chain(mathx.translate(*pivot), mathx.rot_z(swing), mathx.rot_x(tilt))


def smooth(t):
    return t * t * (3 - 2 * t)


class Pose:
    """How a fallen body lies, worked out once from its Fall and its Shape, and how it gets
    there. Everything here is in the model's own size (the unit's SIZE scales it after),
    except `shift`, how far he slides (sitting back against a trench wall), in tiles."""

    def __init__(self, fall, shape, arm_start=-1.0, floor=0.0):
        self.fall, self.shape = fall, shape
        self.arm_start = arm_start                    # how the arms were held (forward), to swing from
        self.ground = Ground(fall, floor)
        self.pitch = self.roll = 0.0                  # lying on bodies: how he's tilted, settling
        f = fall
        sitting = f.style == "slump"
        self.leg_swings = [side * (0.55 + f.legs[k] if sitting else f.legs[k]) for k, side in enumerate((-1, 1))]
        self.arm_swings = [side * f.arms[k] * (0.15 if sitting else 1.0) for k, side in enumerate((-1, 1))]
        if sitting:                                   # (his arms hang, or rest on the ground if they reach it)
            self.lean = f.lean
        else:
            self.sign = -1 if f.style == "back" else 1
            self.angle = self.lie_angle()
        self.shift = (0.0, 0.0)
        near = self.ground.uneven                     # bodies near: put him down flat, and see if he
        self.ground.uneven = False                    # lands on one (then do it again, on them)
        self.bend = self.bent(1.0)
        self.settle(-self.body_clearance(self.bend))
        if near and self.lands_on_bodies(floor):
            self.ground.uneven = True
            self.settle_on_bodies()
            self.bend = self.bent(1.0)
            self.settle(-self.body_clearance(self.bend))
        self.shift = (0.0, 0.0)
        if f.wall:
            self.back_to_the_wall()

    def bent(self, g):
        """The body (g of the way down) turned as it lies or sits, before it's lowered onto the ground."""
        base = self.sit(g) if self.fall.style == "slump" else mathx.rot_x(self.sign * self.angle * g)
        if self.pitch or self.roll:
            return mathx.chain(mathx.rot_x(self.pitch * g), mathx.rot_z(self.roll * g), base)
        return base

    def body_clearance(self, m):
        return self.ground.clearance(m, self.shape.body, self.shape.rests["body"])

    def lands_on_bodies(self, floor):
        """Put down as if on bare floor, would any of him be in a body lying there?"""
        top_at = self.fall.world.top_at
        x, z = self.fall.start
        for name, m in self.parts(x, z, floor, 99.0):
            for p in self.shape.rests[name]:
                wx, wy, wz = mathx.apply(m, p)
                if top_at(wx, wz) > wy - 0.01:
                    return True
        return False

    def settle_on_bodies(self):
        """Lying on other bodies: tilt him the way that lets him settle lowest (his chest's
        height, when he's put down onto whatever's under him), as a dropped weight would."""
        best = None
        for pitch in SETTLE:
            for roll in SETTLE:
                self.pitch, self.roll = pitch, roll
                bend = self.bent(1.0)
                drop = -self.body_clearance(bend)
                chest = mathx.apply(mathx.chain(mathx.translate(0, drop, 0), bend), (0.0, 0.7, 0.0))[1]
                key = chest + 0.02 * (abs(pitch) + abs(roll))      # (no tilt it doesn't need)
                if best is None or key < best[0]:
                    best = (key, pitch, roll)
        self.pitch, self.roll = best[1], best[2]

    def legs_at(self, k):
        return (-0.1 if k == 0 else 0.1, HIP_Y, 0)

    def arm_at(self, k):
        return (-self.shape.shoulder if k == 0 else self.shape.shoulder, SHOULDER_Y, self.shape.shoulder_z)

    def settle(self, drop):
        """Put the body down (`drop` lowers it onto the ground) and lay its limbs on the ground.
        A limb that can't lie without going into what's under it is tucked in along his side;
        if even that can't, it lifts the body instead, and the limbs are laid again."""
        self.drop = drop
        for _ in range(3):
            self.final_body = mathx.chain(mathx.translate(0, self.drop, 0), self.bend)
            self.settle_limbs()
            lows = self.limb_lows()
            for k, low in enumerate(lows):
                if low < -0.004 and self.ground.uneven:
                    if k < 2:
                        self.leg_swings[k] = 0.03 * (1 if self.leg_swings[k] > 0 else -1)
                    else:
                        self.arm_swings[k - 2] = 0.1 * (1 if self.arm_swings[k - 2] > 0 else -1)
            if min(lows) < -0.004 and self.ground.uneven:
                self.settle_limbs()
                lows = self.limb_lows()
            if min(lows) >= -0.004:
                return
            self.drop -= min(lows)
        self.final_body = mathx.chain(mathx.translate(0, self.drop, 0), self.bend)   # (lifted the last time:
        self.settle_limbs()                                                         # lay them down again)

    def limb_lows(self):
        """How low each leg, then each arm, comes over what's under it."""
        return ([self.limb_low(self.legs_at(k), self.leg_swings[k], self.leg_tilts[k], self.shape.leg)
                 for k in range(2)] +
                [self.limb_low(self.arm_at(k), self.arm_swings[k], self.arm_tilts[k], self.shape.arm)
                 for k in range(2)])

    def limb_low(self, pivot, swing, tilt, points):
        """How low a limb comes over what's under it, laid as it is in the final pose."""
        name = "leg" if points is self.shape.leg else "arm"
        return self.ground.clearance(mathx.mul(self.final_body, limb(pivot, swing, tilt)), points,
                                     self.shape.rests[name])

    def settle_limbs(self):
        """Lay the legs and arms on the ground, each as low as it goes without going into it."""
        sitting = self.fall.style == "slump"
        far = 2.4 if self.ground.uneven else 1.3      # (over bodies, an arm may have further to go;
        legs = (-1.9, 0.0) if sitting else (-1.3, 1.3)   # a leg can't fold up through the body)
        arms = (-1.5, 0.3) if sitting else (-far, far)
        self.leg_tilts, self.arm_tilts = [0.0, 0.0], [0.0, 0.0]
        for k in range(2):
            self.leg_swings[k], self.leg_tilts[k] = self.lay_limb(self.legs_at(k), self.leg_swings[k],
                                                                  self.shape.leg, legs, lowest=not sitting)
            self.arm_swings[k], self.arm_tilts[k] = self.lay_limb(self.arm_at(k), self.arm_swings[k],
                                                                  self.shape.arm, arms)

    def lay_limb(self, pivot, swing, points, tilts, lowest=True):
        """Lay one limb down: (its swing, its tilt). Over bodies, one that ends up touching
        nothing hangs straight down instead, if it can without going into anything; failing
        that, it's tucked in along his side."""
        def placed(s):
            return lambda tilt: mathx.mul(self.final_body, limb(pivot, s, tilt))
        tilt = self.rest(placed(swing), points, *tilts, lowest)
        if not self.ground.uneven or self.limb_low(pivot, swing, tilt, points) < 0.02:
            return swing, tilt
        m = self.final_body                            # straight down, in the body's own frame
        down = math.atan2(-m[1], m[5])
        hang = self.rest(placed(down), points, *tilts, lowest)
        if self.limb_low(pivot, down, hang, points) >= -0.004 and self.limb_points_down(pivot, down, hang):
            return down, hang
        if self.limb_points_down(pivot, swing, tilt):
            return swing, tilt
        tucked = 0.05 * (1 if swing > 0 else -1)
        return tucked, self.rest(placed(tucked), points, *tilts, lowest)

    def limb_points_down(self, pivot, swing, tilt):
        """Does a limb hang down (at least 30 degrees below level)?"""
        m = mathx.mul(self.final_body, limb(pivot, swing, tilt))
        return m[5] > 0.5                              # (its own up, the way back to its pivot, points up)

    def sit(self, g):
        """The body sitting down (g of the way there): leaning back from the hips, and a little to one side."""
        return mathx.chain(mathx.translate(0, HIP_Y, 0), mathx.rot_z(self.fall.tilt * g), mathx.rot_x(-self.lean * g),
                           mathx.translate(0, -HIP_Y, 0))

    def lie_angle(self):
        """How far over the body goes: flat, unless something it carries props it up (a pack on
        the back), in which case as far as lets the hips rest on the ground too. (On flat ground:
        over other bodies, settle_on_bodies tilts him further.)"""
        best = None
        for k in range(28):
            a = 1.1 + 0.02 * k
            m = mathx.rot_x(self.sign * a)
            gap = lowest(m, [p for p in self.shape.body if p[1] < 0.5]) - lowest(m, self.shape.body)
            if best is None or gap <= best[0] + 1e-4:
                best = (gap, a)
        return best[1]

    def rest(self, placed, points, low, high, lowest=True):
        """The tilt (between low and high) a limp limb falls to: the one, of those that keep it
        out of the ground and the bodies under it, that brings its middle lowest, pushed on to
        where it touches (or, not `lowest`, the least tilt that has it touch: legs sitting rest
        on their heels). If every tilt goes in, the one that goes in least (settle then tucks
        it in, or lifts the body); over bodies, of those pointing down. `placed(tilt)` is the
        limb's matrix."""
        samples = self.shape.rests["leg" if points is self.shape.leg else "arm"]
        uneven = self.ground.uneven

        def state(tilt):
            m = placed(tilt)
            clear = self.ground.clearance(m, points, samples)
            return clear >= -0.004, m[13] - 0.21 * m[5], clear, m[5] > 0    # fits, its middle's height, ...

        tilts = [low + (high - low) * k / 24 for k in range(25)]
        states = [state(t) for t in tilts]
        fitting = [k for k in range(25) if states[k][0]]
        if not fitting:                               # nothing fits: the least bad
            key = (lambda k: (states[k][3], states[k][2])) if uneven else (lambda k: states[k][2])
            return tilts[max(range(25), key=key)]
        if not lowest:
            k = min(fitting, key=lambda k: (round(states[k][2], 3), abs(tilts[k])))
            return tilts[k]
        best = min(fitting, key=lambda k: (round(states[k][1], 4), abs(tilts[k])))
        tilt, height = tilts[best], states[best][1]
        for j in (best - 1, best + 1):               # on toward a blocked tilt where it would be lower
            if 0 <= j < 25 and not states[j][0] and states[j][1] < height:
                a, b = tilts[best], tilts[j]
                for _ in range(6):
                    mid = (a + b) / 2
                    if state(mid)[0]:
                        a = mid
                    else:
                        b = mid
                if state(a)[1] < height:
                    tilt, height = a, state(a)[1]
        return tilt

    def reach(self, way):
        """How far the sitting body reaches back (way -1) or forward (way 1) from his feet, in tiles."""
        parts = [(self.final_body, self.shape.body)]
        for k in range(2):
            parts.append((mathx.mul(self.final_body, limb(self.legs_at(k), self.leg_swings[k], self.leg_tilts[k])),
                          self.shape.leg))
            parts.append((mathx.mul(self.final_body, limb(self.arm_at(k), self.arm_swings[k], self.arm_tilts[k])),
                          self.shape.arm))
        far = max(way * (m[2] * x + m[6] * y + m[10] * z + m[14]) for m, pts in parts for x, y, z in pts)
        return far * self.fall.size

    def back_to_the_wall(self):
        """Sitting in a trench: slide back till his back nearly touches the earth wall behind,
        and spread his legs wider till his feet keep off the wall in front."""
        (dx, dz), (cx, cz) = self.fall.wall
        for _ in range(10):                             # (on bodies, settle may tuck a leg back in: not for ever)
            if self.reach(1) + self.reach(-1) <= 1.0 - 2 * WALL_GAP or abs(self.leg_swings[1]) >= 1.3:
                break
            self.leg_swings = [s * 1.1 for s in self.leg_swings]
            self.settle(self.drop)
        back = 0.5 - WALL_GAP - self.reach(-1)          # how far from the tile's middle his feet go
        sx, sz = self.fall.start
        self.shift = (cx + dx * back - sx, cz + dz * back - sz)

    def at(self, dead_for):
        """The pose dead_for seconds after he was killed: (yaw, (dx, dz) slid, the body's matrix,
        and each side's (swing, tilt) for the legs and the arms)."""
        f = self.fall
        e = min(1.0, dead_for / f.time)
        g = e * e                                     # he falls faster and faster
        s = smooth(e)
        yaw = f.yaw_from + turn_between(f.yaw_from, f.yaw_to) * smooth(min(1.0, e / 0.6))
        shift = (self.shift[0] * s, self.shift[1] * s)
        legs = [(self.leg_swings[k] * s, self.leg_tilts[k] * (s if f.style == "slump" else g * g)) for k in range(2)]
        arms = [(self.arm_swings[k] * s, self.arm_start + (self.arm_tilts[k] - self.arm_start) * s) for k in range(2)]
        if e >= 1.0:
            return yaw, shift, self.final_body, legs, arms
        bend = self.bent(g)
        drop = self.drop * g if f.style == "slump" else 0.0
        shape, ground = self.shape, self.ground       # (nothing goes into the ground, or the bodies
        low = self.body_clearance(bend)               # under him, on the way down: he's held up by
        for k in range(2):                            # whatever part is lowest)
            low = min(low, ground.clearance(mathx.mul(bend, limb(self.legs_at(k), *legs[k])), shape.leg,
                                            shape.rests["leg"]),
                      ground.clearance(mathx.mul(bend, limb(self.arm_at(k), *arms[k])), shape.arm,
                                       shape.rests["arm"]))
        return yaw, shift, mathx.chain(mathx.translate(0, max(drop, -low), 0), bend), legs, arms

    def parts(self, x, z, floor, dead_for):
        """Where each part is in the world (he fell at (x, z), feet at height `floor`): a list
        of (part, matrix), the part being "body", "leg" or "arm"."""
        yaw, (dx, dz), body, legs, arms = self.at(dead_for)
        body = mathx.chain(mathx.translate(x + dx, floor, z + dz), mathx.rot_y(yaw), mathx.scale(self.fall.size), body)
        parts = [("body", body)]
        for k in range(2):
            parts.append(("leg", mathx.mul(body, limb(self.legs_at(k), *legs[k]))))
            parts.append(("arm", mathx.mul(body, limb(self.arm_at(k), *arms[k]))))
        return parts

    def steady(self):
        """Does he lie steady: on his body, or propped on two limbs at least (not balanced on
        one limb jammed under him)?"""
        lows = self.limb_lows()
        touching = sum(low < 0.02 / self.fall.size for low in lows)
        return self.body_clearance(self.final_body) < 0.04 / self.fall.size or touching >= 2

    def fits(self, x, z, floor):
        """Does he fit where he lies? No part in a wall; on open ground, nothing resting over a
        trench's hole; in a trench, nothing below the ground outside it (in the earth); and
        lying on other bodies, he lies steady."""
        if self.ground.uneven and not self.steady():
            return False
        world = self.fall.world
        n = world.size
        in_trench = floor < -0.1
        corners_of = {"body": self.shape.body, "leg": self.shape.leg, "arm": self.shape.arm}
        for name, m in self.parts(x, z, floor, 99.0):
            for p in corners_of[name]:
                px, py, pz = mathx.apply(m, p)
                if py > 2.5:
                    continue
                if 0 <= px < n and 0 <= pz < n and world.is_blocked(int(px), int(pz)):
                    return False
                trench = world.trench_at(px, pz)
                dug = trench is not None and trench.started
                if in_trench and py < -0.01 and not dug:
                    return False
                if not in_trench and py < floor + 0.05 and dug:
                    return False
        return True

    def surface(self, x, z, floor):
        """Points over his surfaces where he lies, for others to rest on (World.tops)."""
        out = []
        for name, m in self.parts(x, z, floor, 99.0):
            out += [mathx.apply(m, p) for p in self.shape.tops[name]]
        return out

    def rests_on(self, points, floor):
        """The bodies he lies on: those whose tops are just under him."""
        under = set()
        for x, y, z in points:
            for body, top in self.fall.world.tops_at(x, z).items():
                if top > floor + 0.02 and y - top < 0.08:
                    under.add(body)
        return under

    def tiles(self, x, z, floor):
        """The tiles he lies on (his parts near the ground)."""
        corners_of = {"body": self.shape.body, "leg": self.shape.leg, "arm": self.shape.arm}
        out = set()
        for name, m in self.parts(x, z, floor, 99.0):
            for p in corners_of[name]:
                px, py, pz = mathx.apply(m, p)
                if py < floor + 0.3:
                    out.add((math.floor(px), math.floor(pz)))
        return tuple(out)

    def gun_spots(self):
        """Where his gun might lie once it's down, in his final pose's frame, the likeliest
        first: (x, y, z, turn). On the ground beside his hips, on his other side, past his feet
        or past his head (in a trench); sitting, else across his lap, on his legs."""
        f = self.fall
        side, turn, down = f.gun_side, f.gun_turn, self.shape.gun_half
        if f.style == "slump":
            top = max(max(mathx.apply(mathx.mul(self.final_body, limb(self.legs_at(k), self.leg_swings[k],
                                                                          self.leg_tilts[k])), p)[1]
                          for p in self.shape.leg) for k in range(2))
            return [(side * 0.45, down, 0.1, math.pi / 2 + turn), (-side * 0.45, down, 0.1, math.pi / 2 - turn),
                    (side * 0.45, down, 0.1, turn), (-side * 0.45, down, 0.1, -turn),
                    (-self.shape.gun_middle, top + down, 0.2, math.pi / 2)]     # (turned across him, centred)
        ahead = -1 if f.style == "back" else 1       # the way his head lies from his feet
        return [(side * 0.5, down, 0.45 * ahead, turn), (-side * 0.5, down, 0.45 * ahead, -turn),
                (0.0, down, -0.5 * ahead, math.pi * (ahead > 0)), (0.0, down, 1.9 * ahead, math.pi * (ahead > 0))]

    def stain_point(self):
        """Where the stain under him spreads from, in his final pose's frame: under his chest
        (or his hips, sitting)."""
        if self.fall.style == "slump":
            return 0.0, 0.1
        p = mathx.apply(self.final_body, (0.0, 0.7, 0.0))
        return p[0], p[2]
