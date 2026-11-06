# Rosetta Plotter: Machine Orientation, Set Home on the Bar, Hold-to-Move

Date: 2026-11-06. Requested by the professor; described by Adam. Builds on the manager UI spec (`2026-10-07-rosetta-manager-ui-design.md`), which this document amends.

Three changes. A fourth request (the pen-height slider only moving the real pen while the pen is down) was reviewed with Adam and dropped: it stays as it is.

## 1. Machine orientation

### Why
The professor's AxiDraw is mounted on a wall, not lying on a desk. Today the plate always draws the machine as if seen from above on a desk: Home at the screen's top-left, X to the right, Y down. When the real machine hangs some other way, what he sees on screen and what he sees on the wall don't line up, so moving the pen, placing a drawing or reading a position takes mental rotation. The goal is that the screen and the real tool look the same "in his mind's eye."

### What it is
A per-plotter setting that says how the machine sits as the user faces it: which on-screen corner Home is in, and which way the pen's X runs from there. The plate view is drawn in that orientation. It is **only a view**: the artwork's relation to the paper, and therefore what gets plotted, never changes. Changing orientation never moves, rotates or mirrors a drawing on the paper.

There are exactly eight orientations: Home in any of the four corners × X running along either edge from that corner. Y always runs along the other edge. This covers every rotation and every mirror (a mirror happens when the machine is seen from behind or from below, for example through glass). The axes can never be put anywhere arbitrary: Home is always the machine's real Home and the axes are always the machine's real X and Y.

The default (and the meaning of every existing install) is today's view: Home top-left, X to the right.

### Setting it
- A **Set orientation** command in the View menu, and a tool button in the Plotter group of the tools column.
- It works like Rhino's 3-point picks, cut to two clicks on the plate:
  1. The instruction line says "Click the corner where HOME is on your plotter, as you face it." The four corners of the reach outline get pick markers; the user clicks one.
  2. "Click the corner the pen moves toward along X (along the rail)." The two corners next to the first get markers; the user clicks one.
  3. The plate turns to the new orientation and refits.
- Esc cancels at any step and leaves the orientation unchanged.
- A small **Reset orientation** item (View menu) returns to the default.
- Available any time except while a plot runs or is paused, the same rule as Rotate paper 90°.

### Remembered per plotter
Stored in settings keyed the same way pen profiles are (`Machine.profile_key()`: the nickname, or the port on old firmware). When a plotter connects, its saved orientation is applied. With no plotter, or a plotter without a key, the last-used orientation on this laptop is used. A plotter seen for the first time gets the default.

### What follows the orientation
Everything drawn on the plate: grid, reach, paper, margin guides, drawings (and their faint originals), selection handles, the Home marker, the pen crosshair, the trace and preview path, the drawn-lines overlay during a plot, and snapping guides. Specifically:
- **The jog pad and arrow keys follow the screen.** "Up" moves the pen toward the top of the screen, whatever machine direction that is. The pad's tooltips say "Move pen up/down/left/right (on screen)" instead of "back/toward you."
- **Arrow-key nudging** of a selected drawing follows the screen the same way.
- **Drag, scale handles, rotate tool, marquee, click-to-move-pen, drop-to-place** all work in screen directions: what you drag is where it goes.
- **Rotation angle sense:** a drawing's angle readout keeps meaning the angle on the paper (unchanged data). The Rotate tool's drag must still turn the drawing the way the mouse goes on screen; in a mirrored orientation that means the on-screen turn direction is opposite to the stored angle's sense. (Builder: handle this so the drawing follows the mouse.)
- **Shift keeps proportions / constrains to horizontal or vertical** in screen directions.

### Readouts (builder's call made here, as Claude's call)
Positions and sizes stay **machine numbers**, so a number means the same thing on every laptop and in every saved job:
- X/Y readouts are measured from Home along the machine's X and Y.
- A drawing's X/Y is its box corner nearest Home (in the default orientation that is the top-left, exactly as today). W is its extent along machine X, H along machine Y.
- The paper's X/Y readout (already "the paper's corner nearest HOME") is unchanged.
- Tooltips that currently say "top-left" say "corner nearest HOME".
- The status-bar cursor position is in machine X/Y.

### Constraints
- Python layer: unchanged except for storing and returning the orientation (settings + one bridge call to set it, and its value in the start/status payload). Placement data, job files and plotting stay in machine coordinates.
- The camera today is `screen = machine × scale + offset`. The orientation adds a fixed 2×2 matrix (one of the eight) into that transform; `toScreen`/`toMachine` and every place that does its own math with `camera.scale` (grid bounds, handles, crosshair, the SVG `matrix(...)` on the plate) go through it. Grid bounds must use all four corners, not two.
- Fit paper / fit reach work in the turned view.
- The plate shows no numbers or labels (manager spec §2.4 still holds). The Home marker and the red X / green Y axis indicators are how the user sees the orientation.

### Non-goals
- Mirroring or rotating the artwork itself (a separate feature if ever wanted).
- Free-angle views; only the eight.
- Changing where Home physically is.

## 2. Set Home on the control bar

A **Set Home** button on the right end of the control bar, immediately left of Start. It runs the same two-click sequence as Plotter › Set Home and the tools-column button (`app.setHome()`):
- At rest it reads **Set Home** (home icon).
- After the first click (motors released, `homing` true) it reads **Confirm Home** and is visually highlighted, with the tooltip "Slide the pen to the HOME corner, then click again (Esc cancels)."
- It is disabled with the same reason as the other Set Home controls (`disabledReason("setHome")`).
- While paused, when the bar shows Resume · Return Home · Cancel plot, the Set Home button is hidden (the plotter is mid-plot).

No change to the homing logic itself.

## 3. Hold an arrow to keep moving

The jog pad (Plotter panel) currently moves one step (1 or 10 mm) per click.
- **Tap:** unchanged, one step.
- **Hold:** after a short delay (about 300 ms), the pen keeps moving in that direction until the button is released, the pointer leaves the button, the window loses focus, or the reach limit is hit.
- Moves are issued one at a time (never queued up), so the pen stops within about one move of release and can't run on afterward.
- Movement while held should feel continuous, not like a string of separate taps. How (bigger moves after the first second, a long move that is stopped on release, or something else the engine allows) is the builder's choice, as long as it stops promptly on release and never goes past the reach.
- Holding the keyboard arrow keys while the pen pad is the target? Not part of this: keyboard arrows nudge the selected drawing (manager spec §2.4), and that stays.
- The step-size toggle still sets the tap size.

## Testing
- Orientation math: all eight orientations, round-trip `toScreen`/`toMachine`, grid bounds, and that the plotted output (the prepared plot) is byte-for-byte the same in every orientation.
- UI: the two-click picker (including Esc), jog-pad directions per orientation, drag/nudge directions, the readouts staying in machine numbers, persistence per plotter key (FakeApi).
- Set Home button: both labels, the disabled reason, hidden while paused.
- Hold-to-move: tap = one step; hold issues repeated moves with at most one in flight; release stops issuing; FakeApi logs.
- Hardware check for Adam: on a real plotter, set an orientation that matches how it sits, then jog and Move-pen-to-point and confirm the pen goes where the screen says.

## Left to the builder
- Icons for Set orientation and the pick markers.
- Exact hold delay and how continuous motion is produced (within §3's rules).
- Where the orientation sits in the settings file and payloads.
