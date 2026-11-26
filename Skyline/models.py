"""Builds the low-poly meshes: the HQ, the bullet factory, the junkyard and the
warehouse (and the salvage crane and loading dock post that strip them), the
radar station, the soldier (and his rifle) and the engineer, the turrets, the
trenches, the zombies, and the marks drawn on the ground.

Everything is made of boxes (and flat rings and discs on the ground) with a
colour per face, built in code: there are no model files. People share one
skeleton: a body standing on y = 0 facing +Z, legs hung from hips at y = 0.42
(x = +-0.1) and arms from shoulders at y = 0.80 (x = +-0.22; a zombie's
+-0.28), so main.Game can swing them. The look is a zombie apocalypse. (The ground isn't a mesh: gfx.GROUND_FS
paints it.)
"""
import math
from collections import namedtuple

import mathx
from gfx import MeshBuilder
from world import TRENCH_DEPTH, hash01


def shade(color, k):
    return tuple(min(1.0, c * k) for c in color)


# ---------------------------------------------------------------- the HQ

HQ_CONCRETE = (0.58, 0.57, 0.53)
HQ_CONCRETE_DARK = (0.44, 0.43, 0.40)
ROOF_TAR = (0.20, 0.20, 0.20)
STEEL = (0.50, 0.52, 0.54)
STEEL_DARK = (0.22, 0.23, 0.24)
GLASS = (0.10, 0.13, 0.15)
PLANK = (0.45, 0.33, 0.21)
SANDBAG = (0.56, 0.50, 0.37)
LAMP = (1.0, 0.93, 0.70)
BEACON = (0.95, 0.15, 0.10)
HAZARD = (0.92, 0.72, 0.15)
BRICK = (0.52, 0.25, 0.19)
BRICK_DARK = (0.36, 0.17, 0.13)
STONE = (0.72, 0.68, 0.60)
TANK = (0.63, 0.65, 0.67)
BRASS = (0.80, 0.62, 0.26)
COPPER = (0.70, 0.38, 0.22)
AMMO_GREEN = (0.30, 0.34, 0.22)


HQ_BLACK = (0.13, 0.13, 0.14)
HQ_PIER = (0.19, 0.19, 0.20)
HQ_GLASS = (0.06, 0.07, 0.09)
INTERIOR = (0.80, 0.84, 0.88)    # the lights on inside, seen through the windows
DOORWAY = (0.03, 0.03, 0.035)
WIRE = (0.60, 0.62, 0.64)
HQ_STOREYS = 3                   # storeys over the ground floor
HQ_GROUND, HQ_STOREY = 1.15, 0.62   # how tall the ground floor is, and each one over it
HQ_TOP = 0.12 + HQ_GROUND + HQ_STOREY * HQ_STOREYS   # the top of its walls (the slab is 0.12)


def build_hq(hq, team):
    """A fortified headquarters block in dark concrete on its tiles, its entrance facing +Z:
    four storeys with long bands of windows (the lights on inside), piers between the bays
    with a lamp near the top of each, a taller stair tower at its front left, and a block over
    the entrance held up on two piers. Round its roof, a railing, with a plant room, a radio
    mast and the team's flag on it. Round it all, at the edge of its slab, a low wall with
    barbed wire on posts, open at the front where the gate stands slid aside, and lamps along
    its foot.

    Everything stands on the slab and inside the HQ's tiles, so it never pokes into a tile
    someone can walk on, and every part rests on the slab or on what's under it, or is fixed
    to a wall it touches."""
    mb = MeshBuilder()
    i0, j0, i1, j1 = hq.i, hq.j, hq.i + hq.w, hq.j + hq.d
    cx = (i0 + i1) / 2
    slab_h = 0.12
    mb.box(cx, 0, (j0 + j1) / 2, hq.w - 0.1, slab_h, hq.d - 0.1, HQ_CONCRETE_DARK)

    # the block, set back on the slab, a coping round its roof
    left, right, back, front = i0 + 0.40, i1 - 0.40, j0 + 0.40, j1 - 0.85
    bx, bz, bw, bd = (left + right) / 2, (back + front) / 2, right - left, front - back
    top = HQ_TOP
    mb.box(bx, slab_h, bz, bw, top - slab_h - 0.10, bd, HQ_BLACK)
    mb.box(bx, top - 0.10, bz, bw + 0.06, 0.10, bd + 0.06, HQ_PIER, top=ROOF_TAR)

    # the stair tower, at the front left, standing higher than the roof
    tl, tr, tb, tf = left - 0.04, left + 0.85, front - 0.70, front + 0.18
    t_top = top + 0.45
    mb.box((tl + tr) / 2, slab_h, (tb + tf) / 2, tr - tl, t_top - slab_h, tf - tb, HQ_PIER, top=ROOF_TAR)
    mb.box((tl + tr) / 2, 1.0, tf + 0.005, 0.12, t_top - 1.25, 0.01, HQ_GLASS)          # a narrow slot of a window
    mb.box((tl + tr) / 2, t_top - 0.22, tf + 0.015, 0.10, 0.06, 0.03, LAMP)              # a lamp over it

    # bands of windows round the upper storeys, lit inside, and on the ground floor's right
    def band(y, h, faces):
        """A band of windows h tall from y, along each face: (x0, x1, z, sign) runs along x at z,
        (z0, z1, x, sign) along z at x; sign is which way the face looks."""
        for along_x, a0, a1, at, sign in faces:
            mid, length = (a0 + a1) / 2, a1 - a0
            off = at + sign * 0.005
            if along_x:
                mb.box(mid, y, off, length, h, 0.01, HQ_GLASS)
            else:
                mb.box(off, y, mid, 0.01, h, length, HQ_GLASS)
            for k in range(int(length / 0.26)):                  # mullions, and the lights inside
                t = a0 + 0.13 + k * 0.26
                if along_x:
                    mb.box(t, y, at + sign * 0.012, 0.015, h, 0.006, STEEL_DARK)
                    mb.box(t + 0.06, y + h - 0.07, at + sign * 0.012, 0.09, 0.025, 0.006, INTERIOR)
                else:
                    mb.box(at + sign * 0.012, y, t, 0.006, h, 0.015, STEEL_DARK)
                    mb.box(at + sign * 0.012, y + h - 0.07, t + 0.06, 0.006, 0.025, 0.09, INTERIOR)

    for k in range(HQ_STOREYS):
        y = slab_h + HQ_GROUND + k * HQ_STOREY + 0.12
        band(y, 0.36, ((True, tr + 0.13, right - 0.08, front, 1), (True, left + 0.08, right - 0.08, back, -1),
                       (False, back + 0.08, tb - 0.05, left, -1), (False, back + 0.08, front - 0.08, right, 1)))
    band(slab_h + 0.32, 0.55, ((True, cx + 1.03, right - 0.08, front, 1), (False, back + 0.08, front - 0.08, right, 1)))

    # piers between the bays, from the slab to the coping, each with a lamp near its top
    for x in (tr + 0.07, cx + 0.95, right - 0.06):
        mb.box(x, slab_h, front + 0.03, 0.12, top - 0.10 - slab_h, 0.06, HQ_PIER)
        mb.box(x, top - 0.32, front + 0.07, 0.06, 0.05, 0.02, LAMP)
    for z in (back + 0.06, bz, front - 0.06):
        for x, sign in ((left, -1), (right, 1)):
            mb.box(x + sign * 0.03, slab_h, z, 0.06, top - 0.10 - slab_h, 0.12, HQ_PIER)
            mb.box(x + sign * 0.07, top - 0.32, z, 0.02, 0.05, 0.06, LAMP)

    # the entrance: a dark doorway, a block over it on two piers, lamps under it, steps up
    ew, eh = 0.85, 1.32                                       # half its width, how high the block starts
    for side in (-1, 1):
        mb.box(cx + side * (ew - 0.10), slab_h, front + 0.15, 0.20, eh - slab_h, 0.30, HQ_PIER)
    mb.box(cx, eh, front + 0.15, 2 * ew, 0.85, 0.30, HQ_PIER, top=ROOF_TAR)
    mb.box(cx, slab_h, front + 0.005, 2 * ew - 0.40, eh - slab_h - 0.08, 0.01, DOORWAY)
    mb.box(cx, slab_h, front + 0.015, 0.70, 0.95, 0.01, HQ_GLASS)                       # the glass doors
    mb.box(cx, slab_h + 0.95, front + 0.02, 0.74, 0.04, 0.02, STEEL_DARK)
    for x in (cx - 0.35, cx + 0.35):
        mb.box(x, eh - 0.02, front + 0.20, 0.08, 0.02, 0.08, LAMP)                      # lamps under the block
    for k, (y, d) in enumerate(((slab_h, 0.40), (slab_h + 0.05, 0.25))):                 # two steps up to the doors
        mb.box(cx, y, front + d / 2, 1.0 - 0.1 * k, 0.05, d, HQ_CONCRETE)

    # a railing round the roof, a plant room, a radio mast, and the team's flag
    for x0, z0, x1, z1 in ((left + 0.05, back + 0.05, right - 0.05, back + 0.05),         # (not round the tower)
                           (left + 0.05, back + 0.05, left + 0.05, tb - 0.05), (right - 0.05, back + 0.05, right - 0.05, front - 0.05),
                           (tr + 0.05, front - 0.05, right - 0.05, front - 0.05)):
        length = math.hypot(x1 - x0, z1 - z0)
        for k in range(int(length / 0.4) + 1):
            t = k * 0.4 / max(length, 1e-6)
            mb.box(x0 + (x1 - x0) * t, top, z0 + (z1 - z0) * t, 0.025, 0.22, 0.025, STEEL)
        for y in (top + 0.11, top + 0.20):
            mb.box((x0 + x1) / 2, y, (z0 + z1) / 2, max(x1 - x0, 0.02), 0.02, max(z1 - z0, 0.02), STEEL)
    mb.box(bx + 0.6, top, bz - 0.2, 0.9, 0.38, 0.6, (0.28, 0.29, 0.30), top=(0.24, 0.25, 0.26))
    mx, mz = right - 0.45, back + 0.40
    mb.box(mx, top, mz, 0.28, 0.05, 0.28, STEEL_DARK)
    mb.box(mx, top + 0.05, mz, 0.07, 2.0, 0.07, STEEL)
    for y in (top + 0.8, top + 1.4):
        mb.box(mx, y, mz, 0.34, 0.03, 0.03, STEEL)
    mb.box(mx, top + 2.05, mz, 0.11, 0.11, 0.11, BEACON)
    fx, fz = bx - 0.6, bz
    mb.box(fx, top, fz, 0.05, 1.3, 0.05, STEEL)
    mb.box(fx + 0.30, top + 0.88, fz, 0.55, 0.36, 0.02, team)

    # the wall round the slab, barbed wire on posts along it, open at the front for the gate
    wall_h, wt = 0.42, 0.08
    gate = 0.85                                               # half the gate's opening
    e = 0.12                                                  # the wall's middle, in from its tiles' edge
    runs = [(i0 + e - wt / 2, j0 + e, i1 - e + wt / 2, j0 + e), (i0 + e, j0 + e + wt / 2, i0 + e, j1 - e - wt / 2),
            (i1 - e, j0 + e + wt / 2, i1 - e, j1 - e - wt / 2),
            (i0 + e - wt / 2, j1 - e, cx - gate, j1 - e), (cx + gate, j1 - e, i1 - e + wt / 2, j1 - e)]
    for x0, z0, x1, z1 in runs:
        along_x = abs(z1 - z0) < 1e-9
        length = abs(x1 - x0) if along_x else abs(z1 - z0)
        mx_, mz_ = (x0 + x1) / 2, (z0 + z1) / 2
        w, d = (length, wt) if along_x else (wt, length)
        mb.box(mx_, slab_h, mz_, w, wall_h, d, HQ_BLACK, top=HQ_PIER)
        wy = slab_h + wall_h
        for k in range(int(length / 0.5) + 1):                 # posts
            t = min(k * 0.5, length) / length
            mb.box(x0 + (x1 - x0) * t, wy, z0 + (z1 - z0) * t, 0.02, 0.26, 0.02, STEEL_DARK)
        for y in (wy + 0.08, wy + 0.16, wy + 0.24):             # strands, and their barbs
            mb.box(mx_, y, mz_, w if along_x else 0.008, 0.008, d if not along_x else 0.008, WIRE)
            for k in range(int(length / 0.2)):
                t = (k + 0.5) * 0.2 / length
                mb.box(x0 + (x1 - x0) * t, y - 0.012, z0 + (z1 - z0) * t, 0.03, 0.03, 0.03, WIRE, yaw=0.785)
        outward = (0.0, -1.0) if along_x and mz_ < (j0 + j1) / 2 else (0.0, 1.0) if along_x else \
            (-1.0, 0.0) if mx_ < cx else (1.0, 0.0)
        for k in range(int(length / 1.0)):                     # lamps on its outer face, near the foot
            t = (k + 0.5) / int(length / 1.0)
            x, z = x0 + (x1 - x0) * t + outward[0] * (wt / 2 + 0.01), z0 + (z1 - z0) * t + outward[1] * (wt / 2 + 0.01)
            mb.box(x, slab_h + 0.03, z, 0.06 if along_x else 0.02, 0.04, 0.02 if along_x else 0.06, LAMP)

    # the gate: a post either side of the opening, and the gate itself slid open behind the wall on the right
    for side in (-1, 1):
        mb.box(cx + side * (gate + 0.06), slab_h, j1 - e, 0.12, 0.72, 0.12, HQ_PIER)
        mb.box(cx + side * (gate + 0.06), slab_h + 0.72, j1 - e, 0.08, 0.04, 0.08, LAMP)
    gz = j1 - e - wt / 2 - 0.035                               # just behind the wall
    g0 = cx + gate + 0.15
    mb.box(g0 + 0.65, slab_h, gz, 1.3, 0.03, 0.03, STEEL_DARK)                              # its foot rail
    mb.box(g0 + 0.65, slab_h + 0.60, gz, 1.3, 0.03, 0.03, STEEL_DARK)                       # its top rail
    for k in range(14):
        mb.box(g0 + k * 0.1, slab_h + 0.03, gz, 0.02, 0.57, 0.02, STEEL_DARK)              # its bars
    return mb


