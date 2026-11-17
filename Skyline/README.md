# Skyline

A 3D real-time strategy game (RTS) about holding out in a zombie apocalypse, made with **pygame** (window, input, 2D overlay) and **ModernGL** (3D drawing with OpenGL 3.3). Everything you see is made in code: no model, texture or sound files.

It's a playable prototype. You choose where your HQ goes, train soldiers and engineers, build turrets, and hold off waves of zombies that grow every 30 seconds. If the HQ falls, the game is over.

## Contents

- [Run it](#run-it)
- [How the game plays](#how-the-game-plays)
- [Files](#files)
- [How it works](#how-it-works)
- [Rules and numbers](#rules-and-numbers-and-where-to-change-them)
- [Testing](#testing)
- [Decisions so far](#decisions-so-far-and-why)
- [Not built yet](#not-built-yet)

## Run it

```
pip install pygame moderngl
python Skyline/main.py
```

- **Python:** 3.10 or newer (built and tested with 3.12, pygame 2.6, ModernGL 5).
- **Graphics card:** needs OpenGL 3.3. The window is 1280 × 720.
- **Pictures without playing:** `python Skyline/main.py --screenshot out.png` plays a scripted game and saves pictures (see [Testing](#testing)).

## How the game plays

1. **Choose where the HQ goes.** The game opens on the whole map with a see-through HQ that follows the mouse. It's green where it fits (the HQ and its concrete apron must be on the map) and red where it doesn't. Left click builds it, and the 30-second countdown to the first wave starts.
2. **Train units.** Click the HQ. Its panel (bottom left) has **Soldier** (T) and **Engineer** (G) buttons. Left click queues one (no limit) and right click cancels one. New units walk to the rally flag; right click the ground with the HQ selected to move the flag.
3. **Command units:**
   - **Select:** left click a unit, or drag a box round several. Shift adds to the selection.
   - **Move:** right click the ground. They move in a square block.
   - **Line up:** hold the right button and drag along the ground. They stand in a line along it (in rows if it's short), facing away from where they came from.
   - **Attack:** right click a zombie to send them after it.
4. **Build turrets.** Select engineers and press **B** (or click Turret).
   - **Laying:** click a tile to lay one, or hold and drag to lay a row (one per tile, no gaps).
   - **Blueprints:** laid turrets start as blue blueprints that don't take up their tile. Each engineer builds one at a time. A blueprint becomes a real foundation, filling its tile, when an engineer starts on it.
   - **Calling off:** laying a turret again on a blueprint calls it off.
5. **Survive.** Every 30 seconds a wave comes in from beyond one edge of the map: 10 zombies, then 20, 30 and so on. They walk to the HQ and beat on it, turning on any unit or turret that comes within 2.5 tiles. Units shoot anything in range they can see.

**Other keys:**

| Key | Does |
| --- | --- |
| WASD / arrows, or the mouse at a screen edge | Move the camera |
| Mouse wheel | Zoom |
| Q / E, or middle-drag | Turn the camera |
| Space | Camera back to the HQ |
| V | Show or hide range rings (on by default, for testing) |
| R | Play again, after the HQ falls |
| Esc | Stop placing a turret; else drop the selection; else quit |

## Files

| File | Lines | What it holds |
| --- | --- | --- |
| `main.py` | ~1,200 | `Game`: the window, game state, input, the per-frame update, all drawing calls, and the 2D overlay (panels, health bars, wave clock, banners). Also the `--screenshot` test run. |
| `units.py` | ~600 | `Unit` (walking, health, dying), `Gunner` (shooting), `Soldier`, `Engineer` (building), `Turret`, `Headquarters` (health, training queue, rally point), and group movement: `keep_apart`, `formation`, `line_formation`, `order_move`, `order_line` |
| `zombies.py` | ~130 | `Zombie` (picks a victim, shambles at it, hits it) and `Waves` (the countdown, and spawning each wave beyond one map edge) |
| `world.py` | ~250 | `World`: the tile grid and what's blocked, HQ placement rules, A\* pathfinding with path smoothing, `line_clear` (line of sight), and `hash01` (repeatable random numbers) |
| `models.py` | ~400 | Builds every mesh from boxes: the HQ, soldier, engineer, zombie (3 looks), rifle, shotgun, hammer, turret (base and turning head), flag, rings, the tracer beam |
| `gfx.py` | ~490 | ModernGL: the shaders (world, **ground**, sky, overlay), `MeshBuilder` (box, cone, ring, disc), `Mesh`, and `Renderer` (draw, see-through ghosts, the ground, the overlay texture) |
| `camera.py` | ~110 | `RTSCamera`: pan, zoom (pitch changes with zoom), turn, glide to a point, fog range, mouse ray, ground point, and world-to-screen |
| `mathx.py` | ~150 | Small vector and 4×4 matrix helpers (column-major, like OpenGL) |

## How it works

### The map

- **Size:** `MAP_SIZE` × `MAP_SIZE` tiles (96 × 96), one world unit each. Tile `(i, j)` covers x in `[i, i+1]` and z in `[j, j+1]`, and the ground is at y = 0. The camera starts on the +Z side looking toward −Z, so "north" is −Z.
- **Blocking:** `World.blocked` is a flat list of booleans. The HQ (5 × 4 tiles) and started turrets block their tiles.
- **Where units can walk:** `World.reachable` is a flood fill from the HQ's door. It's worked out again whenever a tile's blocking changes (`set_blocked`).
- **Paths:** `find_path` walks straight if the way is clear, otherwise runs A\* over tiles and then smooths the result.
- **Off the map** there are no walls. Zombies spawn out there and walk in; `hits_wall` ignores off-map space.

### Drawing (`gfx.py`)

- **The ground** is not a mesh of tiles. It's one huge square drawn with `GROUND_FS`, a fragment shader that works out every pixel from its world position with noise: dead grass, dirt, puddles that reflect the sky, burn marks, a rutted track, and the HQ's concrete apron with seams and cracks. Uniforms tell it where the apron and HQ are (`set_hq_ground`) and outline an area (`set_mark`: the HQ ghost, a selection, a turret tile). Outside the map it fades darker into the fog.
- **Everything else** is built by `MeshBuilder` as flat-coloured boxes and drawn with `WORLD_FS`: an overcast light, a slight desaturation, distance fog, and a per-draw `tint` (red flash when hit, see-through ghosts and blueprints).
- **Ghosts:** `draw_ghost` draws a mesh see-through without its back faces showing (depth-only pass first, then colour).
- **The 2D overlay** (panels, bars, text) is drawn with pygame onto a surface every frame and uploaded as a texture (`upload_overlay`), then drawn over the 3D view.

### People

Soldiers, engineers and zombies all share one skeleton:
- **Body:** stands on y = 0 and faces +Z.
- **Legs:** hang from the hips at (±0.1, 0.42).
- **Arms:** hang from the shoulders at (±0.29, 0.80).

`Game.draw_gunner` and `draw_zombie` swing those parts with matrices; nothing is skinned. Guns are separate meshes. `Game.gun_matrix` holds one low, raises it to the shoulder to fire, or slings it on the back while an engineer hammers. A shot's tracer starts at the gun's muzzle (`RIFLE_MUZZLE`, `SHOTGUN_MUZZLE`), placed through the same matrix.

### One frame (`Game.update`, then `Game.fight`)

1. **Camera:** keys, screen edges and glide.
2. **Ghosts:** while choosing a spot, the HQ ghost (or the turret ghost, or a dragged row of turrets) follows the mouse.
3. **`fight`**, once the HQ exists and the game isn't over:
   1. **HQ:** it trains; a finished unit walks to the rally point.
   2. **Waves:** `Waves.update` may bring a new wave.
   3. **Zombies:** each zombie `think`s. Its victims are live units and *started* turrets (never blueprints).
   4. **Gunners:** each `fight`s and may shoot; an engineer then `work`s on his turret. Starting a foundation clears anyone off its tile (`clear_tile`).
   5. **Turrets:** each `fight`s. A wrecked one frees its tile.
   6. **Moving:** everyone `update`s (walks along their path), then `keep_apart` nudges overlapping people apart (never into walls).
   7. **Clean-up:** the dead are removed once their fall has played out. If the HQ is at 0 health, the game is over.
4. **Hover, markers, tracers and the message timer** are updated.

### Shooting rules (`Gunner.fight`, `Turret.fight`)

- **Range and sight:** a shooter fires at the nearest zombie within range that it can see. `line_clear` steps along the line checking blocked tiles, so nobody shoots through the HQ or a turret. A turret skips its own tile.
- **Looking round:** each shooter looks around every `LOOK_EVERY` (0.2) seconds, staggered, and keeps the list of zombies in sight between looks. Checking line of sight every frame for every shooter against every zombie dropped big fights to about 67 frames a second; this keeps them above 100.
- **Holding still:** units **never walk off after zombies by themselves**. They turn and shoot whatever's in reach, even while walking. Only a right click on a zombie sends them after it, and then they stop once it's in range and in sight.

## Rules and numbers (and where to change them)

| What | Value | Where |
| --- | --- | --- |
| Map | 96 × 96 tiles | `world.MAP_SIZE` |
| HQ | 5 × 4 tiles, 1,500 health, concrete apron 2 tiles round (3 in front) | `world.HQ_WIDTH`, `HQ_DEPTH`, `APRON`; `units.Headquarters.MAX_HP` |
| Soldier | rifle, 10 damage every 0.8 s, range 20, 100 health, trains in 4 s | `units.Soldier` |
| Engineer | shotgun, 5 damage every 1.0 s (5 pellets, for show), range 10, 90 health, trains in 6 s | `units.Engineer` |
| Turret | 15 damage every 0.55 s, range 30, 400 health, 8 s to build with one engineer | `units.Turret` |
| Zombie | 100 health, speed 1.5, 10 damage a blow every 1.0 s, notices units within 2.5 | `zombies.Zombie` |
| Waves | every 30 s; 10 in the first, 10 more each wave | `zombies.WAVE_TIME`, `WAVE_SIZE`, `MORE_PER_WAVE` |
| Camera zoom | 8 to 72 | `camera.RTSCamera.MIN_DIST`, `MAX_DIST` |
| Range rings on at start | yes (testing aid) | `Game.show_ranges` in `main.py` |
| Hotkeys | T soldier, G engineer, B turret | `main.TRAIN_KEYS`, `Game.on_key` |

**Balance, as tested:**
- **Left at the rally point:** 6 to 8 soldiers there lose the HQ by wave 3 to 6, because zombies reach the back walls unseen.
- **Spread out:** turrets on all four sides with the soldiers spread round, held 7 waves of the old, health-growing waves.
- **With growing waves:** a defence of 4 turrets, 10 soldiers and 2 engineers lasts about 3 to 4 minutes (waves 6 to 7, 60 to 70 zombies at once).

## Testing

There are no unit-test files. The game is tested by playing it headless and by looking at pictures.

- **The scripted run:** `python Skyline/main.py --screenshot out.png` builds an HQ, trains units, lays a turret, waits for a wave, and saves `out_hq.png`, `out_build.png` and `out.png`. It prints a one-line summary.
- **Your own checks:** write a script that makes `main.Game(screenshot="x")` (so the mouse isn't read), then calls its methods: `aim_at` + `build_hq`, `base.train(Soldier)`, `select_units`, `command_move`, `start_placing_turret` + `aim_turret` + `place_turret`, `start_turret_row` / `extend_turret_row` / `finish_turret_row`. Step `update(1 / 60, edge_scroll=False)` in a loop and assert on the state. Without the `screenshot` argument, real input works too: post pygame mouse and key events and call `handle_events`. Mock `pygame.mouse.get_pos` if you need hover and drag previews, because the hidden test window gets no real mouse movement.
- **Speed:** time a few hundred `update` + `draw` + `display.flip` calls with many units. Your monitor's refresh rate (vsync) caps the result.
- **Look at the pictures** after any change to models or the ground. Parts must make physical sense: nothing floating, overlapping or poking through.

## Decisions so far (and why)

- **No assets, all code.** Meshes are boxes built in `models.py`, and the ground is a shader, so the game is a handful of `.py` files.
- **The ground is one shader, not tiles.** Tile-coloured ground looked blotchy. The shader is sharp at every zoom and costs little.
- **The map was once a floating island** with trees and rocks. Those were removed on request ("just ground"), and the style changed from medieval to a zombie apocalypse.
- **The commander** (a unit in black tactical gear) was removed from the game while the map was improved. Its model and code are in git history, in the first Skyline commit (`8be9aa5`).
- **Units hold still.** An earlier "guard your post and chase" behaviour was removed on request: units only move when ordered.
- **Turrets are blueprints first,** so laying out a long row doesn't wall in your own units before anyone builds it.
- **The HQ is placed by the player,** anywhere it fits. Corner start spots for other teams were planned but aren't in the code yet.

## Not built yet

These were part of the original plan or came up along the way:

- **Ally and enemy AI players,** each with a commander (the first plan was an RTS against AI on a square map).
- **The commander unit** coming back.
- **Resources and costs** (training and building are free).
- **Sound and music.**
- **Fog of war, a minimap, saving.**
- **Turning the HQ** before placing it (its door always faces +Z).
- **Packaging as an app** (Fixer's `build_app.py` shows how it was done there).
