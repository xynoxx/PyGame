# Publishing Fixer 3D on itch.io

Everything the itch.io page needs is in this folder: the cover, the screenshots, and the text to paste in.
The game itself is made by `build_app.py`.

## 1. Build the game

On Windows, in the `Fixer` folder:

```
pip install -r requirements.txt pyinstaller
python build_app.py
```

It takes a minute or two and makes:

- `dist/Fixer3D/`: the game. Open `Fixer3D.exe` in it to try it the way players will.
- `dist/Fixer3D-1.0.0-windows.zip` (about 50 MB): the file to upload.

Before each release, run the full test on the built game. It plays every product through, from taking it
apart to its special job, and ends with `every job ok`:

```
python build_app.py --console
dist\Fixer3D\Fixer3D.exe --shot %TEMP%\fixer-shots
python build_app.py
```

(The `--console` build shows what the test prints. Build again without it before you upload.)

For a new version, change `VERSION` at the top of `build_app.py`.

## 2. Make the page

On itch.io: your profile menu > **Upload new project**. Fill it in like this:

| Field | What to put |
| --- | --- |
| Title | Fixer 3D |
| Project URL | `fixer-3d` (or anything you like) |
| Short description or tagline | A cozy repair bench: take it apart, fix it, build it back. |
| Classification | Games |
| Kind of project | Downloadable |
| Release status | Released (or In development, if you plan to add more) |
| Pricing | Your choice: "No payments" for free, or "Donations" / "Paid" with a suggested price |
| Uploads | `Fixer3D-1.0.0-windows.zip`, then tick **Windows** under it |
| Description | The text in section 3 below |
| Genre | Simulation |
| Tags | cozy, relaxing, simulation, 3D, singleplayer, low-poly, casual, repair |
| AI generation disclosure | Answer this honestly: the game's code was written with an AI assistant (Claude) |
| Cover image | `cover.png` (630 × 500) |
| Screenshots | Everything in `screenshots/`, in order |
| Visibility | **Draft** at first (see step 4) |

## 3. The description

Paste this into the Description box:

---

**Take it apart. Fix it. Build it back.** 🔧☕

Pour yourself a cup of tea and pull up a chair at the repair bench. Something broken is waiting for you:
take it apart one screw at a time, brush away the dust, fix what's wrong, then put it back together in
your favourite colours and see it work again.

There's no timer and no way to fail. Just soft music, rain on the window, and the happy little click of
every part.

**Controls**
> 🖱️ Drag to turn it round
> 🔍 Scroll to zoom in and out
> 👆 Click to use your tool
> 🔄 F to flip it over
> ❓ H if you need a hand

Hi there! 👋 This is my very first game, and I'm so happy you're here. If you play it, I'd love to hear
what you think: leave a comment with anything you liked, anything that felt tricky, or ideas for what
to fix next. I read every one, and I'll keep making it better. Thank you for playing! 💛

---

## 4. Check it, then publish

1. Save the page as a **Draft**.
2. Open the page's link (it works for you while it's a draft) and download the zip, just as a player would.
3. Unzip it somewhere new, open `Fixer3D.exe`, and play one product all the way through.
4. If that works, set **Visibility** to **Public** and save. The page is live.

## 5. Updating it later

With the website: upload the new zip, tick Windows, and delete the old file.

With **butler**, itch.io's upload tool (it only sends what changed, so updates are quick):

1. Download butler from <https://itch.io/docs/butler/> and run `butler login` once.
2. After each build:

```
butler push dist/Fixer3D YOUR-ITCH-NAME/fixer-3d:windows --userversion 1.0.0
```

The game folder has an `.itch.toml` in it, so players who use the itch.io app get two buttons:
**Launch** (full screen) and **Play in a window**.

## If a player has trouble

- **"Windows protected your PC"**: they click More info, then Run anyway. Only signing the game with a
  code-signing certificate stops it (they cost money every year), so most itch.io games live with it.
- **Antivirus blocks it**: some antivirus programs distrust any new Python-made app. They can allow it, or you can
  report the false alarm to the antivirus company.
- **The game closes by itself**: ask them for `%APPDATA%\Fixer3D\crash.log`. It says exactly what went wrong.
- **Black screen, or it won't open**: their graphics driver is probably very old: they should update it.
