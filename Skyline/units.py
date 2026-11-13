"""Units on the map. For now there is one kind: the commander."""
import math

from mathx import turn_toward


class Commander:
    RADIUS = 0.35       # how much room they take up on the map
    SPEED = 3.6         # tiles per second
    TURN_RATE = 10.0    # radians per second
    SIZE = 1.5          # drawing scale of the model

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

    @property
    def moving(self):
        return bool(self.path)

    @property
    def destination(self):
        return self.path[-1] if self.path else None

    @property
    def tile(self):
        return int(self.x), int(self.z)

    def move_to(self, x, z):
        """Walk to (x, z), around anything in the way. Returns where they will end up."""
        self.path = self.world.find_path(self.x, self.z, x, z, self.RADIUS)
        return self.destination

    def stop(self):
        self.path = []

    def update(self, dt):
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
        if heading is not None:
            self.yaw = turn_toward(self.yaw, heading, self.TURN_RATE * dt)

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

    def hit_by_ray(self, origin, direction):
        """Does a mouse ray (from the camera) touch this commander?"""
        cx, cy, cz = self.x, 0.75 * self.SIZE, self.z
        radius = 0.55 * self.SIZE
        ox, oy, oz = origin[0] - cx, origin[1] - cy, origin[2] - cz
        b = ox * direction[0] + oy * direction[1] + oz * direction[2]
        c = ox * ox + oy * oy + oz * oz - radius * radius
        disc = b * b - c
        return disc >= 0 and -b + math.sqrt(disc) > 0
