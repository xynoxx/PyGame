import math
import random
import sys

import pygame

WIDTH, HEIGHT = 800, 500
PADDLE_W, PADDLE_H = 12, 90
PADDLE_MARGIN = 30
PADDLE_SPEED = 420  # px per second
AI_SPEED = 330  # slower than the player so the computer can be beaten
BALL_SIZE = 14
BALL_START_SPEED = 360
BALL_SPEEDUP = 1.06  # multiplier on every paddle hit
BALL_MAX_SPEED = 900
MAX_BOUNCE_ANGLE = math.radians(60)
SERVE_DELAY = 1.0  # seconds before each serve
WIN_SCORE = 7

BG = (18, 18, 24)
FG = (235, 235, 235)
DIM = (80, 80, 95)


class Paddle:
    def __init__(self, x):
        self.x = x
        self.y = HEIGHT / 2 - PADDLE_H / 2  # float for smooth movement

    @property
    def rect(self):
        return pygame.Rect(self.x, round(self.y), PADDLE_W, PADDLE_H)

    def move(self, dy):
        self.y = max(0, min(HEIGHT - PADDLE_H, self.y + dy))


class Ball:
    def __init__(self):
        self.serve(random.choice((-1, 1)))

    def serve(self, direction):
        self.x = WIDTH / 2 - BALL_SIZE / 2
        self.y = HEIGHT / 2 - BALL_SIZE / 2
        self.speed = BALL_START_SPEED
        angle = random.uniform(-math.radians(30), math.radians(30))
        self.vx = direction * self.speed * math.cos(angle)
        self.vy = self.speed * math.sin(angle)

    @property
    def rect(self):
        return pygame.Rect(round(self.x), round(self.y), BALL_SIZE, BALL_SIZE)

    def bounce_off(self, paddle, direction):
        # Where the ball hits the paddle sets the return angle: center = straight, edges = steep
        pr = paddle.rect
        offset = ((self.y + BALL_SIZE / 2) - pr.centery) / (PADDLE_H / 2)
        offset = max(-1.0, min(1.0, offset))
        angle = offset * MAX_BOUNCE_ANGLE
        self.speed = min(self.speed * BALL_SPEEDUP, BALL_MAX_SPEED)
        self.vx = direction * self.speed * math.cos(angle)
        self.vy = self.speed * math.sin(angle)


class Game:
    def __init__(self):
        self.state = "menu"  # menu, play, over
        self.vs_ai = True
        self.reset()

    def reset(self):
        self.left = Paddle(PADDLE_MARGIN)
        self.right = Paddle(WIDTH - PADDLE_MARGIN - PADDLE_W)
        self.ball = Ball()
        self.score = [0, 0]
        self.serve_timer = SERVE_DELAY
        self.paused = False
        self.winner = None
        self.ai_offset = 0

    def start(self, vs_ai):
        self.vs_ai = vs_ai
        self.reset()
        self.state = "play"

    def update_ai(self, dt):
        paddle, ball = self.right, self.ball
        if ball.vx > 0:
            target = ball.y + BALL_SIZE / 2 + self.ai_offset
        else:
            target = HEIGHT / 2  # drift back to center while the ball is away
        center = paddle.y + PADDLE_H / 2
        if abs(target - center) > 10:
            step = AI_SPEED * dt
            paddle.move(step if target > center else -step)

    def update(self, dt, keys):
        if self.state != "play" or self.paused:
            return

        step = PADDLE_SPEED * dt
        if keys[pygame.K_w]:
            self.left.move(-step)
        if keys[pygame.K_s]:
            self.left.move(step)
        if self.vs_ai:
            self.update_ai(dt)
        else:
            if keys[pygame.K_UP]:
                self.right.move(-step)
            if keys[pygame.K_DOWN]:
                self.right.move(step)

        if self.serve_timer > 0:
            self.serve_timer -= dt
            return

        ball = self.ball
        ball.x += ball.vx * dt
        ball.y += ball.vy * dt

        if ball.y <= 0:
            ball.y = 0
            ball.vy = abs(ball.vy)
        elif ball.y >= HEIGHT - BALL_SIZE:
            ball.y = HEIGHT - BALL_SIZE
            ball.vy = -abs(ball.vy)

        # Only bounce when moving toward the paddle, so the ball can't get stuck inside it
        if ball.vx < 0 and ball.rect.colliderect(self.left.rect):
            ball.x = self.left.rect.right
            ball.bounce_off(self.left, 1)
            self.ai_offset = random.uniform(-35, 35)  # AI aims imperfectly
        elif ball.vx > 0 and ball.rect.colliderect(self.right.rect):
            ball.x = self.right.rect.left - BALL_SIZE
            ball.bounce_off(self.right, -1)

        if ball.x + BALL_SIZE < 0:
            self.point(1)
        elif ball.x > WIDTH:
            self.point(0)

    def point(self, player):
        self.score[player] += 1
        if self.score[player] >= WIN_SCORE:
            self.winner = player
            self.state = "over"
            return
        # Serve toward the player who just lost the point
        self.ball.serve(-1 if player == 1 else 1)
        self.serve_timer = SERVE_DELAY


