"""Builds the low-poly meshes: the bare ground, the HQ and the commander.

The look is a zombie apocalypse: dead grass, bare dirt, scorch marks and old
stains, a fortified concrete HQ, and a commander in black tactical gear.
"""
from gfx import MeshBuilder
from mathx import mix
from world import hash01, value_noise

# the ground
DEAD_GRASS_DARK = (0.27, 0.29, 0.19)
DEAD_GRASS = (0.40, 0.39, 0.25)
DRY_GRASS = (0.52, 0.47, 0.31)
DIRT = (0.36, 0.29, 0.21)
MUD = (0.23, 0.20, 0.16)
SCORCH = (0.13, 0.12, 0.11)
OLD_BLOOD = (0.30, 0.12, 0.10)
CONCRETE = (0.53, 0.52, 0.49)

ISLAND_DEPTH = 3.0


def shade(color, k):
    return tuple(min(1.0, c * k) for c in color)


def ramp(v, start, width):
    """0 below `start`, rising to 1 at `start + width`."""
    return min(1.0, max(0.0, (v - start) / width))


# ---------------------------------------------------------------- the map

def build_ground(world):
    """The ground tiles, and the dirt sides of the slab the map stands on."""
    mb = MeshBuilder()
    n, seed = world.size, world.seed

    def ground(x, z):
        col = mix(DEAD_GRASS_DARK, DEAD_GRASS, value_noise(x / 9, z / 9, seed + 1))
        col = mix(col, DRY_GRASS, ramp(value_noise(x / 5, z / 5, seed + 2), 0.55, 0.4))
        col = mix(col, DIRT, ramp(value_noise(x / 7, z / 7, seed + 3), 0.52, 0.25))
        col = mix(col, MUD, 0.8 * ramp(value_noise(x / 4, z / 4, seed + 4), 0.72, 0.15))
        col = mix(col, SCORCH, 0.9 * ramp(value_noise(x / 3.2, z / 3.2, seed + 8), 0.80, 0.12))
        col = mix(col, OLD_BLOOD, 0.75 * ramp(value_noise(x / 2.1, z / 2.1, seed + 11), 0.86, 0.08))
        return col

    corner = [[ground(i, j) for j in range(n + 1)] for i in range(n + 1)]
    for j in range(n):
        for i in range(n):
            if (i, j) in world.plaza:
                # cracked concrete slabs, some stained with oil or soot
                k = 1 + (hash01(i, j, seed + 5) - 0.5) * 0.16
                colors = shade(CONCRETE, k)
                stain = hash01(i, j, seed + 6)
                if stain > 0.88:
                    colors = mix(colors, SCORCH, 0.15 + (stain - 0.88) * 1.2)
            else:
                k = 1 + (hash01(i, j, seed + 3) - 0.5) * 0.06
                colors = [shade(corner[i][j], k), shade(corner[i + 1][j], k),
                          shade(corner[i + 1][j + 1], k), shade(corner[i][j + 1], k)]
            mb.quad((i, 0, j), (i + 1, 0, j), (i + 1, 0, j + 1), (i, 0, j + 1), (0, 1, 0), colors)

    # the sides of the slab, in bands, one strip per tile so the colour can vary
    bands = [(0.0, -0.25, (0.30, 0.29, 0.20)), (-0.25, -1.6, (0.35, 0.28, 0.20)),
             (-1.6, -ISLAND_DEPTH, (0.25, 0.22, 0.20))]
    for k in range(n):
        for top, bottom, color in bands:
            c = shade(color, 1 + (hash01(k, int(top * 10), seed + 6) - 0.5) * 0.1)
            mb.quad((k, top, 0), (k + 1, top, 0), (k + 1, bottom, 0), (k, bottom, 0), (0, 0, -1), c)
            mb.quad((k, top, n), (k, bottom, n), (k + 1, bottom, n), (k + 1, top, n), (0, 0, 1), c)
            mb.quad((0, top, k), (0, bottom, k), (0, bottom, k + 1), (0, top, k + 1), (-1, 0, 0), c)
            mb.quad((n, top, k), (n, top, k + 1), (n, bottom, k + 1), (n, bottom, k), (1, 0, 0), c)
    mb.quad((0, -ISLAND_DEPTH, 0), (0, -ISLAND_DEPTH, n), (n, -ISLAND_DEPTH, n), (n, -ISLAND_DEPTH, 0),
            (0, -1, 0), (0.22, 0.19, 0.17))
    return mb


# ---------------------------------------------------------------- the HQ

