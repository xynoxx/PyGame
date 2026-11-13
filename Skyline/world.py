"""The square map: bare ground, each team's HQ, and finding a way across it.

The map is MAP_SIZE x MAP_SIZE tiles, each one unit wide. Tile (i, j) covers
x in [i, i+1] and z in [j, j+1]; the ground is at height 0.
"""
import heapq
import math
from collections import namedtuple

MAP_SIZE = 64
START_INSET = 8            # how far each start sits from its corner
DIAGONAL = math.sqrt(2)

HQ_WIDTH, HQ_DEPTH = 5, 4  # tiles the HQ stands on; its door faces +Z
APRON = 2                  # tiles of concrete round the HQ (one more in front)

# The HQ covers tiles i .. i + w - 1 and j .. j + d - 1.
HQ = namedtuple("HQ", "owner i j w d")


def hash01(i, j, seed):
    """A repeatable pseudo-random number in 0..1 for a grid point."""
    n = (i * 374761393 + j * 668265263 + seed * 982451653) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def value_noise(x, z, seed):
    """Smooth noise in 0..1, used to vary the ground colour across the map."""
    i, j = math.floor(x), math.floor(z)
    fx, fz = x - i, z - j
    fx, fz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a, b = hash01(i, j, seed), hash01(i + 1, j, seed)
    c, d = hash01(i, j + 1, seed), hash01(i + 1, j + 1, seed)
    top = a + (b - a) * fx
    bottom = c + (d - c) * fx
    return top + (bottom - top) * fz


class World:
    def __init__(self, size=MAP_SIZE, seed=7):
        self.size = size
        self.seed = seed
        self.blocked = [False] * (size * size)
        far = size - START_INSET - 0.5
        near = START_INSET + 0.5
        # One start per corner. Only the player uses theirs for now; the ally
        # and the two enemies will take the others.
        self.starts = {
            "player": (near, far),
            "ally": (far, far),
            "enemy 1": (near, near),
            "enemy 2": (far, near),
        }
        self.hqs = {}
        self.spawns = {}
        self.plaza = set()         # concrete tiles round the HQs
        self.build_hq("player")
        self.reachable = self._flood(tuple(int(v) for v in self.spawns["player"]))

    # ------------------------------------------------------------ building the map

    def build_hq(self, owner):
        """Put an HQ on a start, with a concrete apron, and a spawn point at its door."""
        sx, sz = self.starts[owner]
        i0, j0 = int(sx) - HQ_WIDTH // 2, int(sz) - HQ_DEPTH // 2
        hq = HQ(owner, i0, j0, HQ_WIDTH, HQ_DEPTH)
        self.hqs[owner] = hq
        n = self.size
        for i in range(i0, i0 + hq.w):
            for j in range(j0, j0 + hq.d):
                self.blocked[j * n + i] = True
        i_lo, i_hi = i0 - APRON, i0 + hq.w + APRON - 1
        j_lo, j_hi = j0 - APRON, j0 + hq.d + APRON
        for i in range(i_lo, i_hi + 1):
            for j in range(j_lo, j_hi + 1):
                edge = i in (i_lo, i_hi) or j in (j_lo, j_hi)
                if edge and hash01(i, j, self.seed + 21) < 0.35:
                    continue       # broken slabs round the edge
                if 0 <= i < n and 0 <= j < n:
                    self.plaza.add((i, j))
        self.spawns[owner] = (i0 + hq.w / 2, j0 + hq.d + 1.5)

    # ------------------------------------------------------------ asking about the map

    def is_blocked(self, i, j):
        return self.blocked[j * self.size + i]

    def neighbours(self, i, j):
        """Tiles you can step to from (i, j), with the cost of the step.
        Diagonal steps are only allowed when they don't cut a corner."""
        n, blocked = self.size, self.blocked
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < n and 0 <= nj < n and not blocked[nj * n + ni]:
                yield ni, nj, 1.0
        for di, dj in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            ni, nj = i + di, j + dj
            if (0 <= ni < n and 0 <= nj < n and not blocked[nj * n + ni]
                    and not blocked[j * n + ni] and not blocked[nj * n + i]):
                yield ni, nj, DIAGONAL

    def _flood(self, start):
        seen = {start}
        todo = [start]
        while todo:
            i, j = todo.pop()
            for ni, nj, _ in self.neighbours(i, j):
                if (ni, nj) not in seen:
                    seen.add((ni, nj))
                    todo.append((ni, nj))
        return seen

    def circle_free(self, x, z, r):
        """Can something round, of radius r, stand at (x, z)?"""
        n = self.size
        if x - r < 0 or z - r < 0 or x + r > n or z + r > n:
            return False
        for i in range(int(x - r), min(int(x + r), n - 1) + 1):
            for j in range(int(z - r), min(int(z + r), n - 1) + 1):
                if self.blocked[j * n + i]:
                    cx = min(max(x, i), i + 1)
                    cz = min(max(z, j), j + 1)
                    if (x - cx) ** 2 + (z - cz) ** 2 < r * r:
                        return False
        return True

    def segment_free(self, x0, z0, x1, z1, r):
        """Can something of radius r walk straight from one point to the other?"""
        steps = max(1, int(math.hypot(x1 - x0, z1 - z0) / 0.2))
        for k in range(steps + 1):
            t = k / steps
            if not self.circle_free(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, r):
                return False
        return True

    def nearest_reachable(self, x, z):
        return min(self.reachable, key=lambda t: (t[0] + 0.5 - x) ** 2 + (t[1] + 0.5 - z) ** 2)

    # ------------------------------------------------------------ pathfinding

    def find_path(self, sx, sz, gx, gz, r):
        """Points to walk through to get from (sx, sz) to (gx, gz), avoiding obstacles.

        If the goal is inside a building, or somewhere that can't be reached,
        the walker goes to the nearest place it can stand instead.
        """
        n = self.size
        gx = min(max(gx, r + 0.01), n - r - 0.01)
        gz = min(max(gz, r + 0.01), n - r - 0.01)
        goal = (int(gx), int(gz))
        if goal not in self.reachable:
            goal = self.nearest_reachable(gx, gz)
            gx, gz = goal[0] + 0.5, goal[1] + 0.5
        elif not self.circle_free(gx, gz, r):
            gx, gz = goal[0] + 0.5, goal[1] + 0.5   # too close to a wall: stand mid-tile

        if self.segment_free(sx, sz, gx, gz, r):
            return [(gx, gz)]

        start = (min(max(int(sx), 0), n - 1), min(max(int(sz), 0), n - 1))
        tiles = self._astar(start, goal)
        if not tiles:
            return []
        points = [(sx, sz)] + [(i + 0.5, j + 0.5) for i, j in tiles] + [(gx, gz)]
        return self._smooth(points, r)

    def _astar(self, start, goal):
        def guess(t):
            dx, dz = abs(t[0] - goal[0]), abs(t[1] - goal[1])
            return dx + dz + (DIAGONAL - 2) * min(dx, dz)

        best = {start: 0.0}
        came_from = {}
        frontier = [(guess(start), 0.0, start)]
        while frontier:
            _, cost, tile = heapq.heappop(frontier)
            if tile == goal:
                break
            if cost > best[tile]:
                continue
            for ni, nj, step in self.neighbours(*tile):
                new_cost = cost + step
                if new_cost < best.get((ni, nj), math.inf):
                    best[(ni, nj)] = new_cost
                    came_from[(ni, nj)] = tile
                    heapq.heappush(frontier, (new_cost + guess((ni, nj)), new_cost, (ni, nj)))
        else:
            return []
        path = [goal]
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
