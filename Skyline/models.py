"""Builds the low-poly meshes: the HQ, the soldier and the engineer (and their
guns), the turret, the zombies, and the marks drawn on the ground.

Everything is made of boxes (and a cone or two) with a colour per face, built
in code: there are no model files. People share one skeleton: a body standing
on y = 0 facing +Z, legs hung from hips at y = 0.42 (x = +-0.1) and arms from
shoulders at y = 0.80 (x = +-0.29), so main.Game can swing them. The look is a
zombie apocalypse. (The ground isn't a mesh: gfx.GROUND_FS paints it.)
"""
from gfx import MeshBuilder
from world import hash01


def shade(color, k):
    return tuple(min(1.0, c * k) for c in color)


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


# ---------------------------------------------------------------- colours the people share

SKIN = (0.86, 0.68, 0.54)
GUNMETAL = (0.18, 0.19, 0.20)


# ---------------------------------------------------------------- the soldier

OLIVE = (0.33, 0.36, 0.23)
OLIVE_DARK = (0.25, 0.28, 0.18)
KHAKI = (0.47, 0.42, 0.30)
KHAKI_DARK = (0.38, 0.34, 0.24)
BOOT = (0.17, 0.13, 0.10)


def build_soldier(team):
    """A rifleman in olive fatigues and a khaki vest, in parts (the shared skeleton: see the top; same
    joints, so they walk the same way). The team's colour is on the armbands, the chest
    patch and the helmet band. Returns (body, leg, arm)."""
    body = MeshBuilder()
    body.box(0, 0.36, 0, 0.35, 0.12, 0.20, OLIVE_DARK)                # hips
    body.box(0, 0.40, 0, 0.37, 0.06, 0.22, KHAKI_DARK)                # belt
    body.box(0, 0.46, 0, 0.35, 0.37, 0.19, OLIVE)                     # shirt
    body.box(0, 0.49, 0, 0.38, 0.31, 0.24, KHAKI)                     # vest
    for k in (-1, 1):
        body.box(k * 0.09, 0.50, 0.135, 0.11, 0.12, 0.035, KHAKI_DARK)   # vest pockets
    body.box(0.10, 0.70, 0.123, 0.09, 0.06, 0.01, team)               # chest patch
    for side in (-1, 1):
        body.box(side * 0.19, 0.31, 0.03, 0.05, 0.12, 0.09, KHAKI_DARK)  # belt pouches
    body.box(0, 0.83, 0, 0.11, 0.03, 0.11, SKIN)                      # neck
    body.box(0, 0.84, 0, 0.20, 0.20, 0.20, SKIN)                      # head
    for side in (-1, 1):
        body.box(side * 0.045, 0.925, 0.101, 0.035, 0.03, 0.005, (0.10, 0.09, 0.08))   # eyes
    body.box(0, 0.86, 0.101, 0.07, 0.015, 0.005, (0.55, 0.40, 0.32))  # mouth
    body.box(0, 0.97, -0.005, 0.25, 0.11, 0.25, OLIVE_DARK, top=OLIVE)  # helmet
    body.box(0, 0.965, 0.0, 0.27, 0.03, 0.27, OLIVE_DARK)             # its rim
    body.box(0, 1.00, -0.005, 0.255, 0.025, 0.255, team)              # helmet band
    body.box(0, 0.50, -0.165, 0.22, 0.26, 0.08, KHAKI_DARK)           # pack
    body.box(0, 0.76, -0.16, 0.20, 0.06, 0.07, OLIVE_DARK)            # rolled blanket on it

    leg = MeshBuilder()
    leg.box(0, -0.42, 0, 0.13, 0.42, 0.15, OLIVE)                     # trousers
    leg.box(0.0, -0.20, 0.0, 0.135, 0.09, 0.155, OLIVE_DARK)          # thigh pocket
    leg.box(0, -0.42, 0.02, 0.145, 0.11, 0.19, BOOT)                  # boot

    arm = MeshBuilder()
    arm.box(0, -0.36, 0, 0.11, 0.36, 0.12, OLIVE)                     # sleeve
    arm.box(0, -0.12, 0, 0.115, 0.045, 0.125, team)                   # armband
    arm.box(0, -0.44, 0, 0.09, 0.09, 0.09, SKIN)                      # hand
    return body, leg, arm


def build_rifle():
    """The soldier's rifle, held in his hands: it lies along +Z from its grip at the
    origin, the stock behind, the muzzle at z = 0.62 (RIFLE_MUZZLE)."""
    mb = MeshBuilder()
    wood = (0.33, 0.24, 0.15)
    mb.box(0, -0.035, 0.22, 0.045, 0.07, 0.62, GUNMETAL)              # body and barrel
    mb.box(0, -0.06, -0.17, 0.05, 0.10, 0.20, wood)                   # stock
    mb.box(0, -0.13, 0.10, 0.04, 0.10, 0.06, GUNMETAL)                # magazine
    mb.box(0, -0.05, 0.38, 0.05, 0.05, 0.16, wood)                    # handguard
    mb.box(0, 0.035, 0.02, 0.02, 0.025, 0.05, GUNMETAL)               # rear sight
    return mb


RIFLE_MUZZLE = (0.0, 0.0, 0.62)

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
    body.box(0, 0.36, 0, 0.35, 0.12, 0.20, WORKWEAR)                  # hips
    body.box(0, 0.40, 0, 0.38, 0.07, 0.23, LEATHER)                   # tool belt
    for side, w in ((-1, 0.07), (1, 0.06)):
        body.box(side * 0.15, 0.30, 0.08, w, 0.12, 0.06, shade(LEATHER, 0.85))   # its pouches
    body.box(0.07, 0.24, 0.125, 0.03, 0.16, 0.015, STEEL)             # a wrench hung on it
    body.box(0, 0.46, 0, 0.35, 0.37, 0.19, WORKWEAR)                  # shirt
    body.box(0, 0.48, 0, 0.375, 0.32, 0.225, HIVIS)                   # hi-vis vest
    for y in (0.54, 0.66):
        body.box(0, y, 0, 0.38, 0.03, 0.23, REFLECTIVE)               # its stripes, all round
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

    arm = MeshBuilder()
    arm.box(0, -0.36, 0, 0.11, 0.36, 0.12, WORKWEAR)                  # sleeve
    arm.box(0, -0.12, 0, 0.115, 0.045, 0.125, team)                   # armband
    arm.box(0, -0.44, 0, 0.09, 0.09, 0.09, GLOVE)                     # glove
    return body, leg, arm


def build_shotgun():
    """The engineer's pump shotgun, held like the rifle: grip at the origin, along +Z, the
    muzzle at SHOTGUN_MUZZLE."""
    mb = MeshBuilder()
    wood = (0.40, 0.27, 0.16)
    mb.box(0, -0.03, 0.20, 0.05, 0.06, 0.56, GUNMETAL)                # receiver and barrel
    mb.box(0, -0.075, 0.30, 0.04, 0.04, 0.36, GUNMETAL)               # the tube under it
    mb.box(0, -0.085, 0.30, 0.055, 0.055, 0.14, wood)                 # the pump
    mb.box(0, -0.07, -0.16, 0.05, 0.10, 0.20, wood)                   # stock
    return mb


SHOTGUN_MUZZLE = (0.0, 0.0, 0.48)


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


def build_beam():
    """A tracer: a thin bright bar from z = 0 to z = 1, stretched and turned to where a shot went."""
    mb = MeshBuilder()
    mb.box(0, -0.012, 0.5, 0.024, 0.024, 1.0, (1.0, 1.0, 1.0), bottom=True)
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
