"""Skyline: a 3D real-time strategy game made with pygame and ModernGL.

A square patch of a dead, overrun world, with your HQ in the middle of it. The
HQ trains soldiers and engineers, engineers build turrets and buildings (a
vehicle factory trains tanks), soldiers dig trenches, and every 30 seconds a wave of zombies (twenty more in each wave than
the last) comes in from beyond the edge of the map to tear the HQ down. If it
falls, it's over. See README.md for how it's put together.

Run it with:  python main.py             (full screen; Esc twice with nothing selected, or Alt+F4, quits)
              python main.py --window    (in a 1280 x 720 window)
Needs:        pip install pygame moderngl

Controls
  Left click       select the HQ, a turret, a building, a deposit or a unit (Shift: add to the selection);
                   double click a unit: every one of its kind on screen
  Left drag        draw a box round units to select them
  Right click      units: move there, go after a zombie, help build a turret or dig a trench,
                   get into a finished trench, or guard one of your own (engineers repair
                   a hurt turret or the HQ). The HQ: where new units gather
  Right drag       units: line them up along the drag, facing away from where they are
  Shift            with any order: do it after the orders already given
  P, click         units: patrol there and back (Shift-click more points for a longer beat)
  H                units: stop, and drop every order (blueprints nobody else will build go too)
  X, click         engineers: take a turret down (one being built too), or call a blueprint off
  L                units: fire at will, return fire only, or hold fire
  Ctrl + 0-9       make the selection a group; 0-9 selects it again (twice: look at it)
  HQ               Soldier (T) or Engineer (G) to train one, Shift: 5, Ctrl: 20; right click a
                   button to take them off the queue the same way. Hover any button for its numbers
  Engineers        Semi-auto turret (B) or Full-auto turret (M), then click a tile, or drag
                   for a row (on a blueprint: call it off); Bullet factory (N), then click
                   where it goes; Salvage crane (J) or Loading dock post (K), then click a
                   junkyard or a warehouse (it goes up on the spot beside it); Radar station
                   (R), then click where it goes (once it's up, the whole map is open);
                   Vehicle factory (V), then click where it goes
  Vehicle factory  Tank (T) to train one, as at the HQ; right click the ground: where tanks gather
  Soldiers         Trench (C), then click a tile, or drag for a line
  WASD / arrows    move the camera (or push the mouse against a screen edge)
  Mouse wheel      zoom
  Q / E            turn the camera (or drag with the middle mouse button)
  Space            camera back to the HQ
  Pause            pause the game, or go on (or the button at the top right); orders can
                   still be given while it's paused
  F                double speed, or back to normal (or the ×2 button beside the pause button)
  The + by the materials (top left): add a load of each, for testing
  R                play again, once the HQ has fallen
  Esc              stop placing or choosing; let go of what's selected; with nothing selected: press it
                   again within 3 seconds to quit
"""
import math
import os
import random
import sys
from collections import deque

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# on Windows, a screen scaled up (to 125% or 150%) is still drawn on at its own pixels, not blurred
os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
import pygame  # noqa: E402

try:
    import moderngl  # noqa: E402
except ImportError:
    sys.exit("Skyline needs ModernGL to draw in 3D. Install it with:  pip install moderngl")

import mathx  # noqa: E402
import models  # noqa: E402
import sounds  # noqa: E402
from camera import RTSCamera  # noqa: E402
from deaths import GUN_DROP, SHOULDER_Y, Fall, Shape, lay_out, turn_between  # noqa: E402
from deposits import Deposit, Junkyard, place_deposits  # noqa: E402
from gfx import MeshBuilder, Renderer, open_window  # noqa: E402
from orders import FIRE_STATES, Around, Attack, Build, Guard, Move, Patrol, Remove, Repair  # noqa: E402
from stores import FREE, MATERIALS, MOST, TEST_GIFT  # noqa: E402
from tanks import MachineGun, Tank, VehicleFactory  # noqa: E402
from units import (DEATH_TIME, FADE_TIME, HUNGRY_MISS, HUNGRY_PACE, MISS_BY, UPKEEP_TIME, Engineer, Extractor,  # noqa: E402
                   Factory,
                   Fighter, Gunner, Headquarters, LoadingDock, Maker, MinigunTurret, RadarStation, SalvageCrane, Soldier,
                   Structure, Trench, Trooper, Turret, Worker, formation, keep_apart, line_formation,
                   send_to_spots)
from world import HQ, HQ_DEPTH, HQ_WIDTH, World  # noqa: E402
from zombies import COVER_ACID, POOL_TIME, AcidPool, Spitter, Waves, Zombie  # noqa: E402

VERSION = "0.1"            # the version players have (in the window's title, and build_app.py's zip)
FROZEN = getattr(sys, "frozen", False)   # running as the packaged game (built by build_app.py), not from Python
CRASH_LOG = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Skyline", "crash.log")
WINDOW = (1280, 720)       # the window's size, when it isn't full screen (--window, and the tests)
WIDTH, HEIGHT = WINDOW     # the size it's drawn at (lay_out_screen sets it, once the window is open)
EDGE_SCROLL = 6            # pixels from the window edge that scroll the camera
TURN_SPEED = 1.8           # camera turn with Q / E, radians per second
DRAG_MIN = 6               # pixels the mouse must move with the button down to draw a box
LINE_MIN = 1.0             # tiles a right drag must cover to line units up (shorter: a plain move)
MARKER_TIME = 0.6          # how long the "move here" ring lasts
MESSAGE_TIME = 3.5         # seconds a message stays up
QUIT_AGAIN = 3000          # milliseconds to press Esc again, with nothing selected, to quit
DOUBLE_CLICK = 400         # milliseconds between two clicks (or two presses of a group's key) to count as a double
SHIFT_COUNT, CTRL_COUNT = 5, 20   # how many a Shift or a Ctrl click (or key) trains, or takes off the queue
TRACER_TIME = 0.07         # seconds a shot's tracer shows
SPLASH_TIME = 0.35         # seconds a splash of acid shows
DUST_TIME = 0.45           # seconds the dust a missed shot kicks up shows
BULLET_PAST = (0.5, 3.0)   # how far past its target a bullet that hits nothing comes down in the dirt, in tiles
SHELL_TIME = 0.12          # seconds a tank's shell's streak shows
BLAST_TIME = 0.7           # seconds a shell's blast (its fireball, then smoke) shows
SCORCH_TIME = 20.0         # seconds the scorch a shell leaves on the ground takes to fade
TANK_ROOM = 2 * Tank.RADIUS + 0.4   # how far apart tanks stand, in a block or a line (each turns on the spot)
LEVEL_UP_TIME = 1.2        # seconds the mark of a new level rises over whoever went up
TRENCH_REACH = 10.0        # tiles away a free trench can be for someone sent into one
BLUEPRINT_TINT = (0.45, 0.72, 1.0, 0.38)  # a turret or trench laid out that nobody has started on yet

PLAYER_BLUE = (0.24, 0.48, 0.95)
SELECT_GREEN = (0.45, 1.0, 0.55)
ENEMY_RED = (1.0, 0.35, 0.30)
FITS = (0.45, 1.0, 0.55)       # a ghost (a turret's or a trench's) where it can go
DOESNT_FIT = (1.0, 0.36, 0.30)  # and where it can't
HIT_TINT = (1.7, 0.55, 0.5, 1.0)       # a unit, the moment it's hit
HQ_HIT_TINT = (1.12, 0.94, 0.90, 1.0)  # the HQ, when a blow lands: just a touch (it's hit often)
UNBUILT_TINT = (0.75, 0.82, 0.95, 0.75)  # a turret still being built
ACID_GREEN, ACID_LIGHT = (0.40, 0.72, 0.10), (0.62, 0.95, 0.22)   # a puddle of acid, and its middle
STAINS = {"troop": (0.30, 0.03, 0.03), "zombie": (0.14, 0.15, 0.07), "spitter": (0.40, 0.70, 0.12)}   # under the dead
STAIN_TIME = 3.0           # seconds a stain takes to spread
LAYOUTS_A_FRAME = 1        # the most bodies laid out in one frame (any more wait a frame or so, standing)
SLING_GAP = 0.005          # how far off his back (or pack) a slung gun hangs
ARMS_OUT = 0.04            # how far (radians) an engineer's arms hang out from his sides, clear of his belt
GRIP_ELBOW = ((-0.3, -1.0, -0.2), (-1.0, -1.0, 0.2))   # which way his right elbow bends, carrying and raised
FRONT_ELBOW = ((0.3, -1.0, 0.0), (0.6, -1.0, 0.0))     # and his left
RAISE_OUT = 0.03          # how far out from his chest a gun goes midway as he raises it (its butt swings round in front of him)
FRONT_SHOULDER = ((0.0, 0.0), (0.10, 0.04))   # how far his left shoulder comes forward and in, carrying and raised
MAG_GRIPS = {"seat": 0.05, "out": 0.05, "pouch": 0.015, "in": 0.015}   # how far below its top his left hand holds a
#                          magazine he's changing: by its middle at the gun, by its top at the pouch (his hand over it)
MAG_PULL = 0.05           # how far out of the rifle (down along it) a magazine comes, clear of it
MAG_POUCH = (0.075, 0.62, 0.17)   # where a magazine goes into his pouch: the top of his left vest pocket, at its front
MAG_IN = 0.06             # how high over the pouch's top a magazine's top is, down in it (his hand just over the pocket)
# Changing magazines, through the change: (how far through, where his left hand goes). "front": on the
# front of the gun; else holding a magazine at "seat" (in the gun), "out" (pulled clear under it),
# "pouch" (over his pouch) or "in" (down in it)
RELOAD_STEPS = ((0.0, "front"), (0.12, "seat"), (0.25, "out"), (0.45, "pouch"), (0.50, "in"), (0.55, "in"),
                (0.60, "pouch"), (0.80, "out"), (0.90, "seat"), (1.0, "front"))
NEW_MAG = 0.55            # from here the magazine in his hand is the full one (before it, the empty)
RELOAD_RING = 5           # how big the ring over a soldier changing magazines is (pixels, middle to edge)
                                              # (reaching across him for the front of the gun, it rolls forward)

# the panel at the bottom left, with what's selected
PANEL_X = 12                   # every panel sits at the bottom left, as wide as what it holds
BUTTON = 72                    # a train or build button's size
GOLD = (255, 214, 120)
GREY = (175, 186, 202)
TRAIN_KEYS = {Soldier: "T", Engineer: "G", Tank: "T"}
HQ_PANEL_H = 194               # the HQ's panel: its name, its health, a button for each kind it trains, and what it makes
INCOME_GAP = 14                # pixels between one thing made and the next, in a panel's row of them
TIMER_R = 13                   # a round timer's size (pixels from its middle to its edge), over what makes something
TIMER_GAP = 36                 # pixels from one round timer's middle to the next, in a row of them
TIMER_HEIGHTS = {Factory: 2.9, SalvageCrane: 2.2, LoadingDock: 2.6}   # how high a building's round timer sits
CRANE_SAFE = 2.8               # how high a salvage crane carries its magnet over the junkyard (a car under it clears the stacks)
CRANE_LIFT = 30.0              # how long a lift takes (the last of each batch: it rests over its baler till then)
CRANE_REST = 1.35              # and how high it rests it, over its baler
# How a salvage crane lifts a car out, through each of its batches: (how far through, where its magnet is)
CRANE_STEPS = ((0.0, "rest"), (0.08, "over"), (0.30, "above"), (0.38, "on"), (0.42, "on"), (0.50, "above"),
               (0.78, "over"), (0.86, "drop"), (0.94, "rest"), (1.0, "rest"))
CRANE_CARRIES = (0.40, 0.86)   # from when to when it has the car on its magnet
# (PAUSE_BUTTON and SPEED_BUTTON at the top right, IDLE_PANEL and IDLE_BUTTON at the bottom right: lay_out_screen)
STORES_PANEL = pygame.Rect(12, 12, 396, 36)   # top left: the materials there are to spend...
STORES_SLOT = 128              # ...each in a slot this wide: its mark, how much, and what's used and made
USED_RED = (255, 125, 110)     # what's used of a material, every UPKEEP_TIME
MADE_GREEN = (125, 230, 140)   # and what's made
GIFT_BUTTON = pygame.Rect(STORES_PANEL.right + 8, 12, 36, 36)   # beside it: add a load of each, for testing
MATERIAL_COLORS = {"supply": (196, 150, 92), "metal": (178, 186, 198), "bullets": (214, 168, 74)}
NONE_LEFT = (255, 120, 105)    # a material there's none of
BULLETS_AGAIN = 100            # bullets in the stores before running out of them again is news again
FAST = 2                       # how many times as fast the game goes at double speed
ORDER_BUTTONS = (("patrol", "P", 72), ("stop", "H", 64), ("fire", "L", 98), ("remove", "X", 82))  # name, key, width
AIMED_ORDERS = ("patrol", "remove")   # the orders that need a click: a spot, or a turret
BUILD_KEYS = {Turret: "B", MinigunTurret: "M", Factory: "N", SalvageCrane: "J", LoadingDock: "K", RadarStation: "R",
              VehicleFactory: "V", Trench: "C"}
MAKERS = (Factory, SalvageCrane, LoadingDock)      # the buildings that make something...
BUILDINGS = MAKERS + (RadarStation, VehicleFactory)   # ...and all the buildings engineers put up (not turrets)
SWITCH = (70, 26)              # the size of a building's on/off switch, at the top right of its panel
SWITCH_ON, SWITCH_OFF = (110, 215, 125), (240, 110, 95)
VIEW_MARGIN = (320, 200)       # how far off the screen's edges (pixels) a unit is still drawn (its limbs, or its body lying, may reach in)
RADAR_TURN = 0.25              # how fast a radar station's dish turns, once it's up (radians a second)


def lay_out_screen(width, height):
    """Draw at this size, and put what sits against the screen's right and bottom edges there:
    the pause and double-speed buttons at the top right, the idle engineers at the bottom
    right. (Everything else is laid out as it's drawn, from WIDTH and HEIGHT.)"""
    global WIDTH, HEIGHT, PAUSE_BUTTON, SPEED_BUTTON, IDLE_PANEL, IDLE_BUTTON
    WIDTH, HEIGHT = width, height
    PAUSE_BUTTON = pygame.Rect(WIDTH - 12 - 36, 12, 36, 36)            # top right
    SPEED_BUTTON = pygame.Rect(PAUSE_BUTTON.x - 8 - 44, 12, 44, 36)    # beside it: double speed
    IDLE_PANEL = pygame.Rect(WIDTH - 12 - 84, HEIGHT - 12 - 104, 84, 104)   # bottom right, while an engineer has nothing to do
    IDLE_BUTTON = pygame.Rect(IDLE_PANEL.x + 10, IDLE_PANEL.bottom - 10 - 64, 64, 64)   # his portrait, in it


lay_out_screen(*WINDOW)


def health_color(t):
    """Green when full, through yellow, to red when nearly gone."""
    if t > 0.5:
        return (int(255 * (1 - t) * 2), 220, 90)
    return (235, int(220 * t * 2), 70)


def level_of(thing):
    """A soldier's or a turret's level; anyone else (an engineer, a zombie) has only the first."""
    return thing.level if isinstance(thing, Fighter) else 1


def plural(n, kind):
    return f"{n} {kind.NAME}" + ("" if n == 1 else "s")


def slung(depth):
    """A gun slung across a man's back, in his body's frame, `depth` behind his middle: the
    butt low on his left, the muzzle up past his right shoulder, the magazine facing out."""
    return mathx.chain(mathx.translate(0.027, 0.587, depth), mathx.rot_z(0.39), mathx.rot_x(-math.pi / 2),
                       mathx.rot_z(math.pi))


def sling_depth(body, gun):
    """How far behind a man's middle his gun hangs, slung: as near as it goes without going
    into his back or his pack (SLING_GAP off them), worked out from the boxes of his body and
    of the gun (MeshBuilders), at points all through the gun."""
    m = slung(0.0)
    boxes = [([min(c[k] for c in b) for k in range(3)], [max(c[k] for c in b) for k in range(3)]) for b in body.boxes]
    room = math.inf
    for b in gun.boxes:
        lo, hi = [min(c[k] for c in b) for k in range(3)], [max(c[k] for c in b) for k in range(3)]
        for i in range(5):
            for j in range(5):
                for k in range(5):
                    x, y, z = mathx.apply(m, [lo[a] + (hi[a] - lo[a]) * (i, j, k)[a] / 4 for a in range(3)])
                    for blo, bhi in boxes:                  # the body boxes this point is behind
                        if blo[0] <= x <= bhi[0] and blo[1] <= y <= bhi[1]:
                            room = min(room, blo[2] - z)
    return room - SLING_GAP


def game_icon(size=64):
    """The game's icon, drawn: the HQ's dark block with its lit windows and the team's flag, in front of
    a city's towers against an evening sky, on a tile with round corners."""
    k = size / 64
    icon = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(icon, (44, 62, 98), (0, 0, size, size), border_radius=round(12 * k))
    pygame.draw.circle(icon, (236, 222, 180), (round(48 * k), round(14 * k)), round(5 * k))      # the moon
    for x, w, h in ((3, 8, 24), (12, 6, 33), (19, 9, 20), (41, 7, 28), (49, 9, 37), (57, 5, 22)):
        pygame.draw.rect(icon, (78, 94, 120), (round(x * k), round((58 - h) * k), round(w * k), round(h * k)))
    pygame.draw.rect(icon, (58, 54, 50), (0, round(56 * k), size, round(8 * k)),
                     border_bottom_left_radius=round(12 * k), border_bottom_right_radius=round(12 * k))
    pygame.draw.rect(icon, (24, 24, 28), (round(16 * k), round(30 * k), round(32 * k), round(27 * k)))   # the HQ
    for row in range(3):
        for col in range(4):
            pygame.draw.rect(icon, (255, 226, 160), (round((20 + 7 * col) * k), round((34 + 7 * row) * k),
                                                    max(1, round(4 * k)), max(1, round(3 * k))))
    pygame.draw.rect(icon, (150, 152, 156), (round(30 * k), round(14 * k), max(1, round(2 * k)), round(16 * k)))
    team = tuple(round(c * 255) for c in PLAYER_BLUE)
    pygame.draw.rect(icon, team, (round(32 * k), round(14 * k), round(11 * k), round(7 * k)))     # the flag
    return icon


def how_many():
    """How many one click (or key press) trains or takes off the queue: Ctrl 20, Shift 5, else 1."""
    mods = pygame.key.get_mods()
    return CTRL_COUNT if mods & pygame.KMOD_CTRL else SHIFT_COUNT if mods & pygame.KMOD_SHIFT else 1


