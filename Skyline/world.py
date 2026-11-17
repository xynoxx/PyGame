"""The square map: which tiles are blocked (by the HQ or a turret), finding a
way across it, and whether a shot can fly between two points.

The map is MAP_SIZE x MAP_SIZE tiles, each one unit wide. Tile (i, j) covers
x in [i, i+1] and z in [j, j+1]; the ground is at height 0. Off the map there
are no walls: the zombies walk in from out there.
"""
import heapq
import math
from collections import namedtuple

MAP_SIZE = 96
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


class World:
    def __init__(self, size=MAP_SIZE):
        self.size = size
        self.blocked = [False] * (size * size)
        self.hqs = {}
        self.spawns = {}
        self.aprons = {}           # the concrete round each HQ: x0, z0, x1, z1
        self.reachable = set()     # tiles the player can walk to, worked out once their HQ is built

    # ------------------------------------------------------------ building the map

    @staticmethod
    def hq_tiles_at(x, z):
        """The tile an HQ's corner goes on when it's centred as near (x, z) as the tiles allow."""
        return round(x - HQ_WIDTH / 2), round(z - HQ_DEPTH / 2)

    @staticmethod
    def apron_of(i0, j0):
        """The concrete round an HQ on tile (i0, j0): x0, z0, x1, z1 (one more tile in front of its door)."""
        return (i0 - APRON, j0 - APRON, i0 + HQ_WIDTH + APRON, j0 + HQ_DEPTH + APRON + 1)

    def can_build_hq(self, i0, j0):
        """An HQ fits if it and its concrete are on the map, and nothing else is in the way."""
        x0, z0, x1, z1 = self.apron_of(i0, j0)
        if x0 < 0 or z0 < 0 or x1 > self.size or z1 > self.size:
            return False
        return not any(self.is_blocked(i, j)
                       for i in range(i0, i0 + HQ_WIDTH) for j in range(j0, j0 + HQ_DEPTH))

    def build_hq(self, owner, i0, j0):
        """Build an HQ with its corner on tile (i0, j0), its concrete, and a spawn point at its door."""
        hq = HQ(owner, i0, j0, HQ_WIDTH, HQ_DEPTH)
        self.hqs[owner] = hq
        n = self.size
        for i in range(i0, i0 + hq.w):
            for j in range(j0, j0 + hq.d):
                self.blocked[j * n + i] = True
        self.aprons[owner] = self.apron_of(i0, j0)
        self.spawns[owner] = (i0 + hq.w / 2, j0 + hq.d + 1.5)
        if owner == "player":
            self.reachable = self._flood(tuple(int(v) for v in self.spawns[owner]))
        return hq

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
        steps = max(1, int(math.hypot(x1 - x0, z1 - z0) / 0.25))
        n = self.size
        for k in range(1, steps):
            t = k / steps
            x, z = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
            if 0 <= x < n and 0 <= z < n and self.blocked[int(z) * n + int(x)] and (int(x), int(z)) != skip:
                return False
        return True

    def can_build_turret(self, i, j):
        """A turret needs one free tile on the map."""
        return 0 <= i < self.size and 0 <= j < self.size and not self.is_blocked(i, j)

    def set_blocked(self, i, j, blocked):
        """Put something on a tile, or take it away, and work out afresh where the player's units can walk."""
        self.blocked[j * self.size + i] = blocked
        if "player" in self.spawns:
            self.reachable = self._flood(tuple(int(v) for v in self.spawns["player"]))

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
