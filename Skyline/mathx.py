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


# ---------------------------------------------------------------- matrices

def identity():
    return [1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0]


def mul(a, b):
    """a * b: apply b first, then a."""
    out = [0.0] * 16
    for col in range(4):
        for row in range(4):
            out[col * 4 + row] = (a[row] * b[col * 4]
                                  + a[4 + row] * b[col * 4 + 1]
                                  + a[8 + row] * b[col * 4 + 2]
                                  + a[12 + row] * b[col * 4 + 3])
    return out


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