def octagon(mb, x, y, z, r, h, color, bottom=False):
    """An eight-sided upright drum standing on (x, y, z), r from its middle to its corners,
    h tall: four boxes turned an eighth of a turn apart, each reaching from one flat side to
    the one opposite, so together they fill the octagon and no more. (With `bottom`, its
    underside is drawn too, for one that hangs.)"""
    for k in range(4):
        mb.box(x, y, z, 2 * r * math.cos(math.pi / 8), h, 2 * r * math.sin(math.pi / 8), color, yaw=k * math.pi / 4,
               bottom=bottom)


def build_factory(team, w=4, d=3):
    """A bullet factory: a small brick works on w by d tiles, its corner at the origin, its
    loading door facing +Z (as the HQ's door does). A brick hall with tall windows and a
    raised glass roof down its length, two brick chimneys rising from its roof; two steel
    tanks on saddles beside it, piped into its wall, and crates of ammunition on a pallet in
    front of them; over the door, the team's sign with a brass bullet on it.

    Everything stands on the slab and inside its tiles, so it never pokes into a tile someone
    can walk on, and each part rests on the slab or on what's under it. The hall and the
    tanks come within a little of its tiles' edge on every side, so the dead (and workers)
    stopped at its tiles stand at its walls."""
    mb = MeshBuilder()
    slab_h = 0.1
    mb.box(w / 2, 0, d / 2, w - 0.1, slab_h, d - 0.1, HQ_CONCRETE_DARK)

    # the hall: brick walls on a dark plinth, a pale stone cornice round its flat roof
    left, right, back, front = 0.15, 2.90, 0.15, d - 0.35
    hx, hz, hw, hd, hh = (left + right) / 2, (back + front) / 2, right - left, front - back, 1.05
    roof = slab_h + hh
    mb.box(hx, slab_h, hz, hw, hh - 0.08, hd, BRICK)
    mb.box(hx, slab_h, hz, hw + 0.02, 0.16, hd + 0.02, BRICK_DARK)              # plinth
    mb.box(hx, roof - 0.08, hz, hw + 0.06, 0.08, hd + 0.06, STONE, top=ROOF_TAR)   # cornice, and the roof
    for sx in (-1, 1):                                                          # brick piers at the corners
        for sz in (-1, 1):
            mb.box(hx + sx * (hw / 2 - 0.07), slab_h, hz + sz * (hd / 2 - 0.07), 0.18, hh + 0.02, 0.18, BRICK_DARK)

    # the raised roof down the hall's length: glass sides, a dark cap
    rz = hz + 0.25
    mb.box(hx, roof, rz, hw - 0.5, 0.26, 0.7, GLASS)
    for k in range(6):                                                          # its glazing bars
        mb.box(left + 0.4 + k * (hw - 0.8) / 5, roof, rz, 0.03, 0.26, 0.72, STEEL_DARK)
    mb.box(hx, roof + 0.26, rz, hw - 0.4, 0.06, 0.82, ROOF_TAR)

    # tall windows, each with a stone lintel and sill: two either side of the door, two at each end
    for x in (left + 0.32, left + 0.72, right - 0.72, right - 0.32):
        mb.box(x, 0.38, front + 0.005, 0.22, 0.55, 0.01, GLASS)
        mb.box(x, 0.93, front + 0.01, 0.30, 0.06, 0.03, STONE)
        mb.box(x, 0.34, front + 0.015, 0.28, 0.04, 0.04, STONE)
    for side in (-1, 1):
        x = hx + side * (hw / 2 + 0.005)
        for z in (hz - 0.6, hz + 0.6):
            mb.box(x, 0.38, z, 0.01, 0.55, 0.22, GLASS)
            mb.box(x + side * 0.005, 0.93, z, 0.03, 0.06, 0.30, STONE)

    # the loading door: a roll-up steel door in a hazard-striped frame, a step of concrete
    mb.box(hx, slab_h, front + 0.01, 0.96, 0.78, 0.02, HAZARD)
    mb.box(hx, slab_h, front + 0.02, 0.84, 0.72, 0.02, STEEL)
    for k in range(9):                                                          # its slats
        mb.box(hx, slab_h + 0.04 + k * 0.075, front + 0.032, 0.84, 0.02, 0.01, STEEL_DARK)
    mb.box(hx, slab_h, front + 0.13, 1.0, 0.03, 0.24, HQ_CONCRETE)

    # the sign over the door: the team's colour, and a brass bullet (a case and a copper tip)
    mb.box(hx, 0.92, front + 0.015, 0.50, 0.18, 0.03, team)
    mb.box(hx - 0.06, 0.95, front + 0.035, 0.10, 0.06, 0.01, BRASS)
    mb.box(hx + 0.03, 0.955, front + 0.035, 0.08, 0.05, 0.01, COPPER)
    mb.box(hx + 0.08, 0.965, front + 0.035, 0.03, 0.03, 0.01, COPPER)

    # two chimneys rising from the back of the roof
    for x, tall in ((left + 0.45, 2.35), (left + 0.95, 2.15)):
        z = back + 0.35
        mb.box(x, roof, z, 0.32, tall - roof, 0.32, BRICK)
        for y in (1.55, tall - 0.30):                                           # pale bands round it
            mb.box(x, y, z, 0.34, 0.06, 0.34, STONE)
        mb.box(x, tall, z, 0.36, 0.08, 0.36, BRICK_DARK)                         # its cap, sooty
        mb.box(x, tall + 0.08, z, 0.22, 0.01, 0.22, (0.05, 0.05, 0.05))         # the flue

    # two steel tanks on saddles, beside the hall, each piped into its wall
    tx, r, th = 3.42, 0.39, 0.95
    for z in (0.70, 1.75):
        for dx in (-0.2, 0.2):                                                  # concrete saddles under it
            mb.box(tx + dx, slab_h, z, 0.12, 0.10, 0.62, HQ_CONCRETE)
        octagon(mb, tx, slab_h + 0.10, z, r, th, TANK)                          # the tank, eight-sided
        octagon(mb, tx, slab_h + 0.10 + th, z, r * 0.7, 0.08, STEEL)            # its top
        octagon(mb, tx, slab_h + 0.35, z, r + 0.012, 0.05, STEEL_DARK)          # a band round it
        py, near = slab_h + 0.10 + th - 0.20, tx - r * math.cos(math.pi / 8)    # (the side of the tank nearest the hall)
        mb.box((right + near) / 2, py, z, near - right + 0.03, 0.07, 0.07, STEEL_DARK)   # the pipe, wall to tank

    # crates of ammunition on a pallet, in front of the tanks
    px, pz = tx, d - 0.45
    mb.box(px, slab_h, pz, 0.60, 0.05, 0.50, PLANK)
    for k, (x, z, y) in enumerate(((px - 0.15, pz - 0.11, 0.0), (px + 0.15, pz - 0.11, 0.0), (px, pz + 0.12, 0.0),
                                   (px - 0.02, pz - 0.10, 0.14))):
        cy = slab_h + 0.05 + y
        mb.box(x, cy, z, 0.26, 0.14, 0.20, AMMO_GREEN, yaw=0.05 * (k - 1.5))
        mb.box(x, cy + 0.05, z, 0.27, 0.03, 0.21, HAZARD, yaw=0.05 * (k - 1.5))
    return mb


# ---------------------------------------------------------------- the deposits, and what strips them

CAR_L, CAR_W = 1.5, 0.7      # a wrecked car's length and width
CAR_BODY, CAR_CABIN = 0.24, 0.20
CAR_H = CAR_BODY + CAR_CABIN  # how tall one is: cars stack this much apart
CAR_COLORS = [(0.56, 0.18, 0.15), (0.22, 0.30, 0.46), (0.74, 0.73, 0.68),
              (0.28, 0.38, 0.27), (0.68, 0.56, 0.24), (0.40, 0.40, 0.42)]
RUST = (0.45, 0.25, 0.13)
YARD_DIRT = (0.33, 0.30, 0.26)
OIL = (0.12, 0.11, 0.10)
SHEETS = [(0.47, 0.30, 0.20), (0.52, 0.53, 0.52), (0.36, 0.42, 0.46), (0.55, 0.44, 0.30)]   # corrugated fence sheets
TYRE = (0.10, 0.10, 0.11)
CRUSHER = (0.60, 0.48, 0.16)
FENCE_IN = 0.12              # how far in from a junkyard's tiles' edge its fence stands
FENCE_H = 1.15               # how tall its sheets are (its posts stand a little higher)
JUNK_COLUMNS = (1.15, 3.05, 4.95, 6.85)   # where the stacks of cars stand in a junkyard: across...
JUNK_ROWS = (1.4, 3.4, 5.4)               # ...and front to back (its front, toward its crane, at z = 8)
JUNK_STACK = 5                            # how many cars high they're stacked
CRUSHER_SLOT, TYRE_SLOT = (0, 0), (3, 0)  # (column, row) of the old crusher, and of the tyres


def car(mb, x, y, z, yaw, color, rust, bottom=False):
    """A wrecked car, stripped of its wheels, standing on (x, y, z) and turned by yaw, its length
    along x: a body, a cabin with dark glass all round, and a patch of rust on its bonnet or
    boot (rust: which, and where across)."""
    c, s = math.cos(yaw), math.sin(yaw)

    def at(lx, lz):
        return x + lx * c + lz * s, z - lx * s + lz * c

    mb.box(x, y, z, CAR_L, CAR_BODY, CAR_W, color, yaw=yaw, bottom=bottom)
    cx, cz = at(-0.08, 0.0)
    mb.box(cx, y + CAR_BODY, cz, 0.78, CAR_CABIN, 0.64, GLASS, yaw=yaw, top=color, bottom=bottom)
    rx, rz = at(0.5 if rust % 2 else -0.56, (rust % 3 - 1) * 0.12)
    mb.box(rx, y + CAR_BODY, rz, 0.3, 0.01, 0.3, RUST, yaw=yaw + 0.2 * (rust % 3 - 1))


def junkyard_stacks(seed):
    """The stacks of cars in a junkyard, in the order its crane takes them (the front row
    first, the nearest its crane first): (x, z, cars), the cars from the bottom up, each
    (dx, dz, yaw, colour, rust), its yard's own (from its seed)."""
    stacks = []
    for col, x in enumerate(JUNK_COLUMNS):
        for row, z in enumerate(JUNK_ROWS):
            if (col, row) in (CRUSHER_SLOT, TYRE_SLOT):
                continue
            cars = []
            for level in range(JUNK_STACK):
                h = [hash01(col * 7 + level, row * 5 + level, seed + k) for k in range(5)]
                cars.append(((h[0] - 0.5) * 0.08, (h[1] - 0.5) * 0.06, (h[2] - 0.5) * 0.06,
                             CAR_COLORS[int(h[3] * len(CAR_COLORS)) % len(CAR_COLORS)], int(h[4] * 6)))
            stacks.append((x, z, cars))
    crane_x = 4.5                             # (its crane stands in the middle of its front)
    return sorted(stacks, key=lambda s: (-s[1], abs(s[0] - crane_x)))


def junkyard_cars(seed):
    """Every car in a junkyard in the order its crane lifts them out: (x, y, z, yaw, colour,
    rust), each the top one of the first stack that still has any."""
    out = []
    for x, z, cars in junkyard_stacks(seed):
        for level in reversed(range(JUNK_STACK)):
            dx, dz, yaw, color, rust = cars[level]
            out.append((x + dx, level * CAR_H, z + dz, yaw, color, rust))
    return out


