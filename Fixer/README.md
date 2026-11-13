# Fixer 3D

A cozy repair bench in 3D: take a keyboard, a mouse, a mic, a webcam, a headset or a computer apart down to its last screw, clean it, build it back your way, and test it. There are 24 products, and each one has a special job of its own.

- [Part 1: The Basics](#part-1-the-basics)
- [Part 2: Each Product and Its Special Gameplay](#part-2-each-product-and-its-special-gameplay)

---

# Part 1: The Basics

## What the game is

You sit at a wooden desk with a green cutting mat. A product lies on the mat, and you take it apart part by part, the way a real repairer would: keycap by keycap, switch by switch, screw by screw. On the way you brush out the crumbs and dust, and you find what someone lost inside. Then you build it back, in your own colours if you like, and test it with your real keyboard, mouse or voice, and your own ears.

Each product also has a **special job**: a sum to type, a sticky key to clean, a cable to untangle, and so on. It teaches one real repair skill, and earns its own star.

## How it was made

| Part of the game | How it's made |
| --- | --- |
| Language | Python |
| 3D engine | [Ursina](https://www.ursinaengine.org/), which runs on Panda3D |
| 3D models | None loaded from files: every part is built in code from boxes, cylinders and turned (lathe) shapes, each corner with its own colour |
| Look | A custom "cozy" shader with soft lighting and shadows |
| Pictures | The desk's wood, the cutting mat, the stickers under each product and the icons are drawn in code with Pillow when the game starts |
| Sounds and music | Made in code by `fixer3d_sounds.py`: no sound files. They're written to a temp folder the first time the game runs |
| Keyboard layouts | Borrowed from the 2D game, `fixer.py` |
| Saved progress | `%APPDATA%\Fixer3D\save.json`: what you've fixed, your special stars, the trinkets you've found, your volume settings |

All the keycaps of a keyboard are one mesh, and so are all its switches: a keycap comes off by moving just its own corners. That keeps a 104-key keyboard with hundreds of parts running fast.

| File | What it is |
| --- | --- |
| `fixer3d.py` | Fixer 3D, the game this guide is about (about 6,150 lines) |
| `fixer3d_sounds.py` | Makes every sound and the music |
| `fixer.py` | The original 2D game, made with pygame: fans, radios, keyboards and mice, as levels that each teach one real fault |

## How to run it

| Version | Command |
| --- | --- |
| Fixer 3D | `python Fixer/fixer3d.py` |
| Fixer 3D in a window | `python Fixer/fixer3d.py --windowed` |
| Other options | `--fps N` sets the frame cap (120 by default, 0 for none); `--vsync` matches the monitor instead |
| Fixer (2D) | `python Fixer/fixer.py` |

Fixer 3D needs Python 3.12 or newer (Ursina 8 needs it), Ursina and pygame (it borrows the keyboard layouts from the 2D game): `pip install -r Fixer/requirements.txt`. Ursina brings Pillow with it. The 2D game needs only pygame.

Both are desktop games: they open their own window, so they run on Windows, macOS or Linux, not in a web browser.

## The screens

**The menu.** The title FIXER 3D, six tabs (Keyboards, Mice, Mics, Webcams, Headsets, Computers) and a button for each product. Point at a button and that product turns slowly on the mat; click it to start.

**The bench.** While you work, the product sits in the middle with cards around it:

| Where | What it shows |
| --- | --- |
| Top left: the job card | The product's name; the three steps (Take apart > Build > Test) with the one you're on lit up; a progress bar; how messy it came in (from Nearly clean to Filthy) and how many crumbs are left; the special job, with a star that lights up when it's done |
| Left: the tool rail | Your tools, each with its number key |
| Right: the parts box | Every part you've taken off, and how many |
| Right: Colour | The paint for the next part you put back (keyboards) |
| Right: Switches | The kind of switch you'll fit next (keyboards) |
| In front of the product | The keycap tray, the switch tin and the screw dish: what you take off lands there, laid out as it came off. Some jobs add the wash bowl |
| Bottom | A message line: what just happened, and hints for what to do next |
| Top right | Three round buttons: music, sound and quit. Point at music or sound for a volume slider |

**The test card.** Once it's built, the right side shows what to test, how many you've done, the special job's progress, and a **Finish** button.

**The result card.** "Good as new!", your stars, and what you did: crumbs brushed out, keycaps washed, stabilisers lubed, keys tested, the special job, anything you found. It ends with a real repair tip.

**The help card (H).** How to play this kind of product, with its tools and keys.

## The basic gameplay

Every job has three steps.

1. **Take it apart.** One click, one part. A part only comes off once nothing sits on top of it, so the order is the real one. Screws hide underneath, often under the rubber feet: flip it over (F), peel the feet off with the hand, and undo the screws with the screwdriver. Brush up the crumbs, dust and hair as you uncover them.
2. **Build it back.** Click a part in the parts box to hold it, then click where it goes. Each part goes back only once what it sits on is in place, and the game shows where. On a keyboard, keycaps and switches go back from the tray and the tin. Pick a colour and a switch kind first if you want a change.
3. **Test it.** Use it for real: type on your own keyboard, click and scroll your own mouse, or tap the mic and talk (hold Space). Then press **Finish**.

**No two jobs are the same mess.** Every time you start one, it comes in somewhere between Nearly clean and Filthy (the job card says which), and each part keeps its own share: one may be dusty and the next spotless. The crumbs, dust and hair land in new places, a keyboard has more or fewer grimy keycaps, and there isn't always a trinket inside. The mess of its special job changes too: how many knots, which battery contact the leak got to, where the thumbprint is, how badly the cushions flake, which dust filters have clogged.

**Rules a real repairer follows, and so does the game:**

- A wireless product's battery comes out (or its lead is unplugged) before you open the rest.
- The capsule of a studio mic is never brushed: only the air blower may touch it.
- Grimy keycaps can be washed in the bowl while they're off.
- Long keys rattle unless their stabilisers are lubed before they go back.

## The tools

| Tool | Key | What it does | Who has it |
| --- | --- | --- | --- |
| Hand | 1 | Lifts parts off and puts them back, peels feet, unscrews grilles, sleeves, collars and thumb screws, undoes knots | Everything |
| Screwdriver | 2 | Undoes a screw with one click (it turns out and drops in the dish); clicking it in the dish puts it back | Everything |
| Keycap puller | 3 | Pulls one keycap straight up | Keyboards |
| Switch puller | 4 | Pulls one switch out of the plate | Keyboards |
| Brush | 5 (3 on everything else) | Hold it down and drag it over crumbs, dust and hair | Everything |
| Lube | 6 | A dab on a stabiliser's wire: no more rattle | Keyboards |
| Alcohol swab | after the others | Dissolves dried drink and battery crust, wipes a lens clean, and wipes old thermal paste off a CPU | Tenkeyless, wireless mic, clip-on webcam, desktop PC |
| Air blower | 4 | A puff of air: lifts dust without touching | Studio mic |
| Soldering iron | 4 | Solders a loose wire back onto its pad | Gaming headset |

## Colours and switches (keyboards)

You can rebuild any keyboard in its original colours or in any of 12 paints: Cream, Latte, Cocoa, Sage, Matcha, Sky, Ocean, Lavender, Peach, Rose, Butter and Charcoal. The paint goes on each keycap and case part as you put it back, so you can mix them.

| Switch | Kind | Feel |
| --- | --- | --- |
| Red | Linear | Smooth and quiet |
| Brown | Tactile | A soft bump on the way down |
| Blue | Clicky | A crisp click with every press |
| Pink | Silent | Dampened: hardly a sound |

In the test, each key sounds like the switch you fitted.

## Stars

| Star | How to earn it |
| --- | --- |
| Built | Put it back together (always earned) |
| Spotless | Brush out every crumb, speck and hair, and wash every grimy keycap |
| Smooth | Lube every stabiliser (keyboards only) |
| All tested | Test every key, every button, or every check on the test card |
| The special job's star | Do its special job; the star is named after it (Sum, Paired, Gain...) |

Most keyboards hide one lost trinket (not every time: sometimes there's nothing in there), on the plate among the crumbs or on the circuit board: a lucky coin, a paperclip, a guitar pick, a tiny die, a star sticker or a toy brick. Click it to keep it; the game counts how many of the 6 you've found.

## Controls

| Input | What it does |
| --- | --- |
| Click | Use the tool in your hand on one part |
| Hold and drag | Brush (with the brush in hand) |
| Right-drag, or left-drag on an empty spot | Turn the product round |
| Scroll | Zoom in and out; in the test, scrolling on a knob turns it |
| Right-click | Put back what you're holding |
| Number keys | Pick a tool |
| F | Flip it over |
| R | Set it level again |
| H | Help card |
| M | Music on or off |
| F3 | Show the frame rate |
| F11 | Full screen or a window |
| Esc | Close help, let go of a part, or leave the job |

---

# Part 2: Each Product and Its Special Gameplay

Every product below has the same five things: what it is, its parts, how to take it apart, how to build it back, and its special job. Building is always the take-apart order, backwards; the parts lists below are in build order, from the bottom up.

| Product | Parts in all | Special job | Done in |
| --- | --- | --- | --- |
| [Number pad](#number-pad) | 54 | Do a sum | The test |
| [Compact 60%](#compact-60-keyboard) | 147 | Try the Fn layer | The test |
| [Wireless 65%](#wireless-65-keyboard) | 163 | Pair it | The test |
| [75% with a knob](#75-keyboard) | 189 | Turn the music with it | The test |
| [Tenkeyless](#tenkeyless-keyboard) | 201 | Unstick the sticky key | Taking it apart |
| [Gasket 96%](#gasket-96-keyboard) | 242 | Fit new switches | Building it |
| [Full-size](#full-size-keyboard) | 238 | Type the quick brown fox | The test |
| [Vintage](#vintage-keyboard) | 238 | Shake out the loose crumbs | Before you start |
| [Office mouse](#office-mouse) | 11 | Fix the double-click | Taking it apart |
| [Gaming mouse](#gaming-mouse) | 17 | Try every DPI speed | The test |
| [Travel mouse](#travel-mouse) | 15 | Fit a fresh battery | Taking it apart |
| [Lavalier mic](#lavalier-mic) | 6 | Untangle the cable | Before you start |
| [Stage mic](#stage-mic) | 8 | Wash the foam | Building it |
| [Wireless mic](#wireless-mic) | 6 | Clean the contacts | Taking it apart |
| [USB podcast mic](#usb-podcast-mic) | 12 | Set the gain | The test |
| [Studio condenser](#studio-condenser) | 10 | Puff the capsule clean | Taking it apart |
| [Clip-on webcam](#clip-on-webcam) | 9 | Wipe the lens clean | Any time |
| [Ball webcam](#ball-webcam) | 14 | Focus it | The test |
| [Streaming webcam](#streaming-webcam) | 10 | Stop the flicker | Taking it apart |
| [Office headset](#office-headset) | 19 | Fit fresh ear cushions | Taking it apart |
| [Gaming headset](#gaming-headset) | 21 | Fix the dead left side | Taking it apart |
| [Wireless headphones](#wireless-headphones) | 19 | Swap the swollen battery | Taking it apart |
| [PC case](#pc-case) | 29 | Wash the dust filters | Building it |
| [Desktop PC](#desktop-pc) | 35 | Fresh thermal paste | Taking it apart |

## Keyboards

### How every keyboard is built

All eight are built the same way, from the bottom up, so they come apart the same way:

| Layer | Part | What it is |
| --- | --- | --- |
| 1 | Bottom case | The tray everything sits in: floor, walls, screw posts, two ribs on the floor, a sticker underneath |
| 2 | Flip-out legs | Two legs at the back, folded flat (not on the number pad) |
| 3 | USB board | A small board at the back with the USB-C socket |
| 4 | USB-C cable | Plugs into the USB board through the back wall |
| 5 | Case foam | Damping foam on the floor, cut round the posts |
| 6 | Circuit board | A socket, a diode and a light for every key; the controller chip sits under the space bar |
| 7 | Internal cable | Four coloured wires from the USB board up to the circuit board |
| 8 | Plate foam | Pink foam between the board and the plate |
| 9 | Steel plate | Holds the switches in square cut-outs |
| 10 | Stabilisers | One under each long key (space bar, Shift, Enter, Backspace...) to keep it level |
| 11 | Switches | One for every key |
| 12 | Keycaps | One for every key |
| 13 | Top frame | Holds it all together, with the lock lights |
| 14 | Screws | Up from underneath, into the posts |
| 15 | Rubber feet | At the four corners, each hiding a screw |

**Taking a keyboard apart:**

1. Pull every keycap with the keycap puller (3).
2. Pull every switch with the switch puller (4).
3. Lube each stabiliser (6) if you want the Smooth star, then lift it out with the hand (1).
4. Flip it over (F). Peel the 4 rubber feet off with the hand, then undo every screw with the screwdriver (2).
5. Flip it back. Lift off the top frame, the steel plate, the plate foam, the internal cable, the circuit board, the case foam, the cable and the USB board, brushing the crumbs off each layer as it shows.

**Building it back:** the same, backwards. Choose a colour and a switch kind on the right before the parts go back.

**Testing:** press every key, on your own keyboard or by clicking it. Each key lights up when it works.

### Number pad

A little number pad, for sums and spreadsheets: the quickest job in the game.

| | |
| --- | --- |
| Keys | 17 |
| Switches | Pink (silent) |
| Parts | 54: 17 keycaps, 17 switches and 20 other parts |
| Stabilisers | 3: under +, numpad Enter and 0 |
| Screws | 4, every one under a foot |
| Legs | None: it sits flat on its feet |
| Lock lights | 1 (Num Lock) |
| Colours | Mint case, cream and sage keycaps, a coral accent |

**Parts, in build order:** bottom case > USB board > USB-C cable > case foam > circuit board > internal cable > plate foam > steel plate > 3 stabilisers > 17 switches > 17 keycaps > top frame > 4 screws > 4 rubber feet.

**What's different:** its USB socket is in the middle of the back. With no space bar, its controller chip is on the underside of the circuit board, so you won't see it on top.

**Special job: Do a sum.** In the test, the job card shows a sum of two numbers, each from 3 to 9 (for example 7 + 5). Type the answer on the pad's number keys, then press Ent.

- A wrong answer: "7 + 5 isn't 13: try again!", and it clears.
- Back, Num or any of / * - + . also clears what you've typed.
- Right: "7 + 5 = 12. The sums add up!" and the Sum star lights.

**Tip at the end:** a number pad's Enter is a key of its own, and Num Lock decides whether its keys type numbers or move the cursor.

### Compact 60% keyboard

Tiny: no number pad, no arrows and no F keys. Fn reaches them.

| | |
| --- | --- |
| Keys | 61 |
| Switches | Blue (clicky) |
| Parts | 147: 61 keycaps, 61 switches and 25 other parts |
| Stabilisers | 5: Backspace, Enter, both Shifts, space bar |
| Screws | 6: 4 under the feet, 2 showing (one along the front, one along the back) |
| Lock lights | 1 (Caps Lock) |
| Colours | Navy case, cream and blue keycaps, a yellow Esc and Enter, a yellow cable |

**Parts, in build order:** bottom case > flip-out legs > USB board > USB-C cable > case foam > circuit board > internal cable > plate foam > steel plate > 5 stabilisers > 61 switches > 61 keycaps > top frame > 6 screws > 4 rubber feet.

**Special job: Try the Fn layer.** In the test, click Fn. The legends on I, J, K and L change to arrows (Up, Left, Down, Right). Press all four: the card counts "2 of 4 arrows". Pressing them without Fn just types the letters, and the game reminds you to click Fn first. After the fourth, the layer switches off and the Fn layer star lights.

**Tip at the end:** small keyboards keep their missing keys on layers: holding Fn changes what the keys do, the way Shift turns letters into capitals.

### Wireless 65% keyboard

A wireless keyboard, with a battery inside and its little USB receiver kept in a slot underneath.

| | |
| --- | --- |
| Keys | 68 (a 60% plus a column of keys down the right and arrows tucked in) |
| Switches | Brown (tactile) |
| Parts | 163: 68 keycaps, 68 switches and 27 other parts |
| Stabilisers | 4: Backspace, Enter, left Shift, space bar |
| Screws | 6: 4 under the feet, 2 showing |
| Lights | 1 lock light and a pairing light |
| Extra parts | A flat battery on the floor, its battery lead, a USB receiver underneath, a power switch on the back |
| Colours | Sage green case, cream and green keycaps, an orange accent |

**Parts, in build order:** bottom case > flip-out legs > USB board > USB-C cable > battery > case foam > circuit board > battery lead > internal cable > plate foam > steel plate > 4 stabilisers > 68 switches > 68 keycaps > top frame > 6 screws > 4 rubber feet > USB receiver.

**What's different:** the battery lead runs up the back and plugs into the top of the circuit board. Unplug it (lift it out with the hand) before you lift the circuit board out. The receiver slides out of its slot underneath when it's flipped over.

**Special job: Pair it.** In the test, hold Esc down for 2 seconds. The pairing light beside the lock light blinks blue, and the card counts "Pairing... 1.4 s". At 2 seconds it stops blinking and glows blue: "paired over Bluetooth!" Let go early and it starts again from zero.

**Tip at the end:** wireless keyboards pair by holding a key combination until the light blinks. After that, they remember the computer.

### 75% keyboard

A 65% with a tight row of F keys on top, and a volume knob in the top-right corner.

| | |
| --- | --- |
| Keys | 82 |
| Switches | Red (linear) |
| Parts | 189: 82 keycaps, 82 switches and 25 other parts |
| Stabilisers | 4: Backspace, Enter, left Shift, space bar |
| Screws | 6: 4 under the feet, 2 showing |
| Lock lights | 1 |
| Extra parts | A volume knob: an aluminium cap with a grip, on an encoder soldered to the board |
| Colours | Lavender case, cream and purple keycaps, an amber accent |

**Parts, in build order:** bottom case > flip-out legs > USB board > USB-C cable > case foam > circuit board > internal cable > plate foam > steel plate > 4 stabilisers > 82 switches > 82 keycaps > top frame > volume knob > 6 screws > 4 rubber feet.

**What's different:** the knob pulls straight off its shaft by hand (1). Take it off before the top frame; on the circuit board you'll see the encoder it sat on.

**Special job: Turn the music with it.** In the test, the knob really turns the game's music, in notches from 0 to 10. Scroll on the knob to turn it, or click it for one notch up. Turn it all the way down to 0 ("the music's gone quiet"), then all the way up to 10. When you finish, your music goes back to the volume it had before.

**Tip at the end:** a volume knob like this is a rotary encoder: it sends one pulse for every notch it turns, one way or the other.

### Tenkeyless keyboard

A full keyboard without the number pad, so the mouse sits closer. Someone spilled a drink in it.

| | |
| --- | --- |
| Keys | 87 |
| Switches | Brown (tactile) |
| Parts | 201: 87 keycaps, 87 switches and 27 other parts |
| Stabilisers | 5: Backspace, Enter, both Shifts, space bar |
| Screws | 8: 4 under the feet, 2 along the front, 2 along the back |
| Lock lights | 3 (Num, Caps, Scroll) |
| Extra tool | The alcohol swab |
| Colours | Off-white case, white and grey keycaps, an orange accent |

**Parts, in build order:** bottom case > flip-out legs > USB board > USB-C cable > case foam > circuit board > internal cable > plate foam > steel plate > 5 stabilisers > 87 switches > 87 keycaps > top frame > 8 screws > 4 rubber feet.

**Special job: Unstick the sticky key.** One letter, picked at random each time, has a brown ring of dried drink round its switch. The job card names it.

1. If you test it before cleaning, that key sticks down and repeats: "eeeeeeee!"
2. Pull its keycap with the puller (3). The brown spill shows on the plate round the switch.
3. Swab the switch with the alcohol swab, 3 times: "Swab it again: work the alcohol in."
4. On the third swab the spill disappears: "that switch moves freely again."

The swab only works on that one switch, and only with its keycap off.

**Tip at the end:** isopropyl alcohol (90% or more) dissolves dried drink and dries fast: swab it in, press the switch again and again, and let it dry.

### Gasket 96% keyboard

A hobbyist's board: a 75% with a number pad squeezed in beside it. Its plate floats on rubber gaskets, and a brass weight sits inside.

| | |
| --- | --- |
| Keys | 104 |
| Switches | Red (linear), hot-swap |
| Parts | 242: 104 keycaps, 104 switches and 34 other parts |
| Stabilisers | 7: Backspace, Enter, left Shift, space bar, +, numpad Enter, 0 |
| Screws | 8: 4 under the feet, 2 along the front, 2 along the back |
| Lock lights | 3 |
| Extra parts | A brass weight on the floor; 4 coral silicone gaskets (front, back, left, right) round the plate |
| Colours | Slate case, cream and blue-grey keycaps, a coral accent and cable |

**Parts, in build order:** bottom case > flip-out legs > USB board > USB-C cable > brass weight > case foam > circuit board > internal cable > plate foam > steel plate > 7 stabilisers > 104 switches > 104 keycaps > 4 gaskets > top frame > 8 screws > 4 rubber feet.

**What's different:** the gaskets come off after the top frame and before the plate. The brass weight lifts out of the floor once the case foam is off.

**Special job: Fit new switches.** It's hot-swap, so every switch pulls straight out. Build it back with new switches: every one the same kind, and not the red ones it came with. Pick Brown, Blue or Pink on the Switches card before you put them back. The card counts "60 of 104 in" and warns "but mixed kinds" if you mix them.

**Tip at the end:** on a hot-swap board, switches push into sockets. Pull each one straight out, and push the new one straight in with its pins straight.

### Full-size keyboard

The classic office layout, with a number pad on the right.

| | |
| --- | --- |
| Keys | 104 |
| Switches | Red (linear) |
| Parts | 238: 104 keycaps, 104 switches and 30 other parts |
| Stabilisers | 8: Backspace, Enter, both Shifts, space bar, +, numpad Enter, 0 |
| Screws | 8: 4 under the feet, 2 along the front, 2 along the back |
| Lock lights | 3 |
| Colours | Black case, dark grey keycaps, a red Esc and Enter |

**Parts, in build order:** bottom case > flip-out legs > USB board > USB-C cable > case foam > circuit board > internal cable > plate foam > steel plate > 8 stabilisers > 104 switches > 104 keycaps > top frame > 8 screws > 4 rubber feet.

**Special job: Type the quick brown fox.** In the test, type the line on the card: "the quick brown fox jumps over the lazy dog". The card shows what's still left to type, and only the right next letter (or Space) counts. When you've typed it all: "no dead keys hiding anywhere."

**Tip at the end:** that sentence has every letter in it, so typing it shows up a dead or sticky key at once.

### Vintage keyboard

An old office keyboard, yellowed and dusty, with twice the crumbs of any other.

| | |
| --- | --- |
| Keys | 104 (full-size layout) |
| Switches | Blue (clicky) |
| Parts | 238: 104 keycaps, 104 switches and 30 other parts |
| Stabilisers | 8 |
| Screws | 8: 4 under the feet, 2 along the front, 2 along the back |
| Lock lights | 3 |
| Grime | Every keycap is yellowed and greasy |
| Colours | Beige case, cream and putty keycaps, a rust-red accent |

**Parts, in build order:** the same as the full-size: bottom case > flip-out legs > USB board > USB-C cable > case foam > circuit board > internal cable > plate foam > steel plate > 8 stabilisers > 104 switches > 104 keycaps > top frame > 8 screws > 4 rubber feet.

**Special job: Shake out the loose crumbs.** Do it first, before you take anything apart:

1. Flip it over (F).
2. Drag it about to shake it, upside down.
3. Crumbs rattle out of it onto the mat, one at a time. The card counts "Shaken out: 5 of 12".

**Also:** wash its keycaps. Pull them, then click the wash bowl: the grimy ones in the tray go in for a soak and come out clean. Every grimy keycap has to be washed for the Spotless star.

**Tip at the end:** turn a keyboard over and shake it before you take it apart: most of the loose crumbs fall straight out.

## Mice

### How every mouse is built

| Part | What it is |
| --- | --- |
| Bottom shell | The base, with the sensor's window and a sticker or a switch underneath |
| Sensor lens | A clear lens set in the floor, under the sensor |
| Circuit board | Two main click switches, the wheel's encoder, the optical sensor and its red light, a chip |
| Board screw | One small screw holding the board down |
| Scroll wheel | A rubber-tyred wheel on its axle, poking up between the buttons |
| USB cable | Plugs into the board at the front (wired mice) |
| Top shell | The dome with the left and right buttons |
| Screws | Up from underneath, through bosses in the bottom shell, into the top shell |
| Feet | Slippery skates, each hiding a screw |

**Taking a mouse apart:**

1. Flip it over (F). Peel the feet off with the hand (1), and undo the screws under them with the screwdriver (2).
2. Flip it back and lift the top shell off with the hand.
3. Lift out the cable and the scroll wheel, undo the board screw, and lift out the circuit board, brushing the hair from round the wheel and the dust off the board.
4. Lift out the sensor lens, and brush the crumbs out of the bottom shell.

**Testing:** use your own mouse. Left click, right click, scroll the wheel, click the wheel, and move it about: this mouse does what yours does, and its sensor's light shines on the mat as it goes.

### Office mouse

A plain wired office mouse. Its left button double-clicks.

| | |
| --- | --- |
| Parts | 11 |
| Feet and screws | 2 long strip feet, front and back, each over 1 screw |
| Colours | Light grey shell, dark base, a blue accent |

**Parts, in build order:** bottom shell > sensor lens > circuit board > board screw > scroll wheel > USB cable > top shell > 2 screws > 2 feet.

**Special job: Fix the double-click.**

1. In the test (or if you test it first), one left click clicks twice: "Click-click!"
2. Take it apart until the top shell is off.
3. Click the left switch, at the front left of the circuit board, with the hand (1). That bends its spring back: "the left switch clicks once, crisp and clean."

**Tip at the end:** a mouse that double-clicks has a worn switch: the little spring inside has gone soft. Bending it back helps for a while; a new switch fixes it for good.

### Gaming mouse

A gaming mouse: side buttons, a light-up logo, and a weight inside.

| | |
| --- | --- |
| Parts | 17 |
| Feet and screws | 4 round feet, each over 1 screw |
| Extra parts | A steel weight in the floor, a side-button board standing inside the left side, a light-up logo, a DPI button and light behind the wheel |
| Extra test | The side buttons (your mouse's back and forward buttons) |
| Colours | Black shell, a green logo |

**Parts, in build order:** bottom shell > sensor lens > steel weight > circuit board > board screw > side button board > scroll wheel > USB cable > top shell > 4 screws > 4 feet.

**Special job: Try every DPI speed.** In the test, click the DPI button in the slot behind the wheel. Each click goes to the next speed, and its light changes colour. Try all four:

| Speed | Light | The pointer |
| --- | --- | --- |
| 400 DPI | Red | Slowest |
| 800 DPI | Yellow | Faster |
| 1600 DPI | Green | Faster again |
| 3200 DPI | Blue | Fastest |

**Tip at the end:** DPI is how far the pointer moves for each inch you move the mouse: the higher it is, the faster.

### Travel mouse

A small wireless travel mouse, with a battery under a cover underneath. Its battery is flat.

| | |
| --- | --- |
| Parts | 15 |
| Feet and screws | 3: a strip foot at the back and 2 round feet at the front, each over 1 screw |
| Extra parts | An AA battery and a USB receiver, under a battery cover; an on/off switch underneath; no cable |
| Colours | Coral red shell, dark base, a cream accent |

**Parts, in build order:** bottom shell > sensor lens > circuit board > board screw > scroll wheel > top shell > 3 screws > 3 feet > AA battery > USB receiver > battery cover.

**What's different:** the battery has to come out before you open it. Flip it over, push the battery cover off, and lift out the battery and the receiver tucked in beside it. Then the feet and screws, and on as usual. Its sensor sits further forward, just behind the wheel, because the battery fills the middle.

**Special job: Fit a fresh battery.** Once the old battery is out (faded and scuffed), click **Fresh battery** in the parts box. A new green-and-gold AA takes its place: "The old one goes to recycling." Put it back in when you build it.

**Tip at the end:** a flat battery makes a wireless mouse stutter and skip. Take old batteries out before they leak.

## Mics

### How every mic works

The five mics are each made the way that kind really is, so each comes apart in its own way. The hand (1) does most of the work: grilles, sleeves, collars, ring nuts and headbaskets twist off, and thumb screws turn by hand too.

**Testing:** tap it (click the grille, or the capsule on the lavalier) and talk into it: hold Space, and a meter shows how loud it hears you. It's green when you're just right, yellow when loud, and red when it clips.

### Lavalier mic

A tiny clip-on mic, for interviews and videos. Its long, thin cable has tied itself in knots.

| | |
| --- | --- |
| Parts | 6 |
| Screws | None |
| Colours | Black, an orange accent |

**Parts, in build order:** cable > capsule > foam windscreen > tie clip > TA4 connector > locking collar.

**Taking it apart:** twist the knurled locking collar off the connector, then pull the TA4 connector off the cable. Lift the tie clip and the foam windscreen off the capsule, then the capsule off the cable.

**Special job: Untangle the cable.** The cable has 2 to 4 knots in it (a different number, in different places, every time), little loops pulled tight. Click each one with the hand (1) to work it loose. The card counts "1 of 3 knots undone"; after the last, "The cable lies smooth."

**Extra test:** you tap the capsule itself, as it has no grille.

**Tip at the end:** coil a mic cable over-under, one loop forwards and the next one back, and it won't twist into knots next time.

### Stage mic

A tough dynamic mic, for singing on stage.

| | |
| --- | --- |
| Parts | 8 |
| Screws | 1 grub screw, under the tail, holding the XLR insert |
| Colours | Charcoal handle, a red band, a silver ball grille |

**Parts, in build order:** handle > shock mount > capsule > foam windscreen > ball grille > XLR insert > grub screw > XLR cable.

**Taking it apart:** pull the XLR cable off the tail. Flip it to find the grub screw underneath and undo it (2), then slide the XLR insert out of the tail. Unscrew the ball grille by hand (1), then lift out the foam windscreen, the capsule and its rubber shock mount.

**Special job: Wash the foam.** The foam windscreen is brown with lipstick and breath.

1. Unscrew the grille and lift the foam out.
2. Click the foam in the parts box to hold it.
3. Click the wash bowl. Into the warm, soapy water: "Squeaky clean!" It comes out black again, ready to go back in.

**Tip at the end:** a stage mic's foam collects lipstick and breath: wash it in warm, soapy water, and let it dry right through before it goes back in.

### Wireless mic

A wireless handheld mic. Its batteries leaked.

| | |
| --- | --- |
| Parts | 6 |
| Screws | None |
| Extra parts | A little screen, a light and a power switch on the handle; 2 AA batteries under a twist-off sleeve |
| Extra test | Switch it on first (click its power switch) |
| Extra tool | The alcohol swab |
| Colours | Black, a blue accent |

**Parts, in build order:** mic body > capsule > ball grille > 2 AA batteries > battery sleeve.

**Taking it apart:** twist the battery sleeve off the handle by hand, and lift both batteries out. They lie end to end: a spring on the contact at one end, a flat contact at the other. Unscrew the ball grille, then lift out the capsule.

**Special job: Clean the contacts.** A leak has crusted the metal contacts at the ends of the battery bay green-white: one of them, or both (it's different every time).

1. Take both batteries out first: the contacts are under them.
2. Swab a crusty contact 3 times with the alcohol swab: "The crust's coming away: once more."
3. Swab the other one too, if it's crusty. "Both contacts shine like new." (A clean one needs nothing: "That contact's clean: the leak never reached it.")

Until they're clean, the mic's light flickers in the test.

**Tip at the end:** that green-white crust is from a battery that leaked. Alcohol on a swab dissolves it; then fresh batteries, and take them out when it's put away.

### USB podcast mic

A USB mic for podcasts, standing in a yoke on its own desk stand.

| | |
| --- | --- |
| Parts | 12 |
| Screws | 2 thumb screws (through the yoke, into the mic) and 1 panel screw on the back |
| Extra parts | A gain knob and a mute button with a light on the front; a USB board and a headphone socket behind a back panel; rubber feet under the stand |
| Extra test | Mute it, and unmute it |
| Colours | Cream, a coral knob |

**Parts, in build order:** stand base > yoke > mic body > 2 thumb screws > gain knob > capsule > grille > USB board > back panel > panel screw > USB-C cable.

**Taking it apart:** pull the USB-C cable out of the back. Undo the panel screw (2) and take the back panel off: the USB board sits in an opening behind it, with its USB-C socket, headphone jack and chip. Unscrew the grille off the top by hand to reach the gold capsule. Pull the gain knob off the front. Turn the two thumb screws out by hand, and lift the mic out of its yoke.

**Special job: Set the gain.** In the test, the gain starts too low.

1. Hold Space to talk: the card says "too quiet: turn it up".
2. Scroll on the gain knob (or click it) to turn it up, a notch at a time.
3. Too far and it says "too loud: it clips!"
4. When your voice sits in the green for a moment: "your voice sits right in the green."

**Tip at the end:** set the gain so your voice sits in the green: too low and it's lost in hiss, too high and it clips and crackles.

### Studio condenser

A large-diaphragm studio condenser in its shock mount. Its gold capsule is delicate.

| | |
| --- | --- |
| Parts | 10 |
| Screws | 2 capsule screws, and 1 thumb screw that clamps the mic in its mount |
| Extra parts | A desk stand with a pole and rubber feet; a spider shock mount (two hoops on elastic bands); a ring nut at the bottom |
| Extra tool | The air blower |
| Colours | Steel blue body, a gold badge, a silver headbasket |

**Parts, in build order:** desk stand > shock mount > mic body > capsule > 2 capsule screws > thumb screw > headbasket > ring nut > XLR cable.

**Taking it apart:** pull the XLR cable off the bottom and twist the ring nut off. Twist the headbasket off the top by hand: the gold capsule is under it. Undo the 2 capsule screws (2), and lift the capsule out. Turn the thumb screw out by hand, and lift the mic out of its shock mount.

**Special job: Puff the capsule clean.** The capsule's gold diaphragm is dusty.

1. Twist the headbasket off.
2. Click the dust on the capsule with the air blower (4): each puff lifts the specks near it. The card counts the specks left.
3. The brush won't do: never a brush on a capsule. "Not a speck left on the diaphragm, and nothing touched it but air."

**Tip at the end:** never touch a condenser's diaphragm: it's thinner than a hair. A puff of air from a blower is all the cleaning it wants.

## Webcams

### How every webcam works

Each webcam has a circuit board inside with the image sensor under a lens mount, a microphone or two, and a little light; the lens screws into the mount by hand. In the test, its card shows **what it sees**: you, smiling at your desk. The picture blurs if the lens is smudged or out of focus, dims in poor light, and goes black when the privacy shutter is closed. Hold Space to talk (its mics move the level meter), and take a photo.

### Clip-on webcam

A webcam that clips onto the top of a monitor. Somebody's left a greasy thumbprint (or two) on its lens window, somewhere different every time.

| | |
| --- | --- |
| Parts | 9 |
| Screws | 2, holding the circuit board in the back shell |
| Extra parts | A pill-shaped body in two halves; a privacy shutter that slides on rails; a hinged monitor clip with rubber pads |
| Extra tool | The alcohol swab |
| Colours | Charcoal back, a glossy black front, a silver ring round the lens window |

**Parts, in build order:** back shell > USB cable > circuit board > 2 screws > lens > front cover > privacy shutter > monitor clip.

**Taking it apart:** lift the monitor clip off its hinge pin and slide the privacy shutter off its rails. Lift the front cover off, and the lens is in the middle of the board: unscrew it by hand. Undo the 2 board screws (2), lift the board off the cable's plug, then pull the cable out through the back.

**Test:** shut the shutter and open it again (click it), hold Space to talk, and press P to take a photo.

**Special job: Wipe the lens clean.** A greasy thumbprint smudges the lens window, and the picture's hazy.

1. Pick the alcohol swab (4).
2. Click the lens window, the glass in the middle of the front: three wipes and it's clear. You can do it any time.
3. "Crystal clear: not a smear left on the lens window."

**Tip at the end:** clean a lens with a little alcohol on a soft swab or a lens wipe: never a tissue or your shirt, which leave scratches and lint.

### Ball webcam

A round old webcam on a weighted stand. Its focus ring turns by hand, and it's out of focus.

| | |
| --- | --- |
| Parts | 14 |
| Screws | 3 holding the base plate on, underneath; 1 holding the round circuit board; 2 holding the ball's halves together, at the back |
| Extra parts | A stand with a neck, a steel weight inside its base, a base plate with a rubber ring; a snapshot button on top of the ball; a focus ring that threads through the front |
| Extra tool | None |
| Colours | Cream ball and stand, a sky-blue button and trim |

**Parts, in build order:** stand > steel weight > base plate > 3 screws > back half > USB cable > circuit board > screw > front half > 2 screws > focus ring.

**Taking it apart:** twist the focus ring out of the front by hand. Turn it round to undo the 2 screws at the back of the ball (2), and lift the front half off. Undo the board's screw, lift the board out, and pull the cable out through the back. Lift the back half off the neck. Then flip it over (F): undo the 3 screws under the base, and lift the base plate and the steel weight out.

**Test:** click its snapshot button to take a photo, and hold Space to talk.

**Special job: Focus it.** Its picture is a blur.

1. In the test, scroll on the focus ring: each notch moves the lens a little nearer the sensor, or further off.
2. Watch the picture on the card: it sharpens as you get close, and blurs again if you go past.
3. "Pin sharp! Every eyelash in focus."

**Tip at the end:** a manual focus ring moves the lens nearer the sensor or further away: further for things up close, nearer for things far off.

### Streaming webcam

A streamer's webcam with a ring light round its lens, on a little tripod. Its light flickers.

| | |
| --- | --- |
| Parts | 10 |
| Screws | 1 tripod thumb screw (turns by hand), and 2 holding the main board in the housing |
| Extra parts | A three-legged tripod; an LED ring on standoffs; a ribbon cable from the ring to the board; a front panel with a frosted diffuser, which twists off |
| Extra tool | None |
| Colours | Charcoal, with an orange light button |

**Parts, in build order:** tripod > housing > tripod screw > main board > 2 screws > lens > LED ring > ribbon cable > front panel.

**Taking it apart:** twist the front panel off. The ribbon cable is at the right, between the LED ring and the housing's wall: lift it out, then the LED ring. Unscrew the lens, undo the 2 board screws (2) and lift the main board out. Turn it over (F) to turn the tripod screw out by hand, and lift the housing off the tripod.

**Test:** click the button on top to switch the ring light on, scroll on it to set the brightness, hold Space to talk, and press P to take a photo. The light makes the picture brighter.

**Special job: Stop the flicker.** The ring light flickers, and the picture flickers with it: the ribbon cable has worked loose.

1. Twist the front panel off.
2. See the ribbon's end sticking up out of its socket, at the right? Click it with the hand (1) to press it home.
3. "Click! The ribbon's pressed home in its socket: the light won't flicker now."

**Tip at the end:** ribbon cables sit in their sockets under a little latch: a knock can lift one end, and the light (or the screen) flickers. Seat it straight, and close the latch.

## Headsets

### How every headset is built

Each headset lies flat on the mat with its ear cushions up, the way you'd put one down. A headband (with a pad, and steel sliders at its ends) holds a yoke at each end, and each yoke holds an ear cup on two pivot pins. In each cup, the driver (the speaker) sits on its baffle, screwed down, and the ear cushion twists on over the screws. Left is marked with a blue dot, right with a red one, as on real ones.

**Taking one apart:** twist an ear cushion off by hand to find the screws under it. Undo them (2) and lift the driver out of its cup. Then the cup comes out of its yoke, and the yoke off the headband. Last, the pad off the headband.

**Test:** click an ear cup to hear a chime in that ear only (left, then right); hold Space to talk into its mic; scroll on it to set the volume.

### Office headset

A USB headset for calls. Its ear cushions are old and flaking.

| | |
| --- | --- |
| Parts | 19 |
| Screws | 3 under each ear cushion |
| Extra parts | A boom mic on a pivot, with a foam windscreen; a cable into the left cup, with a volume remote on it |
| Extra tool | None |
| Colours | Charcoal, with black cushions |

**Parts, in build order:** headband > headband pad > left yoke > left cup > USB cable > left driver > 3 screws > left ear cushion > right yoke > right cup > right driver > 3 screws > right ear cushion > boom mic > foam windscreen.

**Taking it apart:** pull the foam off the boom mic, and lift the boom off. Then each side, as above. The cable goes into the left cup: the left driver plugs into it, so it comes out once the driver's out.

**Special job: Fit fresh ear cushions.** Both cushions are flaking: bits of old leatherette peel off them.

1. Twist both ear cushions off.
2. Click **Fresh cushions** in the parts box.
3. "Two fresh, soft cushions! The flaky old ones go in the bin."

**Tip at the end:** ear cushions are made to be swapped: most twist or clip off, and fresh ones make an old headset comfy (and clean) again.

### Gaming headset

A gaming headset with lights round its cups. The left side has gone silent.

| | |
| --- | --- |
| Parts | 21 |
| Screws | 4 under each ear cushion |
| Extra parts | A light band round each cup (it glows round the colours in the test); a detachable boom mic, plugged into the left cup; a control board in the left cup; a braided cable |
| Extra tool | The soldering iron |
| Colours | Black, with grey cushions |

**Parts, in build order:** headband > headband pad > left yoke > left cup > control board > USB cable > left driver > 4 screws > left ear cushion > right yoke > right cup > right driver > 4 screws > right ear cushion > boom mic.

**Taking it apart:** pull the boom mic out of its socket. Then each side, as above. In the left cup, the cable and the boom's socket both connect to the control board, which comes out last.

**Test:** as every headset; and click the boom mic twice to mute it and back.

**Special job: Fix the dead left side.** The left ear is silent: a wire has come off the control board.

1. Twist the left cushion off, undo its 4 screws, and lift the left driver out.
2. See the red wire, off its pad on the control board? Pick the soldering iron (4) and click it.
3. "A shiny joint: the wire's back on its pad. The left side will play again." Until then, the left ear stays silent in the test.

**Tip at the end:** a wire that breaks off a board is the commonest headset fault. Heat the pad and the wire together, and let the solder flow: a shiny joint is a good one.

### Wireless headphones

Bluetooth headphones with a battery in the right cup, and the battery's swollen up.

| | |
| --- | --- |
| Parts | 19 |
| Screws | 3 under each ear cushion |
| Extra parts | A main board, a battery and its lead in the right cup; a power button, volume buttons, a light and a USB-C socket round the right cup's edge; mic holes on the left cup |
| Extra tool | None |
| Colours | Oat, with brown cushions |

**Parts, in build order:** headband > headband pad > left yoke > left cup > left driver > 3 screws > left ear cushion > right yoke > right cup > main board > battery > battery lead > right driver > 3 screws > right ear cushion.

**Taking it apart:** each side, as above. In the right cup, unplug the battery lead before anything else, then lift the battery out gently. The main board is under it.

**Test:** click its power button first (on the right cup's edge, at the front): its light comes on. Then as every headset.

**Special job: Swap the swollen battery.** Its battery has puffed up like a pillow.

1. Twist the right cushion off, undo its screws, and lift the right driver out.
2. Unplug the battery lead (1), then lift the battery out. Never press on a swollen battery.
3. Click **New battery** in the parts box. "A new battery, flat as it should be. The swollen one goes to battery recycling."

**Tip at the end:** a lithium battery that swells is worn out and unsafe: never press, bend or puncture it, and take it to a battery recycling point, not the bin.

## Computers

### How every computer is built

Both lie on their right side on the bench with the glass side up, the way you'd work on one: the tower's bottom is to the left, its top to the right, its front towards you and its back away. The steel chassis has a motherboard tray (brass standoffs, rubber grommets for the cables, and a cut-out behind the CPU), a shroud over the power supply, stamped grilles over its vents, feet on its bottom, and the front I/O across the top of its front: a power button, a reset button, two USB ports, a USB-C and a headphone jack. A thumb screw in each corner holds the glass side panel. The glass is see-through, and in the test you click through it.

Some screws are round the back: flip it over (F) to reach them.

### PC case

An empty case, with its fans and filters still in it. Some of its dust filters are clogged.

| | |
| --- | --- |
| Parts | 29 |
| Screws | 4 thumb screws on the glass; 2 thumb screws holding the right side panel, at the back; 4 in each fan |
| Extra parts | Two 120 mm front fans and a rear fan (their cables hang free, with the plugs on the tray, ready for a motherboard); three dust filters (behind the front panel, on top where magnets hold it, and under the power supply, where it slides out to the front); a mesh front panel that clips on; the shroud's cover; the right side panel |
| Extra tool | None (the wash bowl is on the desk) |
| Colours | Slate-blue steel, black trim |

**Parts, in build order:** chassis > right side panel > 2 thumb screws > front fan > 4 screws > front fan > 4 screws > rear fan > 4 screws > front dust filter > top dust filter > bottom dust filter > front panel > shroud cover > glass side panel > 4 thumb screws.

**Taking it apart:** turn the glass's four thumb screws out by hand and lift the glass off, then the shroud's cover. Pull the front panel off (it clips on) and lift out the front filter behind it. The top filter pulls off by hand (turn it round: it's on the right), and the bottom one slides out to the front (on the left). Undo the front fans' screws (2) from the front, and lift the fans out. Flip it over (F) for the rear fan's screws and the right side panel's thumb screws, at the back. Then the right side panel lifts off.

**Test:** press the power button and the reset button (they click, but there's nothing inside to switch on yet), plug a USB stick into a front port (click it), and give each fan a spin (click it, through the glass).

**Special job: Wash the dust filters.** One, two or all three of its dust filters are clogged grey with fluff. Which ones is different every time.

1. Take it apart, filters and all.
2. Click a clogged filter in the parts box to hold it, then click the wash bowl. "Clean as new! 1 more clogged filter to wash."
3. Wash each clogged one. "Every dust filter's clean: the air can flow freely through it again."

**Tip at the end:** dust filters keep the fluff out of a PC. Wash them every few months in warm, soapy water, and let them dry right through before they go back on.

### Desktop PC

A whole desktop PC: just the tower, with no screen and no keyboard. It's been running hot.

| | |
| --- | --- |
| Parts | 35 |
| Screws | 4 thumb screws on the glass; 4 holding the power supply, at the back; 6 holding the motherboard; 2 spring screws holding the CPU cooler; 1 holding the SSD; 2 holding the graphics card's bracket, at the back |
| Extra parts | A power supply in the shroud; a motherboard (CPU socket, memory slots, a PCIe slot, an M.2 slot, its ports through the I/O shield); a CPU; a tower cooler (a copper base, with heat pipes up through its fins) and its fan, clipped on; two memory sticks; an M.2 SSD; a graphics card with two fans; the 24-pin, CPU and graphics card power cables; the front panel's cables. Its fans, filters, front panel and right side panel stay on |
| Extra tool | The alcohol swab |
| Colours | Black, with orange memory and a power button to match |

**Parts, in build order:** chassis > power supply > 4 screws > motherboard > 6 screws > CPU > CPU cooler > 2 spring screws > cooler fan > 2 memory sticks > M.2 SSD > screw > graphics card > 2 screws > 24-pin power cable > CPU power cable > graphics card power cable > front panel cables > shroud cover > glass side panel > 4 thumb screws.

**Taking it apart:** take the glass off, then the shroud's cover. Unplug the cables: the 24-pin by the motherboard's front edge, the graphics card's on its top edge, the front panel's by the bottom of the board, and the CPU's (it runs behind the tray to the top corner, so unplug it at the power supply, in the shroud). Unclip the cooler's fan, undo the cooler's two spring screws, and lift the cooler off the CPU. The memory sticks pull out of their slots; undo the SSD's screw and it slides out of its slot. Flip it over (F) to undo the graphics card's bracket screws and the power supply's four, at the back. Then the card lifts out of its slot, the CPU out of its socket, the motherboard off its standoffs, and the power supply up out of the shroud.

**Test:** press its power button, at the top of its front: it hums to life, its fans spin up, its light glows, and it gives one short beep. Plug a USB stick in (click a front port), and press reset to restart it.

**Special job: Fresh thermal paste.** Its CPU runs hot: the thermal paste between the CPU and its cooler has dried out and gone crumbly.

1. Take the cooler off: unclip its fan, then undo its two spring screws.
2. Pick the alcohol swab (4) and click the CPU: three wipes, and the old paste is gone.
3. Click **Thermal paste** in the parts box. "A pea-sized dot of fresh paste, right in the middle: the cooler will spread it thin."

Until then, it overheats in the test: its CPU climbs to 99 degrees and it shuts itself down.

**Tip at the end:** thermal paste fills the tiny gaps between a CPU and its cooler. When it dries out, wipe the old paste off with alcohol and put on a pea-sized dot: the cooler spreads it thin.