class Game:
    def __init__(self, screenshot=None, window=WINDOW):
        """`window`: the size of the window to play in, or None to play full screen."""
        pygame.mixer.pre_init(sounds.RATE, -16, 2, 512)
        pygame.init()
        pygame.display.set_icon(game_icon())
        self.size = open_window(window, f"Skyline {VERSION}", full_screen=window is None).get_size()
        lay_out_screen(*self.size)
        self.gfx = Renderer(moderngl.create_context(), self.size)
        self.overlay = pygame.Surface(self.size, pygame.SRCALPHA)   # the HUD, cleared and drawn on every frame
        self.screenshot = screenshot
        self.sounds = sounds.Sounds(enabled=not screenshot)   # (a test run plays none)

        mesh = self.gfx.mesh
        # the HQ is built at the map's corner and moved to where it's drawn
        self.hq_mesh = mesh(models.build_hq(HQ(0, 0, HQ_WIDTH, HQ_DEPTH), PLAYER_BLUE))
        # how each kind of unit looks: its body, legs and arms, and its gun (an engineer has none)
        # his rifle in his hands is drawn without its magazine, and the magazine on its own, so he can change it
        self.rifle_parts = (mesh(models.build_rifle(with_magazine=False)), mesh(models.build_magazine()))
        self.looks = {Soldier: (tuple(mesh(m) for m in models.build_soldier()), mesh(models.build_rifle())),
                      Engineer: (tuple(mesh(m) for m in models.build_engineer(PLAYER_BLUE)), None)}
        self.tools = {Soldier: mesh(models.build_shovel()), Engineer: mesh(models.build_hammer())}
        # a soldier's arms in two pieces, upper arm and forearm, to hold his rifle with the elbows bent
        self.arm_halves = tuple(mesh(m) for m in models.build_arm_halves(models.soldier_arm()))
        # how far behind him a soldier's rifle hangs, slung on his back: touching it (or his pack)
        self.slung_depth = sling_depth(models.build_soldier()[0], models.build_rifle())
        # the corners of each kind's parts, to work out how its body lies when it falls (deaths.py)
        shoulders = {"shoulder": models.SHOULDER_X, "shoulder_z": models.SHOULDER_Z}
        self.shapes = {Soldier: Shape(models.build_soldier(), models.build_rifle(), **shoulders),
                       Engineer: Shape(models.build_engineer(PLAYER_BLUE), None, **shoulders)}
        self.zombie_shapes = [Shape(models.build_zombie(v), shoulder=0.28) for v in range(3)]
        self.zombie_shapes.append(Shape(models.build_spitter(), shoulder=0.28))
        self.trench_plan_mesh = mesh(models.build_trench_plan())
        self.trench_mesh = None    # every trench dug so far, built afresh whenever one changes
        self.acid_mesh = mesh(models.build_acid())
        self.dust_mesh = mesh(models.build_dust())
        self.turret_looks = {      # each kind of turret's block, and the part that turns
            Turret: (mesh(models.build_turret_base(PLAYER_BLUE)), mesh(models.build_turret_head(PLAYER_BLUE))),
            MinigunTurret: (mesh(models.build_minigun_turret_base(PLAYER_BLUE)),
                            mesh(models.build_minigun_turret_head(PLAYER_BLUE))),
        }
        self.barrels_mesh = mesh(models.build_minigun_barrels())
        self.factory_mesh = mesh(models.build_factory(PLAYER_BLUE, Factory.W, Factory.D))
        self.dock_mesh = mesh(models.build_loading_dock(PLAYER_BLUE))
        self.crate_mesh = mesh(models.build_crate_stack())
        self.crane_meshes = {"base": mesh(models.build_crane_base(PLAYER_BLUE)), "works": mesh(models.build_crane_works(PLAYER_BLUE)),
                             "boom": mesh(models.build_crane_boom()), "stick": mesh(models.build_crane_stick()),
                             "magnet": mesh(models.build_magnet())}
        self.car_meshes = {color: mesh(models.build_car(color)) for color in models.CAR_COLORS}
        self.radar_meshes = {"base": mesh(models.build_radar_base(PLAYER_BLUE)), "mount": mesh(models.build_radar_mount(PLAYER_BLUE)),
                             "dish": mesh(models.build_radar_dish())}
        self.vehicle_factory_mesh = mesh(models.build_vehicle_factory(PLAYER_BLUE, VehicleFactory.W, VehicleFactory.D))
        # a tank: its hull, its tracks' cleats (drawn on each, running), its turret, main gun and machine guns
        self.tank_meshes = {"hull": mesh(models.build_tank_hull(PLAYER_BLUE)), "links": mesh(models.build_track_links()),
                            "turret": mesh(models.build_tank_turret(PLAYER_BLUE)), "gun": mesh(models.build_tank_gun()),
                            "mgs": [mesh(models.build_tank_mg(foot, height, reach))
                                    for _, foot, height, reach in Tank.GUN_POSTS]}
        self.fireball_mesh = mesh(models.build_fireball())
        self.deposit_meshes = {}   # deposit: (what it looked like when built, its mesh)
        self.zombie_meshes = [tuple(mesh(m) for m in models.build_zombie(v)) for v in range(3)]
        self.zombie_meshes.append(tuple(mesh(m) for m in models.build_spitter()))   # variant 3
        # each look as one standing piece, legs and arms in place: drawn so when the camera's far out
        self.zombie_whole = [mesh(self.whole_zombie(parts)) for parts in
                             [models.build_zombie(v) for v in range(3)] + [models.build_spitter()]]
        self.beam_mesh = mesh(models.build_beam())
        self.flag_mesh = mesh(models.build_flag(PLAYER_BLUE))
        self.ring_mesh = mesh(models.build_ring())
        self.thin_ring_mesh = mesh(models.build_thin_ring())
        self.disc_mesh = mesh(models.build_disc())

        self.turning = False       # dragging with the middle mouse button
        self.running = True
        self.quit_asked = None     # when Esc was pressed with nothing selected (pygame ticks): again soon, and it quits
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui", 15)
        self.font_small = pygame.font.SysFont("segoeui", 13)
        self.font_bold = pygame.font.SysFont("segoeui", 15, bold=True)
        self.font_title = pygame.font.SysFont("segoeui", 24, bold=True)
        self.font_big = pygame.font.SysFont("segoeui", 18, bold=True)
        self.font_huge = pygame.font.SysFont("segoeui", 40, bold=True)
        self.font_tiny = pygame.font.SysFont("segoeui", 11, bold=True)
        self.new_game()

    def new_game(self):
        self.world = World()
        middle = self.world.size / 2
        hq = self.world.build_hq(*World.hq_tiles_at(middle, middle))
        self.base = Headquarters(self.world, hq)   # the HQ as it plays
        self.deposits = place_deposits(self.world, hq.i + hq.w / 2, hq.j + hq.d / 2)
        self.world.find_way_home(hq)
        self.junk_cars = {d: models.junkyard_cars(d.seed) for d in self.deposits if isinstance(d, Junkyard)}
        for _, old in self.deposit_meshes.values():
            old.release()
        self.deposit_meshes = {}
        self.waves = Waves(self.world)   # the countdown to the first wave starts now
        self.home = (hq.i + hq.w / 2, hq.j + hq.d / 2 + 2)   # where Space brings the camera back to
        self.camera = RTSCamera(self.world.open, WIDTH / HEIGHT)
        self.camera.look_at(*self.home, instant=True)
        self.camera.dist = self.camera.dist_goal = 17.0
        self.gfx.set_ground(self.world.size)
        self.gfx.set_open(self.world.open)
        self.opened = False        # a radar station has opened the whole map

        self.units = []            # the player's soldiers and engineers
        self.turrets = []
        self.buildings = []        # bullet factories, salvage cranes and loading dock posts, blueprints and all
        self.zombies = []
        self.selected = []         # the units selected
        self.hq_selected = False
        self.structure_selected = None
        self.deposit_selected = None
        self.placing_turret = False  # choosing a tile for a turret
        self.turret_kind = Turret  # which kind of turret is being laid
        self.turret_aim = None     # the tile, while choosing
        self.turret_row = None     # while the left button's held: the tiles dragged over, to lay turrets on
        self.turret_cancel = []    # and the blueprints dragged over, to call off
        self.row_from = None       # where on the ground the drag was last frame
        self.turret_fits = False
        self.placing_building = None  # the kind of building whose place is being chosen, if any
        self.building_aim = None   # its corner tile (and for one beside a deposit, the deposit), while choosing
        self.building_fits = False
        self.placing_trench = False  # choosing where a trench goes
        self.trench_aim = None     # the tile, while choosing
        self.trench_row = None     # while the left button's held: the tiles dragged over, to dig
        self.trench_cancel = []    # and the blueprints dragged over, to call off
        self.trench_from = None    # where on the ground the drag was last frame
        self.trench_last = None    # the last tile it crossed
        self.trench_fits = False
        self.order_aim = None      # "patrol" or "remove" while choosing where or what (the next click)
        self.groups = {}           # the control groups: key number: units
        self.last_click = (None, 0)  # what was last clicked, and when (to see a double click)
        self.last_group = (None, 0)  # which group was last called up, and when
        self.last_idle = None      # the idle engineer the idle button last went to
        if self.trench_mesh:
            self.trench_mesh.release()
        self.trench_mesh = None
        self.trenches_drawn = -1   # which change to the trenches the mesh shows
        self.spits = []            # globs of acid in flight
        self.splashes = []         # [x, y, z, age] of acid that has just landed
        self.pools = []            # puddles of acid burning on the ground
        self.dust = []             # [x, y, z, age] where a shot that missed came down
        self.shells = []           # [muzzle, where it burst, age] of tanks' shells just fired
        self.blasts = []           # [x, y, z, age] of shells bursting
        self.scorches = []         # [x, z, age] where shells have burst on the ground
        self.levels_up = []        # [fighter, age]: who went up a level just now
        self.hover = None          # what the mouse is over: a unit, a zombie, a turret, "hq" or None
        self.drag_from = None      # where a left-button drag started (pixels)
        self.line_from = None      # where a right-button drag started, on the ground, to line units up
        self.markers = []          # [x, z, age, colour] of recent orders
        self.shots = []            # [muzzle, hit, age] of shots just fired
        self.fired = deque()       # when (self.played) each bullet of the last UPKEEP_TIME was fired
        self.together = {}         # the living dead's parts, gathered to be drawn in one go (see draw)
        self.message = None        # (text, seconds left) of the news in the banner, if any
        self.over = False          # the HQ has fallen
        self.out_of_bullets = False  # the bullets have run out (said once, till BULLETS_AGAIN are back)
        self.bullets_full = False  # the stores are full of bullets (said once, till BULLETS_AGAIN have been used)
        self.paused = False        # nothing moves, but orders can still be given
        self.speed = 1             # game seconds to a second: 1, or FAST at double speed
        self.played = 0.0          # seconds since the game began
        self.kills = 0

    # ------------------------------------------------------------ main loop

    def run(self):
        if self.screenshot:
            return self.take_screenshots()
        while self.running:
            dt = min(self.clock.tick(144) / 1000, 0.05)
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def take_screenshots(self):
        """Play a little with no player input, as pictures. `--screenshot shot.png` saves
        shot_hq.png (the HQ training both kinds), shot_build.png (engineers building a
        turret) and shot.png (the turret and the soldiers shooting a wave)."""
        base, ext = os.path.splitext(self.screenshot)

        def save(suffix):
            self.draw()
            pygame.image.save(self.gfx.read_pixels(), base + suffix + ext)
            print("saved", base + suffix + ext)

        def play(seconds):
            for _ in range(round(seconds * 60)):
                self.update(1 / 60, edge_scroll=False)

        play(1.5)
        self.give_test_gift()                       # (enough to train them all and lay a turret)
        self.select_hq()
        for kind in (Engineer, Engineer, Soldier, Soldier, Soldier, Soldier):
            self.train(kind)
        play(3)
        save("_hq")
        play(10)
        hq = self.base.hq
        self.select_units([u for u in self.units if isinstance(u, Engineer)])
        self.start_placing_turret()
        self.aim_turret(hq.i + 2.5, hq.j + hq.d + 6.5)
        self.place_turret()
        play(4)
        self.camera.look_at(hq.i + 2.5, hq.j + hq.d + 5, instant=True)
        self.camera.dist = self.camera.dist_goal = 12.0
        save("_build")
        while self.played < 360 and not (self.shots and any(not z.alive for z in self.zombies)):   # (the first wave takes minutes to walk in)
            play(1 / 60)
        self.camera.dist = self.camera.dist_goal = 30.0
        self.select_units([u for u in self.units if u.alive])
        save("")
        print(f"wave {self.waves.number}: {self.kills} zombies down, {sum(u.alive for u in self.units)} units up,"
              f" turrets {len(self.turrets)}, buildings {len(self.buildings)}, HQ {int(self.base.hp)}/{self.base.MAX_HP},"
              f" {self.base.stores.bullets} bullets")
        pygame.quit()

    # ------------------------------------------------------------ messages, and the HQ's ground

    def say(self, text):
        self.message = (text, MESSAGE_TIME)

    @staticmethod
    def slab_of(i0, j0):
        """The HQ's floor slab on tile (i0, j0): the ground is shaded at its foot."""
        return (i0 + 0.05, j0 + 0.05, i0 + HQ_WIDTH - 0.05, j0 + HQ_DEPTH - 0.05)

    # ------------------------------------------------------------ turrets

    @property
    def engineers(self):
        return [u for u in self.selected if isinstance(u, Engineer)]

    def start_placing_turret(self, kind=Turret):
        if self.engineers and not self.over:
            self.placing_trench = False
            self.placing_building = None
            self.order_aim = None
            self.placing_turret = True
            self.turret_kind = kind
            self.turret_aim = None

    def turret_at(self, i, j):
        return next((t for t in self.turrets if t.alive and (t.i, t.j) == (i, j)), None)

    def tile_fits(self, i, j):
        """Can a turret be laid on this tile: on the map, nothing built there, no turret (or
        blueprint) on it already? (Someone standing on it is fine: they'll step off when the
        foundation goes down.)"""
        return (self.world.can_build_turret(i, j) and not self.turret_at(i, j) and not self.building_on(i, j)
                and not any(t.standing and (i, j) in t.tiles_under() for t in self.tanks))

    @property
    def tanks(self):
        """The tanks (and wrecks) on the map."""
        return [u for u in self.units if isinstance(u, Tank)]

    def building_on(self, i, j):
        """The building (or its blueprint) on this tile, or None."""
        return next((b for b in self.buildings if b.alive and (i, j) in b.tiles), None)

    def extractor_at(self, deposit):
        """The building (or its blueprint) on a deposit's spot, or None."""
        return next((b for b in self.buildings if b.alive and isinstance(b, Extractor) and b.deposit is deposit), None)

    def free_deposits(self, kind):
        """The deposits a building of this kind could go up beside: of its kind, with no
        building on their spot yet."""
        return [d for d in self.deposits if isinstance(d, kind.DEPOSIT) and not self.extractor_at(d)]

    def start_placing_building(self, kind):
        if self.engineers and not self.over:
            self.placing_turret = self.placing_trench = False
            self.order_aim = None
            self.placing_building = kind
            self.building_aim = None

    def aim_building(self, x, z):
        """Where a building would go with the mouse at (x, z), and whether it can. A bullet
        factory: centred on the mouse, if all its tiles are clear (as a turret's tile must be).
        A salvage crane or a loading dock post: on the spot beside the nearest deposit of its
        kind with none yet, if the mouse is on that deposit or near its spot, and the spot is
        clear; elsewhere, under the mouse, and it can't."""
        kind = self.placing_building
        if x is None or kind is None:
            self.building_aim, self.building_fits = None, False
            return
        corner = (round(x - kind.W / 2), round(z - kind.D / 2))
        deposit = None
        if issubclass(kind, Extractor):
            near = [d for d in self.free_deposits(kind)
                    if math.dist((x, z), (d.spot[0] + 1.5, d.spot[1] + 1.5)) < 4
                    or d.rect[0] <= x < d.rect[2] and d.rect[1] <= z < d.rect[3]]
            deposit = min(near, key=lambda d: math.dist((x, z), (d.spot[0] + 1.5, d.spot[1] + 1.5)), default=None)
            corner = deposit.spot if deposit else corner
        self.building_aim = (corner, deposit)
        i0, j0 = corner
        self.building_fits = (not issubclass(kind, Extractor) or deposit is not None) and all(
            self.tile_fits(i, j) for i in range(i0, i0 + kind.W) for j in range(j0, j0 + kind.D))

    def place_building(self, queue=False):
        """Lay a building where it's aimed, and give it to the selected engineers to build (it's
        paid for as it's built: Site.pay_for). With Shift (queue), they build it after their
        other orders, and more can be laid."""
        kind = self.placing_building
        name = kind.NAME.lower()
        if not (self.building_aim and self.building_fits):
            if issubclass(kind, Extractor):
                self.say(f"A {name} goes up beside a {kind.DEPOSIT.NAME.lower()} that has none: click one.")
            else:
                self.say(f"A {name} needs {kind.W} by {kind.D} clear tiles.")
            return
        if kind is RadarStation and (self.opened or any(isinstance(b, RadarStation) and b.alive for b in self.buildings)):
            self.say("One radar station is all it takes: there's one already." if not self.opened
                     else "The radar station has opened the whole map already.")
            return
        corner, deposit = self.building_aim
        building = kind(self.world, deposit) if deposit else kind(self.world, *corner)
        self.buildings.append(building)
        self.markers.append([building.x, building.z, 0.0, SELECT_GREEN])
        for engineer in self.engineers:
            engineer.order(Build([building]), queue)
        self.placing_building = kind if queue else None
        self.building_aim = None

    def aim_turret(self, x, z):
        if x is None:
            self.turret_aim = None
            return
        self.turret_aim = (int(math.floor(x)), int(math.floor(z)))
        there = self.turret_at(*self.turret_aim)
        # fine where it fits, and on a blueprint too (laying one there again calls it off)
        self.turret_fits = self.tile_fits(*self.turret_aim) or bool(there and there.blueprint)

    def start_turret_row(self, point):
        """The left button goes down while placing: the first turret of a row (or the only one)."""
        self.turret_row, self.turret_cancel = [], []
        self.row_from = point
        if point:
            self.extend_turret_row(point)

    def extend_turret_row(self, point):
        """Take in the tiles the mouse has crossed since last time: a new turret on each one that's
        free, and a blueprint called off on each one that has one."""
        if not point:
            return
        a = self.row_from or point
        steps = max(1, int(math.dist(a, point) / 0.25))
        for k in range(steps + 1):
            t = k / steps
            tile = int(math.floor(a[0] + (point[0] - a[0]) * t)), int(math.floor(a[1] + (point[1] - a[1]) * t))
            if tile in self.turret_row or any((b.i, b.j) == tile for b in self.turret_cancel):
                continue
            there = self.turret_at(*tile)
            if there and there.blueprint:
                self.turret_cancel.append(there)
            elif self.tile_fits(*tile):
                self.turret_row.append(tile)
        self.row_from = point

    def finish_turret_row(self, point, queue=False):
        """The left button is let go: call off the blueprints crossed, and lay the new ones.
        With Shift (queue), the engineers build them after their other orders, and more can be laid."""
        self.extend_turret_row(point)
        row, cancel = self.turret_row, self.turret_cancel
        self.turret_row, self.turret_cancel, self.row_from = None, [], None
        if not row and not cancel:
            self.say("A turret needs a clear tile.")
            return
        for blueprint in cancel:
            self.call_off(blueprint)
        if row:
            self.lay_turrets(row, queue)
        self.placing_turret = queue
        self.turret_aim = None

    def place_turret(self, queue=False):
        """Lay one turret on the tile aimed at, or call off the blueprint there (as a click does)."""
        if self.turret_aim:
            self.start_turret_row((self.turret_aim[0] + 0.5, self.turret_aim[1] + 0.5))
            self.finish_turret_row(None, queue)

    def lay_turrets(self, tiles, queue=False):
        """Lay turret blueprints on these tiles, and give them to the selected engineers to
        build, one after another (each is paid for as it's built). (A blueprint takes up its
        tile only once an engineer starts on it.)"""
        laid = []
        for i, j in tiles:
            turret = self.turret_kind(self.world, i, j)
            self.turrets.append(turret)
            self.markers.append([turret.x, turret.z, 0.0, SELECT_GREEN])
            laid.append(turret)
        if laid:
            for engineer in self.engineers:
                engineer.order(Build(laid), queue)

    def clear_tile(self, i, j):
        """A foundation's going down on this tile: anyone standing on it steps off (a tank
        drives off: see move_tank_off)."""
        for u in self.units + self.zombies:
            if not u.alive:
                continue
            if u.big:
                if (i, j) in u.tiles_under():
                    self.move_tank_off(u)
                continue
            r = u.RADIUS
            cx, cz = min(max(u.x, i), i + 1), min(max(u.z, j), j + 1)
            if (u.x - cx) ** 2 + (u.z - cz) ** 2 >= r * r and not (i < u.x < i + 1 and j < u.z < j + 1):
                continue
            ways = [(i - r - 0.02, u.z), (i + 1 + r + 0.02, u.z), (u.x, j - r - 0.02), (u.x, j + 1 + r + 0.02)]
            ways = [w for w in ways if not self.world.hits_wall(*w, r)] or ways
            u.x, u.z = min(ways, key=lambda w: (w[0] - u.x) ** 2 + (w[1] - u.z) ** 2)

    def move_tank_off(self, tank):
        """A foundation's gone down under a tank (it was laid there before the tank came): it
        goes to the nearest place round it with room for its hull."""
        for reach in (0.5 * k for k in range(1, 21)):
            for k in range(16):
                a = k * math.pi / 8
                x, z = tank.x + math.sin(a) * reach, tank.z + math.cos(a) * reach
                if Tank.room_at(self.world, x, z, tank.yaw):
                    tank.x, tank.z = x, z
                    tank.path = []
                    return

    @property
    def workers(self):
        return [u for u in self.units if isinstance(u, Worker) and u.alive]

    # ------------------------------------------------------------ trenches

    @property
    def diggers(self):
        return [u for u in self.selected if isinstance(u, Soldier)]

    def start_placing_trench(self):
        if self.diggers and not self.over:
            self.placing_turret = False
            self.placing_building = None
            self.order_aim = None
            self.placing_trench = True
            self.trench_aim = None

    def aim_trench(self, x, z):
        if x is None:
            self.trench_aim = None
            return
        self.trench_aim = (math.floor(x), math.floor(z))
        there = self.world.trenches.get(self.trench_aim)
        self.trench_fits = self.trench_tile_fits(*self.trench_aim) or bool(there and there.blueprint)

    def trench_tile_fits(self, i, j):
        """Can a trench be dug here: bare earth, and no turret laid out on it?"""
        return self.world.can_dig(i, j) and not self.turret_at(i, j) and not self.building_on(i, j)

    def start_trench_row(self, point):
        """The left button goes down while placing: the first tile of a trench line."""
        self.trench_row, self.trench_cancel = [], []
        self.trench_from, self.trench_last = point, None
        if point:
            self.extend_trench_row(point)

    def extend_trench_row(self, point):
        """Take in the tiles the mouse has crossed since last time."""
        if not point:
            return
        a = self.trench_from or point
        steps = max(1, int(math.dist(a, point) / 0.25))
        for k in range(steps + 1):
            t = k / steps
            tile = math.floor(a[0] + (point[0] - a[0]) * t), math.floor(a[1] + (point[1] - a[1]) * t)
            last = self.trench_last
            if last and tile != last and tile[0] != last[0] and tile[1] != last[1]:
                self.take_trench_tile((tile[0], last[1]))      # round the corner, so the line stays joined
            self.take_trench_tile(tile)
            self.trench_last = tile
        self.trench_from = point

    def take_trench_tile(self, tile):
        """A new trench on this tile if it's free; a blueprint here is called off."""
        there = self.world.trenches.get(tile)
        if tile in self.trench_row or there in self.trench_cancel:
            return
        if there and there.blueprint:
            self.trench_cancel.append(there)
        elif self.trench_tile_fits(*tile):
            self.trench_row.append(tile)

    def finish_trench_row(self, point, queue=False):
        """The left button is let go: call off the blueprints crossed, and lay out the new line.
        With Shift (queue), the soldiers dig it after their other orders, and more can be laid."""
        self.extend_trench_row(point)
        row, cancel = self.trench_row, self.trench_cancel
        self.trench_row, self.trench_cancel, self.trench_from = None, [], None
        self.placing_trench = queue
        self.trench_aim = None
        if not row and not cancel:
            self.say("A trench needs bare earth: not concrete, a turret's tile or a building's.")
            return
        for blueprint in cancel:
            blueprint.cancel()
        laid = []
        for i, j in row:
            trench = Trench(self.world, i, j)
            self.world.trenches[i, j] = trench
            self.markers.append([trench.x, trench.z, 0.0, SELECT_GREEN])
            laid.append(trench)
        if laid:
            for soldier in self.diggers:
                soldier.order(Build(laid), queue)

    def held_tiles(self, moving):
        """The tiles everyone but these units is standing on, or will be once their orders are done."""
        held = set()
        for unit in self.units:
            if unit.alive and unit not in moving:
                x, z = unit.plan_end()
                held.add((math.floor(x), math.floor(z)))
        return held

    def free_trenches(self, moving, x, z):
        """The finished trenches near (x, z) with nobody else in them, the nearest first."""
        held = self.held_tiles(moving)
        free = [t for t in self.world.trenches.values()
                if t.built and (t.i, t.j) not in held and math.dist((t.x, t.z), (x, z)) <= TRENCH_REACH]
        return sorted(free, key=lambda t: math.dist((t.x, t.z), (x, z)))

    def ground_near(self, x, z, held):
        """The middle of the nearest tile of open ground to (x, z) that nobody has taken."""
        i0, j0 = math.floor(x), math.floor(z)
        tiles = [(i, j) for i in range(i0 - 6, i0 + 7) for j in range(j0 - 6, j0 + 7)
                 if self.world.can_build_turret(i, j) and (i, j) not in held]
        if not tiles:
            return x, z
        i, j = min(tiles, key=lambda t: (t[0] + 0.5 - x) ** 2 + (t[1] + 0.5 - z) ** 2)
        return i + 0.5, j + 0.5

    def man_trenches(self, x, z, queue=False, units=None):
        """Send the selected units (or these) into the free trenches nearest (x, z), one to a
        tile. Anyone left over stands on the open ground beside them."""
        units = self.selected if units is None else units
        spots = [(t.x, t.z) for t in self.free_trenches(units, x, z)[:len(units)]]
        held = self.held_tiles(units) | {(math.floor(a), math.floor(b)) for a, b in spots}
        while len(spots) < len(units):
            spot = self.ground_near(x, z, held)
            held.add((math.floor(spot[0]), math.floor(spot[1])))
            spots.append(spot)
        send_to_spots(units, spots, queue=queue)

    def fit_spots(self, spots):
        """Spots that fall in a dug trench become the middle of its tile, one unit to a tile
        (there's no room for two); anyone else stands on the open ground nearby."""
        held = self.held_tiles(self.selected)
        fitted = []
        for x, z in spots:
            trench = self.world.trench_at(x, z)
            if trench and trench.started:
                x, z = (trench.x, trench.z) if (trench.i, trench.j) not in held else self.ground_near(x, z, held)
                held.add((math.floor(x), math.floor(z)))
            fitted.append((x, z))
        return fitted

    # ------------------------------------------------------------ selecting and commanding

    def select_hq(self):
        self.clear_selection()
        self.hq_selected = True

    def select_structure(self, structure):
        self.clear_selection()
        self.structure_selected = structure

    def select_deposit(self, deposit):
        self.clear_selection()
        self.deposit_selected = deposit

    def select_units(self, units, add=False):
        if add:
            units = self.selected + [u for u in units if u not in self.selected]
        self.clear_selection()
        self.selected = list(units)

    def select_kind_on_screen(self, kind, add=False):
        """Select every unit of this kind that's on the screen (a double click on one)."""
        view_proj = self.camera.view_proj()
        on_screen = []
        for unit in self.units:
            p = unit.alive and type(unit) is kind and self.camera.to_screen(unit.x, 0.5 * unit.SIZE, unit.z,
                                                                              *self.size, view_proj)
            if p and 0 <= p[0] < WIDTH and 0 <= p[1] < HEIGHT:
                on_screen.append(unit)
        self.select_units(on_screen, add)

    def clear_selection(self):
        self.selected = []
        self.hq_selected = False
        self.structure_selected = None
        self.deposit_selected = None
        self.placing_turret = False
        self.placing_trench = False
        self.order_aim = None

    def set_group(self, n):
        """Make the selected units group n (they leave any other group)."""
        for group in self.groups.values():
            group[:] = [u for u in group if u not in self.selected]
        self.groups[n] = list(self.selected)
        if self.selected:
            self.say(f"Group {n}: {self.selection_title()}")

    def recall_group(self, n, add=False):
        """Select group n again; called up twice in a row, the camera goes to it too."""
        units = [u for u in self.groups.get(n, []) if u.alive]
        if not units:
            return
        now = pygame.time.get_ticks()
        if self.last_group[0] == n and now - self.last_group[1] < DOUBLE_CLICK:
            self.camera.look_at(sum(u.x for u in units) / len(units), sum(u.z for u in units) / len(units))
        self.last_group = (n, now)
        self.select_units(units, add)

    def group_of(self, unit):
        return next((n for n, group in self.groups.items() if unit in group), None)

    def idle_engineers(self):
        """The engineers standing about with no orders (one on guard or on patrol isn't idle)."""
        return [u for u in self.units if u.alive and isinstance(u, Engineer) and not u.orders]

    def go_to_idle_engineer(self):
        """The idle button (or I): select the next idle engineer, and the camera goes to him.
        Each press goes on to the next one, round them all in turn."""
        idle = self.idle_engineers()
        if not idle or self.over:
            return
        after = self.units.index(self.last_idle) + 1 if self.last_idle in self.units else 0
        unit = next((u for u in self.units[after:] if u in idle), idle[0])
        self.last_idle = unit
        self.select_units([unit])
        self.camera.look_at(unit.x, unit.z)

    def trainer_for(self, kind):
        """What trains this kind: the HQ, or the vehicle factory selected (if it's ready). None if neither."""
        if kind in self.base.TRAINS:
            return self.base
        t = self.structure_selected
        if isinstance(t, VehicleFactory) and t.ready and kind in t.TRAINS:
            return t
        return None

    def train(self, kind, n=1):
        """Put n of a kind on the queue of what trains it (the HQ, or the vehicle factory
        selected). Each is paid for as it's trained (Trainer.train_step)."""
        trainer = self.trainer_for(kind)
        if not self.over and trainer:
            for _ in range(n):
                trainer.enqueue(kind)

    def untrain(self, kind, n=1):
        """Take up to n of a kind off its trainer's queue, the last first (what's been paid
        for the one in training comes back)."""
        trainer = self.trainer_for(kind)
        for _ in range(n if trainer else 0):
            trainer.dequeue(kind, self.base.stores)

    def give_test_gift(self):
        """The + button: add a load of each material, for testing."""
        self.base.stores.add(TEST_GIFT)

    def toggle_pause(self):
        if not self.over:
            self.paused = not self.paused

    def toggle_speed(self):
        """Double speed, or back to normal: everything in the game goes twice as fast (the
        camera and the mouse don't)."""
        self.speed = 1 if self.speed == FAST else FAST

    def split_tanks(self):
        """The selected tanks, and everyone else selected: tanks keep TANK_ROOM apart, and
        never go into trenches."""
        tanks = [u for u in self.selected if isinstance(u, Tank)]
        return tanks, [u for u in self.selected if not isinstance(u, Tank)]

    def command_move(self, x, z, queue=False):
        """Move there, each to his own spot: in a block round it (the men round the tanks), or
        into the trenches there."""
        self.markers.append([x, z, 0.0, SELECT_GREEN])
        tanks, men = self.split_tanks()
        if tanks:
            send_to_spots(tanks, formation(len(tanks), x, z, TANK_ROOM), queue=queue)
        trench = self.world.trench_at(x, z)
        if not men:
            pass
        elif trench and trench.built:                  # a click on a trench: get in
            self.man_trenches(x, z, queue, men)
        else:
            spots = formation(len(men), x, z) if not tanks else self.spots_round_tanks(len(men), x, z, len(tanks))
            send_to_spots(men, self.fit_spots(spots), queue=queue)

    def spots_round_tanks(self, n, x, z, tanks):
        """n spots for men round (x, z), nearest the middle first, but clear of where `tanks`
        tanks will stand in their block there."""
        taken = formation(tanks, x, z, TANK_ROOM)
        spots, size = [], n + tanks * 30
        while len(spots) < n:
            spots = [s for s in formation(size, x, z) if all(math.dist(s, t) > Tank.RADIUS + 0.5 for t in taken)]
            size *= 2
        return spots[:n]

    def command_line(self, a, b, queue=False):
        """Line up along the drag, facing away from where they are: tanks on the line, the men
        in a line behind them."""
        self.markers.append([*b, 0.0, SELECT_GREEN])
        cx = sum(u.x for u in self.selected) / len(self.selected)
        cz = sum(u.z for u in self.selected) / len(self.selected)
        tanks, men = self.split_tanks()
        back = (0.0, 0.0)
        if tanks:
            spots, yaw = line_formation(len(tanks), a, b, (cx, cz), TANK_ROOM)
            send_to_spots(tanks, spots, lambda u, x, z: Move(x, z, yaw), queue)
            back = (-math.sin(yaw) * (Tank.RADIUS + 1.0), -math.cos(yaw) * (Tank.RADIUS + 1.0))
        if men:
            a2, b2 = (a[0] + back[0], a[1] + back[1]), (b[0] + back[0], b[1] + back[1])
            spots, yaw = line_formation(len(men), a2, b2, (cx, cz))
            send_to_spots(men, self.fit_spots(spots), lambda u, x, z: Move(x, z, yaw), queue)

    def command_patrol(self, x, z, queue=False):
        """Patrol from where they are (or will be, queued) to (x, z) and back, each to his own spot there."""
        self.markers.append([x, z, 0.0, Patrol.COLOR])
        tanks, men = self.split_tanks()

        def patrol(u, px, pz):
            return Patrol(u.plan_end() if queue else (u.x, u.z), (px, pz))
        if tanks:
            send_to_spots(tanks, formation(len(tanks), x, z, TANK_ROOM), patrol, queue)
        if men:
            spots = self.spots_round_tanks(len(men), x, z, len(tanks)) if tanks else formation(len(men), x, z)
            send_to_spots(men, spots, patrol, queue)

    def command_on(self, thing, queue=False):
        """A right click on one of your own (a unit, a turret or the HQ): engineers build or
        repair it if it needs it, and everyone else guards it. False if nobody could take
        the order (nobody guards himself)."""
        units = [u for u in self.selected if u is not thing]
        if not units:
            return False
        for unit in units:
            if unit.can_work_on(thing) and thing.needs_work:
                order = Repair(thing) if thing.built else Build([thing])
            else:
                order = Guard(thing)
            unit.order(order, queue)
        self.markers.append([thing.x, thing.z, 0.0, order.COLOR])
        return True

    def command_remove(self, structure, queue=False):
        """The selected engineers take a turret or a building down (built, or being built).
        A blueprint just goes."""
        if structure.blueprint:
            self.call_off(structure)
            return
        for engineer in self.engineers:
            engineer.order(Remove(structure), queue)
        self.markers.append([structure.x, structure.z, 0.0, Remove.COLOR])

    def call_off(self, site):
        """Call a blueprint off (nothing's been paid for it: the work never started)."""
        site.cancel()
        if site is self.structure_selected:
            self.structure_selected = None

    def tidy_blueprints(self):
        """A blueprint lasts only while some worker means to build it: once none has it in his
        orders (they were given others, or stopped, or fell), it goes, as in Beyond All Reason.
        A turret is coming down while an engineer has orders to take it down."""
        wanted, coming_down = set(), set()
        for worker in self.workers:
            if worker.job:
                wanted.add(worker.job)
            for order in worker.orders:
                if isinstance(order, Build):
                    wanted.update(order.sites)
                elif isinstance(order, Remove):
                    coming_down.add(order.structure)
        for structure in self.turrets + self.buildings:
            structure.coming_down = structure in coming_down
            if structure.blueprint and structure not in wanted:
                self.call_off(structure)
        for trench in list(self.world.trenches.values()):
            if trench.blueprint and trench not in wanted:
                self.call_off(trench)

    def command_stop(self):
        """Every selected unit drops his orders and stands (and any choosing of where to go ends)."""
        self.order_aim = None
        for unit in self.selected:
            unit.stop()

    @property
    def gunners(self):
        """The selected units with guns: soldiers and tanks."""
        return [u for u in self.selected if u.armed]

    def cycle_fire_state(self):
        """The next fire state, for all the selected gunners (from the first one's)."""
        if self.gunners:
            state = FIRE_STATES[(FIRE_STATES.index(self.gunners[0].fire_state) + 1) % len(FIRE_STATES)]
            for unit in self.gunners:
                unit.fire_state = state

    def aim_order(self, name):
        """Choose where a patrol goes (the next left click on the ground), or which turret or
        building the engineers take down (the next left click on one)."""
        if self.selected and not self.over and (name != "remove" or self.engineers):
            self.placing_turret = self.placing_trench = False
            self.placing_building = None
            self.order_aim = name

    def give_aimed_order(self, point, queue=False):
        """The ground was clicked while choosing where a patrol goes. With Shift (queue), it's
        added after their other orders, and another spot can be clicked."""
        if point:
            self.command_patrol(*point, queue)
        if not queue:
            self.order_aim = None

    def line_preview(self):
        """While a right drag is held: where each selected unit would stand, and which way
        they'd face. None if it's too short to be a line yet."""
        if not (self.line_from and self.selected):
            return None
        b = self.camera.ground_point(*pygame.mouse.get_pos(), *self.size)
        if not b or math.dist(self.line_from, b) < LINE_MIN:
            return None
        cx = sum(u.x for u in self.selected) / len(self.selected)
        cz = sum(u.z for u in self.selected) / len(self.selected)
        return line_formation(len(self.selected), self.line_from, b, (cx, cz))

    def command_attack(self, zombie, queue=False):
        """The selected gunners go after a zombie (the others keep to what they were doing)."""
        self.markers.append([zombie.x, zombie.z, 0.0, ENEMY_RED])
        for unit in self.gunners:
            unit.order(Attack(zombie), queue)

    def thing_under(self, pos):
        """The unit, zombie, turret, building, deposit or HQ (self.base) under the mouse (the
        nearest, if they overlap), or None."""
        origin, direction = self.camera.ray(pos[0], pos[1], *self.size)
        best, best_t = None, float("inf")
        for thing in self.units + self.zombies + [t for t in self.turrets + self.buildings if t.alive] + self.deposits:
            t = thing.ray_hit(origin, direction)
            if t is not None and t < best_t:
                best, best_t = thing, t
        t = self.base.ray_hit(origin, direction)
        if t is not None and t < best_t:
            best = self.base
        return best

    def click_select(self, pos, add):
        thing = self.thing_under(pos)
        now = pygame.time.get_ticks()
        double = thing is self.last_click[0] and now - self.last_click[1] < DOUBLE_CLICK
        self.last_click = (thing, now)
        if thing is self.base:
            self.select_hq()
        elif isinstance(thing, Structure):
            self.select_structure(thing)
        elif isinstance(thing, Deposit):
            self.select_deposit(thing)
        elif isinstance(thing, Trooper):
            if double:
                self.select_kind_on_screen(type(thing), add)
            elif add and thing in self.selected:
                self.selected.remove(thing)
            else:
                self.select_units([thing], add)
        elif not add:
            self.clear_selection()

    def box_select(self, a, b, add):
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        view_proj = self.camera.view_proj()
        inside = []
        for unit in self.units:
            p = self.camera.to_screen(unit.x, 0.5 * unit.SIZE, unit.z, *self.size, view_proj)
            if unit.alive and p and x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
                inside.append(unit)
        if inside or not add:
            self.select_units(inside, add)

    # ------------------------------------------------------------ input

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.on_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.on_press(event.button, event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                self.on_release(event.button, event.pos)
            elif event.type == pygame.MOUSEMOTION and self.turning:
                self.camera.turn(-event.rel[0] * 0.008)
            elif event.type == pygame.MOUSEWHEEL:
                self.camera.zoom(event.y)

    def button_at(self, pos):
        """The panel button under the mouse, as (what, the button's rect), or None."""
        layout = self.panel_layout()
        for what, rect in (layout or {}).get("buttons", []):
            if rect.collidepoint(pos):
                return what, rect
        return None

    def on_press(self, button, pos):
        layout = self.panel_layout()
        hit = self.button_at(pos)
        on_panel = layout and layout["panel"].collidepoint(pos)
        queue = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        if button == 2:
            self.turning = True
        elif self.over:
            return
        elif button == 1 and PAUSE_BUTTON.collidepoint(pos):
            self.toggle_pause()
        elif button == 1 and SPEED_BUTTON.collidepoint(pos):
            self.toggle_speed()
        elif button == 1 and GIFT_BUTTON.collidepoint(pos):
            self.give_test_gift()
        elif button == 1 and IDLE_PANEL.collidepoint(pos) and self.idle_engineers():
            self.go_to_idle_engineer()
        elif button == 1:
            if hit:
                what = hit[0]
                if what in (Turret, MinigunTurret):
                    self.start_placing_turret(what)
                elif what in BUILDINGS:
                    self.start_placing_building(what)
                elif what is Trench:
                    self.start_placing_trench()
                elif what in AIMED_ORDERS:
                    self.aim_order(what)
                elif what == "stop":
                    self.command_stop()
                elif what == "fire":
                    self.cycle_fire_state()
                elif what == "switch":
                    self.switch_building()
                else:
                    self.train(what, how_many())
            elif on_panel:
                pass
            elif self.order_aim == "remove":   # which turret or factory to take down
                thing = self.thing_under(pos)
                if isinstance(thing, Structure):
                    self.command_remove(thing, queue)
                if not queue:
                    self.order_aim = None
            elif self.order_aim:           # where a patrol goes
                self.give_aimed_order(self.camera.ground_point(pos[0], pos[1], *self.size), queue)
            elif self.placing_turret:      # a turret, or the start of a row of them (decided when it's let go)
                point = self.camera.ground_point(pos[0], pos[1], *self.size)
                self.aim_turret(*(point or (None, None)))
                self.start_turret_row(point)
            elif self.placing_building:    # a building, there
                point = self.camera.ground_point(pos[0], pos[1], *self.size)
                self.aim_building(*(point or (None, None)))
                self.place_building(queue)
            elif self.placing_trench:      # a tile of trench, or the start of a line of it
                point = self.camera.ground_point(pos[0], pos[1], *self.size)
                self.aim_trench(*(point or (None, None)))
                self.start_trench_row(point)
            else:
                self.drag_from = pos
        elif button == 3:
            if self.placing_turret or self.placing_trench or self.placing_building or self.order_aim:
                self.placing_turret = self.placing_trench = False
                self.placing_building = None
                self.order_aim = None
            elif hit:
                if isinstance(hit[0], type) and issubclass(hit[0], Trooper):
                    self.untrain(hit[0], how_many())
            elif on_panel:
                pass
            elif self.selected:
                thing = self.thing_under(pos)
                if isinstance(thing, Zombie) and self.gunners:
                    self.command_attack(thing, queue)
                elif thing and not isinstance(thing, (Zombie, Deposit)) and self.command_on(thing, queue):
                    pass
                else:
                    point = self.camera.ground_point(pos[0], pos[1], *self.size)
                    trench = self.world.trench_at(*point) if point else None
                    if trench and not trench.built and self.diggers:      # back to digging it
                        for soldier in self.diggers:
                            soldier.order(Build([trench]), queue)
                        self.markers.append([trench.x, trench.z, 0.0, Build.COLOR])
                    else:   # a move: a click, or a drag to line them up (decided when it's let go)
                        self.line_from = point
            elif self.hq_selected or isinstance(self.structure_selected, VehicleFactory):
                point = self.camera.ground_point(pos[0], pos[1], *self.size)
                if point:
                    (self.base if self.hq_selected else self.structure_selected).rally = point
                    self.markers.append([*point, 0.0, SELECT_GREEN])

    def on_release(self, button, pos):
        queue = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        if button == 2:
            self.turning = False
        elif button == 1 and self.turret_row is not None:
            if self.placing_turret and not self.over:
                self.finish_turret_row(self.camera.ground_point(pos[0], pos[1], *self.size), queue)
            self.turret_row = self.row_from = None
        elif button == 1 and self.trench_row is not None:
            if self.placing_trench and not self.over:
                self.finish_trench_row(self.camera.ground_point(pos[0], pos[1], *self.size), queue)
            self.trench_row = self.trench_from = None
        elif button == 3 and self.line_from:
            start, self.line_from = self.line_from, None
            if not self.selected or self.over:
                return
            end = self.camera.ground_point(pos[0], pos[1], *self.size) or start
            if math.dist(start, end) < LINE_MIN:
                self.command_move(*start, queue)
            else:
                self.command_line(start, end, queue)
        elif button == 1 and self.drag_from:
            add = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
            start, self.drag_from = self.drag_from, None
            if abs(pos[0] - start[0]) < DRAG_MIN and abs(pos[1] - start[1]) < DRAG_MIN:
                self.click_select(pos, add)
            else:
                self.box_select(start, pos, add)

    def on_key(self, key):
        mods = pygame.key.get_mods()
        if key == pygame.K_ESCAPE:
            if self.placing_turret or self.placing_trench or self.placing_building or self.order_aim:
                self.placing_turret = self.placing_trench = False
                self.placing_building = None
                self.order_aim = None
            elif self.selected or self.hq_selected or self.structure_selected or self.deposit_selected:
                self.clear_selection()
            elif self.quit_asked is not None and pygame.time.get_ticks() - self.quit_asked < QUIT_AGAIN:
                self.running = False
            else:                                      # (once by mistake shouldn't end the game: it asks)
                self.quit_asked = pygame.time.get_ticks()
                self.say("Press Esc again to quit.")
        elif key == pygame.K_r and self.over:
            self.new_game()
        elif key == pygame.K_r and self.engineers:
            self.start_placing_building(RadarStation)
        elif key == pygame.K_SPACE:
            self.camera.look_at(*self.home)
        elif key == pygame.K_PAUSE:
            self.toggle_pause()
        elif key == pygame.K_f:
            self.toggle_speed()
        elif key == pygame.K_o and isinstance(self.structure_selected, Maker):
            self.switch_building()
        elif key == pygame.K_i:
            self.go_to_idle_engineer()
        elif key == pygame.K_t and self.hq_selected:
            self.train(Soldier, how_many())
        elif key == pygame.K_g and self.hq_selected:
            self.train(Engineer, how_many())
        elif key == pygame.K_t and isinstance(self.structure_selected, VehicleFactory):
            self.train(Tank, how_many())
        elif key == pygame.K_v and self.engineers:
            self.start_placing_building(VehicleFactory)
        elif key == pygame.K_b and self.engineers:
            self.start_placing_turret()
        elif key == pygame.K_m and self.engineers:
            self.start_placing_turret(MinigunTurret)
        elif key == pygame.K_n and self.engineers:
            self.start_placing_building(Factory)
        elif key == pygame.K_j and self.engineers:
            self.start_placing_building(SalvageCrane)
        elif key == pygame.K_k and self.engineers:
            self.start_placing_building(LoadingDock)
        elif key == pygame.K_c and self.diggers:
            self.start_placing_trench()
        elif key == pygame.K_p and self.selected:
            self.aim_order("patrol")
        elif key == pygame.K_h and self.selected:
            self.command_stop()
        elif key == pygame.K_x and self.engineers:
            self.aim_order("remove")
        elif key == pygame.K_l and self.selected:
            self.cycle_fire_state()
        elif pygame.K_0 <= key <= pygame.K_9:
            if mods & pygame.KMOD_CTRL:
                self.set_group(key - pygame.K_0)
            else:
                self.recall_group(key - pygame.K_0, add=bool(mods & pygame.KMOD_SHIFT))

    # ------------------------------------------------------------ update

    def update(self, dt, edge_scroll=True):
        keys = pygame.key.get_pressed()
        forward = (keys[pygame.K_w] or keys[pygame.K_UP]) - (keys[pygame.K_s] or keys[pygame.K_DOWN])
        right = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        if edge_scroll and pygame.mouse.get_focused() and not self.drag_from:
            mx, my = pygame.mouse.get_pos()
            right += (mx >= WIDTH - EDGE_SCROLL) - (mx < EDGE_SCROLL)
            forward += (my < EDGE_SCROLL) - (my >= HEIGHT - EDGE_SCROLL)
        if forward or right:
            self.camera.pan(mathx.clamp(forward, -1, 1), mathx.clamp(right, -1, 1), dt)
        turn = keys[pygame.K_q] - keys[pygame.K_e]
        if turn:
            self.camera.turn(turn * TURN_SPEED * dt)
        self.camera.update(dt)

        mouse = pygame.mouse.get_pos()
        if not self.screenshot:
            point = self.camera.ground_point(*mouse, *self.size) or (None, None)
            if self.placing_turret:
                self.aim_turret(*point)
                if self.turret_row is not None and point[0] is not None:
                    self.extend_turret_row(point)
            elif self.placing_trench:
                self.aim_trench(*point)
                if self.trench_row is not None and point[0] is not None:
                    self.extend_trench_row(point)
            elif self.placing_building:
                self.aim_building(*point)
        if not self.over and not self.paused:
            self.sounds.new_frame()
            for _ in range(self.speed):                 # (at double speed, two steps a frame)
                self.fight(dt)
        if not self.over:
            self.tidy_blueprints()                  # (orders can change while paused, too)

        layout = self.panel_layout()
        over_panel = (layout and layout["panel"].collidepoint(mouse)) or any(
            r.collidepoint(mouse) for r in (PAUSE_BUTTON, SPEED_BUTTON, STORES_PANEL, GIFT_BUTTON)) or (
            IDLE_PANEL.collidepoint(mouse) and self.idle_engineers())
        self.hover = None if (self.screenshot or over_panel) else self.thing_under(mouse)
        for marker in self.markers:
            marker[2] += dt
        self.markers = [m for m in self.markers if m[2] < MARKER_TIME]
        played = 0.0 if self.paused else dt * self.speed   # shots and splashes stand still while paused
        for shot in self.shots:
            shot[2] += played
        self.shots = [s for s in self.shots if s[2] < TRACER_TIME]
        for splash in self.splashes:
            splash[3] += played
        self.splashes = [s for s in self.splashes if s[3] < SPLASH_TIME]
        for puff in self.dust:
            puff[3] += played
        self.dust = [d for d in self.dust if d[3] < DUST_TIME]
        for shell in self.shells:
            shell[2] += played
        self.shells = [s for s in self.shells if s[2] < SHELL_TIME]
        for blast in self.blasts:
            blast[3] += played
        self.blasts = [b for b in self.blasts if b[3] < BLAST_TIME]
        for scorch in self.scorches:
            scorch[2] += played
        self.scorches = [s for s in self.scorches if s[2] < SCORCH_TIME]
        while self.world.promoted:
            self.levels_up.append([self.world.promoted.pop(), 0.0])
        for rise in self.levels_up:
            rise[1] += played
        self.levels_up = [r for r in self.levels_up if r[1] < LEVEL_UP_TIME and r[0].alive]
        if self.message:
            text, left = self.message
            self.message = (text, left - dt) if left > dt else None
        bullets = self.base.stores.bullets
        if bullets <= 0 and not self.out_of_bullets and not self.over:   # (not again for every batch a factory makes)
            self.say("Out of bullets: no gun can fire.")
            self.out_of_bullets = True
        elif bullets >= BULLETS_AGAIN:
            self.out_of_bullets = False
        if self.base.stores.full("bullets") and not self.bullets_full and not self.over:
            self.say(f"Bullets full ({MOST['bullets']}): the bullet factories wait till some are used.")
            self.bullets_full = True
        elif bullets <= MOST["bullets"] - BULLETS_AGAIN:
            self.bullets_full = False

    def fight(self, dt):
        """A moment of the game: training, the waves, the dead attacking, building and shooting."""
        self.played += dt
        new = self.base.update(dt)
        if new:
            self.units.append(new)
        hungry = self.base.feed(dt, [u for u in self.units if u.alive])
        if hungry:
            self.say(f"Not enough supply: {hungry} of your troops go hungry (slower, and they miss more).")
        wave = self.waves.update(dt)
        if wave:
            side, zombies = wave
            self.zombies += zombies
            spitters = sum(isinstance(z, Spitter) for z in zombies)
            self.say(f"Wave {self.waves.number}: {len(zombies)} zombies from the {side}"
                     + (f", {spitters} of them spitting acid" if spitters else ""))

        living = [u for u in self.units if u.alive]
        structures = [t for t in self.turrets + self.buildings if t.alive]
        standing = [t for t in structures if t.started]   # not blueprints: the dead pass those by
        around = Around(self.zombies, self.workers, structures, self.base)
        for zombie in self.zombies:
            spit = zombie.think(dt, self.base, living, standing)
            if spit:
                self.spits.append(spit)
        for spit in self.spits:
            if spit.fly(dt):
                point = spit.land()
                self.splashes.append([*point, 0.0])
                pool = AcidPool(self.world, *point) if spit.struck is None else None
                if pool and pool.radius:                 # on the ground: a burning puddle, if there's room
                    self.pools.append(pool)
        self.spits = [s for s in self.spits if not s.landed]
        self.pools = [p for p in self.pools if not p.burn(dt, living)]
        for unit in living:
            if isinstance(unit, Tank):
                for gun, target in unit.fight(dt, self.zombies, self.base.stores):
                    if gun is unit:
                        self.fire_shell(unit, target)
                    else:
                        self.fire(gun.muzzle(), target, gun)
            target = unit.fight(dt, self.zombies, self.base.stores) if isinstance(unit, Gunner) else None
            if target:
                self.fire(mathx.apply(self.gun_matrix(unit), models.RIFLE_MUZZLE), target, unit)
                self.hear_shot(unit)
            done = unit.obey(dt, around)
            if isinstance(done, Build) and not unit.orders and any(isinstance(s, Trench) for s in done.laid):
                free = self.free_trenches([unit], unit.x, unit.z)
                if free:                                         # the digging's done: get in
                    unit.order(Move(free[0].x, free[0].z))
        for site in self.turrets + self.buildings + list(self.world.trenches.values()):   # every hand's work on it
            site.do_work(dt, self.base.stores)
        while self.world.new_walls:                              # a foundation's down: off its tile, all
            self.clear_tile(*self.world.new_walls.pop())
        for turret in self.turrets:
            target = turret.fight(dt, self.zombies, self.base.stores)
            if target:
                self.fire(turret.muzzle(), target, turret)
        for building in self.buildings:
            if building.update(dt, self.base.stores) and isinstance(building, Extractor):   # it has stripped its deposit
                self.say(f"The {building.deposit.NAME.lower()} is stripped bare: its {building.NAME.lower()} stands idle.")
            if isinstance(building, VehicleFactory):
                self.run_vehicle_factory(building, dt)
        if not self.opened and any(isinstance(b, RadarStation) and b.alive and b.built for b in self.buildings):
            self.open_map()
        for unit in self.units + self.zombies:
            unit.update(dt)
        keep_apart(self.units + self.zombies, self.world)

        fading = DEATH_TIME - FADE_TIME
        for body in self.units + self.zombies:
            if body.fall and body.fall.rests_on:     # a body on others fades when they do
                under = max(u.dead_for for u in body.fall.rests_on)
                if under >= fading and body.dead_for < under:
                    body.dead_for = under
            if body.gone and body.fall:              # faded away: other bodies may lie where it lay
                self.world.remove_body(body.fall.tiles)
                self.world.remove_tops(body, body.fall.top_cells)
        self.units = [u for u in self.units if not u.gone]
        self.zombies = [z for z in self.zombies if not z.gone]
        self.turrets = [t for t in self.turrets if not t.gone]
        self.buildings = [b for b in self.buildings if not b.gone]
        self.selected = [u for u in self.selected if u.alive]
        if self.structure_selected and not self.structure_selected.alive:
            self.structure_selected = None
        if not self.engineers:                       # no engineers left: no laying turrets or buildings, no taking them down
            self.placing_turret = False
            self.placing_building = None
            if self.order_aim == "remove":
                self.order_aim = None
        if self.placing_trench and not self.diggers:
            self.placing_trench = False
        if not self.base.alive:
            self.over = True
            self.spits = []
            self.clear_selection()

    def run_vehicle_factory(self, factory, dt):
        """A vehicle factory trains; a new tank joins the units. Wrecked or being taken down,
        what's on its queue is given back."""
        waiting = factory.blocked
        new = factory.train_step(dt, self.base.stores)
        if new:
            self.units.append(new)
        elif factory.blocked and not waiting:
            self.say("A tank is ready, but something's in the way of the vehicle factory's door.")
        if factory.queue and (not factory.alive or factory.coming_down):
            for kind in list(factory.queue):
                factory.dequeue(kind, self.base.stores)

    def open_map(self):
        """A radar station is up: the whole map is open, for good (the camera can go anywhere on
        it, and the dead come in from beyond its edge)."""
        self.opened = True
        self.world.open_all()
        self.camera.bounds = self.world.open
        self.gfx.set_open(self.world.open)
        n = self.world.size
        self.say(f"The radar station is up: the land all round is open ({n} by {n} tiles).")

    def hear_shot(self, unit):
        """The crack of his rifle: quiet, louder with the camera zoomed in and very low with it
        zoomed all the way out, quieter the further from where the camera looks, and from his
        side of the screen."""
        cam = self.camera
        tx, _, tz = cam.target
        p = cam.to_screen(unit.x, 1.0, unit.z, *self.size)
        pan = (p[0] / WIDTH * 2 - 1) if p else 0.0
        zoom = max(0.0, (cam.PLAY_DIST - cam.dist) / (cam.PLAY_DIST - cam.MIN_DIST))   # (past PLAY_DIST, as low as it goes)
        self.sounds.rifle_shot(math.hypot(unit.x - tx, unit.z - tz), pan, zoom)

    def fire(self, muzzle, target, shooter):
        """A shot at `target`. Whether it's on target goes by how far off the target is
        (Fighter.hit_chance): on target, it flies straight at it; off target, it goes by its
        side (MISS_BY). Either way it hits the first zombie in its way, which needn't be the
        one aimed at. One that hits none flies on into the dirt a little past its target, or
        into a wall, and kicks up dust there."""
        dx, dz = target.x - muzzle[0], target.z - muzzle[2]
        heading, reach = math.atan2(dx, dz), math.hypot(dx, dz)
        if random.random() >= shooter.hit_chance(math.hypot(target.x - shooter.x, target.z - shooter.z)):
            by = target.RADIUS + random.uniform(*MISS_BY)
            heading += math.atan2(by, max(reach, 0.1)) * random.choice((-1, 1))
        zombie, end = self.bullet(muzzle, heading, reach, shooter)
        self.shots.append([muzzle, end, 0.0])
        self.fired.append(self.played)
        if zombie is None:
            self.dust.append([*end, 0.0])
        elif zombie.hurt(shooter.damage(), (shooter.x, shooter.z)):
            self.kills += 1
            shooter.count_kill()
            if isinstance(zombie, Spitter):          # it bursts: acid flies out all round
                for k in range(6):
                    a = k * math.pi / 3
                    self.splashes.append([zombie.x + math.sin(a) * 0.3, 0.5 + 0.12 * (k % 3) - zombie.sink,
                                          zombie.z + math.cos(a) * 0.3, 0.0])

    def fire_shell(self, tank, target):
        """A tank's main gun fires a shell at `target`. On target (Tank.hit_chance), it flies
        straight at it; off target, at a spot beside it, MISS_BY off. It bursts on the first
        zombie in its way, or a wall, or the ground a little past where it was aimed (as a
        bullet would come down there), and the blast does its damage round there."""
        muzzle = tank.muzzle()
        tx, tz = target.x, target.z
        if random.random() >= tank.hit_chance(tank.distance_to(target)):
            dx, dz = tx - muzzle[0], tz - muzzle[2]
            d = max(math.hypot(dx, dz), 1e-6)
            by = random.uniform(*tank.MISS_BY) * random.choice((-1, 1))
            tx, tz = tx - dz / d * by, tz + dx / d * by
        dx, dz = tx - muzzle[0], tz - muzzle[2]
        zombie, end = self.bullet(muzzle, math.atan2(dx, dz), math.hypot(dx, dz), tank)
        self.shells.append([muzzle, end, 0.0])
        self.fired.extend([self.played] * tank.SHELL.bullets)
        self.blast(end, tank.damage(), tank, zombie, on_ground=zombie is None and end[1] <= 0.05)
        self.hear_cannon(tank, end)

    def blast(self, point, damage, tank, struck=None, on_ground=True):
        """A shell bursts at `point`, on the zombie it `struck` (if any): that one takes all its
        `damage`, and every other zombie within the tank's BLAST of it, with no wall between,
        takes the blast's damage there (Tank.blast_damage: less toward its edge). Any it kills
        fall away from it. Our own take none. It leaves a scorch on the ground."""
        x, y, z = point
        for zombie in self.zombies:
            if not zombie.alive:
                continue
            d = 0.0 if zombie is struck else math.hypot(zombie.x - x, zombie.z - z)
            hit = tank.blast_damage(damage, d)
            if hit and self.world.line_clear(x, z, zombie.x, zombie.z) and zombie.hurt(hit, (x, z)):
                self.kills += 1
                tank.count_kill()
                if isinstance(zombie, Spitter):          # it bursts: acid flies out all round
                    for k in range(6):
                        a = k * math.pi / 3
                        self.splashes.append([zombie.x + math.sin(a) * 0.3, 0.5 + 0.12 * (k % 3) - zombie.sink,
                                              zombie.z + math.cos(a) * 0.3, 0.0])
        self.blasts.append([x, max(y, 0.1), z, 0.0])
        if on_ground or y < 0.8:
            self.scorches.append([x, z, 0.0])

    def hear_cannon(self, tank, burst):
        """The boom of a tank's main gun, and the bang of its shell bursting, each as loud as
        a shot is (but louder) for where it is on the screen and how far the camera's out."""
        cam = self.camera
        tx, _, tz = cam.target
        zoom = max(0.0, (cam.PLAY_DIST - cam.dist) / (cam.PLAY_DIST - cam.MIN_DIST))
        for x, z, kind in ((tank.x, tank.z, "cannon"), (burst[0], burst[2], "blast")):
            p = cam.to_screen(x, 1.0, z, *self.size)
            pan = (p[0] / WIDTH * 2 - 1) if p else 0.0
            self.sounds.boom(kind, math.hypot(x - tx, z - tz), pan, zoom)

    def bullet(self, muzzle, heading, reach, shooter):
        """Where one bullet goes, flying straight along `heading`: (the zombie it hits, or None;
        where it stops). With nothing in its way it comes down in the dirt, BULLET_PAST beyond
        `reach` (how far off its target was), its line sloping down from the muzzle to there."""
        world = self.world
        x0, y0, z0 = muzzle
        ux, uz = math.sin(heading), math.cos(heading)
        length = reach + random.uniform(*BULLET_PAST)
        wall = world.wall_along(x0, z0, ux, uz, length, (shooter.i, shooter.j) if isinstance(shooter, Turret) else None)
        far = length if wall is None else max(0.0, wall - 0.05)
        first, nearest = None, far
        for zombie in self.zombies:                  # the first one whose body its line crosses
            if not zombie.alive:
                continue
            ox, oz = zombie.x - x0, zombie.z - z0
            along, side = ox * ux + oz * uz, ox * uz - oz * ux
            r = zombie.RADIUS
            if along > 0 and abs(side) < r and along - r <= nearest:
                t = max(0.0, along - math.sqrt(r * r - side * side))
                if t <= nearest:
                    first, nearest = zombie, t
        if first:
            return first, (x0 + ux * nearest, 0.75 * first.SIZE - first.sink, z0 + uz * nearest)
        x, z = x0 + ux * far, z0 + uz * far
        y = y0 * (1 - far / length) if wall is not None else -world.floor_depth(x, z)
        return None, (x, y, z)

    # ------------------------------------------------------------ drawing

    def refresh_trenches(self):
        """Build the trenches' mesh afresh, and cut their tiles out of the ground, if one has changed."""
        if self.trenches_drawn == self.world.trench_changes:
            return
        self.trenches_drawn = self.world.trench_changes
        dug = [t for t in self.world.trenches.values() if t.started]
        if self.trench_mesh:
            self.trench_mesh.release()
        self.trench_mesh = self.gfx.mesh(models.build_trenches(dug)) if dug else None
        self.gfx.set_holes([(t.i, t.j) for t in dug])

    def draw(self):
        gfx = self.gfx
        self.layouts = 0           # bodies laid out this frame (see draw_fallen)
        self.refresh_trenches()
        hq = self.base.hq
        gfx.set_hq_ground(self.world.apron, self.slab_of(hq.i, hq.j))
        around = (hq.i - 0.35, hq.j - 0.35, hq.i + hq.w + 0.35, hq.j + hq.d + 0.35)   # just outside its walls
        if self.placing_turret and self.turret_aim:
            i, j = self.turret_aim
            gfx.set_mark((i, j, i + 1, j + 1), FITS if self.turret_fits else DOESNT_FIT)
        elif self.placing_trench and self.trench_aim:
            i, j = self.trench_aim
            gfx.set_mark((i, j, i + 1, j + 1), FITS if self.trench_fits else DOESNT_FIT)
        elif self.placing_building and self.building_aim:
            (i, j), kind = self.building_aim[0], self.placing_building
            gfx.set_mark((i, j, i + kind.W, j + kind.D), FITS if self.building_fits else DOESNT_FIT)
        elif self.order_aim == "remove" and isinstance(self.hover, Structure):   # what a click takes down
            t = self.hover
            gfx.set_mark((t.i - 0.15, t.j - 0.15, t.i + t.W + 0.15, t.j + t.D + 0.15), DOESNT_FIT, 0.9)
        elif self.structure_selected:
            t = self.structure_selected
            gfx.set_mark((t.i - 0.15, t.j - 0.15, t.i + t.W + 0.15, t.j + t.D + 0.15), SELECT_GREEN, 0.9)
        elif self.hq_selected:
            gfx.set_mark(around, SELECT_GREEN, 0.9)
        elif self.deposit_selected:
            x0, z0, x1, z1 = self.deposit_selected.rect
            gfx.set_mark((x0 - 0.15, z0 - 0.15, x1 + 0.15, z1 + 0.15), SELECT_GREEN, 0.9)
        elif self.hover is self.base:
            gfx.set_mark(around, (1.0, 1.0, 1.0), 0.5)
        elif isinstance(self.hover, Deposit):
            x0, z0, x1, z1 = self.hover.rect
            gfx.set_mark((x0 - 0.15, z0 - 0.15, x1 + 0.15, z1 + 0.15), (1.0, 1.0, 1.0), 0.5)
        else:
            gfx.set_mark(None)
        gfx.begin(self.camera.view_proj(), self.camera.eye(), self.camera.fog_range())
        gfx.draw_ground()
        if self.trench_mesh:
            gfx.draw(self.trench_mesh)
        tint = HQ_HIT_TINT if self.base.flash > 0 else (1.0, 1.0, 1.0, 1.0)
        if not self.base.alive:
            tint = (0.35, 0.32, 0.30, 1.0)                 # burnt out
        gfx.draw(self.hq_mesh, mathx.translate(hq.i, 0, hq.j), tint)
        for turret in self.turrets:
            self.draw_turret(turret)
        for deposit in self.deposits:
            self.draw_deposit(deposit)
        for building in self.buildings:
            self.draw_building(building)
        if self.placing_building:
            self.draw_building_ghosts()
        view_proj = self.camera.view_proj()
        self.together = {}         # mesh: [(matrix, tint)] of the dead's and the living dead's parts, drawn in one go each
        for unit in self.units:
            if isinstance(unit, Tank):
                if self.in_view(unit, view_proj):
                    self.draw_tank(unit)
            elif self.in_view(unit, view_proj):
                self.draw_troop(unit)
            else:
                self.lay_out_unseen(unit)
        for zombie in self.zombies:
            if self.in_view(zombie, view_proj):
                self.draw_zombie(zombie)
            else:
                self.lay_out_unseen(zombie)
        for mesh, copies in self.together.items():
            self.gfx.draw_many(mesh, copies)
        if self.placing_turret:
            if self.turret_row is not None:            # the row being dragged out (red: blueprints called off)
                ghosts = [(tile, True) for tile in self.turret_row]
                ghosts += [((b.i, b.j), False) for b in self.turret_cancel]
            elif self.turret_aim:
                there = self.turret_at(*self.turret_aim)
                ghosts = [(self.turret_aim, self.turret_fits and not (there and there.blueprint))]
            else:
                ghosts = []
            for (i, j), fits in ghosts:
                self.draw_turret_ghost(self.turret_kind, i + 0.5, j + 0.5, (*(FITS if fits else DOESNT_FIT), 0.55))
        for trench in self.world.trenches.values():
            if trench.blueprint:
                gfx.draw_ghost(self.trench_plan_mesh, mathx.translate(trench.x, 0, trench.z), BLUEPRINT_TINT)
        if self.placing_trench:
            if self.trench_row is not None:            # the line being dragged out (red: blueprints called off)
                ghosts = [(tile, True) for tile in self.trench_row]
                ghosts += [((t.i, t.j), False) for t in self.trench_cancel]
            else:
                ghosts = [(self.trench_aim, self.trench_fits)] if self.trench_aim else []
            for (i, j), fits in ghosts:
                gfx.draw_ghost(self.trench_plan_mesh, mathx.translate(i + 0.5, 0, j + 0.5),
                               (*(FITS if fits else DOESNT_FIT), 0.55))
        self.draw_ground_marks()
        for muzzle, hit, age in self.shots:
            self.draw_tracer(muzzle, hit)
        for muzzle, burst, age in self.shells:
            self.draw_tracer(muzzle, burst, thick=True)
        self.draw_blasts()
        self.draw_acid()
        self.draw_dust()
        self.draw_hud()
        gfx.draw_overlay()

    @staticmethod
    def body_matrix(unit, lean=0.0):
        """Where a living unit's body is drawn (the dead are drawn by draw_fallen)."""
        return mathx.standing(unit.x, -unit.sink, unit.z, unit.yaw, lean, unit.SIZE, unit.bob)

    def gun_hold(self, unit):
        """Where his gun is, in the frame of the way he faces, in model units: carried across
        his chest, or raised level in front of his right eye to fire, and between as he raises
        it (his aim_blend): lifted and pushed out on the way, so its stock swings up over his
        right forearm and round in front of his chest, not through them. See models.Hold."""
        hold, a = models.RIFLE_HOLD, unit.aim_blend
        place = [c + (p - c) * a for c, p in zip(hold.carry, hold.place)]
        place[1] += hold.lift * math.sin(math.pi * a)   # (up and over his right forearm on the way)
        place[2] += RAISE_OUT * math.sin(math.pi * a)   # (and out in front of his chest)
        return mathx.chain(mathx.translate(*place), mathx.rot_y(hold.carry_turn * (1 - a)),
                           mathx.rot_x(hold.carry_tip * (1 - a)))

    def gun_matrix(self, unit, frame=None):
        """His gun in his hands (see gun_hold). At work (digging or hammering) it's slung
        across his back, resting on his pack or his back, clear of his helmet, the magazine
        facing out. `frame` is the way he faces (body_matrix)."""
        frame = frame or self.body_matrix(unit)
        if unit.working:
            return mathx.mul(frame, slung(self.slung_depth))
        return mathx.mul(frame, self.gun_hold(unit))

    def arm_joints(self, unit):
        """His arms holding his gun, in the frame of the way he faces, in model units:
        (shoulder, elbow, hand) for his right arm, its hand on the grip, then for his left,
        its hand on the front of the gun. His body stays square to the way he faces. As he
        raises the gun, his left shoulder rolls forward and in to reach across him for the
        front of it, and his left hand slides along the front. Each elbow bends where it must
        for the hand to reach (mathx.elbow): carrying, both down; raised, the right one down
        and out."""
        hold, a = models.RIFLE_HOLD, unit.aim_blend
        gun = self.gun_hold(unit)

        def mix(pair):
            return [c + (r - c) * a for c, r in zip(*pair)]
        front = mix((hold.carry_front, hold.front))
        forward, inward = mix(FRONT_SHOULDER)
        out = []
        for side, hand, pole, ahead, tuck in ((-1, hold.grip, mix(GRIP_ELBOW), 0.0, 0.0),
                                              (1, front, mix(FRONT_ELBOW), forward, inward)):
            shoulder = (side * (models.SHOULDER_X - tuck), SHOULDER_Y, models.SHOULDER_Z + ahead)
            reach = mathx.apply(gun, hand)
            if side == 1 and getattr(unit, "changing", 0):          # changing magazines: his left hand is busy
                reach = self.reload_pose(unit)[0]
            out.append((shoulder, mathx.elbow(shoulder, reach, models.ELBOW, models.FOREARM, pole), reach))
        return out

    def reload_pose(self, unit):
        """While he changes magazines (the gun carried across his chest, his right hand on the
        grip): where his left hand is, and the matrix of the magazine (seated in the gun, or in
        his hand; None while it's down in his pouch), both in the frame of the way he faces. Through RELOAD_STEPS, his hand goes from the front of the gun to the magazine,
        pulls it down out of the gun, takes it to the pouch at the top of his left vest pocket
        and puts it in, draws out a full one, brings it up under the gun and seats it, and goes
        back to the front of the gun. He holds a magazine MAG_GRIPS below its top, and it stays
        turned as the gun is."""
        gun = self.gun_hold(unit)
        turn = list(gun)
        turn[12:15] = [0.0, 0.0, 0.0]                            # (the gun's turn alone)
        seat = models.MAG_SEAT
        tops = {"seat": mathx.apply(gun, seat), "out": mathx.apply(gun, (seat[0], seat[1] - MAG_PULL, seat[2])),
                "pouch": (MAG_POUCH[0], MAG_POUCH[1] + models.MAG_LENGTH + 0.02, MAG_POUCH[2]),
                "in": (MAG_POUCH[0], MAG_POUCH[1] + MAG_IN, MAG_POUCH[2])}

        def hand_at(name):
            """Where his hand is at a step, and how far below a magazine's top he holds it."""
            if name == "front":
                return mathx.apply(gun, models.RIFLE_HOLD.carry_front), MAG_GRIPS["seat"]
            return mathx.v_add(tops[name], mathx.apply(turn, (0.0, -MAG_GRIPS[name], 0.0))), MAG_GRIPS[name]
        t = 1.0 - unit.changing / unit.change_time
        k = next(k for k in range(len(RELOAD_STEPS) - 1) if t < RELOAD_STEPS[k + 1][0] or k == len(RELOAD_STEPS) - 2)
        (t0, a), (t1, b) = RELOAD_STEPS[k], RELOAD_STEPS[k + 1]
        f = mathx.clamp((t - t0) / (t1 - t0), 0.0, 1.0)
        f = f * f * (3 - 2 * f)
        (pa, ga), (pb, gb) = hand_at(a), hand_at(b)
        hand = tuple(x + (y - x) * f for x, y in zip(pa, pb))
        grip = mathx.apply(turn, (0.0, -(ga + (gb - ga) * f), 0.0))
        if not RELOAD_STEPS[1][0] <= t < RELOAD_STEPS[-2][0]:
            mag = mathx.mul(gun, mathx.translate(*seat))             # seated in the gun
        elif 0.5 <= t < NEW_MAG:
            mag = None                                               # down in his pouch
        else:
            mag = mathx.mul(mathx.translate(*mathx.v_sub(hand, grip)), turn)   # in his hand
        return hand, mag

    def draw_troop(self, unit):
        """A soldier or an engineer: his body and legs; at work, one arm swinging his tool and the
        other at his side; a soldier otherwise holds his rifle with both hands (his gun slung
        while he works), and an engineer swings his arms as he walks."""
        (body_mesh, leg_mesh, arm_mesh), gun_mesh = self.looks[type(unit)]
        if not unit.alive and self.can_lay_out(unit):
            self.draw_fallen(unit, (body_mesh, leg_mesh, arm_mesh), self.shapes[type(unit)], -1.0, gun_mesh)
            return
        body = self.body_matrix(unit)                  # (square to the way he faces)
        tint = HIT_TINT if unit.flash > 0 else (1.0, 1.0, 1.0, 1.0)
        self.gfx.draw(body_mesh, body, tint)
        sx, sz = models.SHOULDER_X, models.SHOULDER_Z
        for side in (-1, 1):
            leg = mathx.hung(body, side * 0.1, 0.42, 0, side * unit.swing)
            self.gfx.draw(leg_mesh, leg, tint)
            if unit.working and side == 1:             # hammering: one arm comes up and down
                swing = -1.3 - 0.55 * (1 + math.sin(unit.hammer * 11))
                arm = mathx.chain(body, mathx.translate(sx, SHOULDER_Y, sz), mathx.rot_x(swing))
                self.gfx.draw(self.tools[type(unit)], mathx.chain(arm, mathx.translate(0, -0.46, 0),
                                                                  mathx.rot_x(math.pi / 2)), tint)
                self.gfx.draw(arm_mesh, arm, tint)
            elif unit.working:
                arm = mathx.chain(body, mathx.translate(-sx, SHOULDER_Y, sz), mathx.rot_y(0.3), mathx.rot_x(-0.9))
                self.gfx.draw(arm_mesh, arm, tint)
            elif not gun_mesh:                         # no gun: his arms swing as he walks
                arm = mathx.chain(body, mathx.translate(side * sx, SHOULDER_Y, sz), mathx.rot_x(-side * unit.swing),
                                  mathx.rot_z(side * ARMS_OUT))
                self.gfx.draw(arm_mesh, arm, tint)
        if gun_mesh:
            if not unit.working:                       # both hands on his rifle, the elbows bent
                upper, lower = self.arm_halves
                for shoulder, elbow, hand in self.arm_joints(unit):
                    self.gfx.draw(upper, mathx.mul(body, mathx.bone(shoulder, elbow, (1.0, 0.0, 0.0))), tint)
                    self.gfx.draw(lower, mathx.mul(body, mathx.bone(elbow, hand, (1.0, 0.0, 0.0))), tint)
            gun = self.gun_matrix(unit, body)
            if unit.working or not unit.changing:      # (slung, or in his hands with its magazine in)
                self.gfx.draw(gun_mesh, gun, tint)
            else:                                      # changing magazines: the magazine's in his hand, or the pouch
                rifle, mag_mesh = self.rifle_parts
                self.gfx.draw(rifle, gun, tint)
                mag = self.reload_pose(unit)[1]
                if mag is not None:
                    self.gfx.draw(mag_mesh, mathx.mul(body, mag), tint)

    def draw_tank(self, tank):
        """A tank: its hull, its tracks' cleats moved along by how far each track has run, its
        turret turned on the hull, its gun (run back a little after a shot), and each machine
        gun turned on its post. Wrecked: burnt dark, then sinking away."""
        parts = self.tank_meshes
        if tank.alive:
            tint = HIT_TINT if tank.flash > 0 else (1.0, 1.0, 1.0, 1.0)
        else:
            tint = (0.24, 0.22, 0.21, 1.0)
        hull = mathx.chain(mathx.translate(tank.x, -tank.sunk * (tank.TOP + 0.5), tank.z), mathx.rot_y(tank.yaw))
        self.gfx.draw(parts["hull"], hull, tint)
        for side, run in ((1, tank.rolled[0]), (-1, tank.rolled[1])):
            links = mathx.chain(hull, mathx.translate(side * models.TRACK_X, 0, run % models.TRACK_PITCH))
            self.gfx.draw(parts["links"], links, tint)
        turret = mathx.chain(hull, mathx.translate(0, 0, tank.TURRET_AT), mathx.rot_y(tank.turret_turn))
        self.gfx.draw(parts["turret"], turret, tint)
        self.gfx.draw(parts["gun"], mathx.chain(turret, mathx.translate(0, 0, -0.25 * tank.recoil / tank.KICK)), tint)
        for gun, mesh in zip(tank.guns, parts["mgs"]):
            post = mathx.chain(turret, mathx.translate(gun.mount[0], 0, gun.mount[1]), mathx.rot_y(gun.turn),
                               mathx.translate(0, 0, -0.3 * gun.recoil))
            self.gfx.draw(mesh, post, tint)

    def barrels_matrix(self, head, angle):
        """Where a minigun's barrels are on its head, turned round their own axis."""
        return mathx.chain(head, mathx.translate(*models.MINIGUN_BARRELS), mathx.rot_z(angle))

    def draw_turret_ghost(self, kind, x, z, tint):
        """A see-through turret: a blueprint, or one about to be laid."""
        base_mesh, head_mesh = self.turret_looks[kind]
        m = mathx.translate(x, 0, z)
        self.gfx.draw_ghost(base_mesh, m, tint)
        self.gfx.draw_ghost(head_mesh, m, tint)
        if kind is MinigunTurret:
            self.gfx.draw_ghost(self.barrels_mesh, self.barrels_matrix(m, 0.0), tint)

    def draw_turret(self, turret):
        if not turret.started:                         # a blueprint: see-through, flat blue
            if turret.alive:
                self.draw_turret_ghost(type(turret), turret.x, turret.z, BLUEPRINT_TINT)
            return
        if turret.alive:
            tint = HIT_TINT if turret.flash > 0 else (1.0, 1.0, 1.0, 1.0)
            if not turret.built:
                tint = UNBUILT_TINT
            rise = 1.0 if turret.built else 0.25 + 0.75 * turret.progress   # it goes up as it's built
            base = mathx.chain(mathx.translate(turret.x, 0, turret.z), mathx.scale(1, rise, 1))
        else:
            tint = (0.25, 0.23, 0.22, 1.0)                 # wrecked, and sinking away
            base = mathx.chain(mathx.translate(turret.x, -turret.dead_for * 0.5, turret.z), mathx.scale(1, 0.7, 1))
        base_mesh, head_mesh = self.turret_looks[type(turret)]
        self.gfx.draw(base_mesh, base, tint)
        if turret.built or turret.progress > 0.6 or not turret.alive:
            head = mathx.chain(base, mathx.rot_y(turret.yaw), mathx.translate(0, 0, -turret.recoil * 0.5))
            self.gfx.draw(head_mesh, head, tint)
            if isinstance(turret, MinigunTurret):
                self.gfx.draw(self.barrels_mesh, self.barrels_matrix(head, turret.barrels), tint)

    def draw_building(self, building):
        """A building: a blueprint see-through and blue; being built, rising from the ground
        and pale; wrecked, dark and sinking away."""
        if not building.started:
            if building.alive:
                self.draw_building_at(type(building), self.building_model(building), BLUEPRINT_TINT, building, ghost=True)
            return
        if building.alive:
            tint = HIT_TINT if building.flash > 0 else (1.0, 1.0, 1.0, 1.0)
            if not building.built:
                tint = UNBUILT_TINT
            rise = 1.0 if building.built else 0.15 + 0.85 * building.progress
            self.draw_building_at(type(building), mathx.chain(self.building_model(building), mathx.scale(1, rise, 1)),
                                  tint, building)
        else:
            sunk = mathx.chain(mathx.translate(0, -building.dead_for * 0.5, 0), self.building_model(building),
                               mathx.scale(1, 0.6, 1))
            self.draw_building_at(type(building), sunk, (0.25, 0.23, 0.22, 1.0), building)

    @staticmethod
    def building_model(building):
        """Where a building stands: a bullet factory on its corner tile; one beside a deposit
        on its spot, its back to the deposit."""
        if isinstance(building, Extractor):
            return building.deposit.spot_model()
        return mathx.translate(building.i, 0, building.j)

    def draw_building_at(self, kind, model, tint, building=None, ghost=False):
        """A building of a kind, put where `model` says: a salvage crane with its arm where
        it's got to in lifting a car out (or at rest over its baler), a loading dock post with
        the crates piled up for the next load, a radar station with its dish turned as far as
        it's got. See-through (a ghost or a blueprint) with `ghost`."""
        draw = self.gfx.draw_ghost if ghost else self.gfx.draw
        working = building is not None and building.working and building.on   # (switched off, it rests)
        if kind is Factory:
            draw(self.factory_mesh, model, tint)
        elif kind is VehicleFactory:
            draw(self.vehicle_factory_mesh, model, tint)
        elif kind is RadarStation:                     # its dish turns, once it's up
            parts, (cx, cz) = self.radar_meshes, models.RADAR_MIDDLE
            turn = mathx.rot_y(self.played * RADAR_TURN if building is not None and building.alive and building.built else 0.0)
            draw(parts["base"], model, tint)
            draw(parts["mount"], mathx.chain(model, mathx.translate(cx, models.PEDESTAL_TOP, cz), turn), tint)
            draw(parts["dish"], mathx.chain(model, mathx.translate(cx, models.PEDESTAL_TOP + models.DISH_AXLE, cz), turn,
                                            mathx.rot_x(models.DISH_TILT)), tint)
        elif kind is LoadingDock:
            draw(self.dock_mesh, model, tint)
            loads = min(len(models.CRATE_SPOTS), int(building.making / building.MAKE_TIME * 4)) if working else 0
            for x, z in models.CRATE_SPOTS[:loads]:
                draw(self.crate_mesh, mathx.chain(model, mathx.translate(x, 0, z)), tint)
        else:
            magnet, car = self.crane_pose(building) if working else (self.crane_rest(), None)
            slew, foot, elbow, tip = models.crane_arm(magnet)
            across = (math.cos(slew), 0.0, -math.sin(slew))
            px, pz = models.CRANE_PIVOT
            parts = self.crane_meshes
            draw(parts["base"], model, tint)
            draw(parts["works"], mathx.chain(model, mathx.translate(px, 0, pz), mathx.rot_y(slew)), tint)
            draw(parts["boom"], mathx.chain(model, mathx.bone(foot, elbow, across)), tint)
            draw(parts["stick"], mathx.chain(model, mathx.bone(elbow, tip, across)), tint)
            yaw = car[3] if car else 0.0
            draw(parts["magnet"], mathx.chain(model, mathx.translate(*tip), mathx.rot_y(yaw)), tint)
            if car:
                hang = mathx.translate(tip[0], tip[1] - models.CHAIN - models.MAGNET_H, tip[2])
                draw(self.car_meshes[car[4]], mathx.chain(model, hang, mathx.rot_y(yaw)), tint)

    @staticmethod
    def crane_rest():
        """Where a salvage crane rests its magnet (the bottom of it, in its spot's frame): over its baler."""
        x, z = models.BALER_MIDDLE
        return x, CRANE_REST, z

    def next_car(self, crane):
        """The car a salvage crane lifts out next (as models.junkyard_cars gives it), or None."""
        yard = crane.deposit
        cars = self.junk_cars[yard]
        out = yard.CARS - yard.cars_left
        return cars[out] if out < len(cars) else None

    def crane_pose(self, crane):
        """Where a salvage crane's magnet is (the bottom of it, in its spot's frame), and the car
        on it if any, as far as it is through its lift (CRANE_STEPS, over the last CRANE_LIFT of
        its batch; before that, it rests): up over its baler, round
        and out over the junkyard to the top car of the next stack, down onto it, up with it,
        back round over the baler, down, and back up to rest. It turns round its turntable as it
        goes (it doesn't cut straight across), so the arm swings out and back."""
        car = self.next_car(crane)
        if car is None:
            return self.crane_rest(), None
        yard = crane.deposit
        cx, cy, cz = car[0] - (yard.W / 2 - 1), car[1], car[2] - yard.D   # (in the spot's frame)
        bx, bz = models.BALER_MIDDLE
        points = {"rest": (bx, CRANE_REST, bz), "over": (bx, CRANE_SAFE, bz),
                  "drop": (bx, models.BALER_H + 0.05 + models.CAR_H, bz),
                  "above": (cx, CRANE_SAFE, cz), "on": (cx, cy + models.CAR_H, cz)}
        t = (crane.making - (crane.MAKE_TIME - CRANE_LIFT)) / CRANE_LIFT
        if t < 0:                                                         # (resting over its baler, till the lift)
            return self.crane_rest(), None
        k = next(k for k in range(len(CRANE_STEPS) - 1) if t < CRANE_STEPS[k + 1][0] or k == len(CRANE_STEPS) - 2)
        (t0, a), (t1, b) = CRANE_STEPS[k], CRANE_STEPS[k + 1]
        f = mathx.clamp((t - t0) / (t1 - t0), 0.0, 1.0)
        f = f * f * (3 - 2 * f)                                           # (easing in and out)
        px, pz = models.CRANE_PIVOT
        (ax, ay, az), (qx, qy, qz) = points[a], points[b]
        angle_a, angle_b = math.atan2(ax - px, az - pz), math.atan2(qx - px, qz - pz)
        turn = (angle_b - angle_a + math.pi) % (2 * math.pi) - math.pi
        angle = angle_a + turn * f
        reach = math.hypot(ax - px, az - pz) * (1 - f) + math.hypot(qx - px, qz - pz) * f
        magnet = (px + math.sin(angle) * reach, ay + (qy - ay) * f, pz + math.cos(angle) * reach)
        return magnet, (car if CRANE_CARRIES[0] <= t < CRANE_CARRIES[1] else None)

    def draw_building_ghosts(self):
        """While choosing where a building goes: a see-through one where it would go (green if
        it can, red if it can't); and for one that goes beside a deposit, a faint one on the
        spot of each deposit of its kind that has none yet."""
        kind = self.placing_building
        aimed = self.building_aim[1] if self.building_aim else None
        if issubclass(kind, Extractor):
            for deposit in self.free_deposits(kind):
                if deposit is not aimed:
                    self.draw_building_at(kind, deposit.spot_model(), (1.0, 1.0, 1.0, 0.22), ghost=True)
        if self.building_aim:
            (i, j), deposit = self.building_aim
            model = deposit.spot_model() if deposit else mathx.translate(i, 0, j)
            self.draw_building_at(kind, model, (*(FITS if self.building_fits else DOESNT_FIT), 0.55), ghost=True)

    def draw_deposit(self, deposit):
        """A junkyard with the cars still in it (less the one on its crane's magnet), or a
        warehouse with the pallets still on its dock and its doors open as it's emptied (its
        middle one once its loading dock post is up). Its mesh is built afresh when that changes."""
        building = self.extractor_at(deposit)
        if isinstance(deposit, Junkyard):
            carrying = building is not None and building.working and building.on and self.crane_pose(building)[1] is not None
            look = deposit.cars_left - carrying
        else:
            left = deposit.left / deposit.HOLDS
            look = (deposit.pallets, (left <= 0.5, building is not None and building.built, left <= 0.25))
        cached = self.deposit_meshes.get(deposit)
        if not cached or cached[0] != look:
            if cached:
                cached[1].release()
            if isinstance(deposit, Junkyard):
                mb = models.build_junkyard(deposit.seed, look)
            else:
                mb = models.build_warehouse(deposit.seed, *look)
            cached = self.deposit_meshes[deposit] = (look, self.gfx.mesh(mb))
        self.gfx.draw(cached[1], deposit.model())

    @staticmethod
    def whole_zombie(parts):
        """A zombie's body, legs and arms as one mesh, standing (legs straight, arms out in
        front), in its body's frame: for drawing from far out, where its limbs swinging can't
        be seen, as one draw rather than five."""
        body, leg, arm = parts
        mb = MeshBuilder()
        mb.add(body, mathx.identity())
        for side in (-1, 1):
            mb.add(leg, mathx.translate(side * 0.1, 0.42, 0))
            mb.add(arm, mathx.chain(mathx.translate(side * 0.28, 0.80, 0), mathx.rot_x(-1.3 + side * 0.12)))
        return mb

    def in_view(self, unit, view_proj):
        """Is a unit (or a body) on the screen, or near enough its edge to show? (Those that
        aren't are left undrawn: with hundreds of the dead walking in, most are off it.)"""
        p = self.camera.to_screen(unit.x, 0.6, unit.z, *self.size, view_proj)
        return p is not None and -VIEW_MARGIN[0] < p[0] < WIDTH + VIEW_MARGIN[0] and -VIEW_MARGIN[1] < p[1] < HEIGHT + VIEW_MARGIN[1]

    def lay_out_unseen(self, unit):
        """A dead unit off the screen is laid out all the same (as many a frame as can_lay_out
        allows), so it's lying at rest when it comes into view."""
        if unit.alive or (unit.fall and unit.fall.pose) or not self.can_lay_out(unit):
            return
        if isinstance(unit, Zombie):
            self.pose_of(unit, self.zombie_shapes[unit.variant], -1.3)
        else:
            self.pose_of(unit, self.shapes[type(unit)], -1.0)

    def draw_zombie(self, zombie):
        """A zombie: one that's down, as it falls and lies (drawn now); one on its feet, its body,
        legs and arms put in self.together, to be drawn in one go with all the others'."""
        body_mesh, leg_mesh, arm_mesh = self.zombie_meshes[zombie.variant]
        if not zombie.alive and self.can_lay_out(zombie):
            self.draw_fallen(zombie, (body_mesh, leg_mesh, arm_mesh), self.zombie_shapes[zombie.variant], -1.3)
            return
        body = self.body_matrix(zombie, lean=0.22 + zombie.lean * 0.3)
        tint = HIT_TINT if zombie.flash > 0 else (1.0, 1.0, 1.0, 1.0)
        put = self.together.setdefault                          # (drawn together, after all of them: see draw)
        if self.camera.dist > self.camera.PLAY_DIST:            # far out: one piece
            put(self.zombie_whole[zombie.variant], []).append((body, tint))
            return
        put(body_mesh, []).append((body, tint))
        swing = zombie.swing if zombie.alive else 0.0
        claw = math.sin(zombie.lunge / 0.35 * math.pi) * 0.7 if zombie.lunge > 0 else 0.0
        for side in (-1, 1):
            leg = mathx.hung(body, side * 0.1, 0.42, 0, side * swing)
            reach = -1.3 + side * 0.12 + side * swing * 0.25 - claw
            arm = mathx.hung(body, side * 0.28, 0.80, 0, reach)
            put(leg_mesh, []).append((leg, tint))
            put(arm_mesh, []).append((arm, tint))

    def can_lay_out(self, unit):
        """Can a dead unit be drawn fallen this frame? Not if it has yet to be laid out and this
        frame has laid out enough already (it's drawn as it stood, for a frame or two more)."""
        if unit.fall and unit.fall.pose:
            return True
        if self.layouts >= LAYOUTS_A_FRAME:
            return False
        self.layouts += 1
        return True

    def pose_of(self, unit, shape, arm_start):
        """How a dead unit lies (worked out the first time it's needed), and where its gun lands."""
        f = unit.fall
        if f is None:                                 # (killed without a blow: it just goes down)
            f = unit.fall = Fall(unit, None)
        if f.pose is None:                            # keeping off anyone standing, or still falling
            others = {(math.floor(u.x), math.floor(u.z)) for u in self.units + self.zombies
                      if u is not unit and (u.alive or (u.fall and u.fall.pose is None))}
            for tank in self.tanks:                    # and off the whole of a tank's hull, or its wreck
                if tank.standing:
                    others |= tank.tiles_under()
            f.pose = lay_out(unit, shape, arm_start, others)
            if shape.gun:
                f.gun_rest = self.gun_spot(unit, shape)
        return f.pose

    def final_frame(self, unit):
        """Where a dead unit ends up: its feet, turned the way it lies, at its size."""
        f = unit.fall
        sx, sz = f.pose.shift
        return mathx.chain(mathx.translate(unit.x + sx, -unit.sink, unit.z + sz), mathx.rot_y(f.yaw_to),
                           mathx.scale(unit.SIZE))

    def gun_at_rest(self, unit, spot):
        """A dead unit's gun lying on its side at one of the spots its pose offers."""
        x, y, z, turn = spot
        return mathx.chain(self.final_frame(unit), mathx.translate(x, y, z), mathx.rot_y(turn), mathx.rot_z(math.pi / 2))

    def gun_spot(self, unit, shape):
        """Where a dead unit's gun lands: the first spot its pose offers where all of it lies on
        open ground (or, in a trench, on the trench's floor); else where least of it doesn't.
        On a body lying there, it rests on top."""
        trench = self.world.trench_at(unit.x, unit.z)
        in_trench = trench is not None and trench.started
        n = self.world.size
        best = None
        for spot in unit.fall.pose.gun_spots():
            m = self.gun_at_rest(unit, spot)
            off = 0
            for p in shape.gun:
                x, _, z = mathx.apply(m, p)
                there = self.world.trench_at(x, z)
                dug = there is not None and there.started
                walled = 0 <= x < n and 0 <= z < n and self.world.is_blocked(int(x), int(z))
                off += not dug if in_trench else (dug or walled)
            if best is None or off < best[0]:
                best = (off, spot)
            if off == 0:
                break
        x, y, z, turn = best[1]
        m = self.gun_at_rest(unit, best[1])
        floor = -unit.rest_depth()
        under = min(p[1] - max(floor, self.world.top_at(p[0], p[2], besides=unit))    # (on others, not himself)
                    for p in (mathx.apply(m, q) for q in shape.rests["gun"]))
        spot = (x, y - min(0.0, under) / unit.SIZE, z, turn)
        m = self.gun_at_rest(unit, spot)                 # others may rest on it too
        unit.fall.top_cells += self.world.add_tops(unit, [mathx.apply(m, q) for q in shape.tops["gun"]])
        return spot

    def fallen_parts(self, unit, shape, arm_start):
        """Where each part of a dead unit is as it falls and lies (see deaths.py): a list of
        (part, matrix), the part being "body", "leg", "arm" or "gun" (dropped beside it).
        Once it's at rest they don't change, so they're kept."""
        pose = self.pose_of(unit, shape, arm_start)
        f = unit.fall
        at_rest = unit.dead_for > max(f.time, GUN_DROP)
        if at_rest and f.rest_parts and f.rest_parts[0] == unit.sink:
            return f.rest_parts[1]
        parts = pose.parts(unit.x, unit.z, -unit.sink, unit.dead_for)
        if shape.gun:
            parts.append(("gun", self.dropped_gun(unit)))
        if at_rest:
            f.rest_parts = (unit.sink, parts)
        return parts

    def draw_fallen(self, unit, meshes, shape, arm_start, gun_mesh=None):
        """A dead unit as it falls and lies, its gun dropped beside it, fading away at the end
        (till then, put in self.together, to be drawn in one go with all the others)."""
        body_mesh, leg_mesh, arm_mesh = meshes
        mesh_of = {"body": body_mesh, "leg": leg_mesh, "arm": arm_mesh, "gun": gun_mesh}
        fade = min(1.0, (DEATH_TIME - unit.dead_for) / FADE_TIME)
        tint = (*(HIT_TINT[:3] if unit.flash > 0 else (1.0, 1.0, 1.0)), fade)
        for part, m in self.fallen_parts(unit, shape, arm_start):
            if fade >= 1.0:                       # solid: drawn in one go with the rest (see draw)
                self.together.setdefault(mesh_of[part], []).append((m, tint))
            else:
                self.gfx.draw_ghost(mesh_of[part], m, tint)

    def dropped_gun(self, unit):
        """A dead unit's gun: dropped from his hands, it falls to the ground beside him and lies on its side."""
        f = unit.fall
        e = min(1.0, unit.dead_for / GUN_DROP)
        held = mathx.apply(mathx.chain(mathx.translate(unit.x, -unit.sink, unit.z), mathx.rot_y(f.yaw_from),
                                       mathx.scale(unit.SIZE)), (0.04, 0.58, 0.30))
        gx, gy, gz, turn = f.gun_rest
        rest = mathx.apply(self.final_frame(unit), (gx, gy, gz))
        x, z = held[0] + (rest[0] - held[0]) * e, held[2] + (rest[2] - held[2]) * e
        y = held[1] + (rest[1] - held[1]) * e * e
        yaw = f.yaw_from + turn_between(f.yaw_from, f.yaw_to + turn) * e
        return mathx.chain(mathx.translate(x, y, z), mathx.rot_y(yaw), mathx.scale(unit.SIZE),
                           mathx.rot_z(math.pi / 2 * e), mathx.rot_x(0.55 * (1 - e)))

    def draw_stain(self, unit):
        """The stain spreading under a body once it's down (and fading with it)."""
        f = unit.fall
        if not (f and f.pose) or unit.dead_for < f.time:
            return
        x, _, z = mathx.apply(self.final_frame(unit), (f.pose.stain_point()[0], 0.0, f.pose.stain_point()[1]))
        kind = "spitter" if isinstance(unit, Spitter) else "zombie" if isinstance(unit, Zombie) else "troop"
        spread = min(1.0, (unit.dead_for - f.time) / STAIN_TIME)
        fade = min(1.0, (DEATH_TIME - unit.dead_for) / FADE_TIME)
        self.ring_at(x, z, unit.SIZE * (0.12 + 0.3 * spread), STAINS[kind], 0.75 * fade, mesh=self.disc_mesh,
                     height=-unit.sink + 0.012)

    def draw_tracer(self, a, b, thick=False):
        """A shot's streak from a to b, and the flash at the muzzle (a tank's shell: thicker, a bigger flash)."""
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length < 1e-3:
            return
        yaw = math.atan2(dx, dz)
        pitch = math.atan2(dy, math.hypot(dx, dz))
        k = 3.0 if thick else 1.0
        m = mathx.chain(mathx.translate(*a), mathx.rot_y(yaw), mathx.rot_x(-pitch), mathx.scale(k, k, length))
        self.gfx.draw(self.beam_mesh, m, (1.6, 1.4, 0.7, 0.9))
        flash = mathx.chain(mathx.translate(*a), mathx.rot_y(yaw), mathx.scale(4 * k, 4 * k, 0.12 * k))
        self.gfx.draw(self.beam_mesh, flash, (2.0, 1.6, 0.6, 0.8))

    def draw_blasts(self):
        """Each shell's blast: a fireball swelling and fading, then a puff of smoke rising."""
        for x, y, z, age in self.blasts:
            t = age / BLAST_TIME
            fire = mathx.chain(mathx.translate(x, y, z), mathx.scale(0.8 + 2.2 * t))
            self.gfx.draw_ghost(self.fireball_mesh, fire, (2.0, 1.3, 0.45, 0.85 * (1 - t) ** 2))
            for k in range(3):                         # smoke, rising and spreading
                a = k * 2 * math.pi / 3 + x * 5.0
                puff = mathx.chain(mathx.translate(x + math.sin(a) * t * 0.9, y + 0.4 + 1.6 * t,
                                                   z + math.cos(a) * t * 0.9), mathx.scale(4.0 + 6.0 * t))
                self.gfx.draw(self.dust_mesh, puff, (0.45, 0.43, 0.42, 0.8 * (1 - t)))

    def draw_acid(self):
        """Globs of acid in flight, and the splashes where they landed."""
        for spit in self.spits:
            self.gfx.draw(self.acid_mesh, mathx.translate(*spit.pos), (1.5, 1.5, 1.5, 1.0))
        for x, y, z, age in self.splashes:
            t = age / SPLASH_TIME
            for k in range(4):                         # drops flying apart, and fading
                a = k * math.pi / 2 + 0.6
                m = mathx.chain(mathx.translate(x + math.sin(a) * t * 0.4, y + t * 0.25 - t * t * 0.3,
                                                z + math.cos(a) * t * 0.4), mathx.scale(0.8 - 0.5 * t))
                self.gfx.draw(self.acid_mesh, m, (1.5, 1.5, 1.5, 1.0 - t))

    def draw_dust(self):
        """Clods of dirt thrown up where shots that missed came down: up, apart, and fading."""
        for x, y, z, age in self.dust:
            t = age / DUST_TIME
            for k in range(3):
                a = k * 2 * math.pi / 3 + x * 7.0          # each puff turned its own way
                up = 0.5 + 0.15 * (k % 3)
                m = mathx.chain(mathx.translate(x + math.sin(a) * t * 0.35, y + up * t * (1 - t) + 0.04,
                                                z + math.cos(a) * t * 0.35), mathx.scale(1.0 - 0.6 * t))
                self.gfx.draw(self.dust_mesh, m, (1.0, 1.0, 1.0, 1.0 - t))

    def ring_at(self, x, z, radius, color, alpha, mesh=None, height=0.03):
        model = mathx.chain(mathx.translate(x, height, z), mathx.scale(radius, 1, radius))
        self.gfx.draw(mesh or self.ring_mesh, model, tint=(*color, alpha))

    def draw_ground_marks(self):
        if isinstance(self.structure_selected, Turret) and self.structure_selected.built:
            t = self.structure_selected
            self.ring_at(t.x, t.z, t.range, SELECT_GREEN, 0.5, mesh=self.thin_ring_mesh, height=0.02)
            self.ring_at(t.x, t.z, t.long_range, SELECT_GREEN, 0.2, mesh=self.thin_ring_mesh, height=0.02)   # long shots
        if self.placing_turret and self.turret_aim:   # how far it would reach from there
            i, j = self.turret_aim
            kind, color = self.turret_kind, FITS if self.turret_fits else DOESNT_FIT
            self.ring_at(i + 0.5, j + 0.5, kind.RANGE, color, 0.45, mesh=self.thin_ring_mesh, height=0.02)
            self.ring_at(i + 0.5, j + 0.5, kind.RANGE * kind.LONG_SHOTS, color, 0.18, mesh=self.thin_ring_mesh,
                         height=0.02)
        for x, z, age in self.scorches:               # where shells burst, fading
            self.ring_at(x, z, 1.4, (0.05, 0.045, 0.04), 0.6 * (1 - age / SCORCH_TIME), mesh=self.disc_mesh, height=0.011)
        for pool in self.pools:                       # puddles of acid, fading as they dry
            fade = 1.0 - (pool.age / POOL_TIME) ** 2
            self.ring_at(pool.x, pool.z, pool.radius, ACID_GREEN, 0.75 * fade, mesh=self.disc_mesh,
                         height=pool.floor + 0.014)
            self.ring_at(pool.x, pool.z, pool.radius * 0.55, ACID_LIGHT, 0.6 * fade, mesh=self.disc_mesh,
                         height=pool.floor + 0.016)
        view_proj = self.camera.view_proj()
        for unit in self.units + self.zombies:
            if not self.in_view(unit, view_proj):    # (off the screen: nothing to draw under it)
                continue
            if not unit.alive:
                if not unit.big:
                    self.draw_stain(unit)
                continue
            r = unit.LENGTH / 2 + 0.2 if unit.big else unit.RADIUS * 1.5
            feet = -unit.sink                          # on the floor of a trench, if it's in one
            if unit in self.selected:
                self.ring_at(unit.x, unit.z, r, SELECT_GREEN, 0.95, height=feet + 0.03)
            elif unit is self.hover:
                self.ring_at(unit.x, unit.z, r, ENEMY_RED if isinstance(unit, Zombie) else (1.0, 1.0, 1.0), 0.6,
                             height=feet + 0.03)
        for unit in self.selected:
            if unit.target and unit.target.alive:
                self.ring_at(unit.target.x, unit.target.z, 0.5, ENEMY_RED, 0.8)
            if isinstance(unit, Tank):                 # its main gun's reach
                self.ring_at(unit.x, unit.z, unit.range, SELECT_GREEN, 0.35, mesh=self.thin_ring_mesh, height=0.02)
                self.ring_at(unit.x, unit.z, unit.long_range, SELECT_GREEN, 0.15, mesh=self.thin_ring_mesh, height=0.02)
            self.draw_order_lines(unit)
        trainer = self.base if self.hq_selected else self.structure_selected
        if self.hq_selected or (isinstance(trainer, VehicleFactory) and trainer.ready):   # where new ones gather
            x, z = trainer.rally
            self.gfx.draw(self.flag_mesh, mathx.translate(x, 0, z))
            self.ring_at(x, z, 0.35, PLAYER_BLUE, 0.8)
        preview = self.line_preview()
        if preview:                                   # the line being dragged: a spot and a pointer each
            spots, yaw = preview
            for x, z in spots:
                self.ring_at(x, z, 0.32, SELECT_GREEN, 0.75)
                pointer = mathx.chain(mathx.translate(x, 0.04, z), mathx.rot_y(yaw), mathx.scale(2.5, 0.5, 0.55))
                self.gfx.draw(self.beam_mesh, pointer, (*SELECT_GREEN, 0.85))
        for x, z, age, color in self.markers:
            t = age / MARKER_TIME
            self.ring_at(x, z, 0.8 - 0.55 * t, color, 1.0 - t, height=0.035)

    def draw_order_lines(self, unit):
        """A selected unit's orders, as lines along the ground: from him to where the order
        he's on takes him, and on through the ones queued after it, each in its order's colour."""
        x, z = unit.x, unit.z
        for order in unit.orders:
            for px, pz in order.points():
                self.ground_line((x, z), (px, pz), order.COLOR)
                self.ring_at(px, pz, 0.2, order.COLOR, 0.7, height=0.04)
                x, z = px, pz

    def ground_line(self, a, b, color):
        dx, dz = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dz)
        if length > 1e-3:
            m = mathx.chain(mathx.translate(a[0], 0.04, a[1]), mathx.rot_y(math.atan2(dx, dz)),
                            mathx.scale(1.5, 0.5, length))
            self.gfx.draw(self.beam_mesh, m, (*color, 0.55))

    # ------------------------------------------------------------ the 2D overlay

    def draw_hud(self):
        """The overlay: health bars, the wave clock, the selection panel. Drawn fresh every frame."""
        mouse = pygame.mouse.get_pos()
        layout = self.panel_layout()
        hover_button = self.button_at(mouse)
        surface = self.overlay           # (the same one each frame: a new one, as big as the screen, took a few ms)
        surface.fill((0, 0, 0, 0))
        self.draw_health_bars(surface)
        if not self.over:
            self.draw_timers(surface)

        self.draw_wave_clock(surface)
        if not self.over:
            self.draw_pause_button(surface, PAUSE_BUTTON.collidepoint(mouse))
            self.draw_speed_button(surface, SPEED_BUTTON.collidepoint(mouse))
            self.draw_stores(surface)
            self.draw_gift_button(surface, GIFT_BUTTON.collidepoint(mouse))
            if STORES_PANEL.collidepoint(mouse):
                self.draw_tooltip(surface, STORES_PANEL, self.income_rows(), below=True)
            idle = len(self.idle_engineers())
            if idle:
                self.draw_idle_button(surface, idle, IDLE_PANEL.collidepoint(mouse))
        if self.message and not self.over:          # news only (a wave, a group made, a tile that won't do)
            self.banner(surface, self.message[0], (255, 205, 150))

        if layout:
            if self.hq_selected:
                self.draw_hq_panel(surface, layout, hover_button)
            elif self.structure_selected:
                self.draw_structure_panel(surface, layout, hover_button)
            elif self.deposit_selected:
                self.draw_deposit_panel(surface, layout)
            else:
                self.draw_units_panel(surface, layout, hover_button)
            if hover_button and hover_button[0] == "switch":
                self.draw_tooltip(surface, layout["panel"], [("On", "it makes what it makes"),
                                                             ("Off", "it waits, and uses nothing (O)")])
            elif hover_button and hover_button[0] not in AIMED_ORDERS + ("stop", "fire"):
                self.draw_tooltip(surface, layout["panel"], self.about(hover_button[0]))
            elif not hover_button and self.fighter_under(layout, mouse):
                self.draw_tooltip(surface, layout["panel"], self.record(self.fighter_under(layout, mouse)))

        if self.drag_from:
            (x0, y0), (x1, y1) = self.drag_from, mouse
            box = pygame.Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            if box.w >= DRAG_MIN or box.h >= DRAG_MIN:
                pygame.draw.rect(surface, (115, 255, 140, 40), box)
                pygame.draw.rect(surface, (115, 255, 140, 220), box, width=1)

        if self.over:
            self.draw_game_over(surface)
        self.gfx.upload_overlay(surface)

    def panel(self, surface, rect, alpha=190):
        pygame.draw.rect(surface, (14, 20, 32, alpha), rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255, 40), rect, width=1, border_radius=8)

    def lighten(self, surface, rect):
        """Lay a see-through white over what's drawn there (a hovered button). Drawn straight on
        the overlay, a see-through colour would replace what's under it, not lighten it."""
        light = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(light, (255, 255, 255, 40), light.get_rect(), border_radius=6)
        surface.blit(light, rect)

    def text(self, surface, text, pos, font=None, color=(235, 240, 248)):
        surface.blit((font or self.font).render(text, True, color), pos)

    def centred(self, surface, text, y, font, color=(235, 240, 248)):
        img = font.render(text, True, color)
        surface.blit(img, ((WIDTH - img.get_width()) // 2, y))

    def banner(self, surface, line, color):
        """A line of text in a panel at the top middle, under the wave clock."""
        width = self.font.size(line)[0] + 40
        self.panel(surface, pygame.Rect((WIDTH - width) // 2, 62, width, 34))
        self.centred(surface, line, 69, self.font, color)

    def bar(self, surface, rect, t, back=(10, 14, 20, 220), color=None):
        pygame.draw.rect(surface, back, rect, border_radius=2)
        if t > 0:
            pygame.draw.rect(surface, color or health_color(t), (rect.x, rect.y, max(1, int(rect.w * t)), rect.h),
                             border_radius=2)

    def draw_health_bars(self, surface):
        """Over the HQ (when it's hurt or selected), over anyone or any turret hurt or selected,
        and how far along each turret being built is. Under the bar of each soldier and turret,
        its rank (if it's gone up a level), and over any who's just gone up, a chevron rising."""
        view_proj = self.camera.view_proj()
        if self.base.hp < self.base.MAX_HP or self.hq_selected:
            hq = self.base.hq
            p = self.camera.to_screen(hq.i + hq.w / 2, self.base.TOP + 0.5, hq.j + hq.d / 2, *self.size, view_proj)
            if p:
                self.bar(surface, pygame.Rect(int(p[0]) - 45, int(p[1]), 90, 7), self.base.hp / self.base.MAX_HP)
        for turret in self.turrets:
            if not turret.alive or turret.blueprint:
                continue
            p = self.camera.to_screen(turret.x, 1.45, turret.z, *self.size, view_proj)   # just over its gun
            if not p:
                continue
            x, y = int(p[0]) - 20, self.bar_over(int(p[1]), turret.level, 5)
            if not turret.built:
                self.bar(surface, pygame.Rect(x, y - 7, 40, 5), turret.progress, color=(110, 175, 255))
            if not turret.built or turret.hp < turret.MAX_HP or turret is self.structure_selected:
                self.bar(surface, pygame.Rect(x, y, 40, 5), turret.hp / turret.MAX_HP)
            self.draw_rank(surface, x + 20, y + 8, turret.level, GOLD)          # under its bar, in the middle
        for building in self.buildings:
            if not building.alive or building.blueprint:
                continue
            p = self.camera.to_screen(building.x, building.TOP + 0.45, building.z, *self.size, view_proj)   # over its roof
            if not p:
                continue
            x, y = int(p[0]) - 30, int(p[1]) - 5
            if not building.built:
                self.bar(surface, pygame.Rect(x, y - 7, 60, 5), building.progress, color=(110, 175, 255))
            if not building.built or building.hp < building.MAX_HP or building is self.structure_selected:
                self.bar(surface, pygame.Rect(x, y, 60, 5), building.hp / building.MAX_HP)
        for unit in self.units + self.zombies:
            if not unit.alive:
                continue
            p = self.camera.to_screen(unit.x, unit.bar_height, unit.z, *self.size, view_proj)  # over his head
            if not (p and 0 <= p[0] < WIDTH and 0 <= p[1] < HEIGHT):
                continue
            level = level_of(unit)
            if isinstance(unit, Gunner) and unit.changing > 0:              # changing magazines...
                loading = 1 - unit.changing / unit.change_time
            elif isinstance(unit, Tank) and unit.reload > 0:                # ...or loading the next shell
                loading = 1 - unit.reload / unit.reload_time
            else:
                loading = None
            head = int(p[1]) - (2 * RELOAD_RING + 4 if loading is not None else 0)   # (room for the ring, under his rank)
            x, y = int(p[0]) - 14, self.bar_over(head, level, 4)
            if loading is not None:
                self.reload_ring(surface, int(p[0]), int(p[1]) - 3 - RELOAD_RING, loading)
            if unit.hp < unit.MAX_HP or unit in self.selected:
                self.bar(surface, pygame.Rect(x, y, 28, 4), unit.hp / unit.MAX_HP)
            if isinstance(unit, Trooper) and unit.hungry:
                self.hungry_mark(surface, x - 20, y - 6)
            self.draw_rank(surface, x + 14, y + 7, level, GOLD)
        for fighter, age in self.levels_up:
            height = 1.6 * fighter.SIZE - fighter.sink if fighter in self.units else 1.9
            if isinstance(fighter, Tank):
                height = fighter.bar_height + 0.5
            p = self.camera.to_screen(fighter.x, height, fighter.z, *self.size, view_proj)
            if p:
                t = age / LEVEL_UP_TIME
                self.chevron(surface, int(p[0]), int(p[1] - 30 * t), 8, (*GOLD, int(255 * (1 - t * t))))

    def draw_timers(self, surface):
        """Over the HQ, a round timer for each material it makes, and over each building that's
        working, one for what it makes: how long till the next batch. (Not zoomed out past
        PLAY_DIST, looking down on the map: there they'd only be a clutter.)"""
        if self.camera.dist > self.camera.PLAY_DIST:
            return
        view_proj = self.camera.view_proj()
        hq = self.base.hq
        made = [(made, every, done) for (made, every), done in zip(self.base.INCOME, self.base.making)]
        p = self.camera.to_screen(hq.i + hq.w / 2, self.base.TOP + 0.5, hq.j + hq.d / 2, *self.size, view_proj)
        if p and self.base.alive:
            self.timer_row(surface, int(p[0]), int(p[1]) - 26, made)
        for f in self.buildings:
            if f.working:
                p = self.camera.to_screen(f.x, TIMER_HEIGHTS[type(f)], f.z, *self.size, view_proj)
                if p:
                    self.timer_row(surface, int(p[0]), int(p[1]), [(f.MAKES, f.MAKE_TIME, f.making)], off=not f.on)

    def timer_row(self, surface, x, y, made, off=False):
        """A row of round timers centred on (x, y), one for each (what's made, every so many
        seconds, seconds toward the next) given (grey, and a pause sign for the mark, `off`)."""
        x0 = x - (len(made) - 1) * TIMER_GAP // 2
        for k, (cost, every, done) in enumerate(made):
            name = next(n for n, a in zip(MATERIALS, cost) if a)
            self.timer(surface, x0 + k * TIMER_GAP, y, name, done / every, every - done, off)

    def timer(self, surface, x, y, name, done, left, off=False):
        """One round timer, its middle at (x, y): a ring in the material's colour that fills
        round from the top as the next batch comes on (`done`, 0 to 1), the material's mark
        inside it, and under it the seconds `left`. Switched off: the ring grey, a pause sign
        for the mark."""
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            return
        pygame.draw.circle(surface, (14, 20, 32, 225), (x, y), TIMER_R + 2)
        pygame.draw.circle(surface, (60, 68, 82, 255), (x, y), TIMER_R)
        if done > 0:
            steps = max(2, int(done * 48))
            points = [(x, y)] + [(x + TIMER_R * math.sin(2 * math.pi * done * k / steps),
                                  y - TIMER_R * math.cos(2 * math.pi * done * k / steps)) for k in range(steps + 1)]
            pygame.draw.polygon(surface, (120, 126, 136) if off else MATERIAL_COLORS[name], points)
        pygame.draw.circle(surface, (24, 30, 42, 255), (x, y), TIMER_R - 4)
        if off:
            for dx in (-4, 1):
                pygame.draw.rect(surface, SWITCH_OFF, (x + dx, y - 5, 3, 10))
        else:
            self.material_icon(surface, name, x - 8, y - 8)
        label = self.font_small.render(f"{math.ceil(left - 1e-6)}s", True, (235, 240, 248))
        tag = pygame.Rect(0, 0, label.get_width() + 8, label.get_height() - 2)
        tag.center = (x, y + TIMER_R + 9)
        pygame.draw.rect(surface, (14, 20, 32, 210), tag, border_radius=4)
        surface.blit(label, label.get_rect(center=tag.center))

    def chevron(self, surface, x, y, half, color):
        """One chevron, pointing up, `half` wide each way of x, its arms' ends at y, with a dark
        edge round it so it shows up on anything."""
        points = [(x - half, y), (x, y - half * 3 // 4), (x + half, y)]
        pygame.draw.lines(surface, (14, 20, 32, color[3] if len(color) > 3 else 255), False, points, 5)
        pygame.draw.lines(surface, color, False, points, 3 if half > 5 else 2)

    def star(self, surface, x, y, color):
        """A small five-pointed star, its middle at (x, y), with a dark edge round it."""
        points = [(x + (5 if k % 2 == 0 else 2.2) * math.sin(k * math.pi / 5),
                   y - (5 if k % 2 == 0 else 2.2) * math.cos(k * math.pi / 5)) for k in range(10)]
        pygame.draw.polygon(surface, (14, 20, 32), points, 3)
        pygame.draw.polygon(surface, color, points)

    def draw_rank(self, surface, x, top, level, color):
        """A fighter's level, centred on x and stacked down from `top` (just under a health bar,
        where there is one): a chevron for each level past the first, up to the fifth; past
        that (a turret goes to ten), a star, and under it a chevron for each level past the sixth."""
        if level > 5:
            self.star(surface, x, top + 5, color)
            top += 9
            level -= 5
        for k in range(level - 1):
            self.chevron(surface, x, top + 3 + 4 * k, 4, color)

    def reload_ring(self, surface, x, y, done):
        """Over a soldier changing magazines, under his rank: a small ring, its middle at (x, y),
        that fills round clockwise from the top as the change goes."""
        r = RELOAD_RING
        pygame.draw.circle(surface, (14, 20, 32, 220), (x, y), r + 2)
        pygame.draw.circle(surface, (90, 98, 110), (x, y), r, 2)
        if done > 0:
            points = [(x, y)] + [(x + r * math.sin(2 * math.pi * done * k / 16), y - r * math.cos(2 * math.pi * done * k / 16))
                                 for k in range(17)]
            pygame.draw.polygon(surface, (235, 240, 248), points)
        pygame.draw.circle(surface, (14, 20, 32), (x, y), 2)

    def hungry_mark(self, surface, x, y):
        """Over a hungry trooper, beside his health bar: a crate of supply, struck through in red."""
        self.material_icon(surface, "supply", x, y)
        pygame.draw.line(surface, (20, 10, 10), (x, y + 15), (x + 15, y), 5)
        pygame.draw.line(surface, NONE_LEFT, (x, y + 15), (x + 15, y), 3)

    def bar_over(self, head, level, bar):
        """Where a health bar `bar` pixels tall goes so that it, and the chevrons of `level`
        under it, sit just over `head` (the top of the unit or turret, on screen) and not on it."""
        rank = self.rank_height(level)
        return head - 2 - rank - (3 if rank else 0) - bar

    @staticmethod
    def rank_height(level):
        """How tall draw_rank's rank is, in pixels, for this level (0 at the first)."""
        if level > 5:
            return 9 + (0 if level == 6 else 5 + 4 * (level - 7))
        return 0 if level < 2 else 5 + 4 * (level - 2)

    def draw_wave_clock(self, surface):
        """The countdown to the next wave, and the zombies about. While paused: "Paused", over the countdown."""
        left = max(0.0, self.waves.left)
        walking = sum(z.alive for z in self.zombies)
        countdown = f"Wave {self.waves.number + 1} in {int(left) // 60}:{int(left) % 60:02d}"
        if self.paused:
            title, color = "Paused", GOLD
            line = f"{countdown}  ·  {walking} zombie{'s' * (walking != 1)} on the map"
        else:
            title, color = countdown, (255, 150, 135) if left < 5 else (235, 240, 248)
            line = f"{walking} zombie{'s' * (walking != 1)} on the map  ·  {self.kills} down"
        width = max(self.font_big.size(title)[0], self.font_small.size(line)[0]) + 36
        rect = pygame.Rect((WIDTH - width) // 2, 12, width, 46)
        self.panel(surface, rect)
        self.centred(surface, title, 15, self.font_big, color)
        self.centred(surface, line, 38, self.font_small, GREY)

    def draw_pause_button(self, surface, hovered):
        """Two bars to pause; a triangle to go on once it's paused."""
        rect = PAUSE_BUTTON
        self.panel(surface, rect)
        if hovered:
            pygame.draw.rect(surface, GOLD, rect, width=2, border_radius=8)
        color = GOLD if self.paused or hovered else (235, 240, 248)
        cx, cy = rect.center
        if self.paused:
            pygame.draw.polygon(surface, color, [(cx - 6, cy - 9), (cx - 6, cy + 9), (cx + 9, cy)])
        else:
            for dx in (-6, 2):
                pygame.draw.rect(surface, color, (cx + dx, cy - 8, 4, 16), border_radius=1)

    def draw_speed_button(self, surface, hovered):
        """"×2", lit gold with a gold rim while the game goes at double speed."""
        rect = SPEED_BUTTON
        self.panel(surface, rect)
        fast = self.speed == FAST
        if hovered:
            self.lighten(surface, rect)
        if fast:
            pygame.draw.rect(surface, GOLD, rect, width=2, border_radius=8)
        label = self.font_big.render(f"×{FAST}", True, GOLD if fast else (235, 240, 248))
        surface.blit(label, label.get_rect(center=rect.center))

    def material_icon(self, surface, name, x, y):
        """A material's mark, 16 pixels square, its top left at (x, y): a crate of supply, a bar
        of metal, a bullet."""
        color = MATERIAL_COLORS[name]
        if name == "supply":
            pygame.draw.rect(surface, color, (x + 1, y + 2, 14, 13), border_radius=2)
            pygame.draw.rect(surface, (96, 66, 34), (x + 1, y + 2, 14, 13), width=1, border_radius=2)
            pygame.draw.line(surface, (96, 66, 34), (x + 1, y + 8), (x + 14, y + 8))
            pygame.draw.line(surface, (96, 66, 34), (x + 8, y + 2), (x + 8, y + 14))
        elif name == "metal":
            pygame.draw.polygon(surface, color, [(x + 4, y + 4), (x + 12, y + 4), (x + 15, y + 13), (x + 1, y + 13)])
            pygame.draw.polygon(surface, (90, 96, 106), [(x + 4, y + 4), (x + 12, y + 4), (x + 15, y + 13), (x + 1, y + 13)], 1)
        else:                                          # a cartridge: a brass case, a copper tip
            pygame.draw.rect(surface, color, (x + 5, y + 6, 6, 10), border_radius=1)
            pygame.draw.rect(surface, (120, 92, 40), (x + 4, y + 14, 8, 2))
            pygame.draw.polygon(surface, (196, 112, 70), [(x + 5, y + 6), (x + 11, y + 6), (x + 10, y + 2), (x + 8, y), (x + 6, y + 2)])

    def draw_stores(self, surface):
        """The materials there are to spend, at the top left: each one's mark and how much (gold
        when there's no room for more), and beside it, as in Beyond All Reason, what's used of it (red, over) and what's made (green,
        under), every UPKEEP_TIME."""
        self.panel(surface, STORES_PANEL)
        flows = self.flows()
        x, y = STORES_PANEL.x + 12, STORES_PANEL.y
        for name, amount in zip(MATERIALS, self.base.stores.amounts()):
            self.material_icon(surface, name, x, y + 10)
            full = self.base.stores.full(name)
            self.text(surface, f"{int(amount)}", (x + 22, y + 8), self.font_bold,
                      NONE_LEFT if amount <= 0 else GOLD if full else (235, 240, 248))
            made, used = flows[name]
            self.text(surface, f"-{used}", (x + 72, y + 3), self.font_tiny, USED_RED if used else GREY)
            self.text(surface, f"+{made}", (x + 72, y + 18), self.font_tiny, MADE_GREEN if made else GREY)
            x += STORES_SLOT

    def flows(self):
        """What's made and what's used of each material every UPKEEP_TIME, at the rate things go
        now: {name: (made, used)}. Made: by the HQ and the buildings at work (not one that's
        waiting). Used: what the troops eat, what the buildings at work use up (a bullet
        factory's supply and metal), what's being trained and built (paid as it goes, at the
        pace it went last step: nothing while it waits), and the bullets fired over the last
        UPKEEP_TIME."""
        stores = self.base.stores
        made, used = dict.fromkeys(MATERIALS, 0.0), dict.fromkeys(MATERIALS, 0.0)
        makers = [(cost, FREE, every) for cost, every in self.base.INCOME] if self.base.alive else []
        makers += [(b.MAKES, b.INPUT, b.MAKE_TIME) for b in self.buildings if b.working and b.on and b.can_make(stores)]
        for cost, uses, every in makers:
            for name, amount, use in zip(MATERIALS, cost, uses):
                made[name] += amount * UPKEEP_TIME / every
                used[name] += use * UPKEEP_TIME / every
        while self.fired and self.fired[0] < self.played - UPKEEP_TIME:
            self.fired.popleft()
        for unit in self.units:
            if unit.alive:
                for name, amount in zip(MATERIALS, unit.upkeep):
                    used[name] += amount
        trainers = [self.base] + [b for b in self.buildings if isinstance(b, VehicleFactory)]
        work = [(t.queue[0].COST, t.train_rate) for t in trainers if t.queue and t.train_rate]
        work += [(s.COST, s.build_rate) for s in self.turrets + self.buildings if s.alive and s.build_rate]
        for cost, rate in work:
            for name, amount in zip(MATERIALS, cost):
                used[name] += amount * rate * UPKEEP_TIME
        used["bullets"] += len(self.fired)
        return {name: (round(made[name]), round(used[name])) for name in MATERIALS}

    def income_rows(self):
        """What the HQ and the buildings make, and what the troops eat and the guns fire, for
        the materials' tooltip."""
        rows = [("Beside each", f"what's used (red) and made (green) every {UPKEEP_TIME:g} s")]
        for made, every in self.base.INCOME:
            name, amount = next((n, a) for n, a in zip(MATERIALS, made) if a)
            rows.append((name.capitalize(), f"+{amount} every {every:g} s"))
        for kind in MAKERS:
            working = sum(type(b) is kind and b.working and b.on for b in self.buildings)
            name, amount = next((n, a) for n, a in zip(MATERIALS, kind.MAKES) if a)
            uses = f", from {kind.INPUT.text()}" if any(kind.INPUT) else ""
            rows.append((name.capitalize(), f"+{amount} every {kind.MAKE_TIME:g} s a {kind.NAME.lower()}{uses} ({working} working)"))
        rows.append(("Most bullets", f"{MOST['bullets']}: with that many, bullet factories wait"))
        troops = [u for u in self.units if u.alive]
        hungry = sum(u.hungry for u in troops)
        eat = sum(u.upkeep.supply for u in troops)
        rows.append(("Troops eat", f"{eat} supply every {UPKEEP_TIME:g} s: {Soldier.UPKEEP.supply} a man, "
                                   f"{Tank.UPKEEP.supply} a tank, less a level up ({len(troops)} troops, "
                                   f"next in {math.ceil(UPKEEP_TIME - self.base.feeding)} s)"))
        if hungry:
            rows.append(("Hungry", f"{hungry}: they walk {1 - HUNGRY_PACE:.0%} slower, "
                                   f"and hit {HUNGRY_MISS:.0%} less often"))
        return rows + [("Every shot", f"uses a bullet ({len(self.fired)} in the last {UPKEEP_TIME:g} s)")]

    def draw_gift_button(self, surface, hovered):
        """A plus: add a load of each material, for testing."""
        rect = GIFT_BUTTON
        self.panel(surface, rect)
        if hovered:
            self.lighten(surface, rect)
            pygame.draw.rect(surface, GOLD, rect, width=2, border_radius=8)
        color = GOLD if hovered else (235, 240, 248)
        cx, cy = rect.center
        pygame.draw.rect(surface, color, (cx - 8, cy - 2, 16, 4), border_radius=1)
        pygame.draw.rect(surface, color, (cx - 2, cy - 8, 4, 16), border_radius=1)
        if hovered:
            self.draw_tooltip(surface, rect, [("For testing", "add " + TEST_GIFT.text())], below=True)

    def draw_tooltip(self, surface, panel, rows, below=False):
        """A small box of (label, value) rows just above the panel (or below it), while the mouse
        is on one of its buttons: the labels in grey, the values lined up beside them."""
        font, line = self.font_small, self.font_small.get_linesize()
        column = max(font.size(label)[0] for label, _ in rows) + 14
        width = column + max(font.size(value)[0] for _, value in rows) + 28
        height = len(rows) * line + 16
        x = min(panel.x, WIDTH - 12 - width)           # (kept on the screen, over a panel at the right)
        rect = pygame.Rect(x, panel.bottom + 8 if below else panel.y - 8 - height, width, height)
        self.panel(surface, rect, alpha=235)
        for k, (label, value) in enumerate(rows):
            y = rect.y + 8 + k * line
            self.text(surface, label, (rect.x + 14, y), font, GREY)
            self.text(surface, value, (rect.x + 14 + column, y), font)

    def about(self, what):
        """What a button tells you while the mouse is on it: a kind of unit to train, a kind of
        turret, or a trench. (A gun's damage a second is as if every shot hit.)"""
        if what is Trench:
            return [("Cover", f"acid does {1 - COVER_ACID:.0%} less"),
                    ("Dig time", f"{Trench.BUILD_TIME:g} s a tile, less with more hands"), ("Cost", "free"),
                    ("Built over", "a turret or a building can go up on it (it's filled in)")]
        rows = []
        if what is Tank:
            low, high = what.DAMAGE
            gun = MachineGun
            rows += [("Main gun", f"{low}-{high} a shell, bursting {what.BLAST:g} tiles round (less at the edge)"),
                     ("Range", self.range_text(what)),
                     ("Reload", f"{what.RELOAD:g} s ({what.LEVEL_RELOAD:g} s quicker a level)"),
                     ("Shells", f"{what.SHELL.bullets} bullets each"),
                     ("Machine guns", f"2: {gun.DAMAGE[0]}-{gun.DAMAGE[1]} a shot every {gun.RELOAD:g} s, "
                                      f"range {self.range_text(gun)}")]
        elif issubclass(what, Fighter):
            low, high = what.DAMAGE
            rows += [("Damage", f"{low}-{high} a shot, {(low + high) / 2 / what.RELOAD:.0f} a second"),
                     ("Range", self.range_text(what)), ("Bullets", f"one a shot, {1 / what.RELOAD:g} a second")]
            if issubclass(what, Gunner):
                rows.append(("Magazine", f"{what.MAGAZINE} rounds, {what.MAGAZINE_TIME:g} s to change "
                                         f"(+{what.LEVEL_ROUNDS} rounds, {what.LEVEL_CHANGE:g} s quicker a level)"))
        rows.append(("Health", f"{what.MAX_HP}"))
        if issubclass(what, Trooper):
            less = f" ({what.LEVEL_UPKEEP} less a level)" if what.LEVEL_UPKEEP else ""
            rows.append(("Upkeep", f"{what.UPKEEP.supply} supply every {UPKEEP_TIME:g} s{less}"))
        if what is Engineer:
            rows.append(("Builds", "turrets and buildings (no gun)"))
        if what is Factory:
            rows.insert(0, ("Makes", f"{what.MAKES.bullets} bullets every {what.MAKE_TIME:g} s, from {what.INPUT.text()}"))
            rows.append(("Size", f"{what.W} by {what.D} tiles"))
        elif what is RadarStation:
            rows.insert(0, ("Opens", "the 8 squares round this one: the whole map, 600 by 600 tiles"))
            rows.append(("Size", f"{what.W} by {what.D} tiles (one is all it takes)"))
        elif what is VehicleFactory:
            rows.insert(0, ("Trains", "tanks, one at a time"))
            rows.append(("Size", f"{what.W} by {what.D} tiles"))
        elif issubclass(what, Extractor):             # a building that goes up beside a deposit
            name = what.DEPOSIT.MATERIAL
            yard = what.DEPOSIT.NAME.lower()
            rows.insert(0, ("Makes", f"{getattr(what.MAKES, name)} {name} every {what.MAKE_TIME:g} s, from a {yard}"))
            rows.append(("Size", f"{what.W} by {what.D} tiles, beside a {yard}"))
        if issubclass(what, Structure):
            rows.append(("Build time", f"{what.BUILD_TIME:g} s, less with more hands"))
        else:
            rows.append(("Train time", f"{what.TRAIN_TIME:g} s"))
        rows.append(("Cost", self.cost_text(what)))
        return rows

    @staticmethod
    def cost_text(kind):
        """What a kind costs, as it's paid while it's built or trained (by one engineer):
        "50 metal every 10 s, 150 in all"."""
        time = kind.BUILD_TIME if issubclass(kind, Structure) else kind.TRAIN_TIME
        every = min(kind.COST_EVERY, time)
        rate = [(round(amount * every / time), name) for name, amount in zip(MATERIALS, kind.COST) if amount]
        rate = ", ".join(f"{amount} {name}" for amount, name in rate)
        return f"{rate} every {every:g} s while it's {'built' if issubclass(kind, Structure) else 'trained'} " \
               f"({kind.COST.text()} in all)" if rate else "free"

    @staticmethod
    def range_text(kind):
        """A kind's range, and how far its long shots (which mostly miss) reach."""
        return f"{kind.RANGE:g}, long shots to {kind.RANGE * kind.LONG_SHOTS:g}"

    def draw_game_over(self, surface):
        shade = pygame.Surface(self.size, pygame.SRCALPHA)
        shade.fill((8, 6, 6, 120))
        surface.blit(shade, (0, 0))
        rect = pygame.Rect((WIDTH - 520) // 2, HEIGHT // 2 - 80, 520, 150)
        self.panel(surface, rect, alpha=225)
        minutes, seconds = divmod(int(self.played), 60)
        waves = self.waves.number
        self.centred(surface, "Your HQ has fallen", rect.y + 18, self.font_huge, (255, 140, 125))
        self.centred(surface, f"Held out {minutes}:{seconds:02d}  ·  {waves} wave{'s' * (waves != 1)}  ·  "
                              f"{self.kills} zombies down", rect.y + 80, self.font)
        self.centred(surface, "Press R to play again", rect.y + 112, self.font_bold, GOLD)

    # ------------------------------------------------------------ the selection panel

    def panel_layout(self):
        """Where the selection panel (bottom left) and its buttons are, or None when nothing's selected.
        Buttons are (what they make, rect): a kind of unit to train, or a kind of turret or a Trench to make."""
        if self.hq_selected:                         # as wide as its name, its buttons in a row, or what it makes
            kinds = self.base.TRAINS
            inner = max(self.font_title.size("Headquarters")[0], len(kinds) * (BUTTON + 10) - 10,
                        self.income_width(self.income_items(self.base.INCOME)))
            panel = pygame.Rect(PANEL_X, HEIGHT - 12 - HQ_PANEL_H, inner + 28, HQ_PANEL_H)
            return {"panel": panel, "buttons": [(kind, pygame.Rect(panel.x + 14 + k * (BUTTON + 10), panel.y + 80,
                                                                   BUTTON, BUTTON)) for k, kind in enumerate(kinds)]}
        if self.structure_selected:                  # its name and health (and a bar of how far it's built)
            t = self.structure_selected
            rows = isinstance(t, Maker) + isinstance(t, Extractor) + (isinstance(t, Maker) and any(t.INPUT))
            height = (80 if t.built else 96) + 24 * rows
            made = [self.income_items(((t.MAKES, t.MAKE_TIME),)), self.income_items(((t.INPUT, t.MAKE_TIME),), "-")] \
                if isinstance(t, Maker) else []
            width = max([self.font_title.size(self.structure_title(t))[0] + (20 if level_of(t) > 1 else 0)
                         + (SWITCH[0] + 14 if isinstance(t, Maker) else 0), 154]
                        + [self.income_width(items) + 10 for items in made if items]) + 28
            if isinstance(t, VehicleFactory) and t.ready:   # a button for each kind it trains
                height += BUTTON + 10
                width = max(width, len(t.TRAINS) * (BUTTON + 10) + 18)
            panel = pygame.Rect(PANEL_X, HEIGHT - 12 - height, width, height)
            switch = pygame.Rect(panel.right - 14 - SWITCH[0], panel.y + 12, *SWITCH)
            if isinstance(t, VehicleFactory) and t.ready:
                return {"panel": panel, "buttons": [(kind, pygame.Rect(panel.x + 14 + k * (BUTTON + 10), panel.y + 76,
                                                                       BUTTON, BUTTON)) for k, kind in enumerate(t.TRAINS)]}
            return {"panel": panel, "buttons": [("switch", switch)] if isinstance(t, Maker) else []}
        if self.deposit_selected:                    # its name, and a bar of what's left in it
            width = max(self.font_title.size(self.deposit_selected.NAME)[0], 180) + 28
            return {"panel": pygame.Rect(PANEL_X, HEIGHT - 12 - 84, width, 84), "buttons": []}
        if self.selected:                            # portraits, then a row of orders, then a row of builds
            rows = (min(len(self.selected), 24) + 7) // 8
            kinds = ([Turret, MinigunTurret, *BUILDINGS] if self.engineers else []) + ([Trench] if self.diggers else [])
            height = 56 + rows * self.portrait_row() + 34 + (10 + 64 if kinds else 0) + 14
            title = self.selection_title()
            inner = max(self.title_font(title).size(title)[0], min(len(self.selected), 8) * 37 - 5,
                        sum(width + 6 for _, _, width in self.order_buttons()) - 6, len(kinds) * 72 - 8)
            panel = pygame.Rect(PANEL_X, HEIGHT - 12 - height, inner + 28, height)
            y = panel.y + 56 + rows * self.portrait_row()
            buttons, x = [], panel.x + 14
            for name, _, width in self.order_buttons():
                buttons.append((name, pygame.Rect(x, y, width, 34)))
                x += width + 6
            buttons += [(kind, pygame.Rect(panel.x + 14 + k * 72, y + 44, 64, 64)) for k, kind in enumerate(kinds)]
            return {"panel": panel, "buttons": buttons}
        return None

    def draw_icon(self, surface, rect, kind):
        """A flat portrait: a soldier's helmet, an engineer's hard hat and vest, a turret, a
        bullet factory, a salvage crane, a loading dock post, a radar station or a trench."""
        r = rect
        pygame.draw.rect(surface, (52, 64, 82), r, border_radius=6)
        cx, s = r.centerx, r.w / 76
        team = tuple(int(c * 255) for c in PLAYER_BLUE)
        if kind is RadarStation:                       # a dish, tipped back, on a pedestal on a deck
            white, grey = (214, 216, 220), (120, 124, 130)
            pygame.draw.rect(surface, (110, 112, 108), (r.x + 8 * s, r.y + 56 * s, 60 * s, 7 * s))
            pygame.draw.rect(surface, grey, (r.x + 32 * s, r.y + 38 * s, 12 * s, 18 * s))
            pygame.draw.polygon(surface, white, [(r.x + 14 * s, r.y + 16 * s), (r.x + 58 * s, r.y + 8 * s),
                                                 (r.x + 50 * s, r.y + 30 * s), (r.x + 26 * s, r.y + 40 * s)])
            pygame.draw.line(surface, (40, 42, 44), (r.x + 38 * s, r.y + 26 * s), (r.x + 26 * s, r.y + 14 * s), 2)
            pygame.draw.rect(surface, (60, 62, 66), (r.x + 22 * s, r.y + 10 * s, 6 * s, 6 * s))
            for lx in (12, 64):
                pygame.draw.circle(surface, (255, 238, 180), (int(r.x + lx * s), int(r.y + 48 * s)), max(2, int(3 * s)))
            return
        if kind is SalvageCrane:                       # a crane's arm, its magnet holding a car, over its tracks
            yellow = tuple(int(c * 255) for c in models.CRANE_YELLOW)
            pygame.draw.rect(surface, (40, 42, 44), (r.x + 8 * s, r.y + 54 * s, 30 * s, 8 * s))
            pygame.draw.rect(surface, yellow, (r.x + 10 * s, r.y + 42 * s, 24 * s, 12 * s))
            pygame.draw.line(surface, yellow, (r.x + 24 * s, r.y + 44 * s), (r.x + 44 * s, r.y + 10 * s), max(2, int(5 * s)))
            pygame.draw.line(surface, yellow, (r.x + 44 * s, r.y + 10 * s), (r.x + 58 * s, r.y + 26 * s), max(2, int(4 * s)))
            pygame.draw.line(surface, (40, 42, 44), (r.x + 58 * s, r.y + 26 * s), (r.x + 58 * s, r.y + 34 * s), 2)
            pygame.draw.rect(surface, (60, 60, 64), (r.x + 50 * s, r.y + 34 * s, 16 * s, 4 * s))
            pygame.draw.rect(surface, (150, 50, 40), (r.x + 46 * s, r.y + 38 * s, 24 * s, 8 * s))
            pygame.draw.rect(surface, (30, 36, 42), (r.x + 50 * s, r.y + 38 * s, 12 * s, 4 * s))
            return
        if kind is LoadingDock:                        # a truck backed up, crates by it, sandbags in front
            team = tuple(int(c * 255) for c in PLAYER_BLUE)
            pygame.draw.rect(surface, (214, 216, 210), (r.x + 8 * s, r.y + 22 * s, 34 * s, 26 * s))
            pygame.draw.rect(surface, team, (r.x + 42 * s, r.y + 30 * s, 14 * s, 18 * s))
            pygame.draw.rect(surface, (30, 36, 42), (r.x + 46 * s, r.y + 32 * s, 8 * s, 6 * s))
            pygame.draw.rect(surface, team, (r.x + 8 * s, r.y + 36 * s, 34 * s, 3 * s))
            for wx in (16, 48):
                pygame.draw.rect(surface, (26, 26, 28), (r.x + wx * s, r.y + 46 * s, 8 * s, 6 * s))
            for k, (cx, cy) in enumerate(((58, 46), (58, 38))):
                pygame.draw.rect(surface, (150, 112, 70), (r.x + cx * s, r.y + cy * s, 10 * s, 8 * s))
            for k in range(5):
                pygame.draw.rect(surface, (160, 146, 106), (r.x + (6 + 13 * k) * s, r.y + 56 * s, 12 * s, 6 * s),
                                 border_radius=int(2 * s))
            return
        if kind is Tank:                               # side on: tracks and wheels, the hull, the turret, its gun
            olive, dark = (92, 100, 66), (66, 74, 48)
            pygame.draw.rect(surface, (34, 34, 34), (r.x + 6 * s, r.y + 46 * s, 64 * s, 14 * s), border_radius=int(7 * s))
            for k in range(5):
                pygame.draw.circle(surface, (78, 80, 72), (int(r.x + (15 + 11.5 * k) * s), int(r.y + 53 * s)), max(2, int(4 * s)))
            pygame.draw.rect(surface, olive, (r.x + 8 * s, r.y + 38 * s, 60 * s, 9 * s))
            pygame.draw.polygon(surface, olive, [(r.x + 68 * s, r.y + 38 * s), (r.x + 72 * s, r.y + 44 * s),
                                                 (r.x + 68 * s, r.y + 47 * s)])
            pygame.draw.rect(surface, olive, (r.x + 20 * s, r.y + 26 * s, 30 * s, 12 * s), border_radius=int(3 * s))
            pygame.draw.rect(surface, team, (r.x + 26 * s, r.y + 29 * s, 7 * s, 6 * s))
            pygame.draw.rect(surface, dark, (r.x + 50 * s, r.y + 29 * s, 22 * s, 3 * s))
            pygame.draw.rect(surface, (46, 48, 52), (r.x + 69 * s, r.y + 28 * s, 4 * s, 5 * s))
            pygame.draw.rect(surface, dark, (r.x + 28 * s, r.y + 22 * s, 6 * s, 4 * s))
            return
        if kind is VehicleFactory:                     # a steel shed, its wide door open, a workshop beside it
            clad, roof = (168, 171, 160), (107, 112, 115)
            pygame.draw.rect(surface, (150, 150, 140), (r.x + 50 * s, r.y + 38 * s, 20 * s, 22 * s))
            pygame.draw.rect(surface, (51, 51, 51), (r.x + 49 * s, r.y + 36 * s, 22 * s, 3 * s))
            pygame.draw.rect(surface, clad, (r.x + 6 * s, r.y + 24 * s, 46 * s, 36 * s))
            pygame.draw.polygon(surface, roof, [(r.x + 4 * s, r.y + 25 * s), (r.x + 29 * s, r.y + 12 * s),
                                                (r.x + 54 * s, r.y + 25 * s)])
            pygame.draw.rect(surface, (12, 12, 14), (r.x + 14 * s, r.y + 34 * s, 26 * s, 26 * s))
            pygame.draw.rect(surface, (235, 185, 40), (r.x + 12 * s, r.y + 34 * s, 2 * s, 26 * s))
            pygame.draw.rect(surface, (235, 185, 40), (r.x + 40 * s, r.y + 34 * s, 2 * s, 26 * s))
            pygame.draw.rect(surface, (128, 130, 134), (r.x + 12 * s, r.y + 30 * s, 30 * s, 4 * s))
            pygame.draw.rect(surface, team, (r.x + 43 * s, r.y + 40 * s, 7 * s, 6 * s))
            return
        if kind is Factory:                            # a brick hall with a glass roof, two chimneys, a tank
            brick, dark, stone = (150, 72, 54), (104, 50, 38), (190, 180, 160)
            for k, h in enumerate((40, 34)):
                pygame.draw.rect(surface, brick, (r.x + (14 + 12 * k) * s, r.y + (64 - h - 14) * s, 8 * s, h * s))
                pygame.draw.rect(surface, dark, (r.x + (13 + 12 * k) * s, r.y + (64 - h - 16) * s, 10 * s, 3 * s))
            pygame.draw.rect(surface, brick, (r.x + 8 * s, r.y + 36 * s, 46 * s, 26 * s))
            pygame.draw.rect(surface, stone, (r.x + 7 * s, r.y + 34 * s, 48 * s, 3 * s))
            pygame.draw.rect(surface, (40, 52, 60), (r.x + 14 * s, r.y + 29 * s, 34 * s, 5 * s))
            for k in range(3):
                pygame.draw.rect(surface, (34, 42, 50), (r.x + (12 + 12 * k) * s, r.y + 41 * s, 6 * s, 10 * s))
            pygame.draw.rect(surface, team, (r.x + 25 * s, r.y + 52 * s, 12 * s, 3 * s))
            pygame.draw.rect(surface, (160, 164, 168), (r.x + 56 * s, r.y + 40 * s, 12 * s, 22 * s),
                             border_radius=int(5 * s))
            return
        if kind in (Turret, MinigunTurret):
            pygame.draw.rect(surface, (110, 108, 102), (r.x + 12 * s, r.bottom - 22 * s, r.w - 24 * s, 16 * s))
            pygame.draw.rect(surface, team, (r.x + 12 * s, r.bottom - 15 * s, r.w - 24 * s, 3 * s))
            pygame.draw.rect(surface, (60, 62, 66), (cx - 6 * s, r.y + 34 * s, 12 * s, 20 * s))
            pygame.draw.rect(surface, (46, 48, 52), (cx - 13 * s, r.y + 22 * s, 26 * s, 16 * s))
            pygame.draw.rect(surface, (82, 90, 60), (cx - 20 * s, r.y + 18 * s, 10 * s, 24 * s))
            if kind is MinigunTurret:                  # three barrels and a clamp, and the ammunition box
                for k in range(3):
                    pygame.draw.rect(surface, (170, 174, 178), (cx - 35 * s, r.y + (24 + 5 * k) * s, 26 * s, 3 * s))
                pygame.draw.rect(surface, (60, 62, 66), (cx - 30 * s, r.y + 22 * s, 4 * s, 16 * s))
                pygame.draw.rect(surface, (235, 185, 40), (cx + 8 * s, r.y + 26 * s, 16 * s, 18 * s))
            else:
                pygame.draw.rect(surface, (46, 48, 52), (cx - 34 * s, r.y + 27 * s, 26 * s, 5 * s))
            return
        if kind is Trench:
            pygame.draw.rect(surface, (92, 74, 54), (r.x + 6 * s, r.y + 40 * s, r.w - 12 * s, 28 * s))
            pygame.draw.rect(surface, (44, 34, 26), (r.x + 22 * s, r.y + 44 * s, r.w - 44 * s, 24 * s))
            for k in range(3):
                for side in (-1, 1):
                    pygame.draw.rect(surface, (178, 158, 112), (cx + side * 29 * s - 8 * s, r.y + (28 + 7 * k) * s,
                                                                16 * s, 6 * s), border_radius=int(2 * s))
            return
        engineer = kind is Engineer
        body, vest = ((62, 69, 82), (242, 122, 26)) if engineer else ((84, 92, 58), (120, 107, 77))
        pygame.draw.rect(surface, body, (r.x + 10 * s, r.bottom - 22 * s, r.w - 20 * s, 22 * s),
                         border_top_left_radius=int(12 * s), border_top_right_radius=int(12 * s))
        pygame.draw.rect(surface, vest, (cx - 15 * s, r.bottom - 22 * s, 30 * s, 22 * s))
        if engineer:
            pygame.draw.rect(surface, (220, 222, 214), (cx - 15 * s, r.bottom - 14 * s, 30 * s, 3 * s))
        pygame.draw.rect(surface, (219, 173, 138), (cx - 11 * s, r.y + 24 * s, 22 * s, 26 * s),
                         border_radius=int(5 * s))
        for side in (-1, 1):
            pygame.draw.rect(surface, (30, 26, 22), (cx + side * 5 * s - 2 * s, r.y + 34 * s, 4 * s, 4 * s))
        hat = (245, 199, 36) if engineer else (84, 92, 58)
        pygame.draw.ellipse(surface, hat, (cx - 17 * s, r.y + 11 * s, 34 * s, 24 * s))
        pygame.draw.rect(surface, hat, (cx - 19 * s, r.y + 25 * s, 38 * s, 5 * s), border_radius=int(2 * s))
        if engineer:                                   # (a soldier's helmet is plain)
            pygame.draw.rect(surface, team, (cx - 17 * s, r.y + 21 * s, 34 * s, 4 * s))

    def draw_button(self, surface, rect, kind, key, hovered, count=0, progress=None):
        self.draw_icon(surface, rect, kind)
        if self.base.stores.lacks(kind.COST):          # none of something it takes, to start on it: dimmed
            shade = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(shade, (14, 20, 32, 150), shade.get_rect(), border_radius=6)
            surface.blit(shade, rect)
        self.button_marks(surface, rect, key, hovered, count)
        if progress is not None:
            bar = pygame.Rect(rect.x + 4, rect.bottom - 10, rect.w - 8, 6)
            pygame.draw.rect(surface, (10, 14, 20, 230), bar, border_radius=3)
            pygame.draw.rect(surface, (115, 230, 135), (bar.x, bar.y, int(bar.w * progress), bar.h), border_radius=3)

    def button_marks(self, surface, rect, key, hovered, count=0):
        """Over a button's picture: lighter and a gold rim while the mouse is on it, its key at
        the top left, and a count (if any) in a round badge at the top right, longer for big numbers."""
        if hovered:
            self.lighten(surface, rect)
        pygame.draw.rect(surface, GOLD if hovered else (255, 255, 255, 70), rect, width=2, border_radius=6)
        tag = pygame.Rect(rect.x + 4, rect.y + 4, 18, 18)
        pygame.draw.rect(surface, (14, 20, 32, 220), tag, border_radius=4)
        self.text(surface, key, (tag.centerx - self.font_bold.size(key)[0] // 2, tag.y), self.font_bold, GOLD)
        if count:
            badge = self.font_bold.render(str(count), True, (20, 24, 30))
            width = max(20, badge.get_width() + 10)
            spot = pygame.Rect(rect.right - 4 - width, rect.y + 4, width, 20)
            pygame.draw.rect(surface, GOLD, spot, border_radius=10)
            surface.blit(badge, badge.get_rect(center=spot.center))

    def draw_idle_button(self, surface, count, hovered):
        """At the bottom right while any engineer has nothing to do: "Idle", an engineer's
        portrait and how many there are. A click on it (or I) goes to the next one."""
        self.panel(surface, IDLE_PANEL)
        self.text(surface, "Idle", (IDLE_PANEL.centerx - self.font_bold.size("Idle")[0] // 2, IDLE_PANEL.y + 6),
                  self.font_bold, GOLD if hovered else (235, 240, 248))
        self.draw_icon(surface, IDLE_BUTTON, Engineer)
        self.button_marks(surface, IDLE_BUTTON, "I", hovered, count)
        if hovered:
            self.draw_tooltip(surface, IDLE_PANEL, [("Idle engineers", f"{count}, with no orders"),
                                                    ("Click", "select the next one, and go to him")])

    def income_items(self, income, sign="+"):
        """What something makes (an INCOME: (made, every so many seconds) pairs), as
        (material, words) for draw_income: ("supply", "+100/30s"); with `sign` "-", what it uses."""
        return [(name, f"{sign}{amount}/{every:g}s") for made, every in income
                for name, amount in zip(MATERIALS, made) if amount]

    def income_width(self, items):
        """How wide draw_income draws these, in pixels."""
        return sum(20 + self.font_bold.size(text)[0] for _, text in items) + INCOME_GAP * (len(items) - 1)

    def draw_income(self, surface, x, y, items, color=(235, 240, 248)):
        """What something makes, in a row from (x, y): each material's mark, and how much how often."""
        for name, text in items:
            self.material_icon(surface, name, x, y + 1)
            self.text(surface, text, (x + 20, y - 1), self.font_bold, color)
            x += 20 + self.font_bold.size(text)[0] + INCOME_GAP

    def draw_hq_panel(self, surface, layout, hover_button):
        """Its name and health, a button for each kind of unit it trains (the details show on
        hover), and under them, what it makes."""
        base, panel = self.base, layout["panel"]
        self.panel(surface, panel)
        x, y = panel.x + 14, panel.y
        self.text(surface, "Headquarters", (x, y + 8), self.font_title)
        self.bar(surface, pygame.Rect(x, y + 44, panel.w - 28, 8), base.hp / base.MAX_HP)
        self.text(surface, f"Health {int(base.hp)} / {base.MAX_HP}", (x, y + 54), self.font_small, GREY)
        for kind, rect in layout["buttons"]:
            training = base.queue and base.queue[0] is kind
            self.draw_button(surface, rect, kind, TRAIN_KEYS[kind], bool(hover_button and hover_button[0] is kind),
                             base.queued(kind), base.training if training else None)
        self.draw_income(surface, x, y + 80 + BUTTON + 12, self.income_items(base.INCOME))

    @staticmethod
    def structure_title(t):
        if t.coming_down:
            return f"{t.NAME} (coming down)"
        if isinstance(t, Maker) and not t.on:
            return f"{t.NAME} (off)"
        if t.short and not t.built:
            return f"{t.NAME} (waiting for {t.short})"
        return t.NAME if t.built else f"{t.NAME} blueprint" if t.blueprint else f"{t.NAME} (being built)"

    def draw_structure_panel(self, surface, layout, hover_button=None):
        """Its name and health (a turret's rank beside its name; what a building makes, and what
        it uses up, and its on/off switch); while it's unfinished, a blue bar of how far it's built."""
        t, panel = self.structure_selected, layout["panel"]
        self.panel(surface, panel)
        for what, rect in layout["buttons"]:
            hovered = bool(hover_button and hover_button[0] == what)
            if what == "switch":
                self.draw_switch(surface, rect, t.on, hovered)
            else:                                      # a kind it trains
                training = t.queue and t.queue[0] is what
                self.draw_button(surface, rect, what, TRAIN_KEYS[what], hovered, t.queued(what),
                                 t.training if training else None)
        x, y = panel.x + 14, panel.y
        self.text(surface, self.structure_title(t), (x, y + 8), self.font_title)
        self.draw_rank(surface, x + self.font_title.size(self.structure_title(t))[0] + 12,   # beside its name
                       y + 24 - self.rank_height(level_of(t)) // 2, level_of(t), GOLD)
        self.bar(surface, pygame.Rect(x, y + 44, panel.w - 28, 8), t.hp / t.MAX_HP)
        self.text(surface, f"Health {int(t.hp)} / {t.MAX_HP}", (x, y + 54), self.font_small, GREY)
        row = y + 76
        busy = isinstance(t, Maker) and t.working and t.on and t.can_make(self.base.stores)
        if isinstance(t, Maker):                       # what it makes (dim while it isn't working, or waits)
            self.draw_income(surface, x, row, self.income_items(((t.MAKES, t.MAKE_TIME),)),
                             (235, 240, 248) if busy else (120, 130, 145))
            row += 24
        if isinstance(t, Maker) and any(t.INPUT):      # what it uses, in red
            self.draw_income(surface, x, row, self.income_items(((t.INPUT, t.MAKE_TIME),), "-"),
                             USED_RED if busy else (120, 130, 145))
            row += 24
        if isinstance(t, Extractor):                   # and what's left in its deposit
            self.draw_left(surface, x, row, t.deposit)
        if not t.built:
            self.bar(surface, pygame.Rect(x, panel.bottom - 18, panel.w - 28, 6), t.progress, color=(110, 175, 255))

    def draw_switch(self, surface, rect, on, hovered):
        """A building's on/off switch: its key, and "On" in green or "Off" in red."""
        pygame.draw.rect(surface, (52, 64, 82), rect, border_radius=6)
        if hovered:
            self.lighten(surface, rect)
        pygame.draw.rect(surface, GOLD if hovered else (255, 255, 255, 70), rect, width=2, border_radius=6)
        tag = pygame.Rect(rect.x + 4, rect.y + 4, 18, 18)
        pygame.draw.rect(surface, (14, 20, 32, 220), tag, border_radius=4)
        self.text(surface, "O", (tag.centerx - self.font_bold.size("O")[0] // 2, tag.y), self.font_bold, GOLD)
        word = "On" if on else "Off"
        self.text(surface, word, (rect.x + 28, rect.y + 3), self.font_bold, SWITCH_ON if on else SWITCH_OFF)

    def switch_building(self):
        """Switch the selected building off, or on again (a building that makes something)."""
        t = self.structure_selected
        if isinstance(t, Maker):
            t.on = not t.on

    def draw_left(self, surface, x, y, deposit):
        """What's left in a deposit, by its material's mark: "2900 left" (red once it's stripped)."""
        self.material_icon(surface, deposit.MATERIAL, x, y + 1)
        self.text(surface, f"{int(deposit.left)} left", (x + 20, y - 1), self.font_bold,
                  NONE_LEFT if deposit.emptied else (235, 240, 248))

    def draw_deposit_panel(self, surface, layout):
        """A deposit's name, a bar of what's left in it (in its material's colour), and how much."""
        d, panel = self.deposit_selected, layout["panel"]
        self.panel(surface, panel)
        x, y = panel.x + 14, panel.y
        self.text(surface, d.NAME, (x, y + 8), self.font_title)
        self.bar(surface, pygame.Rect(x, y + 44, panel.w - 28, 8), d.left / d.HOLDS, color=MATERIAL_COLORS[d.MATERIAL])
        self.draw_left(surface, x, y + 58, d)

    def selection_title(self):
        counts = [(kind, sum(type(u) is kind for u in self.selected)) for kind in (Soldier, Engineer, Tank)]
        return "  ·  ".join(plural(n, kind) for kind, n in counts if n)

    def draw_order_button(self, surface, rect, name, key, hovered):
        """A small order button: its key, and what it does (the fire state button: the state now)."""
        lit = hovered or self.order_aim == name
        pygame.draw.rect(surface, (52, 64, 82), rect, border_radius=6)
        if lit:
            self.lighten(surface, rect)
        pygame.draw.rect(surface, GOLD if lit else (255, 255, 255, 70), rect, width=2, border_radius=6)
        tag = pygame.Rect(rect.x + 4, rect.y + 8, 18, 18)
        pygame.draw.rect(surface, (14, 20, 32, 220), tag, border_radius=4)
        self.text(surface, key, (tag.x + 5, tag.y), self.font_bold, GOLD)
        if name == "fire":
            states = {u.fire_state for u in self.gunners}
            label = states.pop() if len(states) == 1 else "Mixed"
        else:
            label = name.capitalize()
        self.text(surface, label, (rect.x + 26, rect.y + 8), self.font_small)

    def order_buttons(self):
        """The order buttons the selected units get: the fire state only with soldiers among
        them, and Remove only with engineers."""
        return [b for b in ORDER_BUTTONS if (b[0] != "remove" or self.engineers) and (b[0] != "fire" or self.gunners)]

    def title_font(self, title):
        return self.font_title if len(title) < 22 else self.font_big

    def portrait_row(self):
        """How far apart the rows of portraits are: room for each one's health bar, and under
        it the chevrons of the highest level shown."""
        top = max((level_of(u) for u in self.selected[:24]), default=1)
        return 42 if top < 2 else 32 + 8 + self.rank_height(top) + 4

    def portraits(self, panel):
        """Where each selected unit's portrait is in the panel: (unit, rect), up to 24 (with
        more, the last place says how many more)."""
        shown = self.selected[:24] if len(self.selected) <= 24 else self.selected[:23]
        row = self.portrait_row()
        return [(unit, pygame.Rect(panel.x + 14 + (k % 8) * 37, panel.y + 52 + (k // 8) * row, 32, 32))
                for k, unit in enumerate(shown)]

    def fighter_under(self, layout, mouse):
        """The soldier whose portrait the mouse is on, or the selected turret while the mouse is
        on its panel: whose record to show. None if neither (an engineer has no record)."""
        if isinstance(self.structure_selected, Turret) and self.structure_selected.built \
                and layout["panel"].collidepoint(mouse):
            return self.structure_selected
        if self.selected:
            return next((unit for unit, icon in self.portraits(layout["panel"])
                         if icon.collidepoint(mouse) and isinstance(unit, Fighter)), None)
        return None

    def record(self, fighter):
        """What a soldier's portrait (or a turret's panel) tells you while the mouse is on it:
        its level and kills, its range now, a soldier's magazine, and how often its shots hit at
        its range and at its long range."""
        rows = [("Level", f"{fighter.level}"), ("Kills", f"{fighter.kills}")]
        if fighter.next_level_kills is not None:
            rows.append(("Next level", f"at {fighter.next_level_kills} kills"))
        rows.append(("Range", f"{fighter.range:g}, long shots to {fighter.long_range:g}"))
        if isinstance(fighter, Gunner):
            rows.append(("Magazine", f"changing ({math.ceil(fighter.changing)} s)" if fighter.changing
                         else f"{fighter.rounds} of {fighter.magazine} rounds"))
        if isinstance(fighter, Trooper):
            rows.append(("Upkeep", f"{fighter.upkeep.supply} supply every {UPKEEP_TIME:g} s"))
        if isinstance(fighter, Tank):
            rows.append(("Main gun", f"loading ({math.ceil(fighter.reload)} s of {fighter.reload_time:g})"
                         if fighter.reload > 0 else f"loaded ({fighter.reload_time:g} s to load)"))
        for reach in (fighter.range, fighter.long_range):
            rows.append((f"Hits at {reach:g} tiles", f"{fighter.hit_chance(reach):.0%}"))
        return rows

    def draw_units_panel(self, surface, layout, hover_button):
        """What's selected (a portrait each, up to 24), then their orders, then what they can build."""
        panel = layout["panel"]
        self.panel(surface, panel)
        x, y = panel.x + 14, panel.y
        title = self.selection_title()
        self.text(surface, title, (x, y + 8), self.title_font(title))
        pygame.draw.line(surface, (255, 255, 255, 40), (x, y + 44), (panel.right - 14, y + 44))
        for unit, icon in self.portraits(panel):
            self.draw_icon(surface, icon, type(unit))
            self.bar(surface, pygame.Rect(icon.x, icon.bottom + 2, icon.w, 4), unit.hp / unit.MAX_HP)
            group = self.group_of(unit)
            if group is not None:                      # its group's number, in the corner
                self.text(surface, str(group), (icon.right - 9, icon.y - 2), self.font_small, GOLD)
            self.draw_rank(surface, icon.centerx, icon.bottom + 8, level_of(unit), GOLD)   # under its bar
        if len(self.selected) > 24:                    # in the last portrait's place
            self.text(surface, f"+{len(self.selected) - 23}", (x + 7 * 37 + 2, y + 52 + 2 * self.portrait_row() + 6),
                      self.font_bold, GOLD)
        keys = {name: key for name, key, _ in ORDER_BUTTONS}
        for what, rect in layout["buttons"]:
            hovered = bool(hover_button and hover_button[0] == what)
            if what in keys:
                self.draw_order_button(surface, rect, what, keys[what], hovered)
            else:                                      # what they can build (its numbers show on hover)
                self.draw_button(surface, rect, what, BUILD_KEYS[what], hovered)


def main():
    shot = None
    if "--screenshot" in sys.argv:
        shot = sys.argv[sys.argv.index("--screenshot") + 1]
    # full screen, unless it's taking pictures or asked for a window
    Game(screenshot=shot, window=WINDOW if shot or "--window" in sys.argv else None).run()


def main_logging_crashes():
    """The packaged game has no console to show what went wrong: write it to CRASH_LOG (where a player
    can find it and send it in), then let it fail as it would have."""
    try:
        main()
    except Exception:
        import time
        import traceback
        try:
            os.makedirs(os.path.dirname(CRASH_LOG), exist_ok=True)
            with open(CRASH_LOG, "a", encoding="utf-8") as f:
                f.write(time.strftime(f"---- %Y-%m-%d %H:%M:%S, Skyline {VERSION}\n") + traceback.format_exc() + "\n")
        except OSError:
            pass
        raise


if __name__ == "__main__":
    main_logging_crashes() if FROZEN else main()
