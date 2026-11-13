"""Skyline: a 3D real-time strategy game made with pygame and ModernGL.

For now: a square patch of a dead, overrun world, your HQ, and your commander
in black tactical gear, who walks wherever you send them.

Run it with:  python main.py
Needs:        pip install pygame moderngl

Controls
  Left click       select your commander (click empty ground to deselect)
  Right click      send the selected commander there
  WASD / arrows    move the camera (or push the mouse against a screen edge)
  Mouse wheel      zoom in and out
  Q / E            turn the camera (or drag with the middle mouse button)
  Space            select your commander and bring the camera to them
  F                camera follows your commander
  X                stop
  H                hide or show the controls
  Esc              quit
"""
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
from units import Commander  # noqa: E402
from world import World  # noqa: E402

WIDTH, HEIGHT = 1280, 720
EDGE_SCROLL = 6            # pixels from the window edge that scroll the camera
TURN_SPEED = 1.8           # camera turn with Q / E, radians per second
MARKER_TIME = 0.6          # how long the "move here" ring lasts

PLAYER_BLUE = (0.24, 0.48, 0.95)
SELECT_GREEN = (0.45, 1.0, 0.55)

HELP_LINES = [
    ("Left click", "select commander"),
    ("Right click", "move there"),
    ("WASD / edges", "move camera"),
    ("Wheel", "zoom"),
    ("Q / E, mid-drag", "turn camera"),
    ("Space", "find commander"),
    ("F", "follow commander"),
    ("X", "stop"),
    ("H", "hide controls"),
]


