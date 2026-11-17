# Working on this repository

Two independent Python games live here: `Fixer/` (Fixer 3D, Ursina) and `Skyline/` (an RTS, pygame + ModernGL). Read [README.md](README.md), then the guide for the game you're touching:

- `Fixer/DEVELOPING.md` for Fixer's code (`Fixer/README.md` is the player's guide)
- `Skyline/README.md` for Skyline

## How the owner likes the work done

- **Check the change works.** Run the headless test for the game you changed, and **look at the pictures** it saves:
  - **Fixer:** `python Fixer/fixer3d.py --shot DIR` must end with `every job ok`.
  - **Skyline:** use `python Skyline/main.py --screenshot out.png`, or a script that drives `main.Game` (see Skyline's README, "Testing").

  For gameplay changes, simulate the game and report the numbers (who won, how long it held, the frame rate).
- **Things must make physical sense.** Parts don't overlap, float, or sit where they couldn't. Screws go into holes, cables leave from the middle of their sockets, and units stand beside a turret, not in it. Check from below and inside, not only from the top.
- **Plain words.** Code comments, docstrings and in-game text are plain English sentences, as in the existing files. Name things for what they are.
- **No asset files.** Models are built from boxes in code, pictures are drawn with Pillow or shaders, and sounds are made in code.
- **Keep it clean.** Remove code that nothing uses (`python -m vulture` and `python -m pyflakes` help; ModernGL and Ursina settings show up as false positives), and keep the READMEs true when you change how something works.
- **Don't commit or push unless asked.** When asked, check the repository's own git config first (`git config user.name`, `git remote -v`): the owner has several GitHub accounts and each repository uses its own. Ask if unsure.
- **Original games only.** Don't copy a specific existing game's name, characters, art or levels.

## Environment notes

- **Windows.** Both Git Bash and PowerShell are available. Use forward slashes in Bash.
- **Inline scripts break on apostrophes.** In this environment, `python - <<'EOF'` blocks fail to parse when their text contains apostrophes (`doesn't`, `'s'`). Write the script to a file (in a scratch folder outside the repository) and run that instead.
- **Test output goes outside the repository.** Write pictures, logs and builds to a scratch folder. `Fixer/build/` and `Fixer/dist/` are git-ignored build output.
- **Some tests take a while.** Fixer's `--shot` takes about 4 minutes. Skyline's simulations run much faster than real time (a 4-minute game simulates in a few seconds).
