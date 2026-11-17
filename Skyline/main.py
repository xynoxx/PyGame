"""Skyline: a 3D real-time strategy game made with pygame and ModernGL.

A square patch of a dead, overrun world. Before the game starts you choose
where your HQ goes; then the HQ trains soldiers and engineers, engineers build
turrets, and every 30 seconds a wave of zombies (ten more in each wave than
the last) comes in from beyond the edge of the map to tear the HQ down. If it
falls, it's over. See README.md for how it's put together.

Run it with:  python main.py
Needs:        pip install pygame moderngl

Controls
  Before the game: point at the ground and left click to build your HQ there.
  Left click       select the HQ, a turret, a soldier or an engineer (Shift: add to the selection)
  Left drag        draw a box round your units to select them all
  Right click      selected units: move there, or go after the zombie clicked
                   (engineers: finish the unbuilt turret clicked). The HQ: where new units gather.
  Right drag       selected units: hold the button and drag along the ground to line
                   them up along it (in rows if it's short), facing away from where they are
  The HQ's panel   left click Soldier (T) or Engineer (G) to train one; right click to cancel one
  Engineers' panel Turret (B), then left click a tile to lay one there, or hold the button
                   and drag to lay a row of them (right click or Esc: don't). They're blueprints
                   till an engineer starts on them; laying one again on a blueprint calls it off
  WASD / arrows    move the camera (or push the mouse against a screen edge)
  Mouse wheel      zoom in and out
  Q / E            turn the camera (or drag with the middle mouse button)
  Space            bring the camera back to your HQ
  R                play again, once the HQ has fallen
  V                show or hide every unit's and turret's range (for testing)
  Esc              stop placing a turret; let go of what's selected; with nothing selected: quit
"""
import math
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

try:
    import moderngl  # noqa: E402
except ImportError:
    sys.exit("Skyline needs ModernGL to draw in 3D. Install it with:  pip install moderngl")

import mathx  # noqa: E402
import models  # noqa: E402
from camera import RTSCamera  # noqa: E402
from gfx import Renderer, open_window  # noqa: E402
from units import (Engineer, Gunner, Headquarters, Soldier, Turret, keep_apart, line_formation,  # noqa: E402
                   order_line, order_move)
from world import HQ, HQ_DEPTH, HQ_WIDTH, World  # noqa: E402
from zombies import Waves, Zombie  # noqa: E402

WIDTH, HEIGHT = 1280, 720
EDGE_SCROLL = 6            # pixels from the window edge that scroll the camera
TURN_SPEED = 1.8           # camera turn with Q / E, radians per second
DRAG_MIN = 6               # pixels the mouse must move with the button down to draw a box
LINE_MIN = 1.0             # tiles a right drag must cover to line units up (shorter: a plain move)
MARKER_TIME = 0.6          # how long the "move here" ring lasts
MESSAGE_TIME = 3.5         # seconds a message stays up
TRACER_TIME = 0.07         # seconds a shot's tracer shows
SPRAY = 0.035              # radians between a shotgun's pellets
BLUEPRINT_TINT = (0.45, 0.72, 1.0, 0.38)  # a turret laid out that no engineer has started on yet

PLAYER_BLUE = (0.24, 0.48, 0.95)
SELECT_GREEN = (0.45, 1.0, 0.55)
ENEMY_RED = (1.0, 0.35, 0.30)
FITS = (0.45, 1.0, 0.55)       # a ghost (the HQ's or a turret's) where it can go
DOESNT_FIT = (1.0, 0.36, 0.30)  # and where it can't
HIT_TINT = (1.7, 0.55, 0.5, 1.0)       # a unit, the moment it's hit
HQ_HIT_TINT = (1.12, 0.94, 0.90, 1.0)  # the HQ, when a blow lands: just a touch (it's hit often)
UNBUILT_TINT = (0.75, 0.82, 0.95, 0.75)  # a turret still being built

# the panel at the bottom left, with what's selected
PANEL_X, PANEL_W = 12, 330
BUTTON = 72                    # a train or build button's size
GOLD = (255, 214, 120)
GREY = (175, 186, 202)
TRAIN_KEYS = {Soldier: "T", Engineer: "G"}


def health_color(t):
    """Green when full, through yellow, to red when nearly gone."""
    if t > 0.5:
        return (int(255 * (1 - t) * 2), 220, 90)
    return (235, int(220 * t * 2), 70)


def plural(n, kind):
    return f"{n} {kind.NAME}" + ("" if n == 1 else "s")


