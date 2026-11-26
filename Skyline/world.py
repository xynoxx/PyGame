"""The square map: which tiles are blocked (by the HQ, a deposit, a turret or a building),
where the trenches are, finding a way across it, and whether a shot can fly between two points.

The map is MAP_SIZE x MAP_SIZE tiles, each one unit wide. Tile (i, j) covers
x in [i, i+1] and z in [j, j+1]; the ground is at height 0. It's three by three
squares SQUARE tiles across, and only the middle one is open at the start
(World.open): the player's units walk, build and look only there, and the dead
come in from beyond its edge. A radar station opens the rest (World.open_all).
There are no walls past the open part, nor off the map: the dead walk in from out there.
"""
import heapq
import math
from collections import namedtuple

SQUARE = 200               # one square of the map, the one the game starts on (the middle)...
MAP_SIZE = 3 * SQUARE      # ...and the whole map: three by three of them
FIND_MOST = 60000          # the most tiles a search for a way looks at before it settles for the nearest it got
DIAGONAL = math.sqrt(2)

HQ_WIDTH, HQ_DEPTH = 5, 4  # tiles the HQ stands on; its door faces +Z
APRON = 2                  # tiles of concrete round the HQ (one more in front)
TRENCH_DEPTH = 0.55        # how far below the ground a finished trench's floor is
TOP_CELL = 0.1             # how fine the map of how high the dead lie is, in tiles

# The HQ covers tiles i .. i + w - 1 and j .. j + d - 1.
HQ = namedtuple("HQ", "i j w d")


def hash01(i, j, seed):
    """A repeatable pseudo-random number in 0..1 for a grid point."""
    n = (i * 374761393 + j * 668265263 + seed * 982451653) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


