# Publishing Skyline on itch.io

Everything the itch.io page needs is in this folder: the cover, the screenshots, and the text to paste in.
The game itself is made by `build_app.py`. (`cover.png` and `screenshots/` were taken in the game itself, at
1920 × 1080, and the cover's title drawn over one of them.)

## 1. Build the game

On Windows, in the `Skyline` folder:

```
pip install pygame moderngl pillow pyinstaller
python build_app.py
```

It takes about a minute and makes:

- `dist/Skyline/`: the game. Open `Skyline.exe` in it to try it the way players will (it opens full screen;
  press Esc twice with nothing selected, or Alt+F4, to quit).
- `dist/Skyline-0.1-windows.zip` (about 16 MB): the file to upload.

Before each release, run the scripted test on the built game. It plays a little and saves three pictures:

```
python build_app.py --console
dist\Skyline\Skyline.exe --screenshot %TEMP%\skyline.png
python build_app.py
```

(The `--console` build shows what it prints. Build again without it before you upload.)

For a new version, change `VERSION` near the top of `main.py` (the window's title and the zip's name follow it).

## 2. Make the page

On itch.io: your profile menu > **Upload new project**. Fill it in like this:

| Field | What to put |
| --- | --- |
| Title | Skyline |
| Project URL | `skyline` (or anything you like) |
| Short description or tagline | Hold the HQ against the dead: a real-time strategy prototype. |
| Classification | Games |
| Kind of project | Downloadable |
| Release status | **Prototype** (it's version 0.1) |
| Pricing | Your choice: "No payments" for free, or "Donations" |
| Uploads | `Skyline-0.1-windows.zip`, then tick **Windows** under it |
| Description | The text in section 3 below |
| Genre | Strategy |
| Tags | rts, real-time-strategy, zombies, tower-defense, base-building, low-poly, 3D, singleplayer, survival |
| AI generation disclosure | Answer this honestly: the game's code was written with an AI assistant (Claude) |
| Cover image | `cover.png` (630 × 500) |
| Screenshots | Everything in `screenshots/`, in order |
| Visibility | **Draft** at first (see step 4) |

## 3. The description

Paste this into the Description box:

---

**Hold the HQ. The dead are coming.** 🧟🏢

Your HQ stands in the middle of a dead, overrun land, and every 30 seconds another wave of the dead
shambles in from the edge of the map, bigger than the last. Train soldiers and engineers, build turrets and
bullet factories, strip junkyards for metal and warehouses for supply, dig trenches, roll out tanks, and
hold the line for as long as you can.

- **Build a base:** semi-auto and minigun turrets, bullet factories, salvage cranes and loading docks, a
  vehicle factory, and a radar station that opens up the land all round.
- **Command your troops:** move, line up, patrol, guard, attack, queue orders with Shift, control groups.
- **Feed your army:** every soldier, engineer and tank needs supply; run short and they go hungry.
- **Tanks** with a main gun that fires explosive shells and two machine guns on the turret.
- **Spitters**, trenches, levels and ranks, and the dead piling up where they fall.

**Controls**
> 🖱️ Left click / drag to select, right click to order
> ⌨️ WASD or the screen edges to move the camera, mouse wheel to zoom, Q / E to turn
> 🔧 Hover any button for its numbers
> ⏸️ Pause key to pause, F for double speed

The full list of keys is in the README.txt that comes with the game.

**This is version 0.1, an early prototype.** There's no saving yet, and with hundreds of the dead on the map
an older computer may slow down. It needs Windows 10 or 11 and a graphics card with OpenGL 3.3 (any made in
the last ten years). It opens full screen; use "Play in a window" in the itch.io app, or start
`Skyline.exe --window`, for a window.

I'd love to hear what you think: what was fun, what was hard, and what you'd like next. Leave a comment!

---

## 4. Check it, then publish

1. Save the page as a **Draft**.
2. Open the page's link (it works for you while it's a draft) and download the zip, just as a player would.
3. Unzip it somewhere new, open `Skyline.exe`, and play a few waves.
4. If that works, set **Visibility** to **Public** and save. The page is live.

## 5. Updating it later

With the website: upload the new zip, tick Windows, and delete the old file.

With **butler**, itch.io's upload tool (it only sends what changed, so updates are quick):

1. Download butler from <https://itch.io/docs/butler/> and run `butler login` once.
2. After each build:

```
butler push dist/Skyline YOUR-ITCH-NAME/skyline:windows --userversion 0.1
```

The game folder has an `.itch.toml` in it, so players who use the itch.io app get two buttons:
**Launch** (full screen) and **Play in a window**.

## If a player has trouble

- **"Windows protected your PC"**: they click More info, then Run anyway. Only signing the game with a
  code-signing certificate stops it (they cost money every year), so most itch.io games live with it.
- **Antivirus blocks it**: some antivirus programs distrust any new Python-made app. They can allow it, or you
  can report the false alarm to the antivirus company.
- **The game closes by itself**: ask them for `%APPDATA%\Skyline\crash.log`. It says exactly what went wrong.
- **Black screen, or it won't open**: their graphics driver is probably very old (it needs OpenGL 3.3): they
  should update it.
- **It's slow late in a game**: hundreds of the dead on the map cost the most; zooming in (fewer of them on the
  screen) helps.