def build_junkyard(seed, cars_left):
    """A junkyard on 8 by 8 tiles, its corner at the origin, its front (where its salvage crane
    goes) facing +Z: a fence of mismatched corrugated sheets on posts, a gate in its west
    side, a floor of oily dirt, and the wrecks in it: stacks of cars five high (the last
    `cars_left` of them, the rest lifted out from the front), an old broken crusher, piles of
    tyres and a few drums. Everything is inside its tiles, inside the fence."""
    w = d = 8
    mb = MeshBuilder()
    e = FENCE_IN
    mb.box(w / 2, 0, d / 2, w - 2 * e - 0.04, 0.015, d - 2 * e - 0.04, YARD_DIRT)
    for k in range(7):                                                   # oil stains on the dirt
        h = [hash01(k, 3, seed + n) for n in range(3)]
        mb.box(1.0 + h[0] * 6.0, 0.015, 1.0 + h[1] * 6.0, 0.4 + h[2] * 0.5, 0.004, 0.3 + h[2] * 0.4, OIL,
               yaw=h[2] * 3.0)

    # the fence: a post every sheet, the sheets ribbed on the outside, a gate in the west side
    n = 8
    span = (w - 2 * e) / n
    for side, (ox, oz, ux, uz) in enumerate(((e, e, 1, 0), (e, d - e, 1, 0), (e, e, 0, 1), (w - e, e, 0, 1))):
        out = (0, -1) if side == 0 else (0, 1) if side == 1 else (-1, 0) if side == 2 else (1, 0)
        for k in range(n):
            mx, mz = ox + ux * span * (k + 0.5), oz + uz * span * (k + 0.5)
            gate = side == 2 and k in (3, 4)
            color = SHEETS[int(hash01(side, k, seed) * len(SHEETS)) % len(SHEETS)]
            along_x = ux == 1
            if gate:                                                      # a gate leaf: a steel frame round the sheet
                mb.box(mx, 0.02, mz, 0.05, FENCE_H - 0.02, span - 0.02, shade(color, 0.9))
                for y in (0.06, FENCE_H - 0.06):
                    mb.box(mx + out[0] * 0.035, y, mz, 0.02, 0.05, span - 0.04, STEEL_DARK)
                mb.box(mx + out[0] * 0.035, 0.06, mz, 0.02, FENCE_H - 0.12, 0.05, STEEL_DARK)
                continue
            mb.box(mx, 0.0, mz, span - 0.02 if along_x else 0.04, FENCE_H, 0.04 if along_x else span - 0.02, color)
            for r in (-1, 0, 1):                                          # its ribs, outside
                rx = mx + (ux * r * span * 0.3) + out[0] * 0.026
                rz = mz + (uz * r * span * 0.3) + out[1] * 0.026
                mb.box(rx, 0.0, rz, 0.04 if along_x else 0.012, FENCE_H, 0.012 if along_x else 0.04, shade(color, 0.8))
        for k in range(n + 1):                                            # the posts
            px, pz = ox + ux * span * k, oz + uz * span * k
            tall = 1.42 if side == 2 and k in (3, 5) else 1.25            # (the gate's posts stand higher)
            mb.box(px, 0.0, pz, 0.07, tall, 0.07, STEEL_DARK)

    # the old crusher, broken down in the back corner, two flattened cars on it
    cx, cz = JUNK_COLUMNS[CRUSHER_SLOT[0]], JUNK_ROWS[CRUSHER_SLOT[1]]
    mb.box(cx + 0.15, 0.0, cz, 1.2, 0.5, 0.66, CRUSHER, top=shade(CRUSHER, 0.6))
    mb.box(cx - 0.6, 0.0, cz, 0.32, 0.82, 0.66, shade(CRUSHER, 0.85))      # its ram, at one end
    for dz in (-0.2, 0.2):
        mb.box(cx - 0.2, 0.5, cz + dz, 0.5, 0.08, 0.08, STEEL)             # the ram's cylinders
    for k, color in enumerate((CAR_COLORS[1], CAR_COLORS[4])):
        mb.box(cx + 0.2, 0.5 + k * 0.09, cz, 1.0, 0.09, 0.58, color, yaw=0.05 * (k * 2 - 1))

    # tyres in piles, in the other back corner
    tx, tz = JUNK_COLUMNS[TYRE_SLOT[0]], JUNK_ROWS[TYRE_SLOT[1]]
    for k, (dx, dz, count) in enumerate(((-0.42, -0.12, 4), (0.05, 0.14, 3), (0.48, -0.08, 5))):
        for level in range(count):
            octagon(mb, tx + dx, level * 0.11, tz + dz, 0.2, 0.11, TYRE if level % 2 else shade(TYRE, 1.3))

    # a few drums by the front fence
    for k, (x, z, color) in enumerate(((0.55, 7.35, (0.22, 0.32, 0.50)), (0.86, 7.4, RUST), (7.4, 7.3, (0.55, 0.16, 0.12)))):
        octagon(mb, x, 0.0, z, 0.13, 0.38, color)
        octagon(mb, x, 0.38, z, 0.1, 0.02, shade(color, 0.7))

    # the cars still in it
    cars = junkyard_cars(seed)
    for x, y, z, yaw, color, rust in cars[len(cars) - cars_left:]:
        car(mb, x, y, z, yaw, color, rust)
    return mb


def build_car(color):
    """A wrecked car hanging from a crane's magnet: its roof at the origin, the rest below."""
    mb = MeshBuilder()
    car(mb, 0.0, -CAR_H, 0.0, 0.0, color, 1, bottom=True)
    return mb


CLAD = (0.66, 0.67, 0.63)            # a warehouse's corrugated steel walls
ROOF_STEEL = (0.42, 0.44, 0.45)
SKYLIGHT = (0.62, 0.72, 0.76)
RUBBER = (0.08, 0.08, 0.08)
CARDBOARD = (0.66, 0.52, 0.34)
SACKS = (0.78, 0.74, 0.62)
WATER = (0.45, 0.62, 0.78)
WAREHOUSE_DOORS = (1.6, 4.5, 6.9)    # where its three loading doors are along its front (the middle one at its spot)
DOOR_W, DOCK_H = 1.2, 0.35           # a door's width; how high its loading dock stands (a truck's bed)
DOCK_PALLETS = (3.59, 5.42, 3.06, 5.97, 2.53, 0.65)   # pallets on its dock, the ones nearest the middle door first


def pallet(mb, x, y, z, goods):
    """A pallet of stock on (x, y, z): boxes, sacks or packs of water, two layers of four."""
    mb.box(x, y, z, 0.5, 0.07, 0.5, PLANK)
    color = (CARDBOARD, SACKS, WATER)[goods % 3]
    for layer in range(2):
        for dx in (-0.12, 0.12):
            for dz in (-0.12, 0.12):
                mb.box(x + dx, y + 0.07 + layer * 0.2, z + dz, 0.22, 0.2, 0.22, shade(color, 0.93 + 0.07 * layer))


def build_warehouse(seed, pallets, doors_open):
    """A warehouse on 8 by 6 tiles, its corner at the origin, its front facing +Z: a big shed
    of ribbed steel on a concrete plinth, skylights in its roof, and along its front a loading
    dock with three roll-up doors (each open or shut, as `doors_open` says: dark inside when
    open), rubber bumpers at the dock's edge, and the first `pallets` pallets of its stock on
    the dock. Everything is inside its tiles."""
    w, d = 8, 6
    mb = MeshBuilder()
    mb.box(w / 2, 0, d / 2, w - 0.06, 0.06, d - 0.06, HQ_CONCRETE_DARK)
    left, right, back, front, wall = 0.15, w - 0.15, 0.15, 4.65, 1.9
    hx, hz = (left + right) / 2, (back + 4.45) / 2
    mb.box(hx, 0.06, hz, right - left, wall, 4.45 - back, CLAD, top=ROOF_STEEL)      # the shed
    mb.box(hx, 0.06, hz, right - left + 0.02, 0.3, 4.45 - back + 0.02, HQ_CONCRETE)  # its plinth
    for k in range(3):                                                               # skylights down its roof
        mb.box(hx, 0.06 + wall, back + 0.8 + k * 1.25, right - left - 0.8, 0.02, 0.45, SKYLIGHT)
    for x in (left + 1.2, right - 1.6):                                              # roof vents
        mb.box(x, 0.06 + wall, back + 3.6, 0.3, 0.16, 0.3, STEEL_DARK)

    # its ribbed walls: the back and the ends; the front between the doors, with a lintel over each
    rib = shade(CLAD, 0.86)
    for k in range(25):
        x = left + 0.15 + k * (right - left - 0.3) / 24
        mb.box(x, 0.36, back - 0.012, 0.05, wall - 0.3, 0.024, rib)
    for k in range(14):
        z = back + 0.15 + k * (4.45 - back - 0.3) / 13
        for x in (left - 0.012, right + 0.012):
            mb.box(x, 0.36, z, 0.024, wall - 0.3, 0.05, rib)
    edges = [left] + [v for x in WAREHOUSE_DOORS for v in (x - DOOR_W / 2, x + DOOR_W / 2)] + [right]
    for a, b in zip(edges[0::2], edges[1::2]):                                       # wall between doors
        mb.box((a + b) / 2, 0.06, (4.45 + front) / 2, b - a, wall, front - 4.45, CLAD, top=ROOF_STEEL)
        for k in range(int((b - a) / 0.3)):
            mb.box(a + 0.15 + k * 0.3, DOCK_H + 0.05, front + 0.012, 0.05, wall - DOCK_H - 0.05, 0.024, rib)
    for x, is_open in zip(WAREHOUSE_DOORS, doors_open):
        top = DOCK_H + 1.35
        mb.box(x, top, (4.45 + front) / 2, DOOR_W, 0.06 + wall - top, front - 4.45, CLAD, top=ROOF_STEEL)   # lintel
        mb.box(x, top, front + 0.06, DOOR_W + 0.1, 0.14, 0.12, STEEL_DARK)          # the roll the door goes up into
        mb.box(x, top + 0.14, front + 0.05, 0.16, 0.06, 0.1, LAMP)                   # a lamp over it
        mb.box(x, DOCK_H, 4.45 + 0.005, DOOR_W, top - DOCK_H, 0.01, DOORWAY)         # inside, dark
        if not is_open:                                                              # the door, rolled down
            mb.box(x, DOCK_H, front - 0.05, DOOR_W - 0.02, top - DOCK_H, 0.06, STEEL)
            for k in range(10):
                mb.box(x, DOCK_H + 0.05 + k * 0.13, front - 0.015, DOOR_W - 0.02, 0.025, 0.01, STEEL_DARK)
    for x in (left + 0.05, right - 0.05):                                            # downpipes at its front corners
        mb.box(x, 0.06, front + 0.04, 0.06, wall, 0.06, STEEL_DARK)

    # the loading dock along its front: concrete, a steel edge, rubber bumpers below each door
    mb.box(hx, 0.06, (front + d - 0.1) / 2, right - left - 0.3, DOCK_H - 0.06, d - 0.1 - front, HQ_CONCRETE)
    mb.box(hx, DOCK_H - 0.04, d - 0.115, right - left - 0.3, 0.04, 0.03, STEEL)
    for x in WAREHOUSE_DOORS:
        for dx in (-0.4, 0.4):
            mb.box(x + dx, 0.1, d - 0.05, 0.18, 0.2, 0.1, RUBBER)
    for slot, x in enumerate(DOCK_PALLETS):                                          # (those nearest the middle door go first)
        if slot >= len(DOCK_PALLETS) - pallets:
            pallet(mb, x, DOCK_H, 4.95, int(hash01(slot, 1, seed) * 3))
    return mb


# A salvage crane, in its building spot's frame (3 by 3, +Z away from the junkyard, which is at z < 0)
CRANE_YELLOW = (0.86, 0.66, 0.12)
BALER_GREEN = (0.34, 0.40, 0.34)
MAGNET_GREY = (0.22, 0.22, 0.23)
CRANE_PIVOT = (1.5, 1.2)             # the middle of its turntable: its works turn round it
CRANE_DECK = 0.38                    # the top of its turntable
BOOM_FOOT = (0.0, 0.95, 0.4)         # where its boom is pinned, on its works (across, up, forward)
BOOM, STICK = 4.6, 4.3               # its arm: the boom, from its works, and the stick, hanging from the boom's end
CHAIN, MAGNET_H = 0.45, 0.12         # the chain from the stick's end down to its magnet, and the magnet
BALER = (0.6, 2.18, 2.4, 2.98)       # its baler, x0, z0, x1, z1: an open steel box a car is dropped into...
BALER_H = 0.62                       # ...this high
BALER_MIDDLE = ((BALER[0] + BALER[2]) / 2, (BALER[1] + BALER[3]) / 2)


def crane_arm(magnet):
    """Where a salvage crane's arm is with the bottom of its magnet at `magnet` (x, y, z, in its
    spot's frame): (slew, foot, elbow, tip): how far its works are turned (0: facing +Z),
    where its boom is pinned, where boom and stick meet (above the line from foot to tip, as a
    crane's arm bends), and the stick's end, from which the magnet hangs."""
    px, pz = CRANE_PIVOT
    slew = math.atan2(magnet[0] - px, magnet[2] - pz)
    across, up, forward = BOOM_FOOT
    s, c = math.sin(slew), math.cos(slew)
    foot = (px + forward * s + across * c, up, pz + forward * c - across * s)
    tip = (magnet[0], magnet[1] + CHAIN + MAGNET_H, magnet[2])
    return slew, foot, mathx.elbow(foot, tip, BOOM, STICK, (0.0, 1.0, 0.0)), tip