class Game:
    def __init__(self, screenshot=None):
        pygame.init()
        self.size = (WIDTH, HEIGHT)
        open_window(self.size, "Skyline")
        self.gfx = Renderer(moderngl.create_context(), self.size)
        self.screenshot = screenshot

        self.world = World()
        x, z = self.world.spawns["player"]
        self.commander = Commander(self.world, x, z, PLAYER_BLUE, "Blue team", "You")
        self.camera = RTSCamera(self.world.size, WIDTH / HEIGHT)
        self.camera.look_at(x, z - 3, instant=True)

        self.ground_mesh = self.gfx.mesh(models.build_ground(self.world))
        self.hq_mesh = self.gfx.mesh(models.build_hq(self.world.hqs["player"], PLAYER_BLUE))
        body, leg, arm = models.build_commander(PLAYER_BLUE)
        self.body_mesh, self.leg_mesh, self.arm_mesh = (self.gfx.mesh(m) for m in (body, leg, arm))
        self.ring_mesh = self.gfx.mesh(models.build_ring())
        self.disc_mesh = self.gfx.mesh(models.build_disc())

        self.selected = True
        self.hovered = False
        self.follow = False
        self.show_help = True
        self.markers = []          # [x, z, age] of recent move orders
        self.turning = False       # dragging with the middle mouse button
        self.running = True

        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui", 15)
        self.font_bold = pygame.font.SysFont("segoeui", 15, bold=True)
        self.font_title = pygame.font.SysFont("segoeui", 24, bold=True)
        self.hud_key = None
        self.fps_shown = 0
        self.fps_timer = 0.0

    # ------------------------------------------------------------ main loop

    def run(self):
        if self.screenshot:
            return self.take_screenshot()
        while self.running:
            dt = min(self.clock.tick(144) / 1000, 0.05)
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def take_screenshot(self):
        """Walk the commander a little way with no player input, then save one frame."""
        x, z = self.world.spawns["player"]
        self.commander.move_to(x + 9, z - 7)
        self.markers.append([x + 9, z - 7, 0.0])
        for _ in range(55):
            self.update(1 / 60, edge_scroll=False)
        self.draw()
        pygame.image.save(self.gfx.read_pixels(), self.screenshot)
        pygame.quit()
        print("saved", self.screenshot)

    # ------------------------------------------------------------ input

    def mouse_ray(self, pos):
        return self.camera.ray(pos[0], pos[1], *self.size)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.on_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.selected = self.commander.hit_by_ray(*self.mouse_ray(event.pos))
                elif event.button == 3 and self.selected:
                    self.order_move(event.pos)
                elif event.button == 2:
                    self.turning = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                self.turning = False
            elif event.type == pygame.MOUSEMOTION and self.turning:
                self.camera.turn(-event.rel[0] * 0.008)
            elif event.type == pygame.MOUSEWHEEL:
                self.camera.zoom(event.y)

    def on_key(self, key):
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_SPACE:
            self.selected = True
            self.camera.look_at(self.commander.x, self.commander.z)
        elif key == pygame.K_f:
            self.follow = not self.follow
        elif key == pygame.K_x:
            self.commander.stop()
        elif key == pygame.K_h:
            self.show_help = not self.show_help

    def order_move(self, pos):
        point = self.camera.ground_point(pos[0], pos[1], *self.size)
        if point is None:
            return
        self.markers.append([point[0], point[1], 0.0])
        self.commander.move_to(*point)

    # ------------------------------------------------------------ update

    def update(self, dt, edge_scroll=True):
        keys = pygame.key.get_pressed()
        forward = (keys[pygame.K_w] or keys[pygame.K_UP]) - (keys[pygame.K_s] or keys[pygame.K_DOWN])
        right = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        if edge_scroll and pygame.mouse.get_focused():
            mx, my = pygame.mouse.get_pos()
            right += (mx >= WIDTH - EDGE_SCROLL) - (mx < EDGE_SCROLL)
            forward += (my < EDGE_SCROLL) - (my >= HEIGHT - EDGE_SCROLL)
        if forward or right:
            self.follow = False
            self.camera.pan(mathx.clamp(forward, -1, 1), mathx.clamp(right, -1, 1), dt)
        turn = keys[pygame.K_q] - keys[pygame.K_e]
        if turn:
            self.camera.turn(turn * TURN_SPEED * dt)

        self.commander.update(dt)
        if self.follow:
            self.camera.look_at(self.commander.x, self.commander.z)
        self.camera.update(dt)

        self.hovered = (not self.screenshot
                        and self.commander.hit_by_ray(*self.mouse_ray(pygame.mouse.get_pos())))
        for marker in self.markers:
            marker[2] += dt
        self.markers = [m for m in self.markers if m[2] < MARKER_TIME]

        self.fps_timer += dt
        if self.fps_timer >= 0.5:
            self.fps_timer = 0.0
            self.fps_shown = round(self.clock.get_fps())

    # ------------------------------------------------------------ drawing

    def draw(self):
        gfx = self.gfx
        gfx.begin(self.camera.view_proj(), self.camera.eye(), self.camera.fog_range())
        gfx.draw(self.ground_mesh, grid=True)
        gfx.draw(self.hq_mesh)
        self.draw_commander()
        self.draw_ground_marks()
        self.refresh_hud()
        gfx.draw_overlay()

    def draw_commander(self):
        c = self.commander
        base = mathx.chain(mathx.translate(c.x, 0, c.z), mathx.rot_y(c.yaw), mathx.scale(c.SIZE))
        body = mathx.mul(base, mathx.translate(0, c.bob, 0))
        self.gfx.draw(self.body_mesh, body)
        for side in (-1, 1):
            leg = mathx.chain(body, mathx.translate(side * 0.1, 0.42, 0), mathx.rot_x(side * c.swing))
            arm = mathx.chain(body, mathx.translate(side * 0.29, 0.80, 0),
                              mathx.rot_x(-side * c.swing * 0.8))
            self.gfx.draw(self.leg_mesh, leg)
            self.gfx.draw(self.arm_mesh, arm)

    def ring_at(self, x, z, radius, color, alpha, mesh=None, height=0.03):
        model = mathx.chain(mathx.translate(x, height, z), mathx.scale(radius, 1, radius))
        self.gfx.draw(mesh or self.ring_mesh, model, tint=(*color, alpha))

    def draw_ground_marks(self):
        c = self.commander
        self.ring_at(c.x, c.z, 0.5, (0.0, 0.0, 0.0), 0.28, mesh=self.disc_mesh, height=0.015)
        if self.selected:
            self.ring_at(c.x, c.z, 0.62, SELECT_GREEN, 0.95)
            if c.destination:
                self.ring_at(*c.destination, 0.22, SELECT_GREEN, 0.45)
        elif self.hovered:
            self.ring_at(c.x, c.z, 0.62, (1.0, 1.0, 1.0), 0.5)
        for x, z, age in self.markers:
            t = age / MARKER_TIME
            self.ring_at(x, z, 0.8 - 0.55 * t, SELECT_GREEN, 1.0 - t, height=0.035)

    # ------------------------------------------------------------ the 2D overlay

    def refresh_hud(self):
        """Redraw the overlay only when something on it has changed."""
        c = self.commander
        key = (self.show_help, self.selected, c.moving, c.tile, self.follow, self.fps_shown)
        if key == self.hud_key:
            return
        self.hud_key = key
        surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self.draw_hud(surface)
        self.gfx.upload_overlay(surface)

    def panel(self, surface, rect):
        pygame.draw.rect(surface, (14, 20, 32, 175), rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255, 40), rect, width=1, border_radius=8)

    def text(self, surface, text, pos, font=None, color=(235, 240, 248)):
        surface.blit((font or self.font).render(text, True, color), pos)

    def draw_hud(self, surface):
        if self.show_help:
            self.panel(surface, pygame.Rect(12, 12, 270, 52 + 21 * len(HELP_LINES)))
            self.text(surface, "SKYLINE", (26, 20), self.font_title)
            for k, (keys, what) in enumerate(HELP_LINES):
                y = 58 + 21 * k
                self.text(surface, keys, (26, y), self.font_bold, (255, 214, 120))
                self.text(surface, what, (150, y))
        else:
            self.panel(surface, pygame.Rect(12, 12, 118, 30))
            self.text(surface, "H  controls", (24, 17), self.font_bold, (255, 214, 120))

        status = f"{self.fps_shown} FPS" + ("   ·   camera follows" if self.follow else "")
        width = self.font.size(status)[0] + 24
        self.panel(surface, pygame.Rect(WIDTH - width - 12, 12, width, 30))
        self.text(surface, status, (WIDTH - width, 17))

        if self.selected:
            c = self.commander
            rect = pygame.Rect(12, HEIGHT - 104, 250, 92)
            self.panel(surface, rect)
            swatch = tuple(int(v * 255) for v in c.team_color)
            pygame.draw.rect(surface, swatch, (26, rect.y + 16, 14, 14), border_radius=3)
            self.text(surface, "Commander", (48, rect.y + 11), self.font_bold)
            self.text(surface, f"{c.team_name}  ·  {c.owner}", (26, rect.y + 37), color=(190, 200, 215))
            state = "Walking" if c.moving else "Standing"
            self.text(surface, f"{state}  ·  tile {c.tile[0]}, {c.tile[1]}", (26, rect.y + 59),
                      color=(190, 200, 215))


if __name__ == "__main__":
    shot = None
    if "--screenshot" in sys.argv:
        shot = sys.argv[sys.argv.index("--screenshot") + 1]
    Game(screenshot=shot).run()
