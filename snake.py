import random
import sys

import pygame

CELL = 20
COLS, ROWS = 30, 24
WIDTH, HEIGHT = CELL * COLS, CELL * ROWS
START_SPEED = 8  # moves per second
SPEED_STEP = 0.5  # speed gained per food eaten

BG = (18, 18, 24)
GRID = (28, 28, 36)
SNAKE_HEAD = (120, 220, 110)
SNAKE_BODY = (70, 170, 70)
FOOD = (230, 70, 70)
TEXT = (235, 235, 235)

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)
KEY_DIRS = {
    pygame.K_UP: UP, pygame.K_w: UP,
    pygame.K_DOWN: DOWN, pygame.K_s: DOWN,
    pygame.K_LEFT: LEFT, pygame.K_a: LEFT,
    pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT,
}


class Game:
    def __init__(self):
        self.high_score = 0
        self.reset()

    def reset(self):
        cx, cy = COLS // 2, ROWS // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = RIGHT
        self.pending = []  # queued turns so fast key presses aren't lost
        self.score = 0
        self.speed = START_SPEED
        self.game_over = False
        self.paused = False
        self.food = self.spawn_food()

    def spawn_food(self):
        free = [(x, y) for x in range(COLS) for y in range(ROWS)
                if (x, y) not in self.snake]
        return random.choice(free) if free else None

    def queue_turn(self, new_dir):
        last = self.pending[-1] if self.pending else self.direction
        # Ignore reversing into yourself or repeating the same direction
        if new_dir != last and (new_dir[0] + last[0], new_dir[1] + last[1]) != (0, 0):
            if len(self.pending) < 3:
                self.pending.append(new_dir)

    def step(self):
        if self.pending:
            self.direction = self.pending.pop(0)

        hx, hy = self.snake[0]
        new_head = (hx + self.direction[0], hy + self.direction[1])

        will_eat = new_head == self.food
        body = self.snake if will_eat else self.snake[:-1]  # tail moves away unless growing
        if (not 0 <= new_head[0] < COLS or not 0 <= new_head[1] < ROWS
                or new_head in body):
            self.game_over = True
            self.high_score = max(self.high_score, self.score)
            return

        self.snake.insert(0, new_head)
        if will_eat:
            self.score += 1
            self.speed += SPEED_STEP
            self.food = self.spawn_food()
            if self.food is None:  # board filled: you win
                self.game_over = True
                self.high_score = max(self.high_score, self.score)
        else:
            self.snake.pop()


def draw(screen, game, font, big_font):
    screen.fill(BG)
    for x in range(0, WIDTH, CELL):
        pygame.draw.line(screen, GRID, (x, 0), (x, HEIGHT))
    for y in range(0, HEIGHT, CELL):
        pygame.draw.line(screen, GRID, (0, y), (WIDTH, y))

    if game.food:
        fx, fy = game.food
        pygame.draw.circle(screen, FOOD,
                           (fx * CELL + CELL // 2, fy * CELL + CELL // 2), CELL // 2 - 2)

    for i, (x, y) in enumerate(game.snake):
        color = SNAKE_HEAD if i == 0 else SNAKE_BODY
        pygame.draw.rect(screen, color,
                         (x * CELL + 1, y * CELL + 1, CELL - 2, CELL - 2), border_radius=5)

    hud = font.render(f"Score: {game.score}   Best: {game.high_score}", True, TEXT)
    screen.blit(hud, (10, 8))

    if game.game_over or game.paused:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))
        title = "PAUSED" if game.paused else ("YOU WIN!" if game.food is None else "GAME OVER")
        hint = "Press P to resume" if game.paused else "Press SPACE to play again, ESC to quit"
        t = big_font.render(title, True, TEXT)
        h = font.render(hint, True, TEXT)
        screen.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
        screen.blit(h, h.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 25)))

    pygame.display.flip()


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Snake")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 20)
    big_font = pygame.font.SysFont("consolas", 48, bold=True)

    game = Game()
    move_timer = 0.0

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
                if game.game_over:
                    if event.key == pygame.K_SPACE:
                        game.reset()
                        move_timer = 0.0
                elif event.key == pygame.K_p:
                    game.paused = not game.paused
                elif event.key in KEY_DIRS and not game.paused:
                    game.queue_turn(KEY_DIRS[event.key])

        if not game.game_over and not game.paused:
            move_timer += dt
            interval = 1 / game.speed
            while move_timer >= interval and not game.game_over:
                move_timer -= interval
                game.step()

        draw(screen, game, font, big_font)


if __name__ == "__main__":
    main()