def build_crane_base(team):
    """What of a salvage crane doesn't move: its tracks and turntable, its baler (an open steel
    box with a ram at one end, crushed metal in the bottom), and a pallet of crushed blocks."""
    mb = MeshBuilder()
    px, pz = CRANE_PIVOT
    for sx in (-1, 1):                                                    # tracks, along z
        x = px + sx * 0.42
        mb.box(x, 0.0, pz, 0.3, 0.3, 1.4, STEEL_DARK, top=TYRE)
        for z in (pz - 0.62, pz + 0.62):                                  # the wheels at their ends
            mb.box(x + sx * 0.155, 0.06, z, 0.01, 0.18, 0.16, STEEL)
    mb.box(px, 0.1, pz, 0.56, 0.2, 0.7, STEEL_DARK)                       # the frame between them
    octagon(mb, px, 0.3, pz, 0.36, CRANE_DECK - 0.3, STEEL)               # the turntable
    x0, z0, x1, z1 = BALER
    bx, bz = BALER_MIDDLE
    mb.box(bx, 0.0, bz, x1 - x0, 0.06, z1 - z0, STEEL_DARK)               # the baler's floor...
    for z in (z0 + 0.01, z1 - 0.01):                                      # ...its sides...
        mb.box(bx, 0.06, z, x1 - x0, BALER_H - 0.06, 0.02, BALER_GREEN)
    mb.box(x0 + 0.01, 0.06, bz, 0.02, BALER_H - 0.06, z1 - z0 - 0.04, BALER_GREEN)
    mb.box(x1 + 0.17, 0.0, bz, 0.34, 0.78, 0.6, shade(BALER_GREEN, 0.8))  # ...the ram's housing, at its east end...
    mb.box(x1 + 0.17, 0.78, bz, 0.12, 0.08, 0.4, STEEL)                   # ...its cylinder...
    mb.box(x1 - 0.06, 0.06, bz, 0.1, 0.5, z1 - z0 - 0.06, STEEL)          # ...and the ram's plate, inside
    mb.box(bx - 0.3, 0.06, bz, 0.7, 0.16, 0.6, shade(RUST, 0.8))          # crushed metal in the bottom
    mb.box(x0 + 0.3, BALER_H, z0 + 0.01, 0.3, 0.02, 0.025, team)          # the team's mark on its rim
    mb.box(2.7, 0.0, 0.5, 0.5, 0.06, 0.55, PLANK)                         # a pallet of crushed blocks
    for k, (dx, dz) in enumerate(((-0.12, -0.13), (0.12, -0.13), (-0.12, 0.13), (0.12, 0.13))):
        mb.box(2.7 + dx, 0.06, 0.5 + dz, 0.22, 0.22, 0.22, shade(CAR_COLORS[k + 1], 0.7))
    mb.box(2.7, 0.28, 0.5, 0.22, 0.2, 0.22, shade(CAR_COLORS[0], 0.7))
    return mb


def build_crane_works(team):
    """The part of a salvage crane that turns on its turntable, about the origin (its middle),
    facing +Z: a deck, the engine house at the back with its counterweight, the cab raised on
    a post at the front left (glass all round, the team's colour on its back), and the boom's
    pin between two plates at the front."""
    mb = MeshBuilder()
    d = CRANE_DECK
    mb.box(0.0, d, -0.1, 0.9, 0.08, 1.4, shade(CRANE_YELLOW, 0.85))       # deck
    mb.box(0.0, d + 0.08, -0.47, 0.88, 0.4, 0.62, CRANE_YELLOW)           # engine house
    mb.box(0.0, d + 0.08, -0.77, 0.88, 0.36, 0.04, STEEL_DARK)            # counterweight, at its back
    for sx in (-1, 1):
        mb.box(sx * 0.445, d + 0.2, -0.5, 0.01, 0.14, 0.4, STEEL_DARK)     # grilles
    mb.box(0.25, d + 0.48, -0.3, 0.05, 0.2, 0.05, STEEL_DARK)              # exhaust
    mb.box(-0.29, d + 0.08, 0.3, 0.3, 0.32, 0.3, STEEL_DARK)              # the cab's post
    mb.box(-0.29, d + 0.4, 0.33, 0.33, 0.12, 0.47, CRANE_YELLOW)          # the cab
    mb.box(-0.29, d + 0.52, 0.33, 0.32, 0.34, 0.46, GLASS, top=CRANE_YELLOW)
    mb.box(-0.29, d + 0.62, 0.095, 0.3, 0.07, 0.01, team)
    for sx in (-1, 1):                                                    # the boom's pin plates
        mb.box(sx * 0.1, d + 0.08, BOOM_FOOT[2], 0.04, BOOM_FOOT[1] + 0.07 - d - 0.08, 0.3, STEEL_DARK)
    return mb


def build_crane_boom():
    """A salvage crane's boom, hanging down -Y from its pin (see mathx.bone), with the rod of
    the ram that lifts it along one side."""
    mb = MeshBuilder()
    mb.box(0.0, -BOOM, 0.0, 0.18, BOOM, 0.22, CRANE_YELLOW, bottom=True)
    mb.box(0.0, -BOOM * 0.75, 0.13, 0.06, BOOM * 0.55, 0.06, STEEL, bottom=True)
    mb.box(0.0, -BOOM - 0.04, 0.0, 0.22, 0.12, 0.24, STEEL_DARK, bottom=True)   # the pin at its end
    return mb


def build_crane_stick():
    """A salvage crane's stick, hanging down -Y from where it's pinned to the boom."""
    mb = MeshBuilder()
    mb.box(0.0, -STICK, 0.0, 0.14, STICK, 0.17, CRANE_YELLOW, bottom=True)
    mb.box(0.0, -STICK, 0.0, 0.18, 0.12, 0.2, STEEL_DARK, bottom=True)
    return mb


def build_magnet():
    """A crane's magnet on its chain, hanging from the origin (the stick's end)."""
    mb = MeshBuilder()
    mb.box(0.0, -CHAIN, 0.0, 0.04, CHAIN, 0.04, STEEL_DARK, bottom=True)
    octagon(mb, 0.0, -CHAIN - MAGNET_H, 0.0, 0.3, MAGNET_H, MAGNET_GREY, bottom=True)
    octagon(mb, 0.0, -CHAIN - 0.02, 0.0, 0.08, 0.02, STEEL_DARK)
    return mb


# A loading dock post, in its building spot's frame (+Z away from the warehouse, whose dock edge is at z = 0)
TRUCK_WHITE = (0.84, 0.85, 0.82)
TRUCK_X = 1.5                        # the middle of the truck, backed up to the warehouse's middle door
CRATE_SPOTS = ((0.6, 0.65), (0.6, 1.3), (0.6, 1.95))   # where crates pile up, by the truck


def sandbag_wall(mb, a, b, layers=3):
    """A wall of sandbags along a line from a to b (both (x, z), straight along x or z), the
    bags of each layer over the joins of the one below."""
    length = math.dist(a, b)
    n = max(1, round(length / 0.27))
    bag = length / n
    ux, uz = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    for layer in range(layers):
        starts = [k * bag for k in range(n)] if layer % 2 == 0 else [0.0] + [(k + 0.5) * bag for k in range(n)]
        ends = starts[1:] + [length]
        for s, e in zip(starts, ends):
            m = (s + e) / 2
            span = e - s - 0.01
            mb.box(a[0] + ux * m, layer * 0.11, a[1] + uz * m, span if ux else 0.2, 0.11, 0.2 if ux else span,
                   shade(SANDBAG, 0.94 + 0.06 * ((layer + round(m / bag)) % 2)))


def build_loading_dock(team):
    """A loading dock post: a box truck backed up to the warehouse's dock (its back doors
    swung open), its cab in the team's colour; a forklift beside it; sandbags round three
    sides (a gap in front for the truck); and a floodlight on a pole."""
    mb = MeshBuilder()
    x = TRUCK_X
    for z in (0.46, 2.11):                                                 # wheels
        for sx in (-1, 1):
            mb.box(x + sx * 0.405, 0.0, z, 0.14, 0.36, 0.32, TYRE)
    mb.box(x, 0.2, 1.24, 0.7, 0.12, 2.32, STEEL_DARK)                      # chassis
    mb.box(x, 0.32, 0.86, 0.95, 1.13, 1.72, TRUCK_WHITE, top=shade(TRUCK_WHITE, 0.92))   # the box, its back on the dock
    for sx in (-1, 1):
        mb.box(x + sx * 0.48, 0.85, 0.86, 0.01, 0.1, 1.6, team)            # a stripe down each side
        mb.box(x + sx * 0.495, 0.36, 0.23, 0.02, 1.06, 0.46, shade(TRUCK_WHITE, 0.95))   # its back doors, swung open
        mb.box(x + sx * 0.47, 0.85, 2.3, 0.04, 0.14, 0.06, STEEL_DARK)     # mirrors
        mb.box(x + sx * 0.33, 0.52, 2.435, 0.12, 0.07, 0.01, LAMP)         # headlights
    mb.box(x, 0.32, 2.1, 0.9, 0.42, 0.66, team)                            # the cab
    mb.box(x, 0.74, 2.08, 0.9, 0.36, 0.6, GLASS, top=team)
    mb.box(x, 0.22, 2.46, 0.92, 0.12, 0.06, STEEL_DARK)                    # bumper

    fx = 2.375                                                             # the forklift, its forks to the warehouse
    for wx in (2.17, 2.58):
        for wz in (0.62, 1.05):
            mb.box(wx, 0.0, wz, 0.08, 0.16, 0.16, TYRE)
    mb.box(fx, 0.08, 0.84, 0.4, 0.3, 0.6, HAZARD)
    mb.box(fx, 0.08, 1.17, 0.4, 0.32, 0.06, STEEL_DARK)                    # counterweight
    mb.box(fx, 0.38, 0.92, 0.2, 0.1, 0.2, LEATHER)                         # seat
    mb.box(fx, 0.48, 1.0, 0.2, 0.16, 0.04, LEATHER)
    for gx in (2.2, 2.55):                                                 # the guard over the driver
        for gz in (0.62, 1.1):
            mb.box(gx, 0.38, gz, 0.03, 0.5, 0.03, STEEL_DARK)
    mb.box(fx, 0.88, 0.86, 0.4, 0.03, 0.52, STEEL_DARK)
    for mx in (2.24, 2.51):                                                # the mast, the carriage and the forks
        mb.box(mx, 0.08, 0.51, 0.04, 0.9, 0.06, STEEL_DARK)
    mb.box(fx, 0.12, 0.465, 0.36, 0.22, 0.03, STEEL_DARK)
    for kx in (2.29, 2.46):
        mb.box(kx, 0.12, 0.27, 0.05, 0.03, 0.36, STEEL)

    sandbag_wall(mb, (0.14, 0.3), (0.14, 2.97))                            # sandbags round three sides
    sandbag_wall(mb, (2.86, 0.3), (2.86, 2.97))
    sandbag_wall(mb, (0.25, 2.86), (0.85, 2.86))
    sandbag_wall(mb, (2.15, 2.86), (2.75, 2.86))

    lx, lz = 2.45, 2.45                                                    # the floodlight, aimed at the truck's back
    mb.box(lx, 0.0, lz, 0.2, 0.03, 0.2, STEEL_DARK)
    mb.box(lx, 0.03, lz, 0.06, 2.2, 0.06, STEEL_DARK)
    mb.box(lx, 2.18, lz, 0.4, 0.05, 0.05, STEEL_DARK)
    for sx in (-1, 1):
        mb.box(lx + sx * 0.15, 2.1, lz - 0.075, 0.14, 0.14, 0.1, STEEL_DARK)
        mb.box(lx + sx * 0.15, 2.11, lz - 0.13, 0.12, 0.12, 0.01, LAMP)
    return mb


def build_crate_stack():
    """A pallet of wooden crates, its middle at the origin: a load waiting to go."""
    mb = MeshBuilder()
    mb.box(0.0, 0.0, 0.0, 0.5, 0.07, 0.5, PLANK)
    for k, (dx, dz) in enumerate(((-0.12, -0.12), (0.12, -0.12), (-0.12, 0.12), (0.12, 0.12))):
        mb.box(dx, 0.07, dz, 0.22, 0.2, 0.22, shade(PLANK, 1.15 - 0.05 * k))
        mb.box(dx, 0.15, dz, 0.23, 0.03, 0.23, shade(PLANK, 0.7))
    mb.box(0.0, 0.27, 0.0, 0.22, 0.2, 0.22, shade(PLANK, 1.2))
    mb.box(0.0, 0.35, 0.0, 0.23, 0.03, 0.23, shade(PLANK, 0.7))
    return mb


# ---------------------------------------------------------------- the radar station
DISH_WHITE = (0.84, 0.85, 0.86)
RADAR_GREY = (0.52, 0.53, 0.55)
CABLE_YELLOW = (0.86, 0.70, 0.18)
RADAR_MIDDLE = (3.0, 3.0)            # the middle of its deck, on 6 by 6 tiles
RADAR_DECK = 0.24                    # how high its deck stands
PEDESTAL_R, PEDESTAL_TOP = 0.95, 1.6  # its pedestal: its corners from its middle, and its top
DISH_AXLE = 0.85                     # how high over the pedestal's top the dish's axle is
DISH_TILT = 0.85                     # how far the dish is tipped back from facing straight up (radians)
DISH_R, DISH_FOCUS = 2.3, 1.5        # the dish's rim, from its middle, and how far over it its feed is
DISH_HUB = 0.35                      # how far out from its axle the dish's middle is
DISH_RINGS = 6


def dish_height(r):
    """How high the dish's face is, r from its middle (in its own frame, over its axle)."""
    return DISH_HUB + r * r / (4 * DISH_FOCUS)