class Game:
    def __init__(self, screenshot=None):
        pygame.init()
        self.size = (WIDTH, HEIGHT)
        open_window(self.size, "Skyline")
        self.gfx = Renderer(moderngl.create_context(), self.size)
        self.screenshot = screenshot

        mesh = self.gfx.mesh
        # the HQ is built at the map's corner and moved to where it's drawn
        self.hq_mesh = mesh(models.build_hq(HQ("player", 0, 0, HQ_WIDTH, HQ_DEPTH), PLAYER_BLUE))
        # how each kind of unit looks: its body, legs and arms, its gun, and where the gun's muzzle is
        self.looks = {
            Soldier: (tuple(mesh(m) for m in models.build_soldier(PLAYER_BLUE)), mesh(models.build_rifle()),
                      models.RIFLE_MUZZLE),
            Engineer: (tuple(mesh(m) for m in models.build_engineer(PLAYER_BLUE)), mesh(models.build_shotgun()),
                       models.SHOTGUN_MUZZLE),
        }
        self.hammer_mesh = mesh(models.build_hammer())
        self.turret_base_mesh = mesh(models.build_turret_base(PLAYER_BLUE))
        self.turret_head_mesh = mesh(models.build_turret_head(PLAYER_BLUE))
        self.zombie_meshes = [tuple(mesh(m) for m in models.build_zombie(v)) for v in range(3)]
        self.beam_mesh = mesh(models.build_beam())
        self.flag_mesh = mesh(models.build_flag(PLAYER_BLUE))
        self.ring_mesh = mesh(models.build_ring())
        self.thin_ring_mesh = mesh(models.build_thin_ring())
        self.disc_mesh = mesh(models.build_disc())
        self.show_ranges = True    # for testing: a ring round each unit and turret as far as it can shoot

        self.turning = False       # dragging with the middle mouse button
        self.running = True
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui", 15)
        self.font_small = pygame.font.SysFont("segoeui", 13)
        self.font_bold = pygame.font.SysFont("segoeui", 15, bold=True)
        self.font_title = pygame.font.SysFont("segoeui", 24, bold=True)
        self.font_big = pygame.font.SysFont("segoeui", 18, bold=True)
        self.font_huge = pygame.font.SysFont("segoeui", 40, bold=True)
        self.fps_shown = 0
        self.fps_timer = 0.0
        self.new_game()

    def new_game(self):
        self.world = World()
        self.camera = RTSCamera(self.world.size, WIDTH / HEIGHT)
        # start looking at the whole map, to choose where the HQ goes
        self.camera.look_at(self.world.size / 2, self.world.size / 2, instant=True)
        self.camera.dist = self.camera.dist_goal = 66.0
        self.gfx.set_ground(self.world.size)

        self.base = None           # the player's HQ as it plays, once it's built
        self.waves = None          # the zombie waves, once the HQ is built
        self.home = None           # where Space brings the camera back to
        self.aim = None            # the tile the HQ would go on, while choosing
        self.aim_fits = False
        self.units = []            # the player's soldiers and engineers
        self.turrets = []
        self.zombies = []
        self.selected = []         # the units selected
        self.hq_selected = False
        self.turret_selected = None
        self.placing_turret = False  # choosing a tile for a turret
        self.turret_aim = None     # the tile, while choosing
        self.turret_row = None     # while the left button's held: the tiles dragged over, to lay turrets on
        self.turret_cancel = []    # and the blueprints dragged over, to call off
        self.row_from = None       # where on the ground the drag was last frame
        self.turret_fits = False
        self.hover = None          # what the mouse is over: a unit, a zombie, a turret, "hq" or None
        self.drag_from = None      # where a left-button drag started (pixels)
        self.line_from = None      # where a right-button drag started, on the ground, to line units up
        self.markers = []          # [x, z, age, colour] of recent orders
        self.shots = []            # [muzzle, hit, age] of shots just fired
        self.message = None        # (text, seconds left)
        self.over = False          # the HQ has fallen
        self.played = 0.0          # seconds since the HQ was built
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

        play(1 / 60)
        self.aim_at(45, 50)
        self.build_hq()
        play(1.5)
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
        while self.played < 120 and not (self.shots and any(not z.alive for z in self.zombies)):
            play(1 / 60)
        self.camera.dist = self.camera.dist_goal = 30.0
        self.select_units([u for u in self.units if u.alive])
        save("")
        print(f"wave {self.waves.number}: {self.kills} zombies down, {sum(u.alive for u in self.units)} units up,"
              f" turrets {len(self.turrets)}, HQ {self.base.hp}/{self.base.MAX_HP}")
        pygame.quit()

    # ------------------------------------------------------------ choosing where the HQ goes

    @property
    def placing(self):
        return self.base is None

    def aim_at(self, x, z):
        """Show the HQ where it would go if it were built near (x, z) on the ground."""
        if x is None:
            self.aim = None
            return
        self.aim = World.hq_tiles_at(x, z)
        self.aim_fits = self.world.can_build_hq(*self.aim)

    def build_hq(self):
        if not self.aim:
            return
        if not self.aim_fits:
            self.say("It doesn't fit there: keep the HQ and its concrete on the map.")
            return
        hq = self.world.build_hq("player", *self.aim)
        self.base = Headquarters(self.world, hq, PLAYER_BLUE, "Blue team", "You")
        self.waves = Waves(self.world)
        self.aim = None
        self.home = (hq.i + hq.w / 2, hq.j + hq.d / 2 + 2)
        self.camera.look_at(*self.home)
        self.camera.dist_goal = 17.0
        self.say("HQ built. Click it to train soldiers and engineers: the dead come in 30 seconds.")

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

    def start_placing_turret(self):
        if self.engineers and not self.over:
            self.placing_turret = True
            self.turret_aim = None

    def turret_at(self, i, j):
        return next((t for t in self.turrets if t.alive and (t.i, t.j) == (i, j)), None)

    def tile_fits(self, i, j):
        """Can a turret be laid on this tile: on the map, nothing built there, no turret (or
        blueprint) on it already? (Someone standing on it is fine: they'll step off when the
        foundation goes down.)"""
        return self.world.can_build_turret(i, j) and not self.turret_at(i, j)

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

    def finish_turret_row(self, point):
        """The left button is let go: call off the blueprints crossed, and lay the new ones."""
        self.extend_turret_row(point)
        row, cancel = self.turret_row, self.turret_cancel
        self.turret_row, self.turret_cancel, self.row_from = None, [], None
        if not row and not cancel:
            self.say("A turret needs a clear tile on the map.")
            return
        for blueprint in cancel:
            blueprint.cancel()
            if blueprint is self.turret_selected:
                self.turret_selected = None
        for engineer in self.all_engineers:            # off their lists too
            engineer.jobs = [t for t in engineer.jobs if t.alive]
        if row:
            self.lay_turrets(row)
        parts = []
        if len(row) > 1 or (row and cancel):
            parts.append(f"{len(row)} turret blueprint{'s' if len(row) != 1 else ''} laid")
        if cancel:
            parts.append(f"{len(cancel)} called off")
        if parts:
            self.say("  ·  ".join(parts) + ("  ·  the engineers build them one at a time" if len(row) > 1 else ""))
        self.placing_turret = False
        self.turret_aim = None

    def place_turret(self):
        """Lay one turret on the tile aimed at, or call off the blueprint there (as a click does)."""
        if self.turret_aim:
            self.start_turret_row((self.turret_aim[0] + 0.5, self.turret_aim[1] + 0.5))
            self.finish_turret_row(None)

    def lay_turrets(self, tiles):
        """Lay turret blueprints on these tiles, and give them to the selected engineers to build,
        one after another. (A blueprint takes up its tile only once an engineer starts on it.)"""
        laid = []
        for i, j in tiles:
            turret = Turret(self.world, i, j, PLAYER_BLUE)
            self.turrets.append(turret)
            self.markers.append([turret.x, turret.z, 0.0, SELECT_GREEN])
            laid.append(turret)
        crew = self.all_engineers
        for engineer in self.engineers:
            engineer.build(laid, crew)

    def clear_tile(self, i, j):
        """A foundation's going down on this tile: anyone standing on it steps off."""
        for u in self.units + self.zombies:
            if not u.alive:
                continue
            r = u.RADIUS
            cx, cz = min(max(u.x, i), i + 1), min(max(u.z, j), j + 1)
            if (u.x - cx) ** 2 + (u.z - cz) ** 2 >= r * r and not (i < u.x < i + 1 and j < u.z < j + 1):
                continue
            ways = [(i - r - 0.02, u.z), (i + 1 + r + 0.02, u.z), (u.x, j - r - 0.02), (u.x, j + 1 + r + 0.02)]
            ways = [w for w in ways if not self.world.hits_wall(*w, r)] or ways
            u.x, u.z = min(ways, key=lambda w: (w[0] - u.x) ** 2 + (w[1] - u.z) ** 2)

    @property
    def all_engineers(self):
        return [u for u in self.units if isinstance(u, Engineer) and u.alive]

    # ------------------------------------------------------------ selecting and commanding

    def select_hq(self):
        self.clear_selection()
        self.hq_selected = True

    def select_turret(self, turret):
        self.clear_selection()
        self.turret_selected = turret

    def select_units(self, units, add=False):
        if add:
            units = self.selected + [u for u in units if u not in self.selected]
        self.clear_selection()
        self.selected = list(units)

    def clear_selection(self):
        self.selected = []
        self.hq_selected = False
        self.turret_selected = None
        self.placing_turret = False

    def train(self, kind):
        if self.base and not self.over:
            self.base.train(kind)

    def command_move(self, x, z):
        self.markers.append([x, z, 0.0, SELECT_GREEN])
        order_move(self.selected, x, z)

    def command_line(self, a, b):
        self.markers.append([*b, 0.0, SELECT_GREEN])
        order_line(self.selected, a, b)

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

    def command_attack(self, zombie):
        self.markers.append([zombie.x, zombie.z, 0.0, ENEMY_RED])
        for unit in self.selected:
            unit.attack(zombie)

    def thing_under(self, pos):
        """The unit, zombie, turret or HQ under the mouse (the nearest, if they overlap), or None."""
        origin, direction = self.camera.ray(pos[0], pos[1], *self.size)
        best, best_t = None, float("inf")
        for thing in self.units + self.zombies + [t for t in self.turrets if t.alive]:
            t = thing.ray_hit(origin, direction)
            if t is not None and t < best_t:
                best, best_t = thing, t
        if self.base:
            t = self.base.ray_hit(origin, direction)
            if t is not None and t < best_t:
                best = "hq"
        return best

    def click_select(self, pos, add):
        thing = self.thing_under(pos)
        if thing == "hq":
            self.select_hq()
        elif isinstance(thing, Turret):
            self.select_turret(thing)
        elif isinstance(thing, Gunner):
            if add and thing in self.selected:
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
        if button == 2:
            self.turning = True
        elif self.over:
            return
        elif button == 1:
            if self.placing:
                # aim where the click is, not where the mouse was when the last frame was drawn
                self.aim_at(*(self.camera.ground_point(pos[0], pos[1], *self.size) or (None, None)))
                self.build_hq()
            elif hit:
                what = hit[0]
                if what is Turret:
                    self.start_placing_turret()
                else:
                    self.train(what)
            elif on_panel:
                pass
            elif self.placing_turret:      # a turret, or the start of a row of them (decided when it's let go)
                point = self.camera.ground_point(pos[0], pos[1], *self.size)
                self.aim_turret(*(point or (None, None)))
                self.start_turret_row(point)
            else:
                self.drag_from = pos
        elif button == 3 and not self.placing:
            if self.placing_turret:
                self.placing_turret = False
            elif hit:
                if hit[0] is not Turret:
                    self.base.cancel(hit[0])
            elif on_panel:
                pass
            elif self.selected:
                thing = self.thing_under(pos)
                if isinstance(thing, Zombie):
                    self.command_attack(thing)
                elif isinstance(thing, Turret) and not thing.built and self.engineers:
                    for engineer in self.engineers:
                        engineer.build(thing, self.all_engineers)
                    self.markers.append([thing.x, thing.z, 0.0, SELECT_GREEN])
                else:   # a move: a click, or a drag to line them up (decided when it's let go)
                    self.line_from = self.camera.ground_point(pos[0], pos[1], *self.size)
            elif self.hq_selected:
                point = self.camera.ground_point(pos[0], pos[1], *self.size)
                if point:
                    self.base.rally = point
                    self.markers.append([*point, 0.0, SELECT_GREEN])

    def on_release(self, button, pos):
        if button == 2:
            self.turning = False
        elif button == 1 and self.turret_row is not None:
            if self.placing_turret and not self.over:
                self.finish_turret_row(self.camera.ground_point(pos[0], pos[1], *self.size))
            self.turret_row = self.row_from = None
        elif button == 3 and self.line_from:
            start, self.line_from = self.line_from, None
            if not self.selected or self.over:
                return
            end = self.camera.ground_point(pos[0], pos[1], *self.size) or start
            if math.dist(start, end) < LINE_MIN:
                self.command_move(*start)
            else:
                self.command_line(start, end)
        elif button == 1 and self.drag_from:
            add = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
            start, self.drag_from = self.drag_from, None
            if abs(pos[0] - start[0]) < DRAG_MIN and abs(pos[1] - start[1]) < DRAG_MIN:
                self.click_select(pos, add)
            else:
                self.box_select(start, pos, add)

    def on_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.placing_turret:
                self.placing_turret = False
            elif self.selected or self.hq_selected or self.turret_selected:
                self.clear_selection()
            else:
                self.running = False
        elif key == pygame.K_r and self.over:
            self.new_game()
        elif key == pygame.K_SPACE and self.home:
            self.camera.look_at(*self.home)
        elif key == pygame.K_t and self.hq_selected:
            self.train(Soldier)
        elif key == pygame.K_g and self.hq_selected:
            self.train(Engineer)
        elif key == pygame.K_b and self.engineers:
            self.start_placing_turret()
        elif key == pygame.K_v:
            self.show_ranges = not self.show_ranges

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
            if self.placing:
                self.aim_at(*point)
            elif self.placing_turret:
                self.aim_turret(*point)
                if self.turret_row is not None and point[0] is not None:
                    self.extend_turret_row(point)
        if self.base and not self.over:
            self.fight(dt)

        layout = self.panel_layout()
        over_panel = layout and layout["panel"].collidepoint(mouse)
        self.hover = None if (self.screenshot or self.placing or over_panel) else self.thing_under(mouse)
        for marker in self.markers:
            marker[2] += dt
        self.markers = [m for m in self.markers if m[2] < MARKER_TIME]
        for shot in self.shots:
            shot[2] += dt
        self.shots = [s for s in self.shots if s[2] < TRACER_TIME]
        if self.message:
            text, left = self.message
            self.message = (text, left - dt) if left > dt else None

        self.fps_timer += dt
        if self.fps_timer >= 0.5:
            self.fps_timer = 0.0
            self.fps_shown = round(self.clock.get_fps())

    def fight(self, dt):
        """A moment of the game: training, the waves, the dead attacking, building and shooting."""
        self.played += dt
        new = self.base.update(dt)
        if new:
            self.units.append(new)
        wave = self.waves.update(dt)
        if wave:
            side, zombies = wave
            self.zombies += zombies
            self.say(f"Wave {self.waves.number}: {len(zombies)} zombies"
                     f" coming from the {side}!")

        living = [u for u in self.units if u.alive]
        standing = [t for t in self.turrets if t.alive and t.started]   # not blueprints: the dead pass those by
        for zombie in self.zombies:
            zombie.think(dt, self.base, living + standing)
        for unit in living:
            target = unit.fight(dt, self.zombies)
            if target:
                _, _, muzzle = self.looks[type(unit)]
                self.fire(mathx.apply(self.gun_matrix(unit), muzzle), target, unit)
            if isinstance(unit, Engineer):
                started = unit.job and unit.job.started
                unit.work(dt, self.all_engineers)
                if unit.job and unit.job.started and not started:
                    self.clear_tile(unit.job.i, unit.job.j)      # the foundation's down: off the tile, all
        for turret in self.turrets:
            target = turret.fight(dt, self.zombies)
            if target:
                self.fire(turret.muzzle(), target, turret)
            if not turret.alive and self.world.is_blocked(turret.i, turret.j):
                self.world.set_blocked(turret.i, turret.j, False)     # wrecked: its tile is free again
        for unit in self.units + self.zombies:
            unit.update(dt)
        keep_apart(self.units + self.zombies, self.world)

        self.units = [u for u in self.units if not u.gone]
        self.zombies = [z for z in self.zombies if not z.gone]
        self.turrets = [t for t in self.turrets if not t.gone]
        self.selected = [u for u in self.selected if u.alive]
        if self.turret_selected and not self.turret_selected.alive:
            self.turret_selected = None
        if self.placing_turret and not self.engineers:
            self.placing_turret = False
        if not self.base.alive:
            self.over = True
            self.clear_selection()

    def fire(self, muzzle, target, shooter):
        """A shot lands: the tracer (a spray of them for a shotgun), and the damage."""
        hit = (target.x, 0.75 * target.SIZE, target.z)
        if shooter.PELLETS > 1:
            dx, dz = hit[0] - muzzle[0], hit[2] - muzzle[2]
            reach, heading = math.hypot(dx, dz), math.atan2(dx, dz)
            for k in range(shooter.PELLETS):
                a = heading + (k - (shooter.PELLETS - 1) / 2) * SPRAY
                self.shots.append([muzzle, (muzzle[0] + math.sin(a) * reach, hit[1],
                                            muzzle[2] + math.cos(a) * reach), 0.0])
        else:
            self.shots.append([muzzle, hit, 0.0])
        if target.hurt(shooter.DAMAGE):
            self.kills += 1

    # ------------------------------------------------------------ drawing

    def draw(self):
        gfx = self.gfx
        if self.base:
            hq = self.base.hq
            gfx.set_hq_ground(self.world.aprons["player"], self.slab_of(hq.i, hq.j))
            around = (hq.i - 0.35, hq.j - 0.35, hq.i + hq.w + 0.35, hq.j + hq.d + 0.35)   # just outside its walls
            if self.placing_turret and self.turret_aim:
                i, j = self.turret_aim
                gfx.set_mark((i, j, i + 1, j + 1), FITS if self.turret_fits else DOESNT_FIT)
            elif self.turret_selected:
                t = self.turret_selected
                gfx.set_mark((t.i - 0.15, t.j - 0.15, t.i + 1.15, t.j + 1.15), SELECT_GREEN, 0.9)
            elif self.hq_selected:
                gfx.set_mark(around, SELECT_GREEN, 0.9)
            elif self.hover == "hq":
                gfx.set_mark(around, (1.0, 1.0, 1.0), 0.5)
            else:
                gfx.set_mark(None)
        elif self.aim:
            # the concrete it would bring, outlined in green where it fits and red where it doesn't
            gfx.set_hq_ground(World.apron_of(*self.aim), self.slab_of(*self.aim))
            gfx.set_mark(World.apron_of(*self.aim), FITS if self.aim_fits else DOESNT_FIT)
        else:
            gfx.set_hq_ground(None, None)
            gfx.set_mark(None)
        gfx.begin(self.camera.view_proj(), self.camera.eye(), self.camera.fog_range())
        gfx.draw_ground()
        if self.base:
            tint = HQ_HIT_TINT if self.base.flash > 0 else (1.0, 1.0, 1.0, 1.0)
            if not self.base.alive:
                tint = (0.35, 0.32, 0.30, 1.0)             # burnt out
            gfx.draw(self.hq_mesh, mathx.translate(self.base.hq.i, 0, self.base.hq.j), tint)
        elif self.aim:
            tint = (*(FITS if self.aim_fits else DOESNT_FIT), 0.55)
            gfx.draw_ghost(self.hq_mesh, mathx.translate(self.aim[0], 0, self.aim[1]), tint)
        for turret in self.turrets:
            self.draw_turret(turret)
        for unit in self.units:
            self.draw_gunner(unit)
        for zombie in self.zombies:
            self.draw_zombie(zombie)
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
                tint = (*(FITS if fits else DOESNT_FIT), 0.55)
                gfx.draw_ghost(self.turret_base_mesh, mathx.translate(i + 0.5, 0, j + 0.5), tint)
                gfx.draw_ghost(self.turret_head_mesh, mathx.translate(i + 0.5, 0, j + 0.5), tint)
        self.draw_ground_marks()
        for muzzle, hit, age in self.shots:
            self.draw_tracer(muzzle, hit)
        self.draw_hud()
        gfx.draw_overlay()

    def body_matrix(self, unit, lean=0.0):
        """Where a unit's body is drawn: standing, or fallen over backwards and sinking away."""
        m = mathx.chain(mathx.translate(unit.x, 0, unit.z), mathx.rot_y(unit.yaw))
        if not unit.alive:
            fall = min(1.0, unit.dead_for / 0.45)
            sink = max(0.0, unit.dead_for - 2.5) * 0.25
            m = mathx.chain(m, mathx.translate(0, -sink, 0), mathx.rot_x(-fall * 1.45))
        elif lean:
            m = mathx.mul(m, mathx.rot_x(lean))
        return mathx.chain(m, mathx.scale(unit.SIZE), mathx.translate(0, unit.bob, 0))

    def gun_matrix(self, unit, body=None):
        """The gun in the unit's hands: held low, or up at the shoulder to fire. (An engineer
        at work slings it on his back.)"""
        body = body or self.body_matrix(unit)
        if getattr(unit, "working", False):
            return mathx.chain(body, mathx.translate(-0.10, 0.62, -0.24), mathx.rot_x(-1.25))
        a = unit.aim_blend
        return mathx.chain(body, mathx.translate(0.04, 0.58 + 0.18 * a, 0.30 - 0.06 * a), mathx.rot_x(0.55 * (1 - a)))

    def draw_gunner(self, unit):
        (body_mesh, leg_mesh, arm_mesh), gun_mesh, _ = self.looks[type(unit)]
        body = self.body_matrix(unit)
        tint = HIT_TINT if unit.flash > 0 else (1.0, 1.0, 1.0, 1.0)
        self.gfx.draw(body_mesh, body, tint)
        working = getattr(unit, "working", False)
        raise_arms = 1.0 + 0.5 * unit.aim_blend
        for side in (-1, 1):
            leg = mathx.chain(body, mathx.translate(side * 0.1, 0.42, 0), mathx.rot_x(side * unit.swing))
            if working and side == 1:              # hammering: the right arm comes up and down
                swing = -1.3 - 0.55 * (1 + math.sin(unit.hammer * 11))
                arm = mathx.chain(body, mathx.translate(0.29, 0.80, 0), mathx.rot_x(swing))
                self.gfx.draw(self.hammer_mesh, mathx.chain(arm, mathx.translate(0, -0.46, 0),
                                                            mathx.rot_x(math.pi / 2)), tint)
            elif working:
                arm = mathx.chain(body, mathx.translate(-0.29, 0.80, 0), mathx.rot_y(0.3), mathx.rot_x(-0.9))
            else:
                arm = mathx.chain(body, mathx.translate(side * 0.29, 0.80, 0), mathx.rot_y(-side * 0.45),
                                  mathx.rot_x(-raise_arms))
            self.gfx.draw(leg_mesh, leg, tint)
            self.gfx.draw(arm_mesh, arm, tint)
        self.gfx.draw(gun_mesh, self.gun_matrix(unit, body), tint)

    def draw_turret(self, turret):
        if not turret.started:                         # a blueprint: see-through, flat blue
            if turret.alive:
                m = mathx.translate(turret.x, 0, turret.z)
                self.gfx.draw_ghost(self.turret_base_mesh, m, BLUEPRINT_TINT)
                self.gfx.draw_ghost(self.turret_head_mesh, m, BLUEPRINT_TINT)
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
        self.gfx.draw(self.turret_base_mesh, base, tint)
        if turret.built or turret.progress > 0.6 or not turret.alive:
            head = mathx.chain(base, mathx.rot_y(turret.yaw), mathx.translate(0, 0, -turret.recoil * 0.5))
            self.gfx.draw(self.turret_head_mesh, head, tint)

    def draw_zombie(self, zombie):
        body_mesh, leg_mesh, arm_mesh = self.zombie_meshes[zombie.variant]
        body = self.body_matrix(zombie, lean=0.22 + zombie.lean * 0.3)
        tint = HIT_TINT if zombie.flash > 0 else (1.0, 1.0, 1.0, 1.0)
        self.gfx.draw(body_mesh, body, tint)
        swing = zombie.swing if zombie.alive else 0.0
        claw = math.sin(zombie.lunge / 0.35 * math.pi) * 0.7 if zombie.lunge > 0 else 0.0
        for side in (-1, 1):
            leg = mathx.chain(body, mathx.translate(side * 0.1, 0.42, 0), mathx.rot_x(side * swing))
            reach = -1.3 + side * 0.12 + side * swing * 0.25 - claw
            arm = mathx.chain(body, mathx.translate(side * 0.28, 0.80, 0), mathx.rot_x(reach))
            self.gfx.draw(leg_mesh, leg, tint)
            self.gfx.draw(arm_mesh, arm, tint)

    def draw_tracer(self, a, b):
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length < 1e-3:
            return
        yaw = math.atan2(dx, dz)
        pitch = math.atan2(dy, math.hypot(dx, dz))
        m = mathx.chain(mathx.translate(*a), mathx.rot_y(yaw), mathx.rot_x(-pitch), mathx.scale(1, 1, length))
        self.gfx.draw(self.beam_mesh, m, (1.6, 1.4, 0.7, 0.9))
        flash = mathx.chain(mathx.translate(*a), mathx.rot_y(yaw), mathx.scale(4, 4, 0.12))
        self.gfx.draw(self.beam_mesh, flash, (2.0, 1.6, 0.6, 0.8))

    def ring_at(self, x, z, radius, color, alpha, mesh=None, height=0.03):
        model = mathx.chain(mathx.translate(x, height, z), mathx.scale(radius, 1, radius))
        self.gfx.draw(mesh or self.ring_mesh, model, tint=(*color, alpha))

    def draw_ground_marks(self):
        if self.show_ranges:
            for thing in self.units + self.turrets:
                if thing.alive and (not isinstance(thing, Turret) or thing.built):
                    picked = thing in self.selected or thing is self.turret_selected
                    self.ring_at(thing.x, thing.z, thing.RANGE, SELECT_GREEN if picked else (1.0, 1.0, 1.0),
                                 0.55 if picked else 0.18, mesh=self.thin_ring_mesh, height=0.02)
        elif self.turret_selected and self.turret_selected.built:
            t = self.turret_selected
            self.ring_at(t.x, t.z, t.RANGE, SELECT_GREEN, 0.5, mesh=self.thin_ring_mesh, height=0.02)
        if self.placing_turret and self.turret_aim:   # how far it would reach from there
            i, j = self.turret_aim
            self.ring_at(i + 0.5, j + 0.5, Turret.RANGE, FITS if self.turret_fits else DOESNT_FIT, 0.45,
                         mesh=self.thin_ring_mesh, height=0.02)
        for unit in self.units + self.zombies:
            if not unit.alive:
                continue
            r = unit.RADIUS * 1.5
            self.ring_at(unit.x, unit.z, r * 0.9, (0.0, 0.0, 0.0), 0.28, mesh=self.disc_mesh, height=0.015)
            if unit in self.selected:
                self.ring_at(unit.x, unit.z, r, SELECT_GREEN, 0.95)
            elif unit is self.hover:
                self.ring_at(unit.x, unit.z, r, ENEMY_RED if isinstance(unit, Zombie) else (1.0, 1.0, 1.0), 0.6)
        for unit in self.selected:
            if unit.target and unit.target.alive:
                self.ring_at(unit.target.x, unit.target.z, 0.5, ENEMY_RED, 0.8)
        if self.hq_selected:
            x, z = self.base.rally
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

    # ------------------------------------------------------------ the 2D overlay

    def draw_hud(self):
        """The overlay: health bars, the wave clock, the selection panel. Drawn fresh every frame."""
        mouse = pygame.mouse.get_pos()
        layout = self.panel_layout()
        hover_button = self.button_at(mouse)
        surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self.draw_health_bars(surface)

        if self.placing:
            if self.message:
                self.banner(surface, "Choose where your HQ goes", self.message[0], (255, 150, 135))
            elif self.aim and not self.aim_fits:
                self.banner(surface, "Choose where your HQ goes",
                            "Too near the edge: the HQ and its concrete must be on the map.", (255, 150, 135))
            else:
                self.banner(surface, "Choose where your HQ goes", "Point at the ground, and left click to build it.")
        else:
            self.draw_wave_clock(surface)
            if self.placing_turret:
                if self.turret_row is not None:
                    n, c = len(self.turret_row), len(self.turret_cancel)
                    line = f"{n} new turret{'s' if n != 1 else ''}" + (f"  ·  {c} blueprint{'s' if c != 1 else ''}"
                                                                      f" called off" if c else "")
                    line += "  ·  let go to lay them"
                else:
                    line = ("Click a clear tile for a turret, or hold and drag for a row (on a blueprint: call it off)"
                            "  ·  right click or Esc: don't")
                self.banner(surface, None, line, (170, 240, 180), y=62)
            elif self.message and not self.over:
                self.banner(surface, None, self.message[0], (255, 205, 150), y=62)

        if layout:
            if self.hq_selected:
                self.draw_hq_panel(surface, layout, hover_button)
            elif self.turret_selected:
                self.draw_turret_panel(surface, layout)
            else:
                self.draw_units_panel(surface, layout, hover_button)

        if self.drag_from:
            (x0, y0), (x1, y1) = self.drag_from, mouse
            box = pygame.Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            if box.w >= DRAG_MIN or box.h >= DRAG_MIN:
                pygame.draw.rect(surface, (115, 255, 140, 40), box)
                pygame.draw.rect(surface, (115, 255, 140, 220), box, width=1)

        if self.over:
            self.draw_game_over(surface)

        if self.show_ranges and not self.placing:
            note = "Ranges shown  ·  V to hide"
            width = self.font_small.size(note)[0] + 24
            rect = pygame.Rect(WIDTH - width - 12, HEIGHT - 40, width, 28)
            self.panel(surface, rect)
            self.text(surface, note, (rect.x + 12, rect.y + 5), self.font_small, GREY)

        status = f"{self.fps_shown} FPS"
        width = self.font.size(status)[0] + 24
        self.panel(surface, pygame.Rect(WIDTH - width - 12, 12, width, 30))
        self.text(surface, status, (WIDTH - width, 17))
        self.gfx.upload_overlay(surface)

    def panel(self, surface, rect, alpha=190):
        pygame.draw.rect(surface, (14, 20, 32, alpha), rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255, 40), rect, width=1, border_radius=8)

    def text(self, surface, text, pos, font=None, color=(235, 240, 248)):
        surface.blit((font or self.font).render(text, True, color), pos)

    def centred(self, surface, text, y, font, color=(235, 240, 248), x=None, width=WIDTH):
        img = font.render(text, True, color)
        surface.blit(img, ((x or 0) + (width - img.get_width()) // 2, y))

    def banner(self, surface, title, line, line_color=(190, 200, 215), y=12):
        """A panel across the top middle: a title, and a line under it."""
        width = max(self.font_title.size(title)[0] if title else 0, self.font.size(line)[0]) + 40
        rect = pygame.Rect((WIDTH - width) // 2, y, width, 66 if title else 34)
        self.panel(surface, rect)
        if title:
            self.text(surface, title, (rect.x + (width - self.font_title.size(title)[0]) // 2, y + 6),
                      self.font_title)
        self.text(surface, line, (rect.x + (width - self.font.size(line)[0]) // 2, y + (38 if title else 7)),
                  color=line_color)

    def bar(self, surface, rect, t, back=(10, 14, 20, 220), color=None):
        pygame.draw.rect(surface, back, rect, border_radius=2)
        if t > 0:
            pygame.draw.rect(surface, color or health_color(t), (rect.x, rect.y, max(1, int(rect.w * t)), rect.h),
                             border_radius=2)

    def draw_health_bars(self, surface):
        """Over the HQ (when it's hurt or selected), over anyone or any turret hurt or selected,
        and how far along each turret being built is."""
        view_proj = self.camera.view_proj()
        if self.base and (self.base.hp < self.base.MAX_HP or self.hq_selected):
            hq = self.base.hq
            p = self.camera.to_screen(hq.i + hq.w / 2, 3.4, hq.j + hq.d / 2, *self.size, view_proj)
            if p:
                self.bar(surface, pygame.Rect(int(p[0]) - 45, int(p[1]), 90, 7), self.base.hp / self.base.MAX_HP)
        for turret in self.turrets:
            if not turret.alive or turret.blueprint:
                continue
            p = self.camera.to_screen(turret.x, 1.65, turret.z, *self.size, view_proj)
            if not p:
                continue
            x, y = int(p[0]) - 20, int(p[1])
            if not turret.built:
                self.bar(surface, pygame.Rect(x, y - 7, 40, 5), turret.progress, color=(110, 175, 255))
            if not turret.built or turret.hp < turret.MAX_HP or turret is self.turret_selected:
                self.bar(surface, pygame.Rect(x, y, 40, 5), turret.hp / turret.MAX_HP)
        for unit in self.units + self.zombies:
            if not unit.alive or (unit.hp >= unit.MAX_HP and unit not in self.selected):
                continue
            p = self.camera.to_screen(unit.x, 1.35 * unit.SIZE, unit.z, *self.size, view_proj)
            if p and 0 <= p[0] < WIDTH and 0 <= p[1] < HEIGHT:
                self.bar(surface, pygame.Rect(int(p[0]) - 14, int(p[1]), 28, 4), unit.hp / unit.MAX_HP)

    def draw_wave_clock(self, surface):
        left = max(0.0, self.waves.left)
        walking = sum(z.alive for z in self.zombies)
        title = f"Wave {self.waves.number + 1} in {int(left) // 60}:{int(left) % 60:02d}"
        line = f"{walking} zombies on the map  ·  {self.kills} down"
        width = max(self.font_big.size(title)[0], self.font_small.size(line)[0]) + 36
        rect = pygame.Rect((WIDTH - width) // 2, 12, width, 46)
        self.panel(surface, rect)
        self.centred(surface, title, 15, self.font_big, (255, 150, 135) if left < 5 else (235, 240, 248))
        self.centred(surface, line, 38, self.font_small, GREY)

    def draw_game_over(self, surface):
        shade = pygame.Surface(self.size, pygame.SRCALPHA)
        shade.fill((8, 6, 6, 120))
        surface.blit(shade, (0, 0))
        rect = pygame.Rect((WIDTH - 520) // 2, HEIGHT // 2 - 90, 520, 170)
        self.panel(surface, rect, alpha=225)
        minutes, seconds = divmod(int(self.played), 60)
        self.centred(surface, "Your HQ has fallen", rect.y + 18, self.font_huge, (255, 140, 125))
        self.centred(surface, f"You held out {minutes}:{seconds:02d}, through {self.waves.number} waves,", rect.y + 80,
                     self.font)
        self.centred(surface, f"and {self.kills} zombies went down.", rect.y + 102, self.font)
        self.centred(surface, "Press R to play again", rect.y + 134, self.font_bold, GOLD)

    # ------------------------------------------------------------ the selection panel

    def panel_layout(self):
        """Where the selection panel (bottom left) and its buttons are, or None when nothing's selected.
        Buttons are (what they make, rect): a kind of unit to train, or Turret to build."""
        if self.hq_selected:
            panel = pygame.Rect(PANEL_X, HEIGHT - 12 - 252, PANEL_W, 252)
            y = panel.y + 116
            return {"panel": panel, "buttons": [(kind, pygame.Rect(panel.x + 14 + k * (BUTTON + 76), y, BUTTON, BUTTON))
                                                for k, kind in enumerate(self.base.TRAINS)]}
        if self.turret_selected:
            return {"panel": pygame.Rect(PANEL_X, HEIGHT - 12 - 132, PANEL_W, 132), "buttons": []}
        if self.selected:
            rows = (min(len(self.selected), 24) + 7) // 8
            build = 104 if self.engineers else 0
            height = 108 + rows * 42 + build
            panel = pygame.Rect(PANEL_X, HEIGHT - 12 - height, PANEL_W, height)
            buttons = []
            if build:
                buttons.append((Turret, pygame.Rect(panel.x + 14, panel.y + 72 + rows * 42 + 24, 64, 64)))
            return {"panel": panel, "buttons": buttons}
        return None

    def draw_icon(self, surface, rect, kind):
        """A flat portrait: a soldier's helmet, an engineer's hard hat and vest, or a turret."""
        r = rect
        pygame.draw.rect(surface, (52, 64, 82), r, border_radius=6)
        cx, s = r.centerx, r.w / 76
        team = tuple(int(c * 255) for c in PLAYER_BLUE)
        if kind is Turret:
            pygame.draw.rect(surface, (110, 108, 102), (r.x + 12 * s, r.bottom - 22 * s, r.w - 24 * s, 16 * s))
            pygame.draw.rect(surface, team, (r.x + 12 * s, r.bottom - 15 * s, r.w - 24 * s, 3 * s))
            pygame.draw.rect(surface, (60, 62, 66), (cx - 6 * s, r.y + 34 * s, 12 * s, 20 * s))
            pygame.draw.rect(surface, (46, 48, 52), (cx - 13 * s, r.y + 22 * s, 26 * s, 16 * s))
            pygame.draw.rect(surface, (82, 90, 60), (cx - 20 * s, r.y + 18 * s, 10 * s, 24 * s))
            pygame.draw.rect(surface, (46, 48, 52), (cx - 34 * s, r.y + 27 * s, 26 * s, 5 * s))
            return
        engineer = kind is Engineer
        body, vest = ((62, 69, 82), (242, 122, 26)) if engineer else ((84, 92, 58), (120, 107, 77))
        pygame.draw.rect(surface, body, (r.x + 10 * s, r.bottom - 22 * s, r.w - 20 * s, 22 * s),
                         border_top_left_radius=int(12 * s), border_top_right_radius=int(12 * s))
        pygame.draw.rect(surface, vest, (cx - 15 * s, r.bottom - 22 * s, 30 * s, 22 * s))
        if engineer:
            pygame.draw.rect(surface, (220, 222, 214), (cx - 15 * s, r.bottom - 14 * s, 30 * s, 3 * s))
        else:
            pygame.draw.rect(surface, team, (cx + 3 * s, r.bottom - 17 * s, 8 * s, 5 * s))
        pygame.draw.rect(surface, (219, 173, 138), (cx - 11 * s, r.y + 24 * s, 22 * s, 26 * s),
                         border_radius=int(5 * s))
        for side in (-1, 1):
            pygame.draw.rect(surface, (30, 26, 22), (cx + side * 5 * s - 2 * s, r.y + 34 * s, 4 * s, 4 * s))
        hat = (245, 199, 36) if engineer else (84, 92, 58)
        pygame.draw.ellipse(surface, hat, (cx - 17 * s, r.y + 11 * s, 34 * s, 24 * s))
        pygame.draw.rect(surface, hat, (cx - 19 * s, r.y + 25 * s, 38 * s, 5 * s), border_radius=int(2 * s))
        pygame.draw.rect(surface, team, (cx - 17 * s, r.y + 21 * s, 34 * s, 4 * s))

    def draw_button(self, surface, rect, kind, key, hovered, count=0, progress=None):
        self.draw_icon(surface, rect, kind)
        if hovered:
            pygame.draw.rect(surface, (255, 255, 255, 40), rect, border_radius=6)
        pygame.draw.rect(surface, GOLD if hovered else (255, 255, 255, 70), rect, width=2, border_radius=6)
        tag = pygame.Rect(rect.x + 4, rect.y + 4, 18, 18)
        pygame.draw.rect(surface, (14, 20, 32, 220), tag, border_radius=4)
        self.text(surface, key, (tag.x + 5, tag.y), self.font_bold, GOLD)
        if count:
            badge = self.font_bold.render(str(count), True, (20, 24, 30))
            spot = pygame.Rect(rect.right - 24, rect.y + 4, 20, 20)
            pygame.draw.ellipse(surface, GOLD, spot)
            surface.blit(badge, badge.get_rect(center=spot.center))
        if progress is not None:
            bar = pygame.Rect(rect.x + 4, rect.bottom - 10, rect.w - 8, 6)
            pygame.draw.rect(surface, (10, 14, 20, 230), bar, border_radius=3)
            pygame.draw.rect(surface, (115, 230, 135), (bar.x, bar.y, int(bar.w * progress), bar.h), border_radius=3)

    def draw_hq_panel(self, surface, layout, hover_button):
        base, panel = self.base, layout["panel"]
        self.panel(surface, panel)
        x, y = panel.x + 14, panel.y
        self.text(surface, "Headquarters", (x, y + 8), self.font_title)
        self.text(surface, f"{base.team_name}  ·  {base.owner}", (x, y + 40), self.font_small, GREY)
        self.bar(surface, pygame.Rect(x, y + 64, PANEL_W - 28, 8), base.hp / base.MAX_HP)
        self.text(surface, f"Walls {base.hp} / {base.MAX_HP}", (x, y + 74), self.font_small, GREY)
        self.text(surface, "TRAIN", (x, y + 96), self.font_small, GOLD)
        for kind, rect in layout["buttons"]:
            training = base.queue and base.queue[0] is kind
            self.draw_button(surface, rect, kind, TRAIN_KEYS[kind], bool(hover_button and hover_button[0] is kind),
                             base.queued(kind), base.progress if training else None)
            tx = rect.right + 8
            self.text(surface, kind.NAME, (tx, rect.y + 2), self.font_big)
            self.text(surface, f"{kind.TRAIN_TIME:g} s", (tx, rect.y + 26), self.font_small, GREY)
            self.text(surface, f"{kind.DAMAGE} dmg", (tx, rect.y + 42), self.font_small, GREY)
            self.text(surface, f"range {kind.RANGE:g}", (tx, rect.y + 58), self.font_small, GREY)
        if base.queue:
            name = base.queue[0].NAME.lower()
            line = f"Training {'an' if name[0] in 'aeiou' else 'a'} {name}: {int(base.progress * 100)}%"
            if len(base.queue) > 1:
                line += f", {len(base.queue) - 1} more after"
            self.text(surface, line, (x, panel.bottom - 44), self.font_small, (150, 235, 165))
        else:
            self.text(surface, "Click to train, right click to cancel", (x, panel.bottom - 44), self.font_small, GREY)
        self.text(surface, "Right click the ground: where new units gather", (x, panel.bottom - 24),
                  self.font_small, GREY)

    def draw_turret_panel(self, surface, layout):
        t, panel = self.turret_selected, layout["panel"]
        self.panel(surface, panel)
        x, y = panel.x + 14, panel.y
        title = "Turret" if t.built else "Turret blueprint" if t.blueprint else "Turret (being built)"
        self.text(surface, title, (x, y + 8), self.font_title)
        self.text(surface, f"Semi-automatic  ·  {t.DAMAGE} damage  ·  range {t.RANGE:g} tiles", (x, y + 40),
                  self.font_small, GREY)
        self.bar(surface, pygame.Rect(x, y + 64, PANEL_W - 28, 8), t.hp / t.MAX_HP)
        self.text(surface, f"Health {int(t.hp)} / {t.MAX_HP}", (x, y + 74), self.font_small, GREY)
        if t.built:
            self.text(surface, "Shoots the nearest zombie it can see in range.", (x, y + 100), self.font_small, GREY)
        elif t.blueprint:
            self.text(surface, "Waiting for an engineer  ·  lay a turret here again to call it off", (x, y + 100),
                      self.font_small, (140, 195, 255))
        else:
            workers = sum(isinstance(u, Engineer) and u.job is t and u.working for u in self.units)
            self.text(surface, f"Built {int(t.progress * 100)}%  ·  {workers} engineer{'s' * (workers != 1)} at work",
                      (x, y + 100), self.font_small, (140, 195, 255))

    def draw_units_panel(self, surface, layout, hover_button):
        panel = layout["panel"]
        self.panel(surface, panel)
        x, y = panel.x + 14, panel.y
        counts = [(kind, sum(type(u) is kind for u in self.selected)) for kind in (Soldier, Engineer)]
        title = "  ·  ".join(plural(n, kind) for kind, n in counts if n)
        self.text(surface, title, (x, y + 8), self.font_title if len(title) < 22 else self.font_big)
        self.text(surface, "Blue team  ·  You", (x, y + 40), self.font_small, GREY)
        pygame.draw.line(surface, (255, 255, 255, 40), (x, y + 64), (panel.right - 14, y + 64))
        for k, unit in enumerate(self.selected[:24]):
            icon = pygame.Rect(x + (k % 8) * 37, y + 72 + (k // 8) * 42, 32, 32)
            self.draw_icon(surface, icon, type(unit))
            self.bar(surface, pygame.Rect(icon.x, icon.bottom + 2, icon.w, 4), unit.hp / unit.MAX_HP)
        if len(self.selected) > 24:
            self.text(surface, f"+{len(self.selected) - 24}", (panel.right - 46, y + 72 + 2 * 42), self.font_bold, GOLD)
        for what, rect in layout["buttons"]:              # the engineers' build button
            self.text(surface, "BUILD", (x, rect.y - 20), self.font_small, GOLD)
            self.draw_button(surface, rect, what, "B", bool(hover_button and hover_button[0] is what))
            tx = rect.right + 12
            self.text(surface, "Turret", (tx, rect.y + 2), self.font_big)
            self.text(surface, f"{Turret.BUILD_TIME:g} s for one engineer  ·  drag for a row", (tx, rect.y + 26),
                      self.font_small, GREY)
            self.text(surface, f"{Turret.DAMAGE} dmg  ·  range {Turret.RANGE:g}  ·  semi-auto", (tx, rect.y + 42),
                      self.font_small, GREY)
        shooting = sum(u.aiming > 0 for u in self.selected)
        building = sum(isinstance(u, Engineer) and u.working for u in self.selected)
        moving = sum(u.moving for u in self.selected)
        if building:
            hint = f"{building} building  ·  right click an unbuilt turret to help"
        elif shooting:
            hint = f"{shooting} shooting  ·  right click a zombie to go after it"
        elif moving:
            hint = f"{moving} on the move  ·  right click to move them"
        else:
            hint = "Right click: move  ·  right drag: line them up"
        self.text(surface, hint, (x, panel.bottom - 24), self.font_small, GREY)


if __name__ == "__main__":
    shot = None
    if "--screenshot" in sys.argv:
        shot = sys.argv[sys.argv.index("--screenshot") + 1]
    Game(screenshot=shot).run()
