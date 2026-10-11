import random
import sys
from functools import lru_cache

import pygame

CELL = 150
BOARD = CELL * 3
HUD_H = 90
WIDTH, HEIGHT = BOARD, BOARD + HUD_H
LINE_W = 6
MARK_PAD = 32  # gap between a mark and its cell edge
AI_DELAY = 0.45  # seconds the computer "thinks" before moving

BG = (24, 26, 36)
GRID = (70, 75, 95)
HOVER = (38, 41, 56)
X_COLOR = (90, 180, 250)
O_COLOR = (250, 120, 110)
WIN_LINE = (250, 220, 90)
TEXT = (235, 235, 235)
DIM = (150, 150, 165)

LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
         (0, 3, 6), (1, 4, 7), (2, 5, 8),  # columns
         (0, 4, 8), (2, 4, 6)]  # diagonals


def find_winner(board):
    """Return (mark, line) for a winning line, or (None, None)."""
    for line in LINES:
        a, b, c = line
        if board[a] and board[a] == board[b] == board[c]:
            return board[a], line
    return None, None


def other(mark):
    return "O" if mark == "X" else "X"


@lru_cache(maxsize=None)
def minimax(board, turn, ai):
    """Score a position for the AI: +10 win, -10 loss, 0 draw; faster wins score higher."""
    winner, _ = find_winner(board)
    if winner:
        return 10 if winner == ai else -10
    if "" not in board:
        return 0
    scores = []
    for i, cell in enumerate(board):
        if not cell:
            nxt = board[:i] + (turn,) + board[i + 1:]
            scores.append(minimax(nxt, other(turn), ai))
    best = max(scores) if turn == ai else min(scores)
    return best - 1 if best > 0 else best + 1 if best < 0 else 0  # prefer quick wins, slow losses


def best_move(board, ai):
    board = tuple(board)
    empty = [i for i, c in enumerate(board) if not c]
    scored = [(minimax(board[:i] + (ai,) + board[i + 1:], other(ai), ai), i) for i in empty]
    top = max(s for s, _ in scored)
    return random.choice([i for s, i in scored if s == top])  # vary play between equal moves


def easy_move(board, ai):
    empty = [i for i, c in enumerate(board) if not c]
    # Take a win if one is available, otherwise play randomly
    for i in empty:
        trial = list(board)
        trial[i] = ai
        if find_winner(trial)[0] == ai:
            return i
    return random.choice(empty)


class Game:
    def __init__(self):
        self.state = "menu"  # menu, play, over
        self.mode = "2p"  # 2p, easy, hard
        self.scores = {"X": 0, "O": 0, "draw": 0}
        self.round = 0

    @property
    def vs_ai(self):
        return self.mode != "2p"

    def start(self, mode):
        self.mode = mode
        self.scores = {"X": 0, "O": 0, "draw": 0}
        self.round = 0
        self.new_round()

    def new_round(self):
        self.board = [""] * 9
        self.turn = "X" if self.round % 2 == 0 else "O"  # starting player alternates each round
        self.winner = None
        self.win_line = None
        self.ai_timer = AI_DELAY
        self.state = "play"
        self.round += 1

    def ai_turn(self):
        # The human is always X; the computer is O
        return self.vs_ai and self.turn == "O"

    def place(self, i):
        if self.state != "play" or self.board[i]:
            return
        self.board[i] = self.turn
        self.winner, self.win_line = find_winner(self.board)
        if self.winner:
            self.scores[self.winner] += 1
            self.state = "over"
        elif "" not in self.board:
            self.scores["draw"] += 1
            self.state = "over"
        else:
            self.turn = other(self.turn)
            self.ai_timer = AI_DELAY

    def click(self, pos):
        if self.state != "play" or self.ai_turn():
            return
        x, y = pos
        if y < HUD_H:
            return
        col, row = x // CELL, (y - HUD_H) // CELL
        self.place(row * 3 + col)

    def update(self, dt):
        if self.state == "play" and self.ai_turn():
            self.ai_timer -= dt
            if self.ai_timer <= 0:
                move = best_move(self.board, "O") if self.mode == "hard" else easy_move(self.board, "O")
                self.place(move)


def cell_center(i):
    return (i % 3) * CELL + CELL // 2, HUD_H + (i // 3) * CELL + CELL // 2


def draw_text(screen, font, text, center, color=TEXT):
    surf = font.render(text, True, color)
    screen.blit(surf, surf.get_rect(center=center))


