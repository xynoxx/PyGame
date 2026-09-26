# Python Games

A collection of small arcade games made with Python and [pygame](https://www.pygame.org/). Each game is a single file in its own folder.

## Setup

```
python -m pip install pygame
```

## Games

| Game | Run | Controls |
| --- | --- | --- |
| Snake | `python snake/snake.py` | Arrows / WASD to move, P pause, Space restart |
| Pong | `python pong/pong.py` | Menu: 1 = vs computer, 2 = two players. Left W/S, right Up/Down, P pause |
| Flappy | `python flappy/flappy.py` | Space / click / Up to flap |
| Whack-a-Mole | `python whack_a_mole/whack_a_mole.py` | Click moles with the hammer; 45-second rounds |

Esc quits any game.

### Snake
Eat food to grow; each bite speeds you up. Hitting a wall or yourself ends the game. Fill the whole board to win.

### Pong
Classic two-paddle Pong, first to 7. Where the ball hits your paddle sets its return angle, and the ball speeds up with every hit.

### Flappy
Flap through the gaps between pipes. One point per pipe passed; touching a pipe or the ground ends the run.

### Whack-a-Mole
Moles pop out of 9 holes. They appear faster and hide sooner as the timer runs down. Your score, accuracy and escaped moles are shown at the end.
