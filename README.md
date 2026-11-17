# Pygame

Games made in Python. There are two projects, each in its own folder and independent of the other:

| Folder | What it is | Made with | State |
| --- | --- | --- | --- |
| [`Fixer/`](Fixer/) | **Fixer 3D**: a cozy repair bench. Take 24 gadgets (8 keyboards, 3 mice, 5 mics, 3 webcams, 3 headsets, 2 PCs) apart down to the last screw, clean them, fix their one real fault, build them back and test them | Ursina (on Panda3D), Pillow | Finished and packaged as a Windows app for itch.io |
| [`Skyline/`](Skyline/) | **Skyline**: a 3D real-time strategy game in a zombie apocalypse. Place your HQ, train soldiers and engineers, build turrets, survive growing waves | pygame, ModernGL | A playable prototype, still growing |

## Where to start

- **Playing or describing Fixer:** [Fixer/README.md](Fixer/README.md), the player's guide to every product and its special job.
- **Working on Fixer's code:** [Fixer/DEVELOPING.md](Fixer/DEVELOPING.md).
- **Releasing Fixer:** [Fixer/itch/README.md](Fixer/itch/README.md).
- **Working on Skyline:** [Skyline/README.md](Skyline/README.md). It covers how it plays, every file, how a frame runs, the numbers and where to change them, the decisions so far, and what's not built yet.
- **AI agents:** read [CLAUDE.md](CLAUDE.md) first.

## Quick start

Both games are developed on Windows with Python 3.12.

```
pip install -r Fixer/requirements.txt     # Ursina
python Fixer/fixer3d.py --windowed

pip install pygame moderngl
python Skyline/main.py
```

Each game has a headless test that plays it through and saves pictures:

```
python Fixer/fixer3d.py --shot SOME_FOLDER      # every product, every job; ends with "every job ok"
python Skyline/main.py --screenshot out.png     # a scripted game; saves out_hq.png, out_build.png, out.png
```

## The repository

```
.gitignore         __pycache__, *.pyc, Fixer/build/, Fixer/dist/
README.md          this file
CLAUDE.md          how to work on this repository (for AI agents, and useful for people)
Fixer/             Fixer 3D (see Fixer/DEVELOPING.md)
Skyline/           Skyline (see Skyline/README.md)
```

- **Older games:** this repository once held Snake, Pong, Flappy, Whack-a-Mole and a 2D version of Fixer. They were removed to keep it to the current games, and they're still in the git history.
- **Remote:** `origin` on GitHub (`xynoxx/PyGame`), branch `main`.
