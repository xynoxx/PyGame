"""Builds Skyline into a Windows app that anyone can play without installing Python, zipped for itch.io.

    pip install pygame moderngl pillow pyinstaller
    python build_app.py            # the app players get: no console window
    python build_app.py --console  # the same with a console, to see what it prints while testing

It makes dist/Skyline/ (the game: run Skyline.exe in it) and dist/Skyline-<version>-windows.zip (what's in that
folder, zipped, to upload to itch.io; or push the folder itself with itch's butler, see itch/README.md). The
version is main.VERSION. Build it on Windows, with the Python the game runs on.
"""
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import main  # noqa: E402  (for its version and its icon: importing it opens no window)

NAME = "Skyline"
VERSION = main.VERSION
BUILD = os.path.join(HERE, "build")
DIST = os.path.join(HERE, "dist")

# Tells the itch.io app how to start the game (and offers it in a window too).
ITCH_TOML = """[[actions]]
name = "play"
path = "Skyline.exe"

[[actions]]
name = "Play in a window"
path = "Skyline.exe"
args = ["--window"]
"""

PLAYER_README = f"""SKYLINE  (version {VERSION}, an early prototype)
A real-time strategy game about holding out in a zombie apocalypse. Your HQ stands in the middle of a dead,
overrun land: train soldiers and engineers, build turrets, factories and tanks, strip junkyards and warehouses
for metal and supply, dig trenches, and hold the HQ against wave after wave of the dead.

TO PLAY
  Open Skyline.exe. Keep it in this folder: it needs the _internal folder beside it.
  It opens full screen. To play in a window, start it with --window (or use "Play in a window" in the
  itch.io app). To quit, press Esc twice with nothing selected, or Alt+F4.
  If Windows says "Windows protected your PC", click "More info", then "Run anyway".
  (It says that about any new game that isn't signed by a big company.)

CONTROLS
  Left click          select the HQ, a building, a turret, a deposit or a unit (Shift: add)
  Left drag           select the units in a box; double click a unit: all of its kind on screen
  Right click         units: move, attack a zombie, guard or repair something of yours, get into a trench
  Right drag          line units up along the drag
  Shift               with any order: do it after the orders already given
  HQ                  T soldier, G engineer (Shift: 5, Ctrl: 20; right click a button takes them off)
  Vehicle factory     T tank
  Engineers           B semi-auto turret, M full-auto turret, N bullet factory, J salvage crane
                      (beside a junkyard), K loading dock post (beside a warehouse), R radar station,
                      V vehicle factory, X take something down
  Soldiers            C trench (click, or drag a line)
  Units               P patrol, H stop, L fire state
  Groups              Ctrl + 0-9 to make one, 0-9 to select it (twice: look at it)
  O                   switch the selected building on or off
  I                   the next idle engineer
  Camera              WASD or arrows (or the mouse at a screen edge), wheel to zoom, Q / E to turn, Space: the HQ
  Pause, F            pause; double speed
  R                   play again, once the HQ has fallen
  The + button        (beside the materials, top left) a load of each material, to try things out
  Hover any button or portrait for its numbers.

IF IT GOES WRONG
  If the game ever closes by itself, %APPDATA%\\Skyline\\crash.log says why: please send it in.

NEEDS
  Windows 10 or 11 (64-bit) and a graphics card with OpenGL 3.3 or newer (any made in the last ten years).
"""


def run(*command):
    print(">", " ".join(command))
    subprocess.run(command, check=True, cwd=HERE)


def make_icon():
    """The game's icon (main.game_icon, drawn in code), as a Windows .ico of every size it's shown at."""
    import pygame
    from PIL import Image
    os.makedirs(BUILD, exist_ok=True)
    png = os.path.join(BUILD, "skyline.png")
    pygame.image.save(main.game_icon(256), png)
    icon = os.path.join(BUILD, "skyline.ico")
    Image.open(png).save(icon, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    return icon


def build(console):
    icon = make_icon()
    shutil.rmtree(os.path.join(DIST, NAME), ignore_errors=True)
    run(sys.executable, "-m", "PyInstaller", "main.py", "--name", NAME, "--noconfirm", "--clean",
        "--console" if console else "--windowed", "--icon", icon,
        "--distpath", DIST, "--workpath", os.path.join(BUILD, "work"), "--specpath", BUILD,
        "--collect-all", "moderngl", "--collect-all", "glcontext",   # (ModernGL finds its OpenGL context by name)
        "--exclude-module", "tkinter", "--exclude-module", "numpy", "--exclude-module", "PIL")
    app = os.path.join(DIST, NAME)
    with open(os.path.join(app, "README.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(PLAYER_README)
    with open(os.path.join(app, ".itch.toml"), "w", encoding="utf-8") as f:
        f.write(ITCH_TOML)
    return app


def zip_up(app):
    path = os.path.join(DIST, f"{NAME}-{VERSION}-windows.zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, _, files in os.walk(app):
            for name in files:
                full = os.path.join(root, name)
                z.write(full, os.path.relpath(full, app))  # at the top of the zip, as itch.io likes it
    return path


if __name__ == "__main__":
    app = build("--console" in sys.argv)
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(app) for f in fs)
    zipped = zip_up(app)
    print(f"\nthe game: {app} ({size / 1e6:.0f} MB)")
    print(f"for itch.io: {zipped} ({os.path.getsize(zipped) / 1e6:.0f} MB)")