def draw_mark(screen, mark, i):
    cx, cy = cell_center(i)
    half = CELL // 2 - MARK_PAD
    if mark == "X":
        pygame.draw.line(screen, X_COLOR, (cx - half, cy - half), (cx + half, cy + half), 12)
        pygame.draw.line(screen, X_COLOR, (cx - half, cy + half), (cx + half, cy - half), 12)
    else:
        pygame.draw.circle(screen, O_COLOR, (cx, cy), half, 11)


def draw(screen, game, font, small_font, big_font):
    screen.fill(BG)

    if game.state == "menu":
        draw_text(screen, big_font, "X  O", (WIDTH // 2, 150))
        draw_text(screen, font, "1  -  Two Players", (WIDTH // 2, 270))
        draw_text(screen, font, "2  -  vs Computer (Easy)", (WIDTH // 2, 315))
        draw_text(screen, font, "3  -  vs Computer (Hard)", (WIDTH // 2, 360))
        draw_text(screen, small_font, "Click a square to place your mark", (WIDTH // 2, 450))
        draw_text(screen, small_font, "ESC to quit", (WIDTH // 2, 480), DIM)
        pygame.display.flip()
        return

    # HUD: scores and whose turn it is
    x_label = "You (X)" if game.vs_ai else "X"
    o_label = "CPU (O)" if game.vs_ai else "O"
    draw_text(screen, small_font, f"{x_label}: {game.scores['X']}", (WIDTH // 6 + 10, 28), X_COLOR)
    draw_text(screen, small_font, f"Draws: {game.scores['draw']}", (WIDTH // 2, 28), DIM)
    draw_text(screen, small_font, f"{o_label}: {game.scores['O']}", (WIDTH * 5 // 6 - 10, 28), O_COLOR)
    if game.state == "play":
        if game.ai_turn():
            status, color = "Computer is thinking...", O_COLOR
        else:
            status = f"{game.turn}'s turn" if not game.vs_ai else "Your turn"
            color = X_COLOR if game.turn == "X" else O_COLOR
    elif game.winner:
        if game.vs_ai:
            status = "You win!" if game.winner == "X" else "Computer wins!"
        else:
            status = f"{game.winner} wins!"
        color = X_COLOR if game.winner == "X" else O_COLOR
    else:
        status, color = "It's a draw!", TEXT
    draw_text(screen, font, status, (WIDTH // 2, 65), color)

    # Hover highlight on the empty cell under the mouse
    if game.state == "play" and not game.ai_turn():
        mx, my = pygame.mouse.get_pos()
        if my >= HUD_H:
            i = ((my - HUD_H) // CELL) * 3 + mx // CELL
            if 0 <= i < 9 and not game.board[i]:
                pygame.draw.rect(screen, HOVER, ((i % 3) * CELL, HUD_H + (i // 3) * CELL, CELL, CELL))

    for k in (1, 2):
        pygame.draw.line(screen, GRID, (k * CELL, HUD_H + 10), (k * CELL, HEIGHT - 10), LINE_W)
        pygame.draw.line(screen, GRID, (10, HUD_H + k * CELL), (WIDTH - 10, HUD_H + k * CELL), LINE_W)

    for i, mark in enumerate(game.board):
        if mark:
            draw_mark(screen, mark, i)

    if game.win_line:
        start = cell_center(game.win_line[0])
        end = cell_center(game.win_line[2])
        pygame.draw.line(screen, WIN_LINE, start, end, 10)

    if game.state == "over":
        bar = pygame.Surface((WIDTH, 44), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 170))
        screen.blit(bar, (0, HEIGHT - 44))
        draw_text(screen, small_font, "SPACE / click: next round   M: menu", (WIDTH // 2, HEIGHT - 22))

    pygame.display.flip()


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("XO - Tic-Tac-Toe")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 26, bold=True)
    small_font = pygame.font.SysFont("consolas", 18, bold=True)
    big_font = pygame.font.SysFont("consolas", 80, bold=True)

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
                    modes = {pygame.K_1: "2p", pygame.K_2: "easy", pygame.K_3: "hard"}
                    if event.key in modes:
                        game.start(modes[event.key])
                elif event.key == pygame.K_m:
                    game.state = "menu"
                elif game.state == "over" and event.key == pygame.K_SPACE:
                    game.new_round()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if game.state == "over":
                    game.new_round()
                else:
                    game.click(event.pos)

        game.update(dt)
        draw(screen, game, font, small_font, big_font)


if __name__ == "__main__":
    main()
