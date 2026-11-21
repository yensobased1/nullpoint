# Changelog

## v2.2.3
- **Deadlock** is now a built-in game (`project8.exe`): centered on its window, shown only in games, lobby hiding.
- Rainbow / GIF previews in Settings now animate even when no game is focused.
- The Color section says when Rainbow is paused by Reduce motion or low-power mode.

## v2.2.2
- **Fullscreen help**: if "Disable fullscreen optimizations" is set for a game (the usual reason the crosshair
  doesn't show in fullscreen), Nullpoint notices it and fixes it after you confirm (that game, your Windows user
  only). It also tells you when fullscreen optimizations are off for all games.
- The overlay keeps itself on top while a game is focused, so fullscreen games can't cover it.
- The exclusive-fullscreen warning names the exact window mode to pick in Fortnite, VALORANT, CS2, Apex,
  Overwatch 2, Call of Duty and Minecraft.
- True exclusive fullscreen still can't be drawn over: only DirectX hooks can do that, and anti-cheat bans them.

## v2.2.1
- **Hide in lobby and menus** (Settings > App Settings, off by default): the crosshair hides while the game shows
  your mouse cursor (lobby, menus, inventory) and comes back when you aim. Only asks Windows whether the cursor is
  shown; nothing is read from the game. Games that draw their own menu cursor may not be detected.

## v2.2.0
**Crosshair**
- Per-arm lengths and colors ("Link all arms" off), round / diamond center dots, a colored **glow**, **fire expand**
  (lines open while you hold left mouse in a game, visual only), **Reduce motion**, and **SVG export**.
- Share codes are now **XH4**; XH1-XH3 codes still load.

**Editor**
- Line, rectangle and circle tools (outline or filled), mirror with every tool, up to 8 **layers**, **animation
  frames** with onion skin and play preview, animated **GIF export**, **import any image** as pixels (threshold /
  invert / keep colors), and **recolor** with tolerance.

**Games and display**
- **Game profiles are gone**: games are still detected and the crosshair is centered on their window, but they use
  the profile you pick. Make, rename and delete your own profiles next to the profile box; a game can still get a
  profile and an **offset** of its own. Old built-in game profiles that differed from Default are saved to your
  library as "(old profile)".
- **Profile rules** by program and / or window title (contains / exact / regex), **detect installed games** (Epic,
  Riot, Battle.net), **resolution variants**, arrow-key **nudge** (also an in-game nudge hotkey), **HDR
  compensation**, **startup delay**, and a **sensitivity converter** (CS2, Apex, VALORANT, Overwatch 2, cm/360).

**Library and sharing**
- Duplicate check, **import a folder of PNGs**, **recent crosshairs** in the tray, **drag and drop** (`.nullpoint`
  files, images, text), **.nullpoint** single-file export, **VALORANT code export** and **CS2 console commands**,
  animated share cards for GIF crosshairs, **Copy for Discord**, opt-in **clipboard watch**, and 6 **starter packs**.

**Community**
- Gallery search, tag filters, sort and grid; **Submit to gallery** (prefilled GitHub issue).
- OBS page themes, positions, size and toggles. **Twitch `!crosshair`** (opt-in; token in Windows Credential Manager).
- **Web builder**: https://yensobased1.github.io/nullpoint/builder/ (same codes and pixels as the app).

**Reliability and UI**
- Tooltips show a before / after preview of each setting. **Safe mode** (hold Shift while starting, or `--safe`).
  Rotating **backups** (last 10) and **auto-repair** of a damaged config or library.

**Languages**
- New: Deutsch, Русский, Polski, Italiano, 日本語, 한국어, 简体中文 (machine-translated; fixes welcome, see
  docs/TRANSLATING.md). Japanese / Korean / Chinese use the matching Windows UI fonts.

**Updates and distribution**
- **In-app updater**: shows what's new, and only on your click downloads the installer from the GitHub release,
  checks its SHA-256 against the release's `checksums.txt`, and runs it. Optional **beta channel**.
