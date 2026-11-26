"""Small vector and 4x4 matrix helpers.

Matrices are flat lists of 16 floats in column-major order, the layout OpenGL
shaders expect, so they can be sent to the graphics card as they are.
"""
import math
from array import array


# ---------------------------------------------------------------- vectors

def v_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def v_len(a):
    return math.sqrt(v_dot(a, a))


def v_norm(a):
    length = v_len(a)
    if length < 1e-9:
        return (0.0, 0.0, 0.0)
    return (a[0] / length, a[1] / length, a[2] / length)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def turn_toward(angle, target, max_step):
    """Turn an angle toward a target angle along the short way round."""
    diff = (target - angle + math.pi) % (2 * math.pi) - math.pi
    if abs(diff) <= max_step:
        return target
    return angle + math.copysign(max_step, diff)


def elbow(shoulder, hand, upper, lower, pole):
    """Where the elbow goes when an arm (upper and lower long) reaches from the shoulder to
    the hand, bending toward `pole` (a direction). If the hand is out of reach, the arm
    reaches straight toward it as far as it goes."""
    d = v_sub(hand, shoulder)
    dist = min(max(v_len(d), abs(upper - lower) + 1e-6), upper + lower - 1e-6)
    u = v_norm(d)
    cos_a = clamp((upper * upper + dist * dist - lower * lower) / (2 * upper * dist), -1.0, 1.0)
    side = v_norm(v_sub(pole, v_scale(u, v_dot(pole, u))))
    return v_add(shoulder, v_add(v_scale(u, upper * cos_a), v_scale(side, upper * math.sqrt(1 - cos_a * cos_a))))


def bone(start, end, across):
    """A matrix that hangs a limb piece (built hanging down -Y from its origin) from `start`
    toward `end`, its width turned as near to `across` as it can be."""
    y = v_norm(v_sub(start, end))
    x = v_norm(v_sub(across, v_scale(y, v_dot(across, y))))
    z = v_cross(x, y)
    return [x[0], x[1], x[2], 0.0, y[0], y[1], y[2], 0.0, z[0], z[1], z[2], 0.0, start[0], start[1], start[2], 1.0]


# ---------------------------------------------------------------- matrices

def identity():
    return [1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0]


def mul(a, b):
    """a * b: apply b first, then a. (Written out in full, not in loops: it's done hundreds of
    thousands of times a second, and this way is several times quicker; the sums are the same,
    in the same order.)"""
    a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15 = a
    out = []
    for c in (0, 4, 8, 12):
        b0, b1, b2, b3 = b[c], b[c + 1], b[c + 2], b[c + 3]
        out += (a0 * b0 + a4 * b1 + a8 * b2 + a12 * b3,
                a1 * b0 + a5 * b1 + a9 * b2 + a13 * b3,
                a2 * b0 + a6 * b1 + a10 * b2 + a14 * b3,
                a3 * b0 + a7 * b1 + a11 * b2 + a15 * b3)
    return out


def standing(x, y, z, yaw, lean, size, lift):
    """translate(x, y, z) * rot_y(yaw) * rot_x(lean) * scale(size) * translate(0, lift, 0),
    written out (where a body stands, turned, leaning, at its size, bobbing up): the same as
    that chain, in a fraction of the time."""
    ca, sa, cb, sb = math.cos(yaw), math.sin(yaw), math.cos(lean), math.sin(lean)
    up = (sb * sa * size, cb * size, sb * ca * size)
    return [ca * size, 0.0, -sa * size, 0.0,
            up[0], up[1], up[2], 0.0,
            cb * sa * size, -sb * size, cb * ca * size, 0.0,
            x + lift * up[0], y + lift * up[1], z + lift * up[2], 1.0]


def hung(m, x, y, z, angle):
    """m * translate(x, y, z) * rot_x(angle), written out (a limb swinging from a joint on a
    body): the same as that chain, in a fraction of the time."""
    c, s = math.cos(angle), math.sin(angle)
    return [m[0], m[1], m[2], m[3],
            c * m[4] + s * m[8], c * m[5] + s * m[9], c * m[6] + s * m[10], c * m[7] + s * m[11],
            c * m[8] - s * m[4], c * m[9] - s * m[5], c * m[10] - s * m[6], c * m[11] - s * m[7],
            x * m[0] + y * m[4] + z * m[8] + m[12], x * m[1] + y * m[5] + z * m[9] + m[13],
            x * m[2] + y * m[6] + z * m[10] + m[14], x * m[3] + y * m[7] + z * m[11] + m[15]]


def chain(*matrices):
    """Multiply left to right: chain(A, B, C) == A * B * C."""
    out = matrices[0]
    for m in matrices[1:]:
        out = mul(out, m)
    return out


def translate(x, y, z):
    m = identity()
    m[12], m[13], m[14] = x, y, z
    return m


def scale(x, y=None, z=None):
    m = identity()
    m[0] = x
    m[5] = x if y is None else y
    m[10] = x if z is None else z
    return m


def rot_x(angle):
    c, s = math.cos(angle), math.sin(angle)
    m = identity()
    m[5], m[6], m[9], m[10] = c, s, -s, c
    return m


def rot_y(angle):
    """Turns local +Z toward (sin angle, 0, cos angle)."""
    c, s = math.cos(angle), math.sin(angle)
    m = identity()
    m[0], m[2], m[8], m[10] = c, -s, s, c
    return m


def rot_z(angle):
    c, s = math.cos(angle), math.sin(angle)
    m = identity()
    m[0], m[1], m[4], m[5] = c, s, -s, c
    return m


def perspective(fov_y, aspect, near, far):
    f = 1.0 / math.tan(fov_y / 2)
    m = [0.0] * 16
    m[0] = f / aspect
    m[5] = f
    m[10] = (far + near) / (near - far)
    m[11] = -1.0
    m[14] = 2 * far * near / (near - far)
    return m


def look_at(eye, target, up):
    f = v_norm(v_sub(target, eye))
    s = v_norm(v_cross(f, up))
    u = v_cross(s, f)
    m = identity()
    m[0], m[4], m[8] = s
    m[1], m[5], m[9] = u
    m[2], m[6], m[10] = -f[0], -f[1], -f[2]
    m[12] = -v_dot(s, eye)
    m[13] = -v_dot(u, eye)
    m[14] = v_dot(f, eye)
    return m


def to_bytes(m):
    return array("f", m).tobytes()


def apply(m, p):
    """Where the point p ends up after the matrix m (a position, so it's moved too)."""
    x, y, z = p
    return (m[0] * x + m[4] * y + m[8] * z + m[12],
            m[1] * x + m[5] * y + m[9] * z + m[13],
            m[2] * x + m[6] * y + m[10] * z + m[14])


def box_hit(origin, direction, lo, hi):
    """How far along a ray it enters a box (lo and hi corners), or None if it misses."""
    near, far = 0.0, math.inf
    for k in range(3):
        if abs(direction[k]) < 1e-9:
            if not lo[k] <= origin[k] <= hi[k]:
                return None
            continue
        t0 = (lo[k] - origin[k]) / direction[k]
        t1 = (hi[k] - origin[k]) / direction[k]
        near, far = max(near, min(t0, t1)), min(far, max(t0, t1))
    return near if near <= far else None