def build_radar_base(team):
    """What of a radar station doesn't turn, its corner at the origin, its front facing +Z: an
    eight-sided concrete deck with a railing round it and steps up at the front; a pedestal in
    its middle with a door and a band of the team's colour; four lamp posts with globes; a
    small control hut; and a yellow cable run on the deck, from the hut and the steps to the
    pedestal. Everything is inside its tiles, and low enough for the dish to turn over."""
    mb = MeshBuilder()
    cx, cz = RADAR_MIDDLE
    deck = RADAR_DECK
    octagon(mb, cx, 0.0, cz, 2.95, deck - 0.02, HQ_CONCRETE_DARK)                 # the deck
    octagon(mb, cx, deck - 0.02, cz, 2.8, 0.02, HQ_CONCRETE)
    edge = 2.7                                                                    # its railing, at the deck's corners
    corners = [(cx + edge * math.sin(k * math.pi / 4 + math.pi / 8), cz + edge * math.cos(k * math.pi / 4 + math.pi / 8))
               for k in range(8)]
    for k, (x, z) in enumerate(corners):
        mb.box(x, deck, z, 0.06, 0.45, 0.06, STEEL_DARK)
        nx, nz = corners[(k + 1) % 8]
        if k == 7:                                                               # (the front: open for the steps)
            continue
        length = math.dist((x, z), (nx, nz))
        yaw = math.atan2(nx - x, nz - z)
        for y in (deck + 0.2, deck + 0.4):
            mb.box((x + nx) / 2, y, (z + nz) / 2, 0.03, 0.03, length, STEEL, yaw=yaw)
    front = cz + 2.95 * math.cos(math.pi / 8)                                   # steps up at the front
    mb.box(cx, 0.0, front + 0.06, 1.0, deck - 0.02, 0.12, HQ_CONCRETE)            # the upper step, against the deck
    mb.box(cx, 0.0, front + 0.18, 1.0, 0.11, 0.12, HQ_CONCRETE)                   # and the lower one

    octagon(mb, cx, deck, cz, PEDESTAL_R, PEDESTAL_TOP - deck, RADAR_GREY)        # the pedestal
    octagon(mb, cx, PEDESTAL_TOP - 0.22, cz, PEDESTAL_R + 0.02, 0.08, team)
    face = cz + PEDESTAL_R * math.cos(math.pi / 8)
    mb.box(cx, deck, face + 0.005, 0.4, 0.62, 0.01, DOORWAY)                      # its door, at the front
    mb.box(cx, deck + 0.64, face + 0.01, 0.12, 0.05, 0.02, LAMP)

    for k in range(4):                                                            # lamp posts with globes
        a = math.pi / 4 + k * math.pi / 2
        x, z = cx + 2.45 * math.sin(a), cz + 2.45 * math.cos(a)
        mb.box(x, deck, z, 0.16, 0.04, 0.16, STEEL_DARK)
        mb.box(x, deck + 0.04, z, 0.05, 0.86, 0.05, STEEL_DARK)
        octagon(mb, x, deck + 0.9, z, 0.13, 0.22, LAMP)

    hx, hz = cx - 1.7, cz - 0.2                                                   # the control hut
    mb.box(hx, deck, hz, 0.7, 0.62, 0.9, RADAR_GREY, top=ROOF_TAR)
    mb.box(hx + 0.355, deck + 0.05, hz, 0.01, 0.5, 0.3, DOORWAY)
    mb.box(hx, deck + 0.38, hz + 0.455, 0.4, 0.14, 0.01, GLASS)
    mb.box(hx - 0.2, deck + 0.62, hz, 0.06, 0.25, 0.06, STEEL_DARK)              # an aerial on its roof

    side = cx - PEDESTAL_R * math.cos(math.pi / 8)                               # cable runs, yellow, on the deck
    mb.box((hx + 0.35 + side) / 2, deck, hz, side - hx - 0.35, 0.015, 0.08, CABLE_YELLOW)
    mb.box(cx + 0.35, deck, (face + front) / 2, 0.08, 0.015, front - face - 0.15, CABLE_YELLOW)
    return mb


def build_radar_mount(team):
    """The part of a radar station that turns on its pedestal, about the origin (the top of the
    pedestal, in its middle): a turntable, and a yoke of two arms holding the dish's axle."""
    mb = MeshBuilder()
    octagon(mb, 0.0, 0.0, 0.0, 0.8, 0.12, STEEL)
    for sx in (-1, 1):
        mb.box(sx * 0.42, 0.12, 0.0, 0.12, DISH_AXLE, 0.3, RADAR_GREY)
    mb.box(0.0, DISH_AXLE - 0.06, 0.0, 0.96, 0.12, 0.12, STEEL_DARK)              # the axle
    mb.box(0.0, 0.12, -0.3, 0.5, 0.3, 0.3, team)                                  # the drive, behind
    return mb


def build_radar_dish():
    """A radar station's dish, facing +Y from its axle at the origin: a hub out from the axle,
    then a bowl of DISH_RINGS rings of white panels, each ring a step up from the one inside
    it (boxes don't bend), the panels of each reaching down to the ring inside so the bowl is
    whole; a post up its middle to the feed at its focus."""
    mb = MeshBuilder()
    mb.box(0.0, -0.06, 0.0, 0.5, DISH_HUB + 0.06, 0.5, RADAR_GREY, bottom=True)    # the hub, round the axle
    step = DISH_R / DISH_RINGS
    octagon(mb, 0.0, DISH_HUB, 0.0, step * 1.05, 0.06, DISH_WHITE, bottom=True)
    for k in range(1, DISH_RINGS):
        r0, r1 = k * step, (k + 1) * step
        mid = (r0 + r1) / 2
        bottom, top = dish_height(r0) - 0.02, dish_height(r1) + 0.03
        n = max(8, round(2 * math.pi * mid / 0.45))
        for s in range(n):
            a = 2 * math.pi * (s + 0.5) / n
            mb.box(mid * math.sin(a), bottom, mid * math.cos(a), 2 * math.pi * r1 / n + 0.01, top - bottom, r1 - r0,
                   DISH_WHITE if s % 2 else shade(DISH_WHITE, 0.94), yaw=a, bottom=True)
    feed = DISH_HUB + DISH_FOCUS
    mb.box(0.0, DISH_HUB + 0.06, 0.0, 0.08, feed - DISH_HUB - 0.06, 0.08, STEEL_DARK, bottom=True)
    mb.box(0.0, feed, 0.0, 0.3, 0.22, 0.3, RADAR_GREY, bottom=True)
    return mb


# ---------------------------------------------------------------- the tank, and the vehicle factory

TANK_OLIVE = (0.36, 0.39, 0.26)
TANK_OLIVE_DARK = (0.27, 0.30, 0.20)
TRACK = (0.15, 0.15, 0.15)
TRACK_INSIDE = (0.09, 0.09, 0.09)
ROAD_WHEEL = (0.25, 0.26, 0.23)
TRACK_X = 0.825                      # how far out from a tank's middle each track runs
TRACK_PITCH = 0.25                   # how far apart the cleats on a track are
TURRET_RING_Z = -0.1                 # (as tanks.Tank.TURRET_AT: where the turret turns, forward of the hull's middle)


def plate(mb, x, a, b, w, t, color):
    """A flat plate w wide (across x) and t thick, from a to b ((y, z) each, the middle of its
    ends) at x: a sloped plate, which a box (upright, turned only about the upright) can't be."""
    (ya, za), (yb, zb) = a, b
    part = MeshBuilder()
    part.box(0, -t / 2, 0, w, t, math.hypot(yb - ya, zb - za), color)
    mb.add(part, mathx.chain(mathx.translate(x, (ya + yb) / 2, (za + zb) / 2), mathx.rot_x(math.atan2(-(yb - ya), zb - za))))


def wheel(mb, x, y, z, r, t, color):
    """An eight-sided wheel turning about the x axis, its middle at (x, y, z), t thick."""
    part = MeshBuilder()
    octagon(part, 0, -t / 2, 0, r, t, color, bottom=True)
    mb.add(part, mathx.chain(mathx.translate(x, y, z), mathx.rot_z(-math.pi / 2)))


def build_tank_hull(team):
    """A tank's hull on its tracks, its middle at the origin, facing +Z, inside 2.1 by 3.4
    (tanks.Tank.WIDTH and LENGTH). Each track is a loop: a run along the ground, a run along
    the top, and sloped ends between them, with five road wheels inside it, a drive sprocket
    at the back and an idler at the front (their outer faces flush with the hull's side).
    Between the tracks, the hull (the tracks' top runs bare beside it, so they show running),
    with a sloped plate at the front, the engine deck's grilles at the back, two exhausts, and
    two headlights on brackets. The turret turns on
    the ring on top (build_tank_turret). The cleats on the tracks' top runs are drawn apart,
    so they can run (build_track_links)."""
    mb = MeshBuilder()
    for s in (-1, 1):
        x = s * TRACK_X
        mb.box(x, 0.0, 0.0, 0.45, 0.07, 2.5, TRACK)                         # along the ground
        mb.box(x, 0.53, 0.0, 0.45, 0.07, 3.1, TRACK)                        # along the top
        plate(mb, x, (0.035, 1.25), (0.565, 1.6), 0.45, 0.07, TRACK)        # round the front...
        plate(mb, x, (0.035, -1.25), (0.565, -1.6), 0.45, 0.07, TRACK)      # ...and the back
        mb.box(s * 0.7875, 0.07, 0.0, 0.285, 0.46, 2.5, TRACK_INSIDE)        # (the dark inside of the loop, behind the wheels)
        wx = s * 0.985                                                      # the wheels' middles: outer faces at 1.03
        for z in (-1.0, -0.5, 0.0, 0.5, 1.0):
            wheel(mb, wx, 0.28, z, 0.2, 0.09, ROAD_WHEEL)
            wheel(mb, s * 1.04, 0.28, z, 0.08, 0.02, TANK_OLIVE_DARK)        # its hub
        wheel(mb, wx, 0.36, -1.3, 0.15, 0.09, STEEL_DARK)                   # drive sprocket
        wheel(mb, wx, 0.36, 1.3, 0.14, 0.09, ROAD_WHEEL)                    # idler
    mb.box(0, 0.12, 0, 1.2, 0.48, 3.1, TANK_OLIVE_DARK)                      # the lower hull, between the tracks
    mb.box(0, 0.6, -0.15, 1.3, 0.35, 2.7, TANK_OLIVE)                        # the upper hull, on the lower
    for k, (z, top) in enumerate(((1.27, 0.88), (1.39, 0.79), (1.51, 0.71))):   # under the sloped front plate...
        mb.box(0, 0.6, z, 1.28, top - 0.6, 0.12, TANK_OLIVE_DARK)
    plate(mb, 0, (0.95, 1.2), (0.64, 1.62), 1.3, 0.05, TANK_OLIVE)           # ...the plate itself
    mb.box(0, 0.12, -1.54, 1.2, 0.83, 0.08, TANK_OLIVE_DARK)                 # the back plate
    for k in range(5):                                                       # the engine deck's grilles
        mb.box(0, 0.95, -1.35 + k * 0.13, 1.0, 0.015, 0.06, STEEL_DARK)
    for s in (-1, 1):
        mb.box(s * 0.4, 0.5, -1.62, 0.18, 0.12, 0.08, GUNMETAL)              # exhausts
        mb.box(s * 0.69, 0.68, 1.1, 0.08, 0.03, 0.05, STEEL_DARK)            # headlights, on brackets off the hull
        mb.box(s * 0.76, 0.66, 1.1, 0.12, 0.1, 0.12, STEEL_DARK)
        mb.box(s * 0.76, 0.67, 1.165, 0.09, 0.07, 0.01, LAMP)
        mb.box(s * 0.35, 0.3, 1.66, 0.1, 0.1, 0.06, STEEL_DARK)              # tow hooks
    octagon(mb, 0, 0.95, TURRET_RING_Z, 0.62, 0.05, TANK_OLIVE_DARK)         # the turret ring
    mb.box(0, 0.95, 1.05, 0.5, 0.012, 0.18, team)                            # a stripe of the team's colour
    return mb


def build_track_links():
    """The cleats on a track's top run, every TRACK_PITCH: drawn on each track, moved along
    by how far it has run (less than a pitch), so the track runs. They stay on its top run
    however far they're moved."""
    mb = MeshBuilder()
    k = 0
    while -1.5 + k * TRACK_PITCH + TRACK_PITCH <= 1.5:
        mb.box(0, 0.6, -1.5 + k * TRACK_PITCH, 0.45, 0.025, 0.07, STEEL_DARK)
        k += 1
    return mb


def build_tank_turret(team):
    """A tank's turret, its middle (where it turns) at the origin, the ground at y = 0, facing
    +Z: a flat-topped steel box with its front corners angled, a mantlet in front for the
    gun (build_tank_gun), a bustle at the back with a stowage rack, smoke launchers, the
    commander's cupola and the loader's hatch on its roof, an aerial, and a square of the
    team's colour on each side. All of it within 1.05 of its middle (save the aerial, high
    up), so as it turns it stays over the hull."""
    mb = MeshBuilder()
    mb.box(0, 1.0, -0.05, 1.3, 0.58, 1.3, TANK_OLIVE)                        # the turret
    for s in (-1, 1):
        mb.box(s * 0.38, 1.0, 0.62, 0.45, 0.56, 0.3, TANK_OLIVE, yaw=-s * 0.45)   # its angled cheeks
        mb.box(s * 0.656, 1.2, -0.05, 0.012, 0.2, 0.36, team)                # the team's square
        for k in range(3):                                                   # smoke launchers
            mb.box(s * (0.5 + 0.06 * k), 1.38, 0.38, 0.05, 0.05, 0.14, STEEL_DARK)
    mb.box(0, 1.58, -0.05, 1.22, 0.04, 1.22, TANK_OLIVE_DARK)                # the roof
    mb.box(0, 1.32, 0.78, 0.5, 0.36, 0.22, TANK_OLIVE_DARK)                  # the mantlet
    mb.box(0, 1.08, -0.82, 0.9, 0.45, 0.25, TANK_OLIVE)                      # the bustle...
    for k in range(4):                                                       # ...its stowage rack
        mb.box(-0.36 + k * 0.24, 1.53, -0.88, 0.03, 0.12, 0.03, STEEL_DARK)
    mb.box(0, 1.63, -0.88, 0.78, 0.025, 0.03, STEEL_DARK)
    octagon(mb, 0.38, 1.62, -0.3, 0.17, 0.12, TANK_OLIVE_DARK)               # the commander's cupola...
    for k in range(4):                                                       # ...its vision blocks
        a = k * math.pi / 2 + math.pi / 4
        mb.box(0.38 + math.sin(a) * 0.15, 1.65, -0.3 + math.cos(a) * 0.15, 0.06, 0.04, 0.03, GLASS, yaw=a)
    mb.box(-0.38, 1.62, -0.3, 0.32, 0.03, 0.32, TANK_OLIVE_DARK)              # the loader's hatch
    mb.box(0.42, 1.53, -0.9, 0.02, 0.95, 0.02, GUNMETAL)                      # the aerial, on the bustle (clear of the guns)
    return mb