class World:
    def __init__(self, size=MAP_SIZE):
        self.size = size
        lo, hi = (size - SQUARE) // 2, (size + SQUARE) // 2
        self.open = (lo, lo, hi, hi) if size > SQUARE else (0, 0, size, size)   # x0, z0, x1, z1: the open part
        self.blocked = [False] * (size * size)
        self.fixed = [False] * (size * size)    # blocked by what was on the map from the start: the HQ and the deposits
        self.deposits = []         # the junkyards and warehouses (deposits.py)
        self.way_home = []         # each tile's walk to the HQ, round the deposits (see find_way_home)...
        self.home_area = (0, 0, 0, 0)   # ...over this part of the map (the square it starts on)
        self.apron = None          # the concrete round the HQ: x0, z0, x1, z1
        self.trenches = {}         # (i, j): the trench dug, or laid out to dig, on that tile
        self.trench_changes = 0    # counts up whenever a trench looks different, so it's drawn afresh
        self.new_walls = []        # tiles blocked since anyone standing on them was moved off
        self.guns = {}             # (i, j): the turret on that tile, once its gun is there to swing round
        self.structures = {}       # (i, j): the turret or building started on that tile
        self.bodies = {}           # (i, j): how many of the dead lie on that tile (see deaths.py)
        self.tops = {}             # a cell TOP_CELL across: {body: how high it reaches there}
        self.top_tiles = {}        # (i, j): how many such cells on that tile
        self.promoted = []         # fighters who've gone up a level since the game last showed it

    # ------------------------------------------------------------ building the map

    @staticmethod
    def hq_tiles_at(x, z):
        """The tile an HQ's corner goes on when it's centred as near (x, z) as the tiles allow."""
        return round(x - HQ_WIDTH / 2), round(z - HQ_DEPTH / 2)

    @staticmethod
    def apron_of(i0, j0):
        """The concrete round an HQ on tile (i0, j0): x0, z0, x1, z1 (one more tile in front of its door)."""
        return (i0 - APRON, j0 - APRON, i0 + HQ_WIDTH + APRON, j0 + HQ_DEPTH + APRON + 1)

    def build_hq(self, i0, j0):
        """Build the HQ with its corner on tile (i0, j0), and its concrete."""
        hq = HQ(i0, j0, HQ_WIDTH, HQ_DEPTH)
        n = self.size
        for i in range(i0, i0 + hq.w):
            for j in range(j0, j0 + hq.d):
                self.blocked[j * n + i] = self.fixed[j * n + i] = True
        self.apron = self.apron_of(i0, j0)
        return hq

    def add_deposit(self, deposit):
        """A deposit stands on its tiles from the start: nobody walks through it."""
        n = self.size
        for i, j in deposit.tiles:
            self.blocked[j * n + i] = self.fixed[j * n + i] = True
        self.deposits.append(deposit)

    def open_all(self):
        """Open the whole map (a radar station is up)."""
        self.open = (0, 0, self.size, self.size)

    def is_open(self, i, j):
        """Is this tile in the open part of the map?"""
        x0, z0, x1, z1 = self.open
        return x0 <= i < x1 and z0 <= j < z1

    def find_way_home(self, hq):
        """Work out, for every tile of the open part (the square the game starts on, where the
        deposits are), how far it is to walk to the HQ round whatever was on the map from the
        start (the deposits), once, for all the dead to share (next_step_home). Turrets and
        buildings aren't gone round: the dead go for those."""
        n, fixed = self.size, self.fixed
        x0, z0, x1, z1 = self.home_area = self.open
        way = [math.inf] * (n * n)
        todo = []
        for i in range(hq.i, hq.i + hq.w):
            for j in range(hq.j, hq.j + hq.d):
                way[j * n + i] = 0.0
                todo.append((0.0, i, j))
        while todo:
            d, i, j = heapq.heappop(todo)
            if d > way[j * n + i]:
                continue
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    ni, nj = i + di, j + dj
                    if (di or dj) and x0 <= ni < x1 and z0 <= nj < z1 and not fixed[nj * n + ni] and not (
                            di and dj and (fixed[j * n + ni] or fixed[nj * n + i])):    # (no cutting a corner)
                        nd = d + (DIAGONAL if di and dj else 1.0)
                        if nd < way[nj * n + ni]:
                            way[nj * n + ni] = nd
                            heapq.heappush(todo, (nd, ni, nj))
        self.way_home = way

    def next_step_home(self, x, z):
        """The middle of the next tile on the way to the HQ round the deposits, from (x, z), or
        None if it's outside where that's worked out (find_way_home), or as near as it gets."""
        n, fixed, way = self.size, self.fixed, self.way_home
        x0, z0, x1, z1 = self.home_area
        i, j = math.floor(x), math.floor(z)
        if not (x0 <= i < x1 and z0 <= j < z1 and way):
            return None
        best, step = way[j * n + i], None
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                ni, nj = i + di, j + dj
                if ((di or dj) and x0 <= ni < x1 and z0 <= nj < z1 and way[nj * n + ni] < best
                        and not (di and dj and (fixed[j * n + ni] or fixed[nj * n + i]))):
                    best, step = way[nj * n + ni], (ni + 0.5, nj + 0.5)
        return step

    def deposit_between(self, x0, z0, x1, z1, r):
        """Does a deposit stand in the way of something r wide going straight from one point to the other?"""
        for deposit in self.deposits:
            a, b, c, d = deposit.rect
            lo, hi = 0.0, 1.0                        # the part of the line inside the deposit, widened by r
            for p0, p1, low, high in ((x0, x1, a - r, c + r), (z0, z1, b - r, d + r)):
                if abs(p1 - p0) < 1e-9:
                    if not low <= p0 <= high:
                        lo, hi = 1.0, 0.0
                    continue
                t0, t1 = (low - p0) / (p1 - p0), (high - p0) / (p1 - p0)
                lo, hi = max(lo, min(t0, t1)), min(hi, max(t0, t1))
            if lo <= hi:
                return True
        return False

    # ------------------------------------------------------------ asking about the map

    def is_blocked(self, i, j):
        return self.blocked[j * self.size + i]

    def add_body(self, tiles):
        for tile in tiles:
            self.bodies[tile] = self.bodies.get(tile, 0) + 1

    def remove_body(self, tiles):
        for tile in tiles:
            self.bodies[tile] -= 1
            if not self.bodies[tile]:
                del self.bodies[tile]

    @staticmethod
    def top_cell(x, z):
        return math.floor(x / TOP_CELL), math.floor(z / TOP_CELL)

    def add_tops(self, body, points):
        """Mark how high a body reaches, over the cells under these points on it. Returns the cells."""
        cells = set()
        for x, y, z in points:
            cell = self.top_cell(x, z)
            here = self.tops.setdefault(cell, {})
            if body not in here:
                tile = (math.floor(x), math.floor(z))
                self.top_tiles[tile] = self.top_tiles.get(tile, 0) + 1
                cells.add(cell)
            here[body] = max(here.get(body, y), y)
        return tuple(cells)

    def remove_tops(self, body, cells):
        for cell in cells:
            del self.tops[cell][body]
            if not self.tops[cell]:
                del self.tops[cell]
            tile = (math.floor((cell[0] + 0.5) * TOP_CELL), math.floor((cell[1] + 0.5) * TOP_CELL))
            self.top_tiles[tile] -= 1
            if not self.top_tiles[tile]:
                del self.top_tiles[tile]

    def tops_at(self, x, z):
        """{body: how high it reaches} at this point."""
        return self.tops.get(self.top_cell(x, z), {})

    def top_at(self, x, z, besides=None):
        """How high the dead lie at this point (or no height at all), leaving out `besides`."""
        here = self.tops.get(self.top_cell(x, z))
        if not here:
            return -math.inf
        return max((top for body, top in here.items() if body is not besides), default=-math.inf)

    def heights_near(self, x, z, r):
        """{cell: how high the dead lie there}, for the cells within r of this point."""
        out = {}
        for i in range(math.floor((x - r) / TOP_CELL), math.floor((x + r) / TOP_CELL) + 1):
            for j in range(math.floor((z - r) / TOP_CELL), math.floor((z + r) / TOP_CELL) + 1):
                here = self.tops.get((i, j))
                if here:
                    out[i, j] = max(here.values())
        return out

    def tops_near(self, x, z, r):
        """Is anyone lying within r of this point?"""
        return any((i, j) in self.top_tiles for i in range(math.floor(x - r), math.floor(x + r) + 1)
                   for j in range(math.floor(z - r), math.floor(z + r) + 1))

    def gun_over(self, x, z, r):
        """The turret whose gun would swing into something of radius r standing at (x, z), or None."""
        return next((t for t in self.guns.values() if math.hypot(x - t.x, z - t.z) < t.gun_reach + r), None)

    def neighbours(self, i, j):
        """Tiles in the open part you can step to from (i, j), with the cost of the step.
        Diagonal steps are only allowed when they don't cut a corner."""
        n, blocked = self.size, self.blocked
        x0, z0, x1, z1 = self.open
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if x0 <= ni < x1 and z0 <= nj < z1 and not blocked[nj * n + ni]:
                yield ni, nj, 1.0
        for di, dj in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            ni, nj = i + di, j + dj
            if (x0 <= ni < x1 and z0 <= nj < z1 and not blocked[nj * n + ni]
                    and not blocked[j * n + ni] and not blocked[nj * n + i]):
                yield ni, nj, DIAGONAL

    def circle_free(self, x, z, r):
        """Can something round, of radius r, stand at (x, z), in the open part of the map?"""
        n = self.size
        ox0, oz0, ox1, oz1 = self.open
        if x - r < ox0 or z - r < oz0 or x + r > ox1 or z + r > oz1:
            return False
        for i in range(int(x - r), min(int(x + r), n - 1) + 1):
            for j in range(int(z - r), min(int(z + r), n - 1) + 1):
                if self.blocked[j * n + i]:
                    cx = min(max(x, i), i + 1)
                    cz = min(max(z, j), j + 1)
                    if (x - cx) ** 2 + (z - cz) ** 2 < r * r:
                        return False
        return True

    def hits_wall(self, x, z, r):
        """Does something round, of radius r, at (x, z) overlap a blocked tile? (Off the map
        there are none: the dead walk in from out there.)"""
        n = self.size
        for i in range(max(int(x - r), 0), min(int(x + r), n - 1) + 1):
            for j in range(max(int(z - r), 0), min(int(z + r), n - 1) + 1):
                if self.blocked[j * n + i]:
                    cx = min(max(x, i), i + 1)
                    cz = min(max(z, j), j + 1)
                    if (x - cx) ** 2 + (z - cz) ** 2 < r * r:
                        return True
        return False

    def line_clear(self, x0, z0, x1, z1, skip=None):
        """Can a shot fly straight from one point to the other without hitting a wall?
        `skip` is a tile the shot may cross (the one a turret firing it stands on)."""
        length = math.hypot(x1 - x0, z1 - z0)
        if length < 1e-9:
            return True
        return self.wall_along(x0, z0, (x1 - x0) / length, (z1 - z0) / length, length, skip) is None

    def wall_along(self, x0, z0, ux, uz, length, skip=None):
        """How far a shot from (x0, z0), going the way (ux, uz) (one long), flies before it hits
        a wall, or None if nothing's in its way for `length`. It steps from tile to tile along
        the line, so it never skips a corner. `skip` is a tile it may cross (its turret's)."""
        n, blocked = self.size, self.blocked
        i, j = math.floor(x0), math.floor(z0)
        step_i, step_j = (1 if ux > 0 else -1), (1 if uz > 0 else -1)
        next_x = ((i + 1 - x0) / ux if ux > 0 else (i - x0) / ux) if ux else math.inf   # to the next tile's edge
        next_z = ((j + 1 - z0) / uz if uz > 0 else (j - z0) / uz) if uz else math.inf
        across_x, across_z = (abs(1 / ux) if ux else math.inf), (abs(1 / uz) if uz else math.inf)
        t = 0.0
        while t <= length:
            if 0 <= i < n and 0 <= j < n and blocked[j * n + i] and (i, j) != skip:
                return t
            if next_x < next_z:
                t, next_x, i = next_x, next_x + across_x, i + step_i
            else:
                t, next_z, j = next_z, next_z + across_z, j + step_j
        return None

    def can_build_turret(self, i, j):
        """A turret (or a building) needs a free tile in the open part of the map: on a trench
        is fine (it's filled in when the work starts: see Structure.begin)."""
        return self.is_open(i, j) and not self.is_blocked(i, j)

    def can_dig(self, i, j):
        """A trench needs a free tile of bare earth, with no trench on it already: nobody can
        dig through the HQ's concrete."""
        if not self.can_build_turret(i, j) or (i, j) in self.trenches:
            return False
        x0, z0, x1, z1 = self.apron or (0, 0, 0, 0)
        return not (x0 <= i < x1 and z0 <= j < z1)

    def trench_at(self, x, z):
        """The trench on the tile holding this point, or None."""
        return self.trenches.get((math.floor(x), math.floor(z)))

    def floor_depth(self, x, z):
        """How far below the ground someone standing at this point is."""
        trench = self.trench_at(x, z)
        return trench.depth if trench else 0.0

    def set_blocked(self, i, j, blocked):
        """Put something on a tile, or take it away."""
        self.blocked[j * self.size + i] = blocked
        if blocked:
            self.new_walls.append((i, j))

    def segment_free(self, x0, z0, x1, z1, r):
        """Can something of radius r walk straight from one point to the other?"""
        steps = max(1, int(math.hypot(x1 - x0, z1 - z0) / 0.2))
        for k in range(steps + 1):
            t = k / steps
            if not self.circle_free(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, r):
                return False
        return True

    def nearest_free(self, x, z):
        """The free tile in the open part nearest to (x, z): it, if it's free; else the nearest
        round it, ring by ring out (a goal inside a building or a deposit). None if there's none near."""
        i, j = math.floor(x), math.floor(z)
        for ring in range(0, 40):
            ring_tiles = [(i + a, j + b) for a in range(-ring, ring + 1) for b in range(-ring, ring + 1)
                          if max(abs(a), abs(b)) == ring]
            free = [t for t in ring_tiles if self.is_open(*t) and not self.is_blocked(*t)]
            if free:
                return min(free, key=lambda t: (t[0] + 0.5 - x) ** 2 + (t[1] + 0.5 - z) ** 2)
        return None

    # ------------------------------------------------------------ pathfinding

    def find_path(self, sx, sz, gx, gz, r):
        """Points to walk through to get from (sx, sz) to (gx, gz), avoiding obstacles, in the
        open part of the map.

        If the goal is inside a building or a deposit, the walker goes to the nearest free tile
        to it instead; and if there's no way there (it's walled in), to the nearest place to it
        that it can get to.
        """
        x0, z0, x1, z1 = self.open
        gx = min(max(gx, x0 + r + 0.01), x1 - r - 0.01)
        gz = min(max(gz, z0 + r + 0.01), z1 - r - 0.01)
        goal = (math.floor(gx), math.floor(gz))
        if self.is_blocked(*goal):
            goal = self.nearest_free(gx, gz)
            if goal is None:
                return []
            gx, gz = goal[0] + 0.5, goal[1] + 0.5
        elif not self.circle_free(gx, gz, r):
            gx, gz = goal[0] + 0.5, goal[1] + 0.5   # too close to a wall: stand mid-tile

        if self.segment_free(sx, sz, gx, gz, r):
            return [(gx, gz)]

        start = (min(max(math.floor(sx), x0), x1 - 1), min(max(math.floor(sz), z0), z1 - 1))
        roomy = r > 0.5                             # (a tank: every tile on its way must leave it room all round)
        lead = []
        if roomy and not self.circle_free(start[0] + 0.5, start[1] + 0.5, r):
            start = self.nearest_room(start, r)     # in a tight spot (by a wall): out of it first
            if start is None:
                return []
            lead = [(start[0] + 0.5, start[1] + 0.5)]
        if roomy and not self.circle_free(goal[0] + 0.5, goal[1] + 0.5, r):
            goal = self.nearest_room(goal, r) or goal   # no room for it there: as near as there is (or it looks everywhere)
            gx, gz = goal[0] + 0.5, goal[1] + 0.5
        tiles = self._astar(start, goal, r if roomy else 0.0)
        if not tiles and not lead:
            return []
        end = tiles[-1] if tiles else start
        if end != goal:                             # it couldn't get there: as near as it can
            gx, gz = end[0] + 0.5, end[1] + 0.5
        points = [(sx, sz)] + lead + [(i + 0.5, j + 0.5) for i, j in tiles] + [(gx, gz)]
        return self._smooth(points, r)

    def nearest_room(self, tile, r):
        """The tile nearest this one (ring by ring out, a few) whose middle has room for something
        of radius r all round, or None."""
        i, j = tile
        for ring in range(1, 8):
            ring_tiles = [(i + a, j + b) for a in range(-ring, ring + 1) for b in range(-ring, ring + 1)
                          if max(abs(a), abs(b)) == ring]
            free = [t for t in ring_tiles if self.is_open(*t) and self.circle_free(t[0] + 0.5, t[1] + 0.5, r)]
            if free:
                return min(free, key=lambda t: (t[0] - i) ** 2 + (t[1] - j) ** 2)
        return None

    def _astar(self, start, goal, room=0.0):
        """The tiles of the shortest way from start to goal (A*). If there's no way there (or it
        looks at FIND_MOST tiles without finding one), the way to the tile it reached nearest
        the goal. With `room`, only through tiles whose middles have that much room all round
        (for a tank)."""
        def guess(t):
            dx, dz = abs(t[0] - goal[0]), abs(t[1] - goal[1])
            return dx + dz + (DIAGONAL - 2) * min(dx, dz)

        roomy = {}

        def has_room(t):
            if t not in roomy:
                roomy[t] = self.circle_free(t[0] + 0.5, t[1] + 0.5, room)
            return roomy[t]

        best = {start: 0.0}
        came_from = {}
        frontier = [(guess(start), 0.0, start)]
        nearest = start
        while frontier and len(best) < FIND_MOST:
            _, cost, tile = heapq.heappop(frontier)
            if tile == goal:
                nearest = goal
                break
            if cost > best[tile]:
                continue
            if guess(tile) < guess(nearest):
                nearest = tile
            for ni, nj, step in self.neighbours(*tile):
                if room and not has_room((ni, nj)):
                    continue
                new_cost = cost + step
                if new_cost < best.get((ni, nj), math.inf):
                    best[(ni, nj)] = new_cost
                    came_from[(ni, nj)] = tile
                    heapq.heappush(frontier, (new_cost + guess((ni, nj)), new_cost, (ni, nj)))
        if nearest == start:
            return []
        path = [nearest]
        while path[-1] != start:
            path.append(came_from[path[-1]])
        path.reverse()
        return path

    def _smooth(self, points, r):
        """Skip waypoints that can be walked past in a straight line."""
        out = []
        i = 0
        while i < len(points) - 1:
            j = i + 1
            while j + 1 < len(points) and self.segment_free(*points[i], *points[j + 1], r):
                j += 1
            out.append(points[j])
            i = j
        return out