def draw_center_text(screen, font, text, y):
    surf = font.render(text, True, FG)
    screen.blit(surf, surf.get_rect(center=(WIDTH // 2, y)))


def draw(screen, game, font, big_font, score_font):
    screen.fill(BG)

    if game.state == "menu":
        draw_center_text(screen, big_font, "PONG", HEIGHT // 2 - 90)
        draw_center_text(screen, font, "1  -  Play vs Computer", HEIGHT // 2 - 10)
        draw_center_text(screen, font, "2  -  Two Players", HEIGHT // 2 + 25)
        draw_center_text(screen, font, "Left: W / S     Right: Up / Down", HEIGHT // 2 + 90)
        draw_center_text(screen, font, f"First to {WIN_SCORE} wins  -  P to pause  -  ESC to quit",
                         HEIGHT // 2 + 120)
        pygame.display.flip()
        return

    for y in range(0, HEIGHT, 30):
        pygame.draw.rect(screen, DIM, (WIDTH // 2 - 2, y + 5, 4, 18))

    left_score = score_font.render(str(game.score[0]), True, FG)
    right_score = score_font.render(str(game.score[1]), True, FG)
    screen.blit(left_score, left_score.get_rect(center=(WIDTH // 4, 50)))
    screen.blit(right_score, right_score.get_rect(center=(WIDTH * 3 // 4, 50)))

    pygame.draw.rect(screen, FG, game.left.rect, border_radius=4)
    pygame.draw.rect(screen, FG, game.right.rect, border_radius=4)
    if game.state == "play" and game.serve_timer <= 0:
        pygame.draw.rect(screen, FG, game.ball.rect, border_radius=3)

    if game.paused or game.state == "over":
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))
        if game.paused:
            draw_center_text(screen, big_font, "PAUSED", HEIGHT // 2 - 20)
            draw_center_text(screen, font, "Press P to resume", HEIGHT // 2 + 30)
        else:
            if game.vs_ai:
                title = "YOU WIN!" if game.winner == 0 else "COMPUTER WINS"
            else:
                title = "LEFT PLAYER WINS" if game.winner == 0 else "RIGHT PLAYER WINS"
            draw_center_text(screen, big_font, title, HEIGHT // 2 - 20)
            draw_center_text(screen, font, "Press SPACE for menu, ESC to quit", HEIGHT // 2 + 30)

    pygame.display.flip()


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pong")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 22)
    big_font = pygame.font.SysFont("consolas", 52, bold=True)
    score_font = pygame.font.SysFont("consolas", 64, bold=True)

    game = Game()

    while True:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if game.state == "menu":
                    if event.key == pygame.K_1:
                        game.start(vs_ai=True)
                    elif event.key == pygame.K_2:
                        game.start(vs_ai=False)
                elif game.state == "over":
                    if event.key == pygame.K_SPACE:
                        game.state = "menu"
                elif event.key == pygame.K_p:
                    game.paused = not game.paused

        game.update(dt, pygame.key.get_pressed())
        draw(screen, game, font, big_font, score_font)


if __name__ == "__main__":
    main()