def build_tank_gun():
    """A tank's main gun, from the mantlet out: its barrel along +Z, its middle 1.5 up
    (tanks.Tank.GUN_HEIGHT: over anyone's head), with a fume extractor along it and a muzzle
    brake at its end (the muzzle at z = 2.55, tanks.Tank.MUZZLE). Its origin is the turret's middle."""
    mb = MeshBuilder()
    mb.box(0, 1.45, 1.6, 0.1, 0.1, 1.5, GUNMETAL)                            # the barrel, 0.85 to 2.35
    mb.box(0, 1.435, 1.55, 0.15, 0.13, 0.3, GUNMETAL)                        # the fume extractor
    mb.box(0, 1.43, 2.45, 0.17, 0.14, 0.2, STEEL_DARK)                       # the muzzle brake
    return mb


def build_tank_mg(foot, height, reach):
    """A machine gun on its post, the post's foot at (0, foot, 0) (the roof under it), its
    barrel `height` up and pointing +Z, the muzzle `reach` in front of the post: a receiver,
    a barrel with a cooling jacket, a box of ammunition at its side and a small shield."""
    mb = MeshBuilder()
    mb.box(0, foot, 0, 0.06, height - 0.05 - foot, 0.06, STEEL_DARK)          # the post
    mb.box(0, height - 0.05, 0.02, 0.08, 0.1, 0.3, GUNMETAL)                 # the receiver
    mb.box(0, height - 0.02, (0.17 + reach) / 2, 0.035, 0.035, reach - 0.17, GUNMETAL)   # the barrel
    mb.box(0, height - 0.03, 0.26, 0.05, 0.05, 0.12, STEEL_DARK)              # its cooling jacket
    mb.box(0.075, height - 0.07, -0.02, 0.07, 0.09, 0.14, AMMO_GREEN)         # the ammunition box
    mb.box(0, height - 0.06, 0.16, 0.2, 0.14, 0.015, TANK_OLIVE_DARK)         # the shield
    return mb


def build_vehicle_factory(team, w=7, d=5):
    """A vehicle factory on w by d tiles, its corner at the origin, its door facing +Z: a
    tall shed of corrugated steel on a slab, with a low-pitched roof, a door wide and tall
    enough for a tank (its roller door rolled up into the drum over it), the team's sign
    beside the door; a lower concrete workshop along its side, a fuel tank on saddles in front
    of that, and spare road wheels stacked flat behind it. Everything on the slab and inside
    its tiles, the shed's walls a little in from their edge, so the dead at its tiles stand at its walls."""
    mb = MeshBuilder()
    slab_h = 0.1
    mb.box(w / 2, 0, d / 2, w - 0.1, slab_h, d - 0.1, HQ_CONCRETE_DARK)
    # the shed: walls of corrugated steel, ribbed, and a pitched roof over them
    x0, x1, z0, z1, eaves, ridge = 0.12, 5.28, 0.12, 4.88, 2.3, 2.75
    hx, hz = (x0 + x1) / 2, (z0 + z1) / 2
    mb.box(hx, slab_h, hz, x1 - x0, eaves - slab_h, z1 - z0, CLAD)
    for k in range(1, 13):                                                    # ribs along the sides
        x = x0 + k * (x1 - x0) / 13
        for z in (z0 - 0.01, z1 + 0.01):
            if not (z > hz and (abs(x - 2.7) < 1.55 or abs(x - 4.72) < 0.45)):   # (none over the door, or the sign)
                mb.box(x, 0.3, z, 0.04, eaves - 0.3, 0.02, shade(CLAD, 0.85))
    for k in range(1, 10):
        z = z0 + k * (z1 - z0) / 10
        for x in (x0 - 0.01, x1 + 0.01):
            mb.box(x, 0.3, z, 0.02, eaves - 0.3, 0.04, shade(CLAD, 0.85))
    rise = ridge - eaves
    for s in (-1, 1):                                                         # the roof's two slopes, front and back
        plate(mb, hx, (eaves, hz + s * (hz - z0 + 0.08)), (ridge, hz), x1 - x0 + 0.2, 0.06, ROOF_STEEL)
    run, y = hz - z0 + 0.08, eaves                                           # the gables under it, each end: steps,
    for k in range(8):                                                        # each as high as the roof over its ends
        half = (hz - z0) * (8 - k) / 8
        top = eaves + rise * (1 - half / run) - 0.04
        for x in (x0 + 0.02, x1 - 0.02):
            mb.box(x, y, hz, 0.04, top - y, 2 * half, CLAD)
        y = top
    mb.box(hx, ridge - 0.02, hz, x1 - x0 + 0.2, 0.06, 0.16, STEEL_DARK)       # the ridge cap
    # the door: dark inside, a hazard-striped frame, the roller door rolled up in its drum over it
    dx, door_w, door_h = 2.7, 2.8, 2.1
    mb.box(dx, slab_h, z1 + 0.005, door_w, door_h - slab_h, 0.02, DOORWAY)
    for s in (-1, 1):
        mb.box(dx + s * (door_w / 2 + 0.06), slab_h, z1 + 0.02, 0.12, door_h - slab_h + 0.05, 0.05, HAZARD)
    mb.box(dx, door_h, z1 + 0.05, door_w + 0.24, 0.2, 0.1, STEEL)              # the drum
    mb.box(dx, slab_h, z1 + 0.04, door_w, 0.03, 0.08, STEEL_DARK)              # the sill
    # the team's sign on the wall beside the door: a tank, side on
    sx, sy, sz = 4.72, 1.3, z1 + 0.015
    mb.box(sx, sy, sz, 0.8, 0.36, 0.03, team)
    mb.box(sx, sy + 0.06, sz + 0.02, 0.48, 0.09, 0.01, TANK_OLIVE_DARK)       # its tracks...
    mb.box(sx, sy + 0.15, sz + 0.02, 0.38, 0.07, 0.01, TANK_OLIVE)            # ...hull...
    mb.box(sx - 0.03, sy + 0.22, sz + 0.02, 0.2, 0.06, 0.01, TANK_OLIVE)      # ...turret...
    mb.box(sx + 0.19, sy + 0.24, sz + 0.02, 0.26, 0.022, 0.01, GUNMETAL)      # ...and gun
    for x in (x0 + 0.5, x1 - 0.2):                                            # floodlights at the front corners
        mb.box(x, eaves - 0.25, z1 + 0.06, 0.16, 0.12, 0.1, STEEL_DARK)
        mb.box(x, eaves - 0.23, z1 + 0.115, 0.12, 0.08, 0.01, LAMP)
    # the workshop along its side: concrete, a flat roof, a door and a window
    wx0, wx1, wz0, wz1, wh = x1, w - 0.12, 0.7, 4.2, 1.45
    mb.box((wx0 + wx1) / 2, slab_h, (wz0 + wz1) / 2, wx1 - wx0, wh - slab_h, wz1 - wz0, HQ_CONCRETE)
    mb.box((wx0 + wx1) / 2, wh, (wz0 + wz1) / 2, wx1 - wx0 + 0.06, 0.06, wz1 - wz0 + 0.06, ROOF_TAR)
    mb.box(wx1 + 0.005, slab_h, 3.2, 0.01, 0.9, 0.5, STEEL_DARK)               # its door...
    mb.box(wx1 + 0.005, 0.6, 1.6, 0.01, 0.4, 0.8, GLASS)                      # ...and window
    # a fuel tank on saddles in front of the workshop
    fx, fz = (wx0 + wx1) / 2 + 0.1, 4.6
    for dz in (-0.15, 0.15):
        mb.box(fx, slab_h, fz + dz, 0.6, 0.12, 0.08, HQ_CONCRETE)
    octagon(mb, fx, slab_h + 0.12, fz, 0.22, 0.55, TANK)
    octagon(mb, fx, slab_h + 0.67, fz, 0.16, 0.05, STEEL)
    # spare road wheels stacked flat behind the workshop
    for k in range(4):
        octagon(mb, (wx0 + wx1) / 2, slab_h + k * 0.09, 0.35, 0.2, 0.09, ROAD_WHEEL)
    return mb


# ---------------------------------------------------------------- colours the people share

SKIN = (0.86, 0.68, 0.54)
GUNMETAL = (0.18, 0.19, 0.20)


# ---------------------------------------------------------------- the soldier

OLIVE = (0.33, 0.36, 0.23)
OLIVE_DARK = (0.25, 0.28, 0.18)
KHAKI = (0.47, 0.42, 0.30)
KHAKI_DARK = (0.38, 0.34, 0.24)
BOOT = (0.17, 0.13, 0.10)


SHOULDER_X = 0.22      # a soldier's or engineer's shoulders: how far out from his middle (his arms just clear his vest)...
SHOULDER_Z = 0.06      # ...and forward of it, as a man's are, so a gun's butt can rest in front of one
ELBOW = 0.19           # how far down the arm his elbow is...
FOREARM = 0.205        # ...and from it to the middle of his hand


def build_soldier():
    """A rifleman in plain olive fatigues, a khaki vest and an olive helmet, in parts (the
    shared skeleton: see the top; same joints, so they walk the same way). Returns (body, leg, arm)."""
    body = MeshBuilder()
    body.box(0, 0.36, 0, 0.33, 0.12, 0.20, OLIVE_DARK)                # hips
    body.box(0, 0.40, 0, 0.34, 0.06, 0.22, KHAKI_DARK)                # belt
    body.box(0, 0.46, 0, 0.30, 0.37, 0.19, OLIVE)                     # shirt
    body.box(0, 0.49, 0, 0.32, 0.31, 0.24, KHAKI)                     # vest
    for k in (-1, 1):
        body.box(k * 0.075, 0.50, 0.135, 0.10, 0.12, 0.035, KHAKI_DARK)  # vest pockets
    for side in (-1, 1):
        body.box(side * 0.10, 0.31, 0.10, 0.07, 0.12, 0.06, KHAKI_DARK)  # belt pouches, in front
    body.box(0, 0.83, 0, 0.11, 0.03, 0.11, SKIN)                      # neck
    body.box(0, 0.84, 0, 0.20, 0.20, 0.20, SKIN)                      # head
    for side in (-1, 1):
        body.box(side * 0.045, 0.925, 0.101, 0.035, 0.03, 0.005, (0.10, 0.09, 0.08))   # eyes
    body.box(0, 0.86, 0.101, 0.07, 0.015, 0.005, (0.55, 0.40, 0.32))  # mouth
    body.box(0, 0.97, -0.005, 0.25, 0.11, 0.25, OLIVE_DARK, top=OLIVE)  # helmet
    body.box(0, 0.965, 0.0, 0.27, 0.03, 0.27, OLIVE_DARK)             # its rim
    body.box(0, 0.50, -0.165, 0.22, 0.26, 0.08, KHAKI_DARK)           # pack
    body.box(0, 0.76, -0.16, 0.20, 0.06, 0.07, OLIVE_DARK)            # rolled blanket on it

    leg = MeshBuilder()
    leg.box(0, -0.42, 0, 0.13, 0.42, 0.15, OLIVE)                     # trousers
    leg.box(0.0, -0.20, 0.0, 0.135, 0.09, 0.155, OLIVE_DARK)          # thigh pocket
    leg.box(0, -0.42, 0.02, 0.145, 0.11, 0.19, BOOT)                  # boot

    return body, leg, build_arm(soldier_arm())


def soldier_arm():
    """A soldier's arm, as boxes (see build_arm): his sleeve and hand."""
    return [((0, -0.36, 0, 0.11, 0.36, 0.12), OLIVE),                  # sleeve
            ((0, -0.44, 0, 0.09, 0.09, 0.09), SKIN)]                   # hand


MAG_SEAT = (0.0, -0.04, 0.10)    # where a magazine's top goes into the rifle, in the rifle's frame
MAG_LENGTH = 0.11                # how long a magazine is, from its top down


def magazine(mb, x=0.0, y=0.0, z=0.0):
    """A rifle's curved magazine, its top's middle at (x, y, z), hanging down -Y and curving
    forward (+Z)."""
    black = (0.12, 0.12, 0.13)
    mb.box(x, y - 0.06, z, 0.034, 0.06, 0.05, black, bottom=True)
    mb.box(x, y - 0.11, z + 0.012, 0.032, 0.05, 0.048, black, bottom=True)


def build_magazine():
    """A magazine on its own (one being changed), its top at the origin."""
    mb = MeshBuilder()
    magazine(mb)
    return mb


