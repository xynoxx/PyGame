import random
import sys

import pygame

WIDTH, HEIGHT = 600, 660
HUD_H = 80
GRID = 3
HOLE_RX, HOLE_RY = 60, 22  # hole ellipse radii
MOLE_R = 42
MOLE_RISE = 60  # how far the mole pops out of the hole, in px

GAME_TIME = 45  # seconds per round
# Difficulty ramps linearly from the start value to the end value over the round
SPAWN_EVERY = (0.90, 0.40)  # seconds between new moles
STAY_UP = (1.20, 0.55)  # seconds a mole stays up
ANIM_TIME = 0.12  # rise / sink animation length
HIT_SHOW_TIME = 0.30  # how long a whacked mole stays on screen, stunned
RESTART_DELAY = 0.6

GRASS = (106, 170, 72)
GRASS_DARK = (88, 150, 60)
HUD_BG = (60, 100, 45)
HOLE = (50, 35, 25)
HOLE_RIM = (120, 85, 55)
MOLE = (130, 90, 60)
MOLE_BELLY = (190, 150, 110)
NOSE = (230, 110, 130)
WHITE = (255, 255, 255)
BLACK = (20, 20, 20)
HANDLE = (150, 100, 55)
HEAD = (200, 60, 50)


def hole_centers():
    top = HUD_H + 120
    spacing_x = WIDTH // GRID
    spacing_y = (HEIGHT - top) // GRID
    return [(spacing_x // 2 + c * spacing_x, top + r * spacing_y)
            for r in range(GRID) for c in range(GRID)]


class Mole:
    def __init__(self, stay_up):
        self.age = 0.0
        self.stay_up = stay_up
        self.hit_at = None  # age when whacked

    @property
    def done(self):
        if self.hit_at is not None:
            return self.age - self.hit_at > HIT_SHOW_TIME
        return self.age > self.stay_up

    def height(self):
        """How far out of the hole the mole is, from 0 (hidden) to 1 (fully up)."""
        if self.hit_at is not None:
            return max(0.0, 1 - (self.age - self.hit_at) / HIT_SHOW_TIME)
        if self.age < ANIM_TIME:
            return self.age / ANIM_TIME
        if self.age > self.stay_up - ANIM_TIME:
            return max(0.0, (self.stay_up - self.age) / ANIM_TIME)
        return 1.0


class Game:
    def __init__(self):
        self.holes = hole_centers()
        self.high_score = 0
        self.state = "ready"  # ready, play, over
        self.reset()

    def reset(self):
        self.moles = {}  # hole index -> Mole
        self.score = 0
        self.misses = 0  # clicks that hit nothing
        self.escaped = 0  # moles that went back down un-whacked
        self.time_left = GAME_TIME
        self.spawn_timer = 0.5
        self.over_time = 0.0

    def progress(self):
        return 1 - self.time_left / GAME_TIME

    def lerp(self, pair):
        start, end = pair
        return start + (end - start) * self.progress()

    def update(self, dt):
        if self.state == "over":
            self.over_time += dt
            return
        if self.state != "play":
            return

        self.time_left -= dt
        if self.time_left <= 0:
            self.time_left = 0
            self.state = "over"
            self.moles.clear()
            self.high_score = max(self.high_score, self.score)
            return

        for i in list(self.moles):
            mole = self.moles[i]
            mole.age += dt
            if mole.done:
                if mole.hit_at is None:
                    self.escaped += 1
                del self.moles[i]

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_timer = self.lerp(SPAWN_EVERY)
            free = [i for i in range(len(self.holes)) if i not in self.moles]
            if free:
                self.moles[random.choice(free)] = Mole(self.lerp(STAY_UP))

    def click(self, pos):
        if self.state == "ready":
            self.state = "play"
            return
        if self.state == "over":
            if self.over_time > RESTART_DELAY:
                self.reset()
                self.state = "play"
            return

        mx, my = pos
        for i, mole in self.moles.items():
            if mole.hit_at is not None or mole.height() < 0.3:
                continue
            hx, hy = self.holes[i]
            head_y = hy - MOLE_RISE * mole.height()
            if (mx - hx) ** 2 + (my - head_y) ** 2 <= (MOLE_R + 8) ** 2:
                mole.hit_at = mole.age
                self.score += 1
                return
        self.misses += 1


def draw_mole(screen, x, y, height, stunned):
    head_y = round(y - MOLE_RISE * height)
    # Clip at the hole so the mole looks like it's coming out of the ground
    screen.set_clip(pygame.Rect(x - MOLE_R - 5, 0, (MOLE_R + 5) * 2, y + 4))
    pygame.draw.circle(screen, MOLE, (x, head_y), MOLE_R)
    pygame.draw.rect(screen, MOLE, (x - MOLE_R, head_y, MOLE_R * 2, MOLE_RISE + 10))
    pygame.draw.ellipse(screen, MOLE_BELLY, (x - 24, head_y + 10, 48, MOLE_RISE))
    if stunned:
        for ex in (x - 15, x + 15):  # X-shaped eyes
            pygame.draw.line(screen, BLACK, (ex - 5, head_y - 17), (ex + 5, head_y - 7), 3)
            pygame.draw.line(screen, BLACK, (ex - 5, head_y - 7), (ex + 5, head_y - 17), 3)
    else:
        for ex in (x - 15, x + 15):
            pygame.draw.circle(screen, WHITE, (ex, head_y - 12), 7)
            pygame.draw.circle(screen, BLACK, (ex, head_y - 12), 4)
    pygame.draw.ellipse(screen, NOSE, (x - 9, head_y - 2, 18, 12))
    pygame.draw.line(screen, WHITE, (x - 4, head_y + 12), (x - 4, head_y + 18), 4)
    pygame.draw.line(screen, WHITE, (x + 4, head_y + 12), (x + 4, head_y + 18), 4)
    screen.set_clip(None)


def draw_hammer(screen, pos, swinging):
    x, y = pos
    # Swinging tilts the head down onto the cursor
    if swinging:
        pygame.draw.line(screen, HANDLE, (x + 10, y + 10), (x + 60, y + 30), 8)
        head = pygame.Rect(x - 18, y - 12, 36, 26)
    else:
        pygame.draw.line(screen, HANDLE, (x + 10, y - 5), (x + 55, y + 35), 8)
        head = pygame.Rect(x - 10, y - 40, 30, 40)
    pygame.draw.rect(screen, HEAD, head, border_radius=6)
    pygame.draw.rect(screen, BLACK, head, 2, border_radius=6)


def draw_text(screen, font, text, center, color=WHITE):
    surf = font.render(text, True, color)
    screen.blit(surf, surf.get_rect(center=center))


def draw(screen, game, font, big_font, swinging):
    screen.fill(GRASS)
    for y in range(HUD_H, HEIGHT, 40):
        pygame.draw.rect(screen, GRASS_DARK, (0, y, WIDTH, 20))

    for i, (hx, hy) in enumerate(game.holes):
        pygame.draw.ellipse(screen, HOLE_RIM, (hx - HOLE_RX - 6, hy - HOLE_RY - 4,
                                               (HOLE_RX + 6) * 2, (HOLE_RY + 4) * 2))
        pygame.draw.ellipse(screen, HOLE, (hx - HOLE_RX, hy - HOLE_RY, HOLE_RX * 2, HOLE_RY * 2))
        mole = game.moles.get(i)
        if mole:
            draw_mole(screen, hx, hy, mole.height(), mole.hit_at is not None)

    pygame.draw.rect(screen, HUD_BG, (0, 0, WIDTH, HUD_H))
    hud_font_y = HUD_H // 2
    draw_text(screen, font, f"Score: {game.score}", (WIDTH // 6, hud_font_y))
    draw_text(screen, font, f"Time: {max(0, int(game.time_left + 0.99))}", (WIDTH // 2, hud_font_y))
    draw_text(screen, font, f"Best: {game.high_score}", (WIDTH * 5 // 6, hud_font_y))

    if game.state in ("ready", "over"):
        overlay = pygame.Surface((WIDTH, HEIGHT - HUD_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, HUD_H))
        mid = (HEIGHT + HUD_H) // 2
        if game.state == "ready":
            draw_text(screen, big_font, "WHACK-A-MOLE", (WIDTH // 2, mid - 50))
            draw_text(screen, font, f"Whack as many moles as you can in {GAME_TIME}s", (WIDTH // 2, mid + 10))
            draw_text(screen, font, "Click to start", (WIDTH // 2, mid + 50))
        else:
            clicks = game.score + game.misses
            accuracy = round(100 * game.score / clicks) if clicks else 0
            draw_text(screen, big_font, "TIME'S UP!", (WIDTH // 2, mid - 70))
            draw_text(screen, font, f"Score: {game.score}   Best: {game.high_score}", (WIDTH // 2, mid - 10))
            draw_text(screen, font, f"Accuracy: {accuracy}%   Escaped: {game.escaped}", (WIDTH // 2, mid + 25))
            if game.over_time > RESTART_DELAY:
                draw_text(screen, font, "Click to play again", (WIDTH // 2, mid + 70))

    draw_hammer(screen, pygame.mouse.get_pos(), swinging)
    pygame.display.flip()


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Whack-a-Mole")
    pygame.mouse.set_visible(False)  # the hammer replaces the cursor
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 22, bold=True)
    big_font = pygame.font.SysFont("consolas", 48, bold=True)

    game = Game()
    swing_timer = 0.0

    while True:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                swing_timer = 0.1
                game.click(event.pos)

        swing_timer = max(0.0, swing_timer - dt)
        game.update(dt)
        draw(screen, game, font, big_font, swing_timer > 0)


if __name__ == "__main__":
    main()
