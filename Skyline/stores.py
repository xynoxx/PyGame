"""What the player has to spend, and what things cost.

There are three materials: supply, to train troops; metal, to build turrets
and buildings; and bullets, which every shot a soldier or a turret fires uses
one of (with none left, nobody can shoot). The HQ makes some of each as time
goes by (see units.Headquarters), and bullet factories make more bullets (see
units.Factory). Training a unit, or building a turret or a building, costs
what its kind's COST says, paid bit by bit as the work goes on (see owing), as
in Beyond All Reason: while the work stops, or there isn't enough to pay for
the next of it, it costs nothing. Taking the unit in training off the queue
gives back what's been paid for it. Bullets can be stored only up to MOST
(there's no room for more): any more are lost.
"""
import math
from collections import namedtuple

MATERIALS = ("supply", "metal", "bullets")


class Cost(namedtuple("Cost", MATERIALS)):
    """An amount of each material: what something costs, or what's made or given."""
    __slots__ = ()

    def __new__(cls, supply=0, metal=0, bullets=0):
        return super().__new__(cls, supply, metal, bullets)

    def text(self):
        """As words: "500 metal, 200 supply" (the biggest first), or "free"."""
        parts = sorted(((amount, name) for name, amount in zip(MATERIALS, self) if amount), reverse=True)
        return ", ".join(f"{amount} {name}" for amount, name in parts) or "free"


FREE = Cost()
START = Cost(supply=3000, metal=500, bullets=4000)         # what a game starts with
TEST_GIFT = Cost(supply=10000, metal=5000, bullets=10000)  # what the test button adds
MOST = {"bullets": 20000}                                   # the most of a material that can be stored (the rest: no limit)


def owing(cost, done, paid):
    """What's still to pay of `cost` once `done` (0 to 1) of the work is done, with `paid`
    paid so far: each material's share of it rounded up to a whole one, less what's paid."""
    return Cost(*(max(0, math.ceil(c * done - 1e-9) - p) for c, p in zip(cost, paid)))


def plus(a, b):
    return Cost(*(x + y for x, y in zip(a, b)))


class Stores:
    """How much of each material the player has."""

    def __init__(self, start=START):
        self.supply, self.metal, self.bullets = start

    def amounts(self):
        return Cost(self.supply, self.metal, self.bullets)

    def short_of(self, cost):
        """The first material there isn't enough of to pay `cost`, or None if there's enough of all."""
        return next((name for name, have, need in zip(MATERIALS, self.amounts(), cost) if have < need), None)

    def pay(self, cost):
        """Pay `cost` if there's enough of everything it takes. True if it was paid."""
        if self.short_of(cost):
            return False
        self.supply, self.metal, self.bullets = (have - need for have, need in zip(self.amounts(), cost))
        return True

    def add(self, cost):
        """Add to the stores: what's made, given back, or given for testing (as much as there's
        room for: see MOST)."""
        self.supply, self.metal, self.bullets = (min(have + more, MOST.get(name, have + more))
                                                 for name, have, more in zip(MATERIALS, self.amounts(), cost))

    def lacks(self, cost):
        """Is there none at all of something `cost` takes? (Then nothing paid for bit by bit can start.)"""
        return any(need and have <= 0 for need, have in zip(cost, self.amounts()))

    def full(self, name):
        """Is there no room for any more of this material?"""
        return name in MOST and getattr(self, name) >= MOST[name]