def build_rifle(with_magazine=True):
    """The soldier's rifle, a modern one in black: an adjustable stock on a buffer tube, a
    pistol grip, a curved magazine (left out with `with_magazine` False, for one drawn on its
    own: build_magazine), a railed handguard round a short barrel, a flash hider, and a
    red-dot sight on the top rail. Held in his hands it lies along +Z from the pistol grip at
    the origin: the stock behind, the barrel's axis at y = 0, and its muzzle at RIFLE_MUZZLE.
    Nothing is wider than the stock, so it lies flat on its side when dropped."""
    mb = MeshBuilder()
    black, grey, rubber = (0.12, 0.12, 0.13), (0.24, 0.25, 0.26), (0.08, 0.08, 0.08)
    mb.box(0, -0.10, -0.205, 0.05, 0.12, 0.02, rubber)               # butt pad
    mb.box(0, -0.075, -0.14, 0.046, 0.095, 0.11, black)              # the stock, slid in short on...
    mb.box(0, -0.012, -0.05, 0.03, 0.036, 0.10, grey)                # ...its buffer tube
    mb.box(0, -0.04, 0.065, 0.042, 0.04, 0.15, black)                # lower receiver
    mb.box(0, 0.0, 0.075, 0.042, 0.032, 0.17, black)                 # upper receiver
    mb.box(0, 0.002, -0.02, 0.03, 0.02, 0.025, grey)                 # charging handle
    mb.box(0, -0.115, -0.005, 0.034, 0.08, 0.04, black)              # pistol grip
    mb.box(0, -0.067, 0.04, 0.012, 0.008, 0.05, grey)                # trigger guard
    if with_magazine:
        magazine(mb, *MAG_SEAT)
    mb.box(0, -0.032, 0.28, 0.046, 0.062, 0.24, black)               # handguard, round the barrel
    mb.box(0, 0.032, 0.175, 0.02, 0.008, 0.43, grey)                 # the top rail, along it all
    mb.box(0, 0.04, 0.07, 0.034, 0.042, 0.075, black)                # red-dot sight on the rail
    mb.box(0, 0.048, 0.1085, 0.026, 0.026, 0.002, (0.30, 0.42, 0.46))   # its front glass
    mb.box(0, -0.011, 0.46, 0.022, 0.022, 0.12, grey)                # barrel
    mb.box(0, -0.016, 0.415, 0.028, 0.034, 0.025, black)             # gas block
    mb.box(0, -0.014, 0.52, 0.028, 0.028, 0.04, black)               # flash hider (to 0.54)
    return mb


RIFLE_MUZZLE = (0.0, 0.0, 0.54)


class Hold(namedtuple("Hold", "grip front place carry_front carry carry_turn carry_tip lift")):
    """How a gun is held, two ways, in the frame of the way he faces (model units). The middle
    of his right hand on its grip, and of his left on its front: `front` raised, `carry_front`
    carried. His body is always square to the way he faces. Raised to fire, its grip is at
    `place`, the gun level, its sight in front of his right eye and its butt against the right
    of his chest. Carried as he walks or stands about, the gun is across his chest, its grip at
    `carry`, turned `carry_turn` (radians) so its muzzle points to his left, and tipped
    `carry_tip` down. Raised from one to the other, it goes up by as much as `lift` on the way
    (and out a little: main.RAISE_OUT), so its stock swings up over his right forearm and
    round in front of his chest, not through them."""
    __slots__ = ()


RIFLE_HOLD = Hold(grip=(0.0, -0.075, -0.005), front=(0.0, -0.06, 0.13), place=(-0.05, 0.80, 0.33),
                  carry_front=(0.0, -0.06, 0.17), carry=(-0.06, 0.70, 0.26), carry_turn=1.4, carry_tip=0.15,
                  lift=0.14)

ZOMBIE_SKIN = (0.58, 0.64, 0.50)
ZOMBIE_SHIRTS = [(0.52, 0.48, 0.42), (0.36, 0.42, 0.52), (0.55, 0.30, 0.26)]
ZOMBIE_TROUSERS = [(0.26, 0.28, 0.34), (0.34, 0.30, 0.24), (0.22, 0.22, 0.22)]
GORE = (0.36, 0.08, 0.07)


def build_zombie(variant):
    """A shambling dead man in torn clothes, in parts like a soldier (same joints). Three looks,
    by variant. Returns (body, leg, arm); the arms are drawn reaching forward."""
    shirt, trousers = ZOMBIE_SHIRTS[variant % 3], ZOMBIE_TROUSERS[variant % 3]
    torn = shade(shirt, 0.75)
    body = MeshBuilder()
    body.box(0, 0.36, 0, 0.34, 0.12, 0.20, trousers)                  # hips
    body.box(0, 0.46, 0, 0.36, 0.36, 0.20, shirt)                     # shirt
    body.box(0.06, 0.46, 0.0, 0.18, 0.10, 0.205, torn)                # its ragged hem
    body.box(-0.08, 0.60, 0.096, 0.12, 0.14, 0.01, GORE)              # old blood down the front
    body.box(0.10, 0.70, 0.096, 0.07, 0.06, 0.01, GORE)
    body.box(0.0, 0.58, -0.096, 0.16, 0.10, 0.01, ZOMBIE_SKIN)        # skin through a tear at the back
    body.box(0, 0.82, 0.01, 0.11, 0.04, 0.11, ZOMBIE_SKIN)            # neck
    body.box(0.02, 0.84, 0.03, 0.20, 0.20, 0.20, ZOMBIE_SKIN)         # head, hanging forward
    for side in (-1, 1):
        body.box(0.02 + side * 0.045, 0.93, 0.131, 0.04, 0.035, 0.005, (0.85, 0.80, 0.55))   # pale eyes
    body.box(0.02, 0.865, 0.131, 0.09, 0.03, 0.005, (0.20, 0.06, 0.05))   # open mouth
    body.box(0.02, 1.03, 0.02, 0.21, 0.02, 0.19, (0.16, 0.14, 0.12))  # what's left of the hair
    body.box(-0.07, 1.04, -0.03, 0.08, 0.02, 0.08, ZOMBIE_SKIN)       # a bald patch

    leg = MeshBuilder()
    leg.box(0, -0.42, 0, 0.13, 0.42, 0.15, trousers)
    leg.box(0, -0.28, 0.0, 0.135, 0.08, 0.155, shade(trousers, 0.7))  # a rip
    leg.box(0, -0.42, 0.02, 0.14, 0.09, 0.18, (0.20, 0.17, 0.14))     # shoe

    arm = MeshBuilder()
    arm.box(0, -0.30, 0, 0.11, 0.30, 0.12, shirt)                     # sleeve
    arm.box(0, -0.44, 0, 0.09, 0.14, 0.09, ZOMBIE_SKIN)               # bare forearm and hand
    arm.box(0, -0.40, 0.046, 0.06, 0.05, 0.005, GORE)
    return body, leg, arm


ACID = (0.56, 0.95, 0.18)
ACID_DARK = (0.30, 0.55, 0.10)
BLOATED_SKIN = (0.50, 0.60, 0.34)


def build_spitter():
    """A swollen zombie with a sac of acid at its throat and sores that glow, in parts like the
    others (same joints). Returns (body, leg, arm)."""
    rags, trousers = (0.34, 0.36, 0.26), (0.20, 0.22, 0.17)
    body = MeshBuilder()
    body.box(0, 0.36, 0, 0.36, 0.12, 0.24, trousers)                  # hips
    body.box(0, 0.46, 0.01, 0.42, 0.34, 0.34, BLOATED_SKIN)           # the swollen belly, clear of the arms
    body.box(0, 0.46, 0.01, 0.43, 0.10, 0.35, rags)                   # what's left of a shirt
    for x, y, z in ((-0.13, 0.66, 0.18), (0.14, 0.60, 0.18), (0.04, 0.72, 0.18)):
        body.box(x, y, z, 0.07, 0.07, 0.02, ACID)                     # sores on the belly
    body.box(0, 0.80, 0.02, 0.17, 0.05, 0.17, BLOATED_SKIN)           # neck
    body.box(0.0, 0.76, 0.14, 0.17, 0.13, 0.12, ACID_DARK, top=ACID)  # the sac at its throat
    body.box(0.0, 0.85, 0.03, 0.21, 0.20, 0.21, BLOATED_SKIN)         # head
    for side in (-1, 1):
        body.box(side * 0.05, 0.96, 0.14, 0.04, 0.035, 0.005, ACID)   # glowing eyes
    body.box(0.0, 0.87, 0.14, 0.11, 0.05, 0.005, ACID)                # the mouth it spits from

    leg = MeshBuilder()
    leg.box(0, -0.42, 0, 0.14, 0.42, 0.16, trousers)
    leg.box(0, -0.42, 0.02, 0.15, 0.09, 0.19, (0.17, 0.15, 0.12))     # shoe

    arm = MeshBuilder()
    arm.box(0, -0.30, 0, 0.11, 0.30, 0.12, rags)                      # sleeve
    arm.box(0, -0.44, 0, 0.09, 0.14, 0.09, BLOATED_SKIN)              # forearm and hand
    return body, leg, arm


def build_acid():
    """A glob of acid, centred on the origin."""
    mb = MeshBuilder()
    mb.box(0, -0.09, 0, 0.18, 0.18, 0.18, ACID, bottom=True)
    mb.box(0, -0.06, 0, 0.24, 0.12, 0.12, ACID_DARK, yaw=0.8, bottom=True)
    return mb


# ---------------------------------------------------------------- the trenches

EARTH = (0.30, 0.24, 0.17)
EARTH_DARK = (0.20, 0.16, 0.12)
RIM = 0.14             # how thick the earth wall left round a trench is, inside its tile
BANK = 0.08            # how high the earth is banked up on that wall
BAG_H = 0.06           # how high one sandbag is


def trench_wall(mb, x, z, along_x, outward, grow, finished):
    """One side of a trench: the earth wall from the floor up, the bank of earth thrown up on
    it, and, once the trench is finished, planks facing the wall and two rows of sandbags.
    (x, z) is the middle of the wall; `outward` is +1 or -1 along the axis across it."""
    w, d = (1.0, RIM) if along_x else (RIM, 1.0)
    bottom = -TRENCH_DEPTH - 0.06
    mb.box(x, bottom, z, w, BANK * grow - bottom, d, EARTH_DARK, top=EARTH)
    if not finished:
        return
    inner = -outward * (RIM / 2 + 0.008)
    px, pz = (x, z + inner) if along_x else (x + inner, z)
    for k in range(3):
        y = -TRENCH_DEPTH + 0.05 + k * 0.17
        tone = shade(PLANK, 0.75 + 0.1 * k)
        mb.box(px, y, pz, 0.98 if along_x else 0.016, 0.14, 0.016 if along_x else 0.98, tone)
    for row, spots in enumerate(((-0.3, 0.0, 0.3), (-0.15, 0.15))):
        for k, spot in enumerate(spots):
            bx, bz = (x + spot, z) if along_x else (x, z + spot)
            tone = 0.88 + 0.2 * hash01(int(x * 7) + k, int(z * 7) + row, 53)
            bag = shade(SANDBAG, tone)
            mb.box(bx, BANK + row * BAG_H, bz, 0.27 if along_x else 0.12, BAG_H, 0.12 if along_x else 0.27, bag)


def build_trenches(trenches):
    """All the trenches started so far, as one mesh in world positions. A trench takes up its
    whole tile: a floor, and on each side with no trench next to it, an earth wall."""
    mb = MeshBuilder()
    dug = {(t.i, t.j) for t in trenches}
    for t in trenches:
        grow = t.stage / t.STAGES
        h = TRENCH_DEPTH + 0.06 - t.depth
        mb.box(t.x, -TRENCH_DEPTH - 0.06, t.z, 1.0, h, 1.0, EARTH_DARK, top=shade(EARTH, 0.8))
        sides = (((t.i, t.j - 1), t.x, t.z - 0.5 + RIM / 2, True, -1),
                 ((t.i, t.j + 1), t.x, t.z + 0.5 - RIM / 2, True, 1),
                 ((t.i - 1, t.j), t.x - 0.5 + RIM / 2, t.z, False, -1),
                 ((t.i + 1, t.j), t.x + 0.5 - RIM / 2, t.z, False, 1))
        for neighbour, x, z, along_x, outward in sides:
            if neighbour not in dug:
                trench_wall(mb, x, z, along_x, outward, grow, t.built)
        if t.built:                                   # boards to stand on, across the way it runs
            runs_x = (t.i - 1, t.j) in dug or (t.i + 1, t.j) in dug
            for k in range(-2, 3):
                if runs_x:
                    mb.box(t.x + k * 0.19, -t.depth, t.z, 0.15, 0.03, 0.6, shade(PLANK, 0.8 + 0.05 * (k % 3)))
                else:
                    mb.box(t.x, -t.depth, t.z + k * 0.19, 0.6, 0.03, 0.15, shade(PLANK, 0.8 + 0.05 * (k % 3)))
    return mb


def build_trench_plan():
    """A trench laid out but not started: a flat plate over its tile, drawn see-through."""
    mb = MeshBuilder()
    mb.box(0, 0.0, 0, 0.94, 0.05, 0.94, (1.0, 1.0, 1.0))
    return mb