HQ_CONCRETE = (0.58, 0.57, 0.53)
HQ_CONCRETE_DARK = (0.44, 0.43, 0.40)
GRIME = (0.33, 0.31, 0.27)
ROOF_TAR = (0.20, 0.20, 0.20)
STEEL = (0.50, 0.52, 0.54)
STEEL_DARK = (0.22, 0.23, 0.24)
DOOR_GREEN = (0.24, 0.27, 0.21)
GLASS = (0.10, 0.13, 0.15)
PLANK = (0.45, 0.33, 0.21)
SANDBAG = (0.56, 0.50, 0.37)
LAMP = (1.0, 0.93, 0.70)
BEACON = (0.95, 0.15, 0.10)
HAZARD = (0.92, 0.72, 0.15)


def build_hq(hq, team):
    """A fortified one-storey concrete command post on its tiles, its door facing +Z.

    Everything stands on the slab and inside the HQ's tiles, so it never pokes
    into a tile someone can walk on.
    """
    mb = MeshBuilder()
    cx, cz = hq.i + hq.w / 2, hq.j + hq.d / 2
    light = shade(team, 1.3)

    slab_h = 0.12
    mb.box(cx, 0, cz, hq.w - 0.1, slab_h, hq.d - 0.1, HQ_CONCRETE_DARK)

    # the walls: one block, set back so there's room for the step and sandbags in front
    ww, wd, wh = hq.w - 0.6, hq.d - 0.8, 2.3
    wz = cz - 0.15
    fz = wz + wd / 2                      # the front face
    bz = wz - wd / 2                      # the back face
    roof = slab_h + wh
    mb.box(cx, slab_h, wz, ww, wh, wd, HQ_CONCRETE, top=ROOF_TAR)
    mb.box(cx, slab_h, wz, ww + 0.02, 0.32, wd + 0.02, GRIME)          # damp and dirt at the foot

    # parapet round the roof, with a cap
    ph, pt = 0.22, 0.14
    for z in (fz - pt / 2, bz + pt / 2):
        mb.box(cx, roof, z, ww, ph, pt, HQ_CONCRETE, top=HQ_CONCRETE_DARK)
    for side in (-1, 1):
        mb.box(cx + side * (ww / 2 - pt / 2), roof, wz, pt, ph, wd - 2 * pt, HQ_CONCRETE,
               top=HQ_CONCRETE_DARK)
    top = roof + ph

    # reinforced columns at the corners
    for sx in (-1, 1):
        for sz in (-1, 1):
            mb.box(cx + sx * ww / 2, slab_h, wz + sz * wd / 2, 0.26, top - slab_h + 0.04, 0.26,
                   HQ_CONCRETE_DARK)

    # the steel door, its frame, handle, a warning plate and the step
    mb.box(cx, slab_h, fz + 0.015, 1.1, 1.75, 0.03, STEEL_DARK)
    mb.box(cx, slab_h, fz + 0.04, 0.9, 1.62, 0.02, DOOR_GREEN)
    mb.box(cx + 0.32, 0.92, fz + 0.06, 0.05, 0.10, 0.02, STEEL)
    mb.box(cx, 1.30, fz + 0.055, 0.30, 0.20, 0.01, HAZARD)
    mb.box(cx, slab_h, fz + 0.2, 1.2, 0.08, 0.4, HQ_CONCRETE_DARK)

    # the HQ sign over the door, its letters in the team's colour
    sign_y, lz = 1.98, fz + 0.05
    mb.box(cx, sign_y, fz + 0.02, 1.1, 0.36, 0.04, (0.09, 0.09, 0.10))
    y0, hgt, t = sign_y + 0.05, 0.26, 0.05
    for x in (-0.30, -0.14):                                            # H
        mb.box(cx + x, y0, lz, t, hgt, 0.02, light)
    mb.box(cx - 0.22, y0 + hgt / 2 - t / 2, lz, 0.11, t, 0.02, light)
    for x in (0.12, 0.32):                                              # Q
        mb.box(cx + x, y0, lz, t, hgt, 0.02, light)
    for y in (y0, y0 + hgt - t):
        mb.box(cx + 0.22, y, lz, 0.15, t, 0.02, light)
    mb.box(cx + 0.33, y0 - 0.04, lz, 0.07, 0.07, 0.02, light)

    # front windows: one barred, one boarded up
    for side in (-1, 1):
        x = cx + side * 1.35
        mb.box(x, 1.0, fz + 0.01, 0.9, 0.5, 0.02, GLASS)
        mb.box(x, 0.94, fz + 0.05, 1.0, 0.06, 0.10, HQ_CONCRETE_DARK)    # sill
        if side < 0:
            for k in (-0.3, -0.1, 0.1, 0.3):
                mb.box(x + k, 0.98, fz + 0.035, 0.035, 0.54, 0.03, STEEL)
        else:
            for k, y in enumerate((1.04, 1.20, 1.36)):
                mb.box(x, y, fz + 0.035, 1.02, 0.11, 0.03, shade(PLANK, 0.9 + 0.1 * k),
                       yaw=0.04 * (k - 1))
    # slit windows in the sides
    for side in (-1, 1):
        mb.box(cx + side * (ww / 2 + 0.01), 1.25, wz - 0.3, 0.02, 0.25, 0.9, GLASS)

    # sandbags against the front wall, either side of the step, in staggered rows
    for side in (-1, 1):
        for row, (y, count, start) in enumerate(((slab_h, 4, 0.83), (slab_h + 0.15, 3, 1.005))):
            for k in range(count):
                x = cx + side * (start + k * 0.35)
                tone = 0.9 + 0.2 * hash01(int(x * 10), row, 31)
                mb.box(x, y, fz + 0.15, 0.33, 0.15, 0.28, shade(SANDBAG, tone),
                       yaw=(hash01(k, row + side, 37) - 0.5) * 0.08, top=shade(SANDBAG, tone * 1.06))

    # a ladder up the right side wall, on brackets
    lx, l0, l1 = cx + ww / 2 + 0.06, wz + 0.65, wz + 1.05
    for z in (l0, l1):
        mb.box(lx, slab_h, z, 0.04, top + 0.10 - slab_h, 0.04, STEEL_DARK)
        for y in (0.4, 2.2):
            mb.box(lx - 0.04, y, z, 0.05, 0.04, 0.04, STEEL_DARK)
    for k in range(8):
        mb.box(lx, 0.40 + 0.28 * k, (l0 + l1) / 2, 0.035, 0.03, l1 - l0, STEEL_DARK)

    # floodlights on the front corners of the parapet
    for side in (-1, 1):
        x = cx + side * (ww / 2 - 0.25)
        mb.box(x, top, fz - 0.075, 0.22, 0.15, 0.15, STEEL_DARK)
        mb.box(x, top + 0.025, fz + 0.005, 0.16, 0.10, 0.01, LAMP)

    # on the roof: a radio mast, a satellite dish, a generator, a hatch and the team flag
    mx, mz = cx - 1.7, bz + 0.40
    mb.box(mx, roof, mz, 0.30, 0.05, 0.30, STEEL_DARK)
    mb.box(mx, roof + 0.05, mz, 0.07, 2.6, 0.07, STEEL)
    for y in (roof + 1.0, roof + 1.8):
        mb.box(mx, y, mz, 0.34, 0.03, 0.03, STEEL)
    mb.box(mx, roof + 2.65, mz, 0.11, 0.11, 0.11, BEACON)

    dx, dz = cx + 1.4, bz + 0.70
    mb.box(dx, roof, dz, 0.08, 0.45, 0.08, STEEL_DARK)
    mb.cone(dx, roof + 0.63, dz, 0.42, -0.18, (0.74, 0.74, 0.72), sides=12)
    mb.box(dx, roof + 0.45, dz, 0.03, 0.42, 0.03, STEEL_DARK)
    mb.box(dx, roof + 0.85, dz, 0.07, 0.07, 0.07, STEEL_DARK)

    gx, gz = cx + 1.1, wz + 0.5
    mb.box(gx, roof, gz, 0.9, 0.5, 0.6, (0.38, 0.41, 0.35), top=(0.33, 0.36, 0.31))
    mb.disc(gx - 0.15, roof + 0.505, gz, 0.18, (0.08, 0.08, 0.08), segments=14)
    mb.box(gx + 0.32, roof + 0.5, gz - 0.18, 0.07, 0.25, 0.07, STEEL_DARK)   # exhaust

    mb.box(cx, roof, wz - 0.3, 0.6, 0.06, 0.6, STEEL_DARK)

    fx, fzz = cx - 1.6, wz + 0.9
    mb.box(fx, roof, fzz, 0.05, 1.6, 0.05, STEEL)
    mb.box(fx + 0.30, roof + 1.15, fzz, 0.55, 0.36, 0.02, team)
    mb.box(fx + 0.30, roof + 1.27, fzz, 0.55, 0.06, 0.025, light)
    return mb


