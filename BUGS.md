# Bug list (audit 2026-11-19)

Found by rendering sample crosshairs and counting pixels, and by reading the settings code.

| # | Bug | Cause |
|---|-----|-------|
| 1 | Even thickness/dot size sits 1 px right/down of the true screen center (thick 2 = rows 0..+1, dot 2 = 0..+1) | Band start used `c - (t-1)//2`; for even sizes that centers on the wrong pixel edge |
| 2 | Even-thickness lines are off by half a pixel against their own arms (band centered on one point, arms on another) | Arms always started at `c+1+gap` (odd rule) even for even thickness |
| 3 | Gap means something different for odd vs even thickness | Same as #2: no per-parity rule |
| 4 | Preview looks weird: the dark/grey split runs straight through the crosshair center, max 3x zoom, no 1x, no grid | Preview background was two halves; zoom was auto-picked |
| 5 | Big crosshairs/PNGs get blurred in the preview | Smooth scaling when zoom < 1 |
| 6 | Hex color only applies on Enter / focus-out | Bound to `editingFinished` only |
| 7 | Save debounce 400 ms (spec: ~300 ms) | Timer value |
| 8 | Editor tab missing | Never built: Feature Pack v2 stopped before phase 2 |
| 9 | Any Java app (javaw.exe) switches to the Minecraft profile | New v2 game list landed before the title check was wired into polling |

Checked and fine: slider/number-box sync (signals blocked one way, no loops), clamping (ranges on both widgets),
outline drawn under fill without changing size (rects grown by outline px on every side, unioned so overlaps
don't double), per-section opacity, Reset to default (resets + refreshes), every change re-applies the overlay.

## Fixed
1-3. One rule for every band (lines, dot): first pixel = `c - size//2`, and arms start `gap` px from the
     center (`c + gap + size%2` / end at `c - gap`). Pixel c's left/top edge is the true screen center, so even
     sizes are exactly centered and odd sizes sit on pixel c. All four arms mirror each other.
     Covered by `crosshair/test_render.py` (pixel counts for thick 1/2/3, gap 0/3, len 1/4/5, outline, dot 1/2/3).
4-5. New preview (`crosshair/preview.py`): Checker/Dark/Grey/Light background, 1x/2x/4x/8x whole-number
     nearest-neighbour zoom (halves itself if it doesn't fit, never stretched/cropped), optional pixel grid,
     center pixel on the widget center. Preview draws through `Overlay.draw` = same function + same settings
     object as the overlay window.
6. Hex color applies live while typing a valid `#RRGGBB`.
7. Save debounce 300 ms.
8. New Editor tab (`crosshair/editor.py`), see README.
9. javaw.exe only counts as Minecraft when the window title contains "Minecraft".