def build_shovel():
    """A soldier's shovel, held like the hammer: the handle along Y from the grip at the origin,
    the blade at the far end."""
    mb = MeshBuilder()
    mb.box(0, -0.25, 0, 0.03, 0.72, 0.03, (0.42, 0.30, 0.18))         # handle
    mb.box(0, 0.45, 0, 0.17, 0.22, 0.025, STEEL_DARK)                 # blade
    return mb


# ---------------------------------------------------------------- the engineer, and what he builds

HIVIS = (0.95, 0.48, 0.10)
REFLECTIVE = (0.86, 0.87, 0.84)
HARD_HAT = (0.96, 0.78, 0.14)
WORKWEAR = (0.24, 0.27, 0.32)
LEATHER = (0.36, 0.24, 0.14)
GLOVE = (0.62, 0.50, 0.32)


def build_engineer(team):
    """An engineer in dark workwear, an orange hi-vis vest with silver stripes, a yellow hard
    hat and a tool belt, in parts like a soldier (same joints). The team's colour is on the
    armbands and the hat's band. Returns (body, leg, arm)."""
    body = MeshBuilder()
    body.box(0, 0.36, 0, 0.33, 0.12, 0.20, WORKWEAR)                  # hips
    body.box(0, 0.40, 0, 0.34, 0.07, 0.23, LEATHER)                   # tool belt
    for side, w in ((-1, 0.07), (1, 0.06)):
        body.box(side * 0.11, 0.30, 0.08, w, 0.12, 0.06, shade(LEATHER, 0.85))   # its pouches
    body.box(0.07, 0.24, 0.125, 0.03, 0.16, 0.015, STEEL)             # a wrench hung on it
    body.box(0, 0.46, 0, 0.30, 0.37, 0.19, WORKWEAR)                  # shirt
    body.box(0, 0.48, 0, 0.32, 0.32, 0.225, HIVIS)                    # hi-vis vest
    for y in (0.54, 0.66):
        body.box(0, y, 0, 0.325, 0.03, 0.23, REFLECTIVE)              # its stripes, all round
    for side in (-1, 1):
        body.box(side * 0.10, 0.48, 0.0, 0.03, 0.32, 0.23, REFLECTIVE)   # and up over the shoulders
    body.box(0, 0.83, 0, 0.11, 0.03, 0.11, SKIN)                      # neck
    body.box(0, 0.84, 0, 0.20, 0.20, 0.20, SKIN)                      # head
    for side in (-1, 1):
        body.box(side * 0.045, 0.925, 0.101, 0.035, 0.03, 0.005, (0.10, 0.09, 0.08))   # eyes
    body.box(0, 0.86, 0.101, 0.07, 0.015, 0.005, (0.55, 0.40, 0.32))  # mouth
    body.box(0, 0.98, 0, 0.23, 0.10, 0.23, HARD_HAT)                  # hard hat
    body.box(0, 0.975, 0.03, 0.27, 0.02, 0.29, HARD_HAT)              # its brim, longer in front
    body.box(0, 1.08, 0, 0.05, 0.025, 0.21, shade(HARD_HAT, 1.08))    # the ridge on top
    body.box(0, 0.995, 0, 0.235, 0.025, 0.235, team)                  # hat band
    body.box(0, 0.48, -0.17, 0.24, 0.20, 0.10, (0.62, 0.15, 0.12), top=(0.70, 0.18, 0.14))   # tool bag

    leg = MeshBuilder()
    leg.box(0, -0.42, 0, 0.13, 0.42, 0.15, WORKWEAR)                  # trousers
    leg.box(0, -0.25, 0.02, 0.135, 0.08, 0.15, shade(WORKWEAR, 0.75))  # knee pad
    leg.box(0, -0.42, 0.02, 0.145, 0.11, 0.19, LEATHER)               # work boot

    return body, leg, build_arm(engineer_arm(team))


def engineer_arm(team):
    """An engineer's arm, as boxes (see build_arm): his sleeve, armband and glove."""
    return [((0, -0.36, 0, 0.11, 0.36, 0.12), WORKWEAR),               # sleeve
            ((0, -0.12, 0, 0.115, 0.045, 0.125), team),                # armband
            ((0, -0.44, 0, 0.09, 0.09, 0.09), GLOVE)]                  # glove


def build_arm(boxes):
    """An arm in one piece, hanging from the shoulder at the origin (as the dead have it):
    `boxes` is a list of ((x, y, z, w, h, d), colour), each standing on y."""
    mb = MeshBuilder()
    for args, color in boxes:
        mb.box(*args, color)
    return mb


def build_arm_halves(boxes):
    """The same arm in two pieces, bending at the elbow (ELBOW below the shoulder), for the
    living holding a gun: the upper arm hanging from the shoulder at its origin, and the
    forearm and hand hanging from the elbow at its origin. A box across the elbow is cut in two."""
    upper, lower = MeshBuilder(), MeshBuilder()
    for (x, y, z, w, h, d), color in boxes:
        if y >= -ELBOW:
            upper.box(x, y, z, w, h, d, color)
        elif y + h <= -ELBOW:
            lower.box(x, y + ELBOW, z, w, h, d, color)
        else:
            upper.box(x, -ELBOW, z, w, y + h + ELBOW, d, color)
            lower.box(x, y + ELBOW, z, w, -ELBOW - y, d, color)
    return upper, lower


def build_hammer():
    """A claw hammer for the engineer's right hand: the handle along -Y from the grip at the origin."""
    mb = MeshBuilder()
    mb.box(0, -0.02, 0, 0.03, 0.26, 0.03, (0.45, 0.32, 0.18))          # handle
    mb.box(0, 0.22, 0.0, 0.05, 0.05, 0.13, STEEL)                     # head
    return mb


def build_turret_base(team):
    """A turret's block, filling one tile (centred on the origin): a concrete plinth with the
    team's colour round it, an ammo box, and the steel post the gun turns on."""
    mb = MeshBuilder()
    mb.box(0, 0, 0, 0.92, 0.30, 0.92, HQ_CONCRETE_DARK, top=HQ_CONCRETE)
    mb.box(0, 0.18, 0, 0.935, 0.05, 0.935, team)                      # the team's band
    mb.box(0, 0.30, 0, 0.30, 0.45, 0.30, STEEL_DARK)                  # post
    mb.box(0.30, 0.30, -0.22, 0.20, 0.16, 0.30, (0.30, 0.34, 0.22), top=(0.36, 0.40, 0.26))   # ammo box
    mb.box(0.30, 0.46, -0.22, 0.06, 0.02, 0.10, STEEL)                # its latch
    return mb


def build_turret_head(team):
    """The part that turns: a gun with a shield in front, its barrel along +Z at TURRET height
    (y = 1.05, the muzzle at z = 0.78). Built centred on the post, so it's drawn turned about it."""
    mb = MeshBuilder()
    drab = (0.32, 0.35, 0.24)
    mb.box(0, 0.75, 0, 0.44, 0.06, 0.44, STEEL_DARK)                  # turntable
    mb.box(0, 0.81, 0.02, 0.26, 0.22, 0.50, GUNMETAL, top=shade(GUNMETAL, 1.2))   # gun body
    mb.box(0.16, 0.86, -0.02, 0.07, 0.10, 0.14, drab)                 # the feed from the box
    mb.box(0, 0.76, 0.33, 0.58, 0.38, 0.04, drab, top=shade(drab, 1.15))   # shield
    mb.box(0, 1.12, 0.33, 0.58, 0.03, 0.045, team)                    # the team's colour along it
    mb.box(0, 1.02, 0.52, 0.06, 0.06, 0.52, GUNMETAL)                 # barrel, from the body through the shield
    mb.box(0, 1.01, 0.76, 0.09, 0.08, 0.05, STEEL_DARK)               # muzzle brake
    mb.box(0, 1.03, -0.20, 0.05, 0.12, 0.05, STEEL_DARK)              # the handles at the back
    return mb


def build_minigun_turret_base(team):
    """A minigun turret's block, filling one tile (centred on the origin): a steel-plated plinth
    with the team's colour round it, warning marks at its corners, and a thick post."""
    mb = MeshBuilder()
    mb.box(0, 0, 0, 0.92, 0.30, 0.92, STEEL_DARK, top=shade(STEEL, 0.75))
    mb.box(0, 0.18, 0, 0.935, 0.05, 0.935, team)                      # the team's band
    for sx in (-1, 1):
        for sz in (-1, 1):
            mb.box(sx * 0.37, 0.30, sz * 0.37, 0.14, 0.012, 0.14, HAZARD)   # warning marks
    mb.box(0, 0.30, 0, 0.36, 0.45, 0.36, STEEL_DARK)                  # post
    return mb


MINIGUN_BARRELS = (0.0, 1.05, 0.24)    # where the turning barrels start on the head: y is the gun's height


def build_minigun_turret_head(team):
    """The part that turns: the gun's body and motor on a turntable, the ammunition box that
    feeds it, and a shield with a square opening the barrels fire through. The barrels are a mesh
    of their own (build_minigun_barrels), so they can turn."""
    mb = MeshBuilder()
    drab = (0.32, 0.35, 0.24)
    mb.box(0, 0.75, 0, 0.66, 0.06, 0.66, STEEL_DARK)                  # turntable
    mb.box(0, 0.81, -0.04, 0.16, 0.12, 0.30, STEEL_DARK)              # the cradle under the gun
    mb.box(0, 0.93, -0.04, 0.26, 0.24, 0.44, GUNMETAL, top=shade(GUNMETAL, 1.25))   # the gun's body
    mb.box(0, 0.97, -0.33, 0.16, 0.16, 0.14, STEEL_DARK)              # the motor behind it
    mb.box(0, 0.95, 0.21, 0.20, 0.20, 0.06, STEEL_DARK)               # the plate the barrels turn in
    mb.box(-0.24, 0.81, -0.04, 0.18, 0.24, 0.30, drab, top=shade(drab, 1.15))   # the ammunition box, on the left
    mb.box(-0.195, 1.05, -0.04, 0.13, 0.025, 0.08, STEEL)             # the belt from its lid into the gun
    # the shield stands on the turntable, in four pieces round the opening
    shield_z, top = 0.29, 1.30
    for side in (-1, 1):
        mb.box(side * 0.225, 0.81, shield_z, 0.21, top - 0.81, 0.04, drab, top=shade(drab, 1.15))
    mb.box(0, 0.81, shield_z, 0.24, 0.12, 0.04, drab)                 # under the opening
    mb.box(0, 1.17, shield_z, 0.24, top - 1.17, 0.04, drab, top=shade(drab, 1.15))   # over it
    mb.box(0, top, shield_z, 0.66, 0.03, 0.045, team)                 # the team's colour along it
    return mb


def build_minigun_barrels():
    """Six barrels round the Z axis, reaching 0.62 forward, held by two clamps. Built on the axis
    they turn about."""
    mb = MeshBuilder()
    for k in range(6):
        a = k * math.pi / 3
        mb.box(math.cos(a) * 0.055, math.sin(a) * 0.055 - 0.0125, 0.31, 0.025, 0.025, 0.62, STEEL, bottom=True)
    for z in (0.20, 0.56):
        mb.box(0, -0.08, z, 0.16, 0.16, 0.025, STEEL_DARK, bottom=True)
    return mb


def build_beam():
    """A tracer: a thin bright bar from z = 0 to z = 1, stretched and turned to where a shot went."""
    mb = MeshBuilder()
    mb.box(0, -0.012, 0.5, 0.024, 0.024, 1.0, (1.0, 1.0, 1.0), bottom=True)
    return mb


def build_dust():
    """A clod of dust kicked up by a shot that missed, centred on the origin."""
    mb = MeshBuilder()
    mb.box(0, -0.05, 0, 0.10, 0.10, 0.10, (0.56, 0.48, 0.37), bottom=True)
    mb.box(0, -0.03, 0, 0.13, 0.06, 0.07, (0.42, 0.35, 0.27), yaw=0.7, bottom=True)
    return mb


def build_fireball():
    """A shell's fireball, a rough ball about one tile across centred on the origin: three
    eight-sided drums, the middle one widest, yellow at the heart and orange round it."""
    mb = MeshBuilder()
    octagon(mb, 0, -0.25, 0, 0.5, 0.5, (1.0, 0.62, 0.18), bottom=True)
    octagon(mb, 0, 0.25, 0, 0.34, 0.22, (1.0, 0.80, 0.30), bottom=True)
    octagon(mb, 0, -0.47, 0, 0.34, 0.22, (0.95, 0.45, 0.12), bottom=True)
    return mb


def build_flag(team):
    """The rally point's flag: a thin pole with a pennant in the team's colour, standing on y = 0."""
    mb = MeshBuilder()
    mb.box(0, 0, 0, 0.05, 1.3, 0.05, (0.55, 0.56, 0.58))
    mb.box(0.24, 0.95, 0, 0.42, 0.28, 0.02, team)
    return mb


def build_ring():
    """A unit ring (radius 1), drawn scaled and tinted for selection and move markers."""
    mb = MeshBuilder()
    mb.ring(0, 0, 0, 0.80, 1.0, (1.0, 1.0, 1.0))
    return mb


def build_thin_ring():
    """A thin unit ring (radius 1), smooth enough to scale up big: a soldier's range."""
    mb = MeshBuilder()
    mb.ring(0, 0, 0, 0.988, 1.0, (1.0, 1.0, 1.0), segments=120)
    return mb


def build_disc():
    """A unit disc (radius 1), drawn dark and see-through as a soft shadow."""
    mb = MeshBuilder()
    mb.disc(0, 0, 0, 1.0, (1.0, 1.0, 1.0))
    return mb
