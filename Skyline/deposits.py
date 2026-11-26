"""Deposits: what's left on the map from before, holding a material to strip. A junkyard
holds metal, a warehouse supply. Each stands on W by D tiles that nobody walks through,
and faces the HQ: beside its front is its building spot, three tiles square, where
engineers put up the building that strips it (units.Extractor): a salvage crane at a
junkyard, a loading dock post at a warehouse. What it holds runs out.

Each is built facing +Z in its own frame, its corner at the origin (models.build_junkyard
and build_warehouse), and turned on the map to face its way. Its building spot, in that
frame, is x from W/2 - 1 to W/2 + 2 and z from D to D + 3, so it's on whole tiles however
the deposit faces; a building on it is built facing +Z in its own frame too (its back to
the deposit), and turned the same way.
"""
import math
import random

import mathx

SPOT = 3                   # a building spot is this many tiles square
EDGE = 3                   # tiles kept clear between a deposit (and its spot) and the open part's edge
APART = 3                  # tiles kept clear round the HQ's concrete, and between deposits
TRIES = 400                # places tried for each deposit before it's left out


class Deposit:
    NAME = "Deposit"
    MATERIAL = "metal"     # what it holds (a name from stores.MATERIALS)
    HOLDS = 0              # how much of it, to start with
    W = D = 1              # tiles across its front, and deep
    TOP = 1.0              # how high it stands, where the mouse finds it

    def __init__(self, cx, cz, front):
        """A deposit with the middle of its tiles at (cx, cz) (whole numbers), facing `front`,
        one of (0, 1), (1, 0), (0, -1) and (-1, 0)."""
        self.x, self.z = cx, cz
        self.front = front
        self.yaw = math.atan2(*front)
        self.left = self.HOLDS
        self.seed = random.randrange(1 << 20)     # how its yard or its stock is laid out
        self.rect = self._bounds((0, 0), (self.W, self.D))
        x0, z0, _, _ = self._bounds((self.W / 2 - 1, self.D), (self.W / 2 + 2, self.D + SPOT))
        self.spot = (round(x0), round(z0))        # the corner tile of its building spot

    def _bounds(self, a, b):
        """Where the rectangle with corners a and b in its own frame lies on the map: x0, z0, x1, z1."""
        model = self.model()
        corners = [mathx.apply(model, (x, 0.0, z)) for x in (a[0], b[0]) for z in (a[1], b[1])]
        return (round(min(c[0] for c in corners)), round(min(c[2] for c in corners)),
                round(max(c[0] for c in corners)), round(max(c[2] for c in corners)))

    def model(self):
        """The matrix that puts it, built in its own frame, where it stands on the map."""
        return mathx.chain(mathx.translate(self.x, 0, self.z), mathx.rot_y(self.yaw),
                           mathx.translate(-self.W / 2, 0, -self.D / 2))

    def spot_model(self):
        """The matrix that puts a building on its spot, built in its own frame (3 by 3, its
        back to the deposit), where it stands on the map."""
        i, j = self.spot
        return mathx.chain(mathx.translate(i + SPOT / 2, 0, j + SPOT / 2), mathx.rot_y(self.yaw),
                           mathx.translate(-SPOT / 2, 0, -SPOT / 2))

    @property
    def tiles(self):
        x0, z0, x1, z1 = self.rect
        return [(i, j) for i in range(x0, x1) for j in range(z0, z1)]

    @property
    def emptied(self):
        return self.left <= 0

    def take(self, amount):
        """Take up to `amount` from it; returns how much there was to take."""
        got = min(amount, self.left)
        self.left -= got
        return got

    def ray_hit(self, origin, direction):
        """How far along a mouse ray it touches it, or None."""
        x0, z0, x1, z1 = self.rect
        return mathx.box_hit(origin, direction, (x0, 0.0, z0), (x1, self.TOP, z1))


class Junkyard(Deposit):
    """A fenced yard of wrecked cars, stacked five high, and an old broken crusher. A
    salvage crane lifts the cars out, one at a time, each worth PER_CAR metal."""
    NAME = "Junkyard"
    MATERIAL = "metal"
    CARS = 50
    PER_CAR = 100
    HOLDS = CARS * PER_CAR
    W = D = 8
    TOP = 2.2              # its stacks of cars (its fence is lower)

    @property
    def cars_left(self):
        return math.ceil(self.left / self.PER_CAR)


class Warehouse(Deposit):
    """A big shed of corrugated steel, with loading bays along its front and pallets of stock
    on its dock. A loading dock post takes the stock out, a truckload at a time."""
    NAME = "Warehouse"
    MATERIAL = "supply"
    HOLDS = 20000
    W, D = 8, 6
    TOP = 2.1              # its walls and roof
    PALLETS = 6            # pallets on its dock when it's full; they go as it's emptied

    @property
    def pallets(self):
        return math.ceil(self.left / self.HOLDS * self.PALLETS)


# Which deposits the square the game starts on has, and how far the middle of each is from
# the HQ's: one of each kind near enough to reach early on, one of each a little further, and
# two of each well out, toward where the dead come in.
PLAN = ((Junkyard, 20, 26), (Warehouse, 20, 26), (Junkyard, 30, 40), (Warehouse, 30, 40),
        (Junkyard, 50, 90), (Warehouse, 50, 90), (Junkyard, 50, 90), (Warehouse, 50, 90))


def facing(cx, cz, x, z):
    """Which way a deposit at (cx, cz) faces to face the point (x, z) most nearly."""
    dx, dz = x - cx, z - cz
    if abs(dx) > abs(dz):
        return (1 if dx > 0 else -1, 0)
    return (0, 1 if dz > 0 else -1)


def area_of(deposit):
    """The tiles a deposit and its building spot take up, together: x0, z0, x1, z1."""
    x0, z0, x1, z1 = deposit.rect
    i, j = deposit.spot
    return min(x0, i), min(z0, j), max(x1, i + SPOT), max(z1, j + SPOT)


def overlaps(a, b, gap=0):
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def place_deposits(world, x, z, plan=PLAN):
    """Lay the deposits out at random round the HQ, whose middle is at (x, z): each as far
    from it as the plan says, facing it, in the open part of the map with room round it, clear
    of the HQ's concrete and of the others. Their tiles are blocked from then on. Returns them."""
    x0, z0, x1, z1 = world.open
    placed = []
    for kind, near, far in plan:
        for _ in range(TRIES):
            angle, reach = random.uniform(0, 2 * math.pi), random.uniform(near, far)
            cx, cz = round(x + math.sin(angle) * reach), round(z + math.cos(angle) * reach)
            deposit = kind(cx, cz, facing(cx, cz, x, z))
            area = area_of(deposit)
            if (area[0] >= x0 + EDGE and area[1] >= z0 + EDGE and area[2] <= x1 - EDGE and area[3] <= z1 - EDGE
                    and not overlaps(area, world.apron, APART)
                    and not any(overlaps(area, area_of(other), APART) for other in placed)):
                world.add_deposit(deposit)
                placed.append(deposit)
                break
    return placed
