import math
import random
import sys

import pygame

WIDTH, HEIGHT = 400, 600
GROUND_H = 80
PLAY_BOTTOM = HEIGHT - GROUND_H

BIRD_X = 100
BIRD_R = 15
GRAVITY = 1500  # px per second squared
FLAP_VELOCITY = -450
MAX_FALL_SPEED = 700

PIPE_W = 70
PIPE_GAP = 160
PIPE_SPEED = 170  # px per second
PIPE_SPACING = 230  # horizontal distance between pipes
PIPE_MARGIN = 60  # minimum pipe length at top and bottom
RESTART_DELAY = 0.6  # ignore input briefly after dying so you don't restart by accident

SKY = (112, 197, 206)
GROUND = (222, 216, 149)
GROUND_TOP = (84, 176, 67)
PIPE = (96, 184, 72)
PIPE_DARK = (60, 130, 45)
BIRD = (250, 205, 60)
BEAK = (240, 120, 40)
WHITE = (255, 255, 255)
BLACK = (20, 20, 20)


class Pipe:
    def __init__(self, x):
        self.x = x
        self.gap_y = random.randint(PIPE_MARGIN + PIPE_GAP // 2,
                                    PLAY_BOTTOM - PIPE_MARGIN - PIPE_GAP // 2)
        self.passed = False

    def rects(self):
        top = pygame.Rect(round(self.x), 0, PIPE_W, self.gap_y - PIPE_GAP // 2)
        bottom_y = self.gap_y + PIPE_GAP // 2
        bottom = pygame.Rect(round(self.x), bottom_y, PIPE_W, PLAY_BOTTOM - bottom_y)
        return top, bottom


def circle_hits_rect(cx, cy, r, rect):
    # Closest point on the rectangle to the circle center
    nx = max(rect.left, min(cx, rect.right))
    ny = max(rect.top, min(cy, rect.bottom))
    return (cx - nx) ** 2 + (cy - ny) ** 2 < r * r


class Game:
    def __init__(self):
        self.high_score = 0
        self.reset()

    def reset(self):
        self.state = "ready"  # ready, play, over
        self.bird_y = HEIGHT / 2 - 40
        self.velocity = 0.0
        self.pipes = []
        self.score = 0
        self.time = 0.0
        self.death_time = 0.0
        self.ground_offset = 0.0

    def flap(self):
        if self.state == "ready":
            self.state = "play"
            self.pipes = [Pipe(WIDTH + 60)]
        if self.state == "play":
            self.velocity = FLAP_VELOCITY
        elif self.state == "over" and self.time - self.death_time > RESTART_DELAY:
            self.reset()

    def die(self):
        self.state = "over"
        self.death_time = self.time
        self.high_score = max(self.high_score, self.score)

    def update(self, dt):
        self.time += dt

        if self.state == "ready":
            self.bird_y = HEIGHT / 2 - 40 + math.sin(self.time * 5) * 8  # idle bobbing
            self.ground_offset = (self.ground_offset + PIPE_SPEED * dt) % 24
            return

        if self.state == "over":
            # Let the bird drop to the ground after a crash
            if self.bird_y < PLAY_BOTTOM - BIRD_R:
                self.velocity = min(self.velocity + GRAVITY * dt, MAX_FALL_SPEED)
                self.bird_y = min(self.bird_y + self.velocity * dt, PLAY_BOTTOM - BIRD_R)
            return

        self.velocity = min(self.velocity + GRAVITY * dt, MAX_FALL_SPEED)
        self.bird_y += self.velocity * dt
        self.ground_offset = (self.ground_offset + PIPE_SPEED * dt) % 24

        for pipe in self.pipes:
            pipe.x -= PIPE_SPEED * dt
        if self.pipes and self.pipes[-1].x < WIDTH - PIPE_SPACING:
            self.pipes.append(Pipe(WIDTH))
        self.pipes = [p for p in self.pipes if p.x + PIPE_W > 0]

        for pipe in self.pipes:
            if not pipe.passed and pipe.x + PIPE_W < BIRD_X:
                pipe.passed = True
                self.score += 1

        if self.bird_y + BIRD_R >= PLAY_BOTTOM:
            self.bird_y = PLAY_BOTTOM - BIRD_R
            self.die()
            return
        if self.bird_y - BIRD_R < 0:
            self.bird_y = BIRD_R  # the ceiling blocks you but doesn't kill
            self.velocity = 0
        for pipe in self.pipes:
            if any(circle_hits_rect(BIRD_X, self.bird_y, BIRD_R, r) for r in pipe.rects()):
                self.die()
                return


def draw_bird(screen, y, velocity):
    # Tilt the face up when rising and down when falling
    tilt = max(-0.5, min(1.2, velocity / 500))
    cx, cy = BIRD_X, round(y)
    pygame.draw.circle(screen, BIRD, (cx, cy), BIRD_R)
    pygame.draw.circle(screen, BLACK, (cx, cy), BIRD_R, 2)
    eye_x = cx + 6
    eye_y = cy - 5 + round(tilt * 3)
    pygame.draw.circle(screen, WHITE, (eye_x, eye_y), 5)
    pygame.draw.circle(screen, BLACK, (eye_x + 2, eye_y), 2)
    beak_y = cy + 3 + round(tilt * 4)
    pygame.draw.polygon(screen, BEAK, [(cx + 12, beak_y - 4), (cx + 24, beak_y), (cx + 12, beak_y + 4)])


def draw_pipe(screen, pipe):
    top, bottom = pipe.rects()
    for rect, cap_y in ((top, top.bottom - 20), (bottom, bottom.top)):
        pygame.draw.rect(screen, PIPE, rect)
        pygame.draw.rect(screen, PIPE_DARK, rect, 3)
        cap = pygame.Rect(rect.x - 5, cap_y, PIPE_W + 10, 20)
        pygame.draw.rect(screen, PIPE, cap)
        pygame.draw.rect(screen, PIPE_DARK, cap, 3)


def draw_text(screen, font, text, center, color=WHITE):
    # Text with a dark outline so it's readable over the sky and pipes
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        shadow = font.render(text, True, BLACK)
        screen.blit(shadow, shadow.get_rect(center=(center[0] + dx, center[1] + dy)))
    surf = font.render(text, True, color)
    screen.blit(surf, surf.get_rect(center=center))


def draw(screen, game, font, big_font):
    screen.fill(SKY)
    for pipe in game.pipes:
        draw_pipe(screen, pipe)

    pygame.draw.rect(screen, GROUND, (0, PLAY_BOTTOM, WIDTH, GROUND_H))
    pygame.draw.rect(screen, GROUND_TOP, (0, PLAY_BOTTOM, WIDTH, 12))
    for x in range(-24, WIDTH + 24, 24):
        sx = x - round(game.ground_offset)
        pygame.draw.line(screen, PIPE_DARK, (sx, PLAY_BOTTOM + 12), (sx + 12, PLAY_BOTTOM), 3)

    draw_bird(screen, game.bird_y, game.velocity)

    if game.state == "ready":
        draw_text(screen, big_font, "FLAPPY", (WIDTH // 2, 130))
        draw_text(screen, font, "SPACE / click to flap", (WIDTH // 2, 400))
        draw_text(screen, font, f"Best: {game.high_score}", (WIDTH // 2, 440))
    else:
        draw_text(screen, big_font, str(game.score), (WIDTH // 2, 70))

    if game.state == "over":
        draw_text(screen, big_font, "GAME OVER", (WIDTH // 2, 220))
        draw_text(screen, font, f"Score: {game.score}   Best: {game.high_score}", (WIDTH // 2, 280))
        if game.time - game.death_time > RESTART_DELAY:
            draw_text(screen, font, "SPACE / click to retry", (WIDTH // 2, 320))

    pygame.display.flip()


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Flappy")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 22, bold=True)
    big_font = pygame.font.SysFont("consolas", 50, bold=True)

    game = Game()

    while True:
        dt = min(clock.tick(60) / 1000, 1 / 30)  # cap dt so a lag spike can't teleport the bird
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    game.flap()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.flap()

        game.update(dt)
        draw(screen, game, font, big_font)


if __name__ == "__main__":
    main()