- Signing step (Azure Trusted Signing) in `build.bat`, Scoop and Chocolatey packages, MSIX setup (docs/SIGNING.md,
  docs/STORE.md).

**Security**
- Full audit: docs/SECURITY_AUDIT.md. pip-audit and bandit clean; the git history was scanned for secrets (none).
- Dependencies pinned with hashes and installed with `--require-hashes`.
- All network access goes through one checked path: HTTPS, GitHub hosts only (redirects too), timeouts, size limits.
- Every image load is size-checked (and Pillow's bomb guard is on); network (UNC) paths aren't opened automatically.
- SVGs with scripts or external references are refused. Backup imports can't write outside Nullpoint's folder or
  change the update source. `nullpoint://` links can't set command-line flags. Only your own Windows user can talk
  to the running app. The current folder is no longer in the DLL search path.
- OBS page: random private link, Host check against DNS rebinding, GET only, no CORS.
- Fuzz tests for every parser. `SECURITY.md` with private reporting, Dependabot and CodeQL on GitHub.

## v2.1.3
- **Import CS2 / CS:GO crosshair codes** (`CSGO-xxxxx-...`) in the same box as VALORANT codes, plus Paste Code,
  `nullpoint://` links and QR images. Sized like the game draws it at your screen height.
- VALORANT codes now convert 1:1 in pixels (VALORANT doesn't scale its crosshair with resolution). "Keep 1080p size"
  is optional and off by default.
- The import preview no longer counts hidden lines, so it zooms in properly.

## v2.1.2
- **Import VALORANT codes** (e.g. from vcrdb.net): paste a VALORANT crosshair code on the Share tab, see a live
  preview and apply it or save it to the library. Paste Code, `nullpoint://` links and QR images accept them too.
  "VALORANT-accurate size" scales it to your screen height so it matches in game.
- Dashed lines now always look different from dotted lines.
- No more Windows accent color (e.g. purple) in drop-down lists.
- The settings only show what the current Mode uses (Line crosshair / Text / Image).
- Fixed: per-part color boxes stayed visible with "Use same color for all" ticked.

## v2.1.1
- Fixed: Windows' accent color (e.g. purple) showing on the changelog box and square buttons; they now follow the
  black and white theme in dark and light mode.

## v2.1.0
- **Crosshair visuals:** soft shadow, gradient lines (center to tip), solid / dashed / dotted lines, new shapes
  (Hexagon, Triangle, Diamond, thick Plus), text / symbol crosshairs with any font, colorblind presets.
- **Compare mode:** current crosshair next to any library item or pasted share code.
- **Workflow:** hold-to-hide key (keyboard or Mouse2-5), quick switcher (Alt+X) for 8 favorites, library tags,
  search and favorites, "Copy to..." between game profiles, hold F1 for a hotkey cheat sheet, settings search.
- **Sharing:** share card PNG with QR, import a share code from a QR image, `nullpoint://` links,
  local stream page for OBS, optional Discord Rich Presence, community Gallery tab.
- **Utility:** eDPI calculator, resource monitor, low-power mode on battery, portable mode.
- **Onboarding:** first-run wizard, this changelog popup, feedback button, crash reporter (local only).
- **Accessibility:** keyboard focus rings, accessible names, UI text scale, large text.
- **Languages:** Spanish, Portuguese (BR), French and Turkish (machine-translated, fixes welcome).
- Share codes are now `XH3`; `XH1` / `XH2` codes still import.

## v2.0.0
- First public release as Nullpoint: shapes, ring, rainbow, per-part colors, PNG / GIF / SVG images,
  pixel editor, library, per-game profiles with auto-switching, monitor picker, stretched-resolution helper,
  share codes + QR, backup export / import, undo / redo, stream-safe mode, alignment test, dark / light theme,
  English / Arabic, update checker.
