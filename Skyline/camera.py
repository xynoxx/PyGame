"""The RTS camera: looks down at a point on the map from an angle, pans, zooms and turns."""
import math

import mathx


class RTSCamera:
    MIN_DIST, MAX_DIST = 8.0, 72.0

    def __init__(self, map_size, aspect):
        self.map_size = map_size
        self.aspect = aspect
        self.fov = math.radians(45)
        self.tx = self.tz = map_size / 2    # the point on the ground we look at
        self.yaw = 0.0                      # 0: camera sits on the +Z side, looking toward -Z
        self.dist = self.dist_goal = 17.0
        self.glide = None                   # a point we're sliding toward, if any

    @property
    def pitch(self):
        """Steeper when zoomed out, flatter when zoomed in."""
        t = (self.dist - self.MIN_DIST) / (self.MAX_DIST - self.MIN_DIST)
        return math.radians(42 + 20 * t)

    @property
    def target(self):
        return (self.tx, 0.0, self.tz)

    def eye(self):
        p = self.pitch
        return (self.tx + math.sin(self.yaw) * math.cos(p) * self.dist,
                math.sin(p) * self.dist,
                self.tz + math.cos(self.yaw) * math.cos(p) * self.dist)

    def fog_range(self):
        return (self.dist + 6.0, self.dist + 70.0)    # thick haze

    def view_proj(self):
        view = mathx.look_at(self.eye(), self.target, (0.0, 1.0, 0.0))
        proj = mathx.perspective(self.fov, self.aspect, 0.3, 400.0)
        return mathx.mul(proj, view)

    # ------------------------------------------------------------ moving it

    def pan(self, forward, right, dt):
        """Move across the map relative to where the camera faces (inputs -1..1)."""
        speed = self.dist * 1.2
        fx, fz = -math.sin(self.yaw), -math.cos(self.yaw)
        rx, rz = math.cos(self.yaw), -math.sin(self.yaw)
        self.tx += (fx * forward + rx * right) * speed * dt
        self.tz += (fz * forward + rz * right) * speed * dt
        self.glide = None
        self._clamp()

    def zoom(self, steps):
        self.dist_goal = mathx.clamp(self.dist_goal * 0.88 ** steps, self.MIN_DIST, self.MAX_DIST)

    def turn(self, angle):
        self.yaw += angle

    def look_at(self, x, z, instant=False):
        if instant:
            self.tx, self.tz = x, z
            self.glide = None
        else:
            self.glide = (x, z)

    def update(self, dt):
        self.dist += (self.dist_goal - self.dist) * min(1.0, dt * 10)
        if self.glide:
            gx, gz = self.glide
            k = min(1.0, dt * 7)
            self.tx += (gx - self.tx) * k
            self.tz += (gz - self.tz) * k
            if math.hypot(gx - self.tx, gz - self.tz) < 0.02:
                self.glide = None
        self._clamp()

    def _clamp(self):
        self.tx = mathx.clamp(self.tx, 0, self.map_size)
        self.tz = mathx.clamp(self.tz, 0, self.map_size)

    # ------------------------------------------------------------ the mouse

    def ray(self, mx, my, width, height):
        """The line from the camera through a pixel on the screen: (origin, direction)."""
        eye = self.eye()
        fwd = mathx.v_norm(mathx.v_sub(self.target, eye))
        right = mathx.v_norm(mathx.v_cross(fwd, (0.0, 1.0, 0.0)))
        up = mathx.v_cross(right, fwd)
        half = math.tan(self.fov / 2)
        nx = (2 * mx / width - 1) * half * self.aspect
        ny = (1 - 2 * my / height) * half
        d = mathx.v_add(fwd, mathx.v_add(mathx.v_scale(right, nx), mathx.v_scale(up, ny)))
        return eye, mathx.v_norm(d)

    def to_screen(self, x, y, z, width, height, view_proj=None):
        """Where a point in the world shows on the screen, in pixels, or None if it's behind the camera."""
        m = view_proj or self.view_proj()
        cx = m[0] * x + m[4] * y + m[8] * z + m[12]
        cy = m[1] * x + m[5] * y + m[9] * z + m[13]
        cw = m[3] * x + m[7] * y + m[11] * z + m[15]
        if cw <= 1e-6:
            return None
        return (cx / cw + 1) * 0.5 * width, (1 - cy / cw) * 0.5 * height

    def ground_point(self, mx, my, width, height):
        """Where on the ground (y = 0) the mouse points, as (x, z), or None for the sky."""
        origin, d = self.ray(mx, my, width, height)
        if d[1] > -1e-6:
            return None
        t = -origin[1] / d[1]
        return origin[0] + d[0] * t, origin[2] + d[2] * t