# ---------------------------------------------------------------- the commander

SKIN = (0.86, 0.68, 0.54)
BLACK = (0.10, 0.10, 0.11)
CARRIER = (0.15, 0.15, 0.16)
POUCH = (0.20, 0.20, 0.21)
STRAP = (0.06, 0.06, 0.07)
GUNMETAL = (0.18, 0.19, 0.20)
LENS = (0.20, 0.55, 0.45)


def build_commander(team):
    """The commander in black tactical gear, in parts so the arms and legs can swing.

    Returns (body, leg, arm). The body stands on y = 0 and faces +Z. A leg hangs
    down from its hip at y = 0, an arm from its shoulder at y = 0. The team's
    colour is on the armbands, the chest and back patches and the helmet band.
    """
    light = shade(team, 1.3)

    body = MeshBuilder()
    body.box(0, 0.36, 0, 0.36, 0.12, 0.21, BLACK)                     # hips
    body.box(0, 0.40, 0, 0.38, 0.07, 0.23, STRAP)                     # belt
    body.box(0, 0.415, 0.116, 0.06, 0.045, 0.01, GUNMETAL)            # buckle
    for side in (-1, 1):
        body.box(side * 0.20, 0.33, 0.02, 0.05, 0.13, 0.10, POUCH)    # belt pouches
    body.box(0, 0.47, 0, 0.36, 0.36, 0.20, BLACK)                     # shirt
    body.box(0, 0.50, 0, 0.39, 0.30, 0.25, CARRIER)                   # plate carrier
    for side in (-1, 1):
        body.box(side * 0.12, 0.80, 0, 0.08, 0.03, 0.25, STRAP)       # shoulder straps
    for k in (-1, 0, 1):
        body.box(k * 0.095, 0.51, 0.14, 0.085, 0.13, 0.04, POUCH)    # magazine pouches
    body.box(0, 0.67, 0.128, 0.14, 0.08, 0.01, team)                  # chest patch
    body.box(-0.015, 0.73, -0.128, 0.12, 0.06, 0.01, team)            # back patch
    body.box(0, 0.83, 0, 0.12, 0.03, 0.12, BLACK)                     # neck
    body.box(0, 0.84, 0, 0.21, 0.21, 0.21, BLACK)                     # head, in a balaclava
    body.box(0, 0.905, 0.1, 0.16, 0.07, 0.02, SKIN)                   # the eye opening
    for side in (-1, 1):
        body.box(side * 0.045, 0.925, 0.111, 0.035, 0.03, 0.002, (0.08, 0.08, 0.10))   # eyes
    body.box(0, 0.98, -0.005, 0.25, 0.11, 0.24, GUNMETAL)             # helmet
    body.box(0, 0.98, -0.005, 0.255, 0.025, 0.245, team)              # helmet band
    for side in (-1, 1):
        body.box(side * 0.115, 0.90, -0.01, 0.03, 0.09, 0.14, GUNMETAL)  # ear protectors
    body.box(0, 1.00, 0.125, 0.07, 0.05, 0.02, STRAP)                 # night-vision mount
    body.box(0, 0.995, 0.140, 0.10, 0.03, 0.01, LENS)

    # on the back: a rifle on its sling (muzzle up past the shoulder) and a radio
    body.box(0.09, 0.38, -0.155, 0.05, 0.70, 0.05, GUNMETAL)          # rifle
    body.box(0.09, 0.38, -0.155, 0.06, 0.13, 0.06, STRAP)             # stock
    body.box(0.09, 0.56, -0.195, 0.04, 0.12, 0.04, STRAP)             # magazine
    body.box(-0.09, 0.52, -0.16, 0.11, 0.20, 0.06, POUCH)             # radio
    body.box(-0.12, 0.72, -0.16, 0.015, 0.36, 0.015, STRAP)           # radio antenna

    leg = MeshBuilder()
    leg.box(0, -0.42, 0, 0.13, 0.42, 0.15, BLACK)                     # trousers
    leg.box(0, -0.25, 0.02, 0.135, 0.08, 0.15, STRAP)                 # knee pad
    leg.box(0, -0.12, 0, 0.14, 0.035, 0.16, STRAP)                    # thigh strap
    leg.box(0, -0.42, 0.02, 0.145, 0.11, 0.19, STRAP, top=GUNMETAL)  # boot

    arm = MeshBuilder()
    arm.box(0, -0.36, 0, 0.11, 0.36, 0.12, BLACK)                     # sleeve
    arm.box(0, -0.12, 0, 0.115, 0.045, 0.125, team)                   # armband
    arm.box(0, -0.44, 0, 0.09, 0.09, 0.09, STRAP)                     # glove
    return body, leg, arm


def build_ring():
    """A unit ring (radius 1), drawn scaled and tinted for selection and move markers."""
    mb = MeshBuilder()
    mb.ring(0, 0, 0, 0.80, 1.0, (1.0, 1.0, 1.0))
    return mb


def build_disc():
    """A unit disc (radius 1), drawn dark and see-through as a soft shadow."""
    mb = MeshBuilder()
    mb.disc(0, 0, 0, 1.0, (1.0, 1.0, 1.0))
    return mb
