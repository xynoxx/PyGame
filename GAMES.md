# Python Games Guide

English | [ภาษาไทย](GAMES.th.md)

Everything about the five games in this project: how to run them, how to play, how each one works, what you can change, and how the code is organized.

## Contents

- [Setup](#setup)
- [Quick reference](#quick-reference)
- [Things all games share](#things-all-games-share)
- [Snake](#snake)
- [Pong](#pong)
- [Flappy](#flappy)
- [Whack-a-Mole](#whack-a-mole)
- [XO (Tic-Tac-Toe)](#xo-tic-tac-toe)

## Setup

You need Python 3 and pygame 2.0 or newer.

```
python -m pip install pygame
```

Run a game from the project folder, for example:

```
python snake/snake.py
```

The run command for every game is in the table below.

## Quick reference

| Game | Run | Goal | Controls |
| --- | --- | --- | --- |
| Snake | `python snake/snake.py` | Eat food and grow without crashing | Arrows / WASD to turn, P pause, Space restart |
| Pong | `python pong/pong.py` | First to 7 points | Menu 1 / 2. Left paddle W / S, right paddle Up / Down, P pause |
| Flappy | `python flappy/flappy.py` | Fly through as many pipes as you can | Space, Up, W or left click to flap |
| Whack-a-Mole | `python whack_a_mole/whack_a_mole.py` | Whack as many moles as you can in 45 seconds | Move the mouse to aim, left click to whack |
| XO | `python xo/xo.py` | Get three in a row | Menu 1 / 2 / 3. Click a square, Space next round, M menu |

## Things all games share

- **Quitting:** Esc or closing the window quits any game, on any screen.
- **One file per game:** each game is a single Python file in its own folder. There are no image or sound files; everything is drawn with pygame shapes and text.
- **Settings:** sizes, speeds, timings and colors are constants at the top of each file. Change a number and run the game again to try it.
- **Timing:** every game runs at up to 60 frames per second. Movement and timers are based on the time between frames, not the frame count, so game speed doesn't depend on the frame rate.
- **Scores aren't saved:** Best scores and match scores last only while the game window is open.
- **Font:** text uses Consolas. If it isn't installed, pygame uses its default font instead.

---

## Snake

Steer a growing snake around a grid, eat food, and don't crash. Every bite makes the snake longer and faster.

**Window:** 600 × 480 pixels, a grid of 30 × 24 cells of 20 px each.

### Controls

| Key | Action |
| --- | --- |
| Arrow keys or W A S D | Turn the snake |
| P | Pause / resume |
| Space | Play again (on the Game Over / You Win screen) |
| Esc | Quit |

### Rules

- The snake starts 3 cells long in the middle of the board, moving right.
- Eat the red food to score 1 point and grow by one cell. New food appears on a random free cell.
- The game ends if the head hits a wall or any part of the snake's body.
- Moving into the cell the tail is just leaving is allowed, because the tail moves out of the way in the same step.
- **Winning:** if the snake fills all 720 cells so no food can be placed, the game shows **YOU WIN!**

### Score and speed

- **Score:** food eaten in this run.
- **Best:** the highest score since the game was opened.
- **Speed:** the snake starts at 8 moves per second and gains 0.5 moves per second for each food eaten. There is no top speed.

### Turning

- You can't turn straight back into yourself (for example Left while moving Right); that press is ignored. Pressing the direction you're already going is ignored too.
- Up to 3 turns are queued, and one is used per move. Quick sequences like Up then Left aren't lost, even if both keys are pressed between two moves.
- Turns are ignored while paused.

### Screens

| Screen | What you see | Keys |
| --- | --- | --- |
| Playing | Grid, snake (bright head, darker body), food, Score and Best in the top-left | Arrows / WASD, P, Esc |
| Paused | Dimmed board with **PAUSED** | P to resume |
| Game over | **GAME OVER** or **YOU WIN!** | Space to play again, Esc to quit |

### Settings

All in [snake/snake.py](snake/snake.py):

| Constant | Default | Meaning |
| --- | --- | --- |
| `CELL` | 20 | Size of one grid cell in pixels |
| `COLS`, `ROWS` | 30, 24 | Board size in cells (the window size follows from these) |
| `START_SPEED` | 8 | Moves per second at the start |
| `SPEED_STEP` | 0.5 | Moves per second gained per food |
| `BG`, `GRID`, `SNAKE_HEAD`, `SNAKE_BODY`, `FOOD`, `TEXT` | — | Colors (RGB) |

### Code layout

| Part | What it does |
| --- | --- |
| `KEY_DIRS` | Maps arrow keys and WASD to directions |
| `Game.reset()` | Sets up a new snake, score, speed and food |
| `Game.spawn_food()` | Picks a random cell the snake isn't on; returns `None` when the board is full |
| `Game.queue_turn()` | Checks that a turn is allowed and adds it to the queue |
| `Game.step()` | Moves the snake one cell; handles eating, growing, crashing and winning |
| `draw()` | Draws the grid, food, snake, score and the pause / game-over overlay |
| `main()` | Window setup, key handling and the main loop. Moves are timed with an accumulator, so the snake's speed doesn't depend on the frame rate. |

---

## Pong

Classic two-paddle Pong. Play the computer or a friend on the same keyboard. First to 7 points wins.

**Window:** 800 × 500 pixels.

### Controls

| Key | Action |
| --- | --- |
| 1 | (Menu) Play vs Computer |
| 2 | (Menu) Two Players |
| W / S | Move the left paddle up / down |
| Up / Down | Move the right paddle (Two Players only) |
| P | Pause / resume during a match |
| Space | Back to the menu after a match |
| Esc | Quit |

Against the computer you always play the **left** paddle with W / S. The arrow keys do nothing in that mode.

### Rules

- Before every serve there is a 1-second wait. The ball isn't shown yet, but the paddles can already move.
- The first serve of a match goes left or right at random. After that, the ball is always served toward the player who just **lost** the point.
- A serve leaves at a random angle of up to 30° above or below horizontal, at 360 px/s.
- The ball bounces off the top and bottom edges.
- When the ball gets past a paddle and leaves the screen, the other player scores.
- First to **7** points wins the match.

### Ball physics

- **Aiming:** where the ball hits your paddle sets its return angle. The center sends it back straight; the ends send it off at up to 60°.
- **Speed-up:** each paddle hit makes the ball 6% faster, up to 900 px/s. The speed goes back to 360 px/s on every serve.
- The ball only bounces off a paddle while moving toward it, so it can't get stuck inside one.

### The computer opponent

- It follows the ball while the ball is coming toward it, and drifts back to the middle while the ball is going away.
- It moves at 330 px/s, slower than a player's paddle (420 px/s), so fast balls can get past it.
- Every time you hit the ball, it picks a random aiming error of up to 35 px, so it doesn't always meet the ball dead center.
- It stops moving when it is within 10 px of where it wants to be, so it doesn't jitter.

### Screens

| Screen | What you see | Keys |
| --- | --- | --- |
| Menu | **PONG**, the two modes, control help | 1, 2, Esc |
| Match | Dashed center line, both scores at the top, paddles and ball | W / S, Up / Down, P, Esc |
| Paused | Dimmed field with **PAUSED** | P to resume |
| Match over | **YOU WIN!** or **COMPUTER WINS** (vs Computer); **LEFT PLAYER WINS** or **RIGHT PLAYER WINS** (Two Players) | Space for the menu, Esc to quit |

### Settings

All in [pong/pong.py](pong/pong.py):

| Constant | Default | Meaning |
| --- | --- | --- |
| `WIDTH`, `HEIGHT` | 800, 500 | Window size |
| `PADDLE_W`, `PADDLE_H` | 12, 90 | Paddle size in pixels |
| `PADDLE_MARGIN` | 30 | Gap between each paddle and its edge of the screen |
| `PADDLE_SPEED` | 420 | Player paddle speed (px/s) |
| `AI_SPEED` | 330 | Computer paddle speed (px/s); raise it to make the computer harder |
| `BALL_SIZE` | 14 | Ball size in pixels |
| `BALL_START_SPEED` | 360 | Ball speed on each serve (px/s) |
| `BALL_SPEEDUP` | 1.06 | Speed multiplier per paddle hit |
| `BALL_MAX_SPEED` | 900 | Top ball speed (px/s) |
| `MAX_BOUNCE_ANGLE` | 60° | Steepest return angle, off the end of a paddle |
| `SERVE_DELAY` | 1.0 | Wait before each serve (seconds) |
| `WIN_SCORE` | 7 | Points needed to win |
| `BG`, `FG`, `DIM` | — | Colors (RGB) |

### Code layout

| Part | What it does |
| --- | --- |
| `Paddle` | Paddle position (a float, for smooth movement); `move()` keeps it on screen |
| `Ball` | Position and velocity; `serve()` puts it back in the center, `bounce_off()` sets its angle and speed after a paddle hit |
| `Game` | Match state (`menu`, `play`, `over`), mode, score, pause and serve timer |
| `Game.update()` | Reads held keys, moves the paddles, runs the computer, moves the ball, and handles edges, paddle hits and scoring |
| `Game.update_ai()` | The computer paddle's movement |
| `Game.point()` | Adds a point, checks for a winner and serves the next ball |
| `draw()` | Draws the menu, or the field, scores, paddles, ball and overlays |
| `main()` | Window setup, key handling and the main loop |

---

## Flappy

A Flappy Bird–style game. Flap to stay in the air, fly through the gaps between pipes, and see how far you get.

**Window:** 400 × 600 pixels, with an 80 px ground strip at the bottom.

### Controls

| Input | Action |
| --- | --- |
| Space, Up or W | Flap (also starts the game, and retries after a crash) |
| Left click | Same as Space |
| Esc | Quit |

### Rules

- On the start screen the bird bobs in place. Your first flap starts the run, and the first pipe comes in from the right.
- Gravity pulls the bird down all the time. A flap sets the bird's upward speed to a fixed value. Flaps don't stack, so flapping faster doesn't launch you higher.
- Each pipe pair has a 160 px gap at a random height.
- **Scoring:** 1 point for each pipe you get past.
- **Game over:** touching a pipe or the ground. After a crash the pipes stop and the bird drops to the ground.
- The top of the screen stops the bird but does **not** end the game.
- After a crash, input is ignored for 0.6 seconds so you don't restart by accident. "SPACE / click to retry" appears when you can restart.

### Score

- The current score is shown in large digits at the top of the screen.
- **Best** is the highest score since the game was opened. It is shown on the start and game-over screens.

### Physics

| What | Value |
| --- | --- |
| Gravity | 1500 px/s² |
| Flap | Sets the bird's speed to 450 px/s upward |
| Top falling speed | 700 px/s |
| Pipe speed | 170 px/s |
| Distance between pipes | 230 px |
| Gap | 160 px, with at least 60 px of pipe above and below it |

- Hits are checked between a circle (the bird, radius 15 px) and the pipe rectangles, so clipping a corner is judged fairly.
- The wider pipe caps are only decoration. Hits use the pipe body, so the extra 5 px on each side of a cap don't count.
- Time per frame is capped at 1/30 second, so a lag spike can't carry the bird through a pipe.
- The bird's eye and beak tilt with its speed: up when rising, down when falling.

### Screens

| Screen | What you see |
| --- | --- |
| Ready | **FLAPPY**, "SPACE / click to flap", Best score, bobbing bird, scrolling ground |
| Playing | Pipes, ground, bird and the score at the top |
| Game over | **GAME OVER**, Score and Best; "SPACE / click to retry" after 0.6 s |

### Settings

All in [flappy/flappy.py](flappy/flappy.py):

| Constant | Default | Meaning |
| --- | --- | --- |
| `WIDTH`, `HEIGHT` | 400, 600 | Window size |
| `GROUND_H` | 80 | Height of the ground strip |
| `BIRD_X` | 100 | The bird's fixed horizontal position |
| `BIRD_R` | 15 | Bird radius |
| `GRAVITY` | 1500 | Downward acceleration (px/s²) |
| `FLAP_VELOCITY` | -450 | Vertical speed set by a flap (negative is up) |
| `MAX_FALL_SPEED` | 700 | Top falling speed (px/s) |
| `PIPE_W` | 70 | Pipe width |
| `PIPE_GAP` | 160 | Gap height; smaller is harder |
| `PIPE_SPEED` | 170 | Pipe speed (px/s); higher is harder |
| `PIPE_SPACING` | 230 | Horizontal distance between pipes |
| `PIPE_MARGIN` | 60 | Shortest a pipe can be, at the top and bottom |
| `RESTART_DELAY` | 0.6 | Seconds input is ignored after a crash |
| `SKY`, `GROUND`, `GROUND_TOP`, `PIPE`, `PIPE_DARK`, `BIRD`, `BEAK`, `WHITE`, `BLACK` | — | Colors (RGB) |

### Code layout

| Part | What it does |
| --- | --- |
| `Pipe` | A pipe pair with a random gap height; `rects()` returns the top and bottom rectangles |
| `circle_hits_rect()` | Circle-vs-rectangle hit test used for the bird |
| `Game` | State (`ready`, `play`, `over`), the bird's height and speed, pipes and score |
| `Game.flap()` | Starts the run, flaps, or restarts, depending on the state |
| `Game.update()` | Gravity, pipe movement and spawning, scoring, hits, and the fall after a crash |
| `draw_bird()`, `draw_pipe()` | Draw the bird (with tilt) and the pipes (with caps) |
| `draw_text()` | Text with a dark outline so it stays readable over the sky and pipes |
| `main()` | Window setup, input and the main loop |

---

## Whack-a-Mole

Moles pop out of nine holes. Whack as many as you can with the hammer before the 45-second timer runs out. They come faster as time runs down.

**Window:** 600 × 660 pixels: an 80 px scoreboard on top and a 3 × 3 field of holes below.

### Controls

| Input | Action |
| --- | --- |
| Mouse | Move the hammer (it replaces the mouse cursor) |
| Left click | Swing the hammer; also starts a round and starts the next one |
| Esc | Quit |

### Rules

- Click on the start screen to begin a 45-second round. The first mole appears half a second later.
- Moles pop up in random empty holes, at most one per hole.
- Click a mole to whack it for **1 point**. A whacked mole gets X-shaped eyes and sinks.
- A mole must be at least 30% out of its hole to be hit, so you can't hit one that has only just started rising or has nearly sunk back.
- The hit area is a circle a little bigger than the mole's head (50 px radius), so near misses still count.
- One click whacks at most one mole.
- A click that hits nothing counts as a **miss**, including clicks on the scoreboard.
- A mole that goes back down without being hit has **escaped**.
- When the timer reaches 0 the round ends and all moles disappear.

### Difficulty

Difficulty rises steadily from the start of the round to the end:

| | Start of round | End of round |
| --- | --- | --- |
| Time between new moles | 0.90 s | 0.40 s |
| Time a mole stays up | 1.20 s | 0.55 s |

A mole takes 0.12 s to rise and 0.12 s to sink, both counted in its time up. If every hole is taken when a new mole is due, that mole is skipped.

### Results

The **TIME'S UP!** screen shows:

- **Score:** moles whacked this round
- **Best:** the highest score since the game was opened
- **Accuracy:** hits ÷ (hits + misses), as a percentage
- **Escaped:** moles that went back down without being hit

Clicks are ignored for 0.6 seconds after the round ends so you don't restart by accident. "Click to play again" appears when you can.

### Screens

| Screen | What you see |
| --- | --- |
| Ready | Dimmed field with **WHACK-A-MOLE** and "Click to start" |
| Playing | Scoreboard with Score, Time (whole seconds, rounded up) and Best; holes and moles |
| Time's up | Dimmed field with the results |

The scoreboard and the hammer are shown on every screen.

### Settings

All in [whack_a_mole/whack_a_mole.py](whack_a_mole/whack_a_mole.py):

| Constant | Default | Meaning |
| --- | --- | --- |
| `WIDTH`, `HEIGHT` | 600, 660 | Window size |
| `HUD_H` | 80 | Scoreboard height |
| `GRID` | 3 | Holes per row and column (3 means 9 holes) |
| `HOLE_RX`, `HOLE_RY` | 60, 22 | Hole size (ellipse radii) |
| `MOLE_R` | 42 | Mole head radius |
| `MOLE_RISE` | 60 | How far a mole pops out of its hole (px) |
| `GAME_TIME` | 45 | Round length in seconds |
| `SPAWN_EVERY` | (0.90, 0.40) | Seconds between moles at the start and end of a round |
| `STAY_UP` | (1.20, 0.55) | Seconds a mole stays up at the start and end of a round |
| `ANIM_TIME` | 0.12 | Rise / sink animation length (seconds) |
| `HIT_SHOW_TIME` | 0.30 | How long a whacked mole stays visible (seconds) |
| `RESTART_DELAY` | 0.6 | Seconds clicks are ignored after a round ends |
| `GRASS`, `GRASS_DARK`, `HUD_BG`, `HOLE`, `HOLE_RIM`, `MOLE`, `MOLE_BELLY`, `NOSE`, `WHITE`, `BLACK`, `HANDLE`, `HEAD` | — | Colors (RGB) |

### Code layout

| Part | What it does |
| --- | --- |
| `hole_centers()` | Works out where the holes go, below the scoreboard |
| `Mole` | A mole's age, how long it stays up, and when it was hit; `height()` says how far out of the hole it is (0 to 1) for the animation |
| `Game` | State (`ready`, `play`, `over`), moles by hole, score, misses, escaped count and timer |
| `Game.lerp()` | Blends a (start, end) setting by how far the round has gone; this is what makes difficulty rise |
| `Game.update()` | Counts down the timer, ages and removes moles, and spawns new ones |
| `Game.click()` | Starts or restarts a round, or checks for a hit |
| `draw_mole()` | Draws a mole cut off at its hole, so it looks like it's coming out of the ground |
| `draw_hammer()` | Draws the hammer cursor, swung down for 0.1 s after each click |
| `main()` | Window setup, hides the system cursor, input and the main loop |

---

## XO (Tic-Tac-Toe)

Get three of your marks in a row on a 3 × 3 board. Play a friend on the same computer, or play the computer on Easy or Hard.

**Window:** 450 × 540 pixels: a 90 px scoreboard above a 450 × 450 board.

### Controls

| Input | Action |
| --- | --- |
| 1 | (Menu) Two Players |
| 2 | (Menu) vs Computer, Easy |
| 3 | (Menu) vs Computer, Hard |
| Left click | Place your mark on an empty square; after a round ends, start the next round |
| Space | Next round (after a round ends) |
| M | Back to the menu (during or after a round) |
| Esc | Quit |

### Rules

- Players take turns placing X and O on empty squares.
- Three of the same mark in a row, column or diagonal wins the round, and a yellow line is drawn through them.
- If the board fills up with no three in a row, the round is a draw.
- **X starts the first round**, and the starting player switches every round (X, O, X, O, …).
- Clicking a taken square or the scoreboard, or clicking while the computer is moving, does nothing.
- Going back to the menu ends the match. Picking a mode starts a new match with all scores at 0.

### Game modes

| Mode | Players |
| --- | --- |
| Two Players | Two people take turns with the mouse, as X and O |
| vs Computer (Easy) | You are X, the computer is O |
| vs Computer (Hard) | You are X, the computer is O |

Against the computer you are always X. Because the starting player switches every round, the computer moves first in rounds 2, 4, 6 and so on.

### Computer difficulty

- **Easy:** if it can win with one move, it does; otherwise it picks a random empty square. It does **not** block your winning moves, so it is easy to beat.
- **Hard:** uses **minimax**, which looks at every possible way the rest of the game can go. It never loses; the best you can get is a draw.
  - When it can win, it takes the quickest win.
  - When several moves are equally good, it picks one at random, so games vary.
  - It remembers positions it has already worked out (`lru_cache`), which keeps it fast.
- The computer waits 0.45 seconds before each move ("Computer is thinking...") so you can follow what it does.

### Scoreboard

- The top row shows X's wins, draws, and O's wins. Against the computer they are labelled **You (X)** and **CPU (O)**.
- Below it, the status line shows whose turn it is, "Computer is thinking...", who won, or "It's a draw!".
- Scores carry over from round to round until you go back to the menu.

### Screens

| Screen | What you see |
| --- | --- |
| Menu | **X O**, the three modes and control hints |
| Playing | Scoreboard, status line and board. On your turn, the empty square under the mouse is highlighted. |
| Round over | The winning line (if any), and a bar at the bottom: "SPACE / click: next round   M: menu" |

### Settings

All in [xo/xo.py](xo/xo.py):

| Constant | Default | Meaning |
| --- | --- | --- |
| `CELL` | 150 | Size of one square in pixels (the window size follows from this) |
| `HUD_H` | 90 | Scoreboard height |
| `LINE_W` | 6 | Grid line thickness |
| `MARK_PAD` | 32 | Gap between a mark and the edge of its square |
| `AI_DELAY` | 0.45 | Seconds the computer waits before moving |
| `BG`, `GRID`, `HOVER`, `X_COLOR`, `O_COLOR`, `WIN_LINE`, `TEXT`, `DIM` | — | Colors (RGB) |

### Code layout

| Part | What it does |
| --- | --- |
| `LINES` | The 8 winning lines (3 rows, 3 columns, 2 diagonals) as square numbers |
| `find_winner()` | Returns the winning mark and its line, or `(None, None)` |
| `minimax()` | Scores a position for the computer: +10 win, −10 loss, 0 draw, moved 1 point toward 0 for each extra move, so faster wins score higher |
| `best_move()` | Hard mode: picks at random among the best-scoring moves |
| `easy_move()` | Easy mode: takes a win if there is one, otherwise a random move |
| `Game` | State (`menu`, `play`, `over`), mode (`2p`, `easy`, `hard`), board, turn, scores and round count |
| `Game.start()` | Starts a mode with scores at 0 |
| `Game.new_round()` | Clears the board and sets who starts |
| `Game.place()` | Puts a mark down and checks for a win or draw |
| `Game.click()` | Turns a mouse click into a square number |
| `Game.update()` | Counts down the computer's wait and makes its move |
| `draw()` | Draws the menu, or the scoreboard, highlight, grid, marks, winning line and round-over bar |
| `main()` | Window setup, input and the main loop |

The board is a list of 9 strings (`""`, `"X"` or `"O"`), numbered left to right, top to bottom:

```
0 | 1 | 2
---------
3 | 4 | 5
---------
6 | 7 | 8
```
