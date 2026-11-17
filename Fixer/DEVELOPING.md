# Fixer 3D: developer guide

How the code is put together, how to test it, and how to add to it. For what the game *is*, every product and its special job, read [README.md](README.md). For releasing it on itch.io, read [itch/README.md](itch/README.md).

## Contents

- [The files](#the-files)
- [Run, test and build](#run-test-and-build)
- [How fixer3d.py is laid out](#how-fixer3dpy-is-laid-out)
- [Key ideas](#key-ideas)
- [Adding a product](#adding-a-product)
- [Rules this project keeps](#rules-this-project-keeps)
- [Gotchas](#gotchas)

## The files

| File | What it is |
| --- | --- |
| `fixer3d.py` | The whole game (~8,300 lines): constants, every product's spec and model, the desk, sounds playback, saving, and `Workshop`, the game itself |
| `fixer3d_sounds.py` | Makes every sound effect and the music as `.wav` files, from code (seeded, so the same every time) |
| `build_app.py` | Builds the game into a Windows app with PyInstaller, and zips it for itch.io |
| `requirements.txt` | `ursina` (it brings Panda3D and Pillow) |
| `README.md` | The player's guide: the basics, then all 24 products and their special jobs |
| `itch/` | The itch.io page: publishing steps and the page text (`README.md`), `cover.png`, `screenshots/` |
| `build/`, `dist/` | Made by `build_app.py`. Ignored by git |

The game used to borrow keyboard layouts from an older 2D pygame game, `fixer.py`. That game has been removed and its layouts now live in `fixer3d.py`, so Fixer 3D needs nothing outside this folder.

## Run, test and build

```
pip install -r Fixer/requirements.txt          # Python 3.12+ (Ursina 8 needs it)
python Fixer/fixer3d.py                        # full screen
python Fixer/fixer3d.py --windowed             # in a 1280 x 720 window; also --fps N, --vsync
python Fixer/fixer3d.py --shot SOME_FOLDER     # the full test, offscreen (see below)
python Fixer/build_app.py                      # the Windows app and the itch.io zip (pip install pyinstaller first)
```

**The full test** is `--shot`. It renders offscreen with no window:
- **What it does:** it takes pictures of the menu and of every stage of one keyboard, then plays **every product** through. For each one it takes it apart in order (checking nothing comes off before what's on top of it), does its special job, builds it back (checking nothing goes on before what it sits on), and tests it.
- **The results:** it prints one line per product, then `every job ok`. A failure is an `AssertionError` naming the product. The pictures are in the folder you gave.
- **When to run it:** after any change, and look at the pictures. It takes a few minutes.

**The packaged app** is also worth testing: `python build_app.py --console`, then run `dist/Fixer3D/Fixer3D.exe --shot SOME_FOLDER`.

## How fixer3d.py is laid out

It reads top to bottom in sections, each starting with a `# ---- name ----` comment:

| Section | What's in it |
| --- | --- |
| Top | Paths (`CACHE` in the temp folder, `SAVE_FILE` in `%APPDATA%\Fixer3D`), and `FROZEN` for the packaged app |
| The first three keyboards, every key layout | `KEYBOARD_MODELS`, `keyboard_layout(size)` (rows of `(label, width)`), `KEY_LEGENDS`, `shade` |
| Constants | The keyboard's layer heights (`FOAM_Y`, `PCB_Y`, `PLATE_Y`...), colours, `PAINTS`, `SWITCH_KINDS`, `TOOLS`, `TRINKETS`, key names |
| Product specs | `MORE_KEYBOARDS`, `MICE`, `MICS`, `WEBCAMS`, `HEADSETS`, `COMPUTERS`: one `dict` per product |
| Special jobs | `SPECIALS` (`key: (job title, star name, how to do it)`), the loop that gives each product its special, and `TIPS` |
| `MODELS`, `ALL_MODELS`, `KINDS` | The menu's order and its tabs |
| Meshes | `Shapes` (boxes, cylinders, lathes, surfaces, each corner with a colour), `Mesh3` (an editable Panda3D mesh), and `COZY`, the shader |
| Pictures | Pillow draws the icons, wood, cutting mat, labels, key legends (`legend_atlas`) and the webcam preview |
| The keyboard | `Part3D`, `KeySet`/`KeyItem` (every keycap in one mesh, every switch in another), `Dirt` (specks), `Trinket`, `Board`, and `build_keyboard` |
| Mice, mics, webcams, headsets, computers | `build_mouse`, `build_*_mic`, `build_*_cam`, `build_headset`, `build_pc`, and `build_mic`, which dispatches the non-keyboards by `spec["form"]` |
| `build_product` | Picks the builder by `kind_of(spec)` and gives the product a random mess level |
| The desk | The mug, plant, notes, pencil, trays, screw dish and wash bowl |
| Sound | `Sounds`: plays the `.wav` files, with volumes saved |
| Saving | `load_save`, `write_save` |
| `Workshop(Entity)` | The game: the menu, the bench, tools, taking apart and putting on, the test, special jobs, the result card, the camera, input |
| End | `main` (arguments), `take_shots` and `every_job` (the full test), and `main_logging_crashes` (writes `crash.log` in the packaged app) |

## Key ideas

- **Parts and their order.** A product is a `Board` holding `Part3D`s. Each part has `below`, the parts it sits on.
  - **Taking apart:** a part comes off only when nothing sits on it.
  - **Building:** it goes back only when everything below it is on.
  - **Phases:** the order comes from these dependencies, not from a list. The game moves from "Take apart" to "Build" to "Test".
- **One mesh for many keys.** All of a keyboard's keycaps share one mesh, and so do all its switches. Taking a keycap off rewrites only its corners. That keeps 104-key boards with hundreds of parts fast.
- **Special jobs.**
  - **Where they're set:** a product's `spec["special"]` names its job in `SPECIALS`. The model builder sets up what the job needs in `board.special`: the sticky key, the knots, the dust on a capsule.
  - **The code:** `Workshop` has a method per job (`untie`, `swab`, `blow`, `solder`, `fresh_battery`...), plus `special_ok` and `special_status` for the job card.
  - **The star:** each job earns its own star on the result card.
- **Tools.** The rail on the left. `TOOLS` are always there, and `SWAB`, `BLOWER` and `SOLDER` only for the jobs that need them. Parts say which tool takes them off (screws need the screwdriver, a `twist` part comes off by hand).
- **Tests.** Keyboards are tested by pressing every key (your real keyboard works). Mice use your real mouse. Mics, webcams and headsets are tested by holding Space to "talk" (there's no real microphone) and clicking things. PCs are tested by pressing their power button.
- **Look.** `COZY` gives soft light and shadows. Colours are per corner, so nothing needs textures except the labels and legends that Pillow draws.
- **Sounds.** From Python, `fixer3d_sounds.py` runs in a second process the first time and writes into `CACHE/sounds<VERSION>`; bump `VERSION` there to remake them. The packaged app brings them, made at build time.

## Adding a product

1. **The spec.** Add a `dict` to the right list (`MORE_KEYBOARDS`, `MICE`...) with a unique `key`, `name`, `kind`, its colours and an `intro`. Non-keyboards also need a `form`.
2. **The model.** Build it in a `build_...` function, or teach an existing one a new `form`. Make each `Part3D` with its `below` dependencies, and its screws, click boxes and dirt.
3. **The special job.** Add it to `SPECIALS` and to the loop that hands out specials, add a `TIPS` line, add a `Workshop` method for it, and add it to `special_ok`, `special_status` and the help card.
4. **The full test.** Teach `every_job` (at the end of the file) how to do the new job, then run `--shot` until it prints `every job ok`.
5. **The look.** Look at the pictures from every side, including underneath and inside (see the first rule below).
6. **The player's guide.** Update `README.md`: the overview table, and a section for the product.

## Rules this project keeps

- **Every part must make physical sense.** No overlapping parts, no screws without holes, no feet, screws and legs on the same spot, no batteries longer than their bays, no cables leaving from the edge of a socket. Check the underside and the inside at every stage of taking it apart, not just the top. This came from real bug reports on the numpad.
- **Comments and messages in plain words.** The code explains itself in plain English sentences, and the game's messages read like a friendly repairer talking.
- **Keep `every job ok` passing.** If a change breaks the full test, it isn't done.

## Gotchas

- **Fonts.** The game uses Candara from the Windows fonts folder if it's there, copying it into the cache because Ursina looks for fonts in one folder. Otherwise it uses Ursina's own OpenSans. Don't ship Candara: it's a Microsoft font.
- **The packaged app's sounds.** In the app, `sys.executable` is the game itself, so the sound fallback runs `Fixer3D.exe --make-sounds DIR`, not a `.py` file.
- **Trimming Panda3D.** `build_app.py` leaves out the parts of Panda3D the game never loads, saving 49 MB, but **not** `cg.dll` and `cgGL.dll`: Panda3D's core and its OpenGL renderer link to them.
