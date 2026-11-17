"""Builds Fixer 3D into a Windows app that anyone can play without installing Python, zipped for itch.io.

    pip install -r requirements.txt pyinstaller
    python build_app.py            # the app players get: no console window
    python build_app.py --console  # the same with a console, to see what it prints while testing

It makes dist/Fixer3D/ (the game: run Fixer3D.exe in it) and dist/Fixer3D-<version>-windows.zip (what's in that
folder, zipped, to upload to itch.io; or push the folder itself with itch's butler, see itch/README.md). The
sounds are made here, once, and go in with the game, so players hear them from the first click. Build it on
Windows, with the Python the game runs on.
"""
import os
import shutil
import subprocess
import sys
import zipfile

VERSION = "1.0.0"
NAME = "Fixer3D"
HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
DIST = os.path.join(HERE, "dist")

# Parts of Panda3D the game never uses (physics, video, DirectX, other audio and model loaders): leaving them out
# makes the download about half the size. (Not cg.dll or cgGL.dll: Panda3D's core and its OpenGL need them.)
UNUSED = ("avcodec", "avformat", "avutil", "swresample", "swscale", "libp3ffmpeg", "cgD3D9",
          "d3dx9", "libpandadx9", "fmodex", "libp3fmod", "libp3assimp", "libp3vrpn", "vrpn.", "libp3vision",
          "vision.", "libpandabullet", "bullet.", "libpandaode", "ode.", "libp3ptloader", "libp3tinydisplay")

# Tells the itch.io app how to start the game (and offers it in a window too).
ITCH_TOML = """[[actions]]
name = "play"
path = "Fixer3D.exe"

[[actions]]
name = "Play in a window"
path = "Fixer3D.exe"
args = ["--windowed"]
"""

PLAYER_README = f"""FIXER 3D  (version {VERSION})
A cozy repair bench: take keyboards, mice, mics, webcams, headsets and computers apart, clean them, fix
what's wrong, build them back up and test them.

TO PLAY
  Open Fixer3D.exe. Keep it in this folder: it needs the _internal folder beside it.
  If Windows says "Windows protected your PC", click "More info", then "Run anyway".
  (It says that about any new game that isn't signed by a big company.)

CONTROLS
  Mouse: drag to turn it round, scroll to zoom, click to use the tool in your hand.
  Number keys pick a tool (the rail on the left shows which)
  F flip it over  .  R set it level  .  H help  .  M music
  F11 full screen or a window  .  Esc back

YOUR PROGRESS
  Saved by itself in %APPDATA%\\Fixer3D\\save.json
  If the game ever closes by itself, crash.log in that folder says why: please send it in.

NEEDS
  Windows 10 or 11 (64-bit) and a graphics card with OpenGL 3.2 or newer (any made in the last ten years).
"""


def run(*command):
    print(">", " ".join(command))
    subprocess.run(command, check=True, cwd=HERE)


def make_assets():
    """The sounds and the icon, made by the game's own code."""
    sys.path.insert(0, HERE)
    import fixer3d_sounds
    sounds = os.path.join(BUILD, "sounds")
    print("making the sounds...")
    fixer3d_sounds.make_effects(sounds)
    fixer3d_sounds.make_ambience(sounds)
    icon = os.path.join(BUILD, "fixer3d.ico")
    # draw the icon in a Python of its own: importing the game loads the engine, which this one doesn't need
    run(sys.executable, "-c", "import sys; sys.argv = ['x']; import fixer3d; "
        f"fixer3d.draw_game_icon(256).save(r'{icon}', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])")
    return sounds, icon


def build(console):
    os.makedirs(BUILD, exist_ok=True)
    sounds, icon = make_assets()
    shutil.rmtree(os.path.join(DIST, NAME), ignore_errors=True)
    run(sys.executable, "-m", "PyInstaller", "fixer3d.py", "--name", NAME, "--noconfirm", "--clean",
        "--console" if console else "--windowed", "--icon", icon,
        "--distpath", DIST, "--workpath", os.path.join(BUILD, "work"), "--specpath", BUILD,
        "--add-data", f"{sounds}{os.pathsep}sounds",
        "--collect-all", "ursina", "--collect-all", "panda3d", "--collect-submodules", "direct",
        "--exclude-module", "tkinter", "--exclude-module", "numpy")
    app = os.path.join(DIST, NAME)
    trim(app)
    with open(os.path.join(app, "README.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(PLAYER_README)
    with open(os.path.join(app, ".itch.toml"), "w", encoding="utf-8") as f:
        f.write(ITCH_TOML)
    return app


def trim(app):
    """Take out the parts of Panda3D the game never loads."""
    gone = 0
    for root, _, files in os.walk(app):
        for name in files:
            if any(name.startswith(u) or u in name for u in UNUSED):
                path = os.path.join(root, name)
                gone += os.path.getsize(path)
                os.remove(path)
    print(f"left out {gone / 1e6:.0f} MB of Panda3D the game doesn't use")


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
