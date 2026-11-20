# Next steps

## v2.2 progress (2026-11-20)
Done and committed: phase 1 (visuals), phase 2 (editor), phase 3 (games, display, tools), phase 4 (library and sharing),
phase 5 (community), phase 6 (reliability and UI), phase 7 (languages), phase 8 (security audit), plus: built-in game profiles removed (games keep centering; optional profile + offset
per game). 131 tests pass (incl. fuzz tests) (incl. the web builder's JS check with Node).
Nothing is pushed or released yet: v2.2 work lives in local commits on `main`.

Left to do, in order (spec: "Feature Pack v2.2"):
- Phase 9: in-app updater with SHA-256 check (#96), beta channel (#97), signing step + docs/SIGNING.md (#98),
  Scoop + Chocolatey (#99), MSIX + docs/STORE.md (#100), release v2.2.0.

Notes from phases 1-8:
- Security audit: docs/SECURITY_AUDIT.md. Private vulnerability reporting is enabled on GitHub.
- Dependencies are pinned with hashes: after changing requirements.in, run
  `.venv\Scripts\pip-compile --generate-hashes --strip-extras --allow-unsafe -o requirements.txt requirements.in`.
- New languages (de, ru, pl, it, ja, ko, zh_CN) are machine-translated and not reviewed by native speakers.
  Japanese / Korean / Chinese use the Windows UI fonts Yu Gothic UI / Malgun Gothic / Microsoft YaHei UI.
- Safe mode: hold Shift while Nullpoint starts (or run it with --safe). Backups: %APPDATA%\Nullpoint\backups (last 10
  of config.json and library.json, made when a file loads fine). A damaged file is kept as <name>.<time>.corrupt.
- Web builder (docs/builder) supports cross / T / dot / plus / square, line styles, dot shapes, outline,
  shadow / glow and per-arm lengths. Rings, rotation, polygons, text and gradients stay app-only.
  docs/builder/vectors.json is written by the app (crosshair/test_builder.py --write) and checked by both sides.
- The stream page URL now has a private token: http://127.0.0.1:<port>/<token>/ (shown in App Settings).
  Update the OBS browser source once after upgrading. "New link" makes a fresh token.
- Twitch status messages that include the channel name or a retry time are English only.
- CS2 share codes (CSGO-...) are not generated: no real game-made codes were available to verify the encoder.
  Export gives the console commands only.
- Export warnings (VALORANT / CS2) are English only for now: they name the left-out feature in the text.
- Upgrading removes the built-in game profiles (Fortnite, VALORANT, ...). Crosshairs that differed from Default are
  saved to the library as '<name> (old profile)'.
- Share codes are now XH4 (adds per-arm, dot shape, glow, fire expand). XH1-XH3 still load.
- Pillow was added to requirements.txt (animated GIF export from the editor).
- Sensitivity converter covers CS2, Apex, VALORANT and Overwatch 2. Fortnite and Roblox are left out: no reliable
  published yaw value was found to check against.
- HDR "Auto" reads Windows' advanced-color flag per monitor (DisplayConfig API); not tested on a real HDR screen.
- Fire expand, nudge mode and resolution variants were tested with unit tests and an offscreen settings window,
  not inside a real game.
- "Start with Windows" entries are rewritten on launch to add `--autostart` (needed for the startup delay).

## Manual steps for you

### GitHub Pages for the web builder (after the v2.2 push)
1. Push `main` (the release step does this).
2. GitHub -> yensobased1/nullpoint -> **Settings** -> **Pages**.
3. **Source**: Deploy from a branch. **Branch**: `main`, folder `/docs`. **Save**.
4. After a minute the builder is at https://yensobased1.github.io/nullpoint/builder/ and its self-test at
   https://yensobased1.github.io/nullpoint/builder/test.html (should say "All passed.").
   (Or: `gh api -X POST repos/yensobased1/nullpoint/pages -f "source[branch]=main" -f "source[path]=/docs"`.)

### Twitch !crosshair (token)
Minimum scopes: `chat:read` and `chat:edit` (read your chat, send the reply). Nothing else.
1. Open https://dev.twitch.tv/console/apps (sign in with your streaming account) -> **Register Your Application**.
   Name: anything (e.g. `Nullpoint chat`). OAuth Redirect URL: `http://localhost`. Category: **Chat Bot**.
   Client type: **Public**. Create, then copy the **Client ID**.
2. In your browser (still signed in as your channel), open, with your Client ID filled in:
   `https://id.twitch.tv/oauth2/authorize?response_type=token&client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost&scope=chat:read+chat:edit`
3. Click **Authorize**. The browser goes to `http://localhost/#access_token=...` (the page itself won't load; that's fine).
   Copy only the part after `access_token=` and before the next `&`.
4. Nullpoint -> **App Settings** -> **Twitch chat**: type your channel name, **Set token...**, paste, then tick
   **Reply to !crosshair**. The token is stored in Windows Credential Manager (entry `Nullpoint/twitch`), not in
   config.json. **Forget token** removes it.
5. These tokens expire after a while; when replies stop and the status says "login failed", repeat steps 2-4.
   Never share the token: it can post in your chat.

### Discord Rich Presence (client ID)
1. Open https://discord.com/developers/applications and sign in.
2. Click **New Application**, name it `Nullpoint` (this name is what friends see), accept the terms, **Create**.
3. On **General Information**, copy the **Application ID** (a long number).
4. In Nullpoint: **App Settings** -> paste it into **Discord client ID**, then tick **Discord Rich Presence**.
   Discord desktop must be running. Nothing is sent when the box is off or the ID is empty.

### winget (submit it yourself)
The manifests are in `packaging/winget/manifests/y/yensobased1/Nullpoint/<version>/` (2.1.0 - 2.1.3) and pass `winget validate`.
1. Make sure release v2.1.0 is live and the installer URL in `yensobased1.Nullpoint.installer.yaml` downloads.
2. Optional local test (admin PowerShell): `winget settings --enable LocalManifestFiles`, then
   `winget install --manifest packaging\winget\manifests\y\yensobased1\Nullpoint\2.1.0`.
3. Fork https://github.com/microsoft/winget-pkgs, copy the `2.1.0` folder to
   `manifests/y/yensobased1/Nullpoint/2.1.0/` in your fork, commit, and open a pull request titled
   `New package: yensobased1.Nullpoint version 2.1.0`. Fill in the PR checklist and wait for the bots / reviewers.
   (Or use `wingetcreate submit <folder>`.)
4. For each new release: new version folder, new InstallerUrl + InstallerSha256.

## Not verified / known limits
- Not tested inside real games (Fortnite, VALORANT, CS2, ...) or with exclusive fullscreen.
- The installer was compiled but not installed / uninstalled on this PC (it would change your Start menu and registry).
- Discord Rich Presence: not tested with a real client ID. Stream-safe capture hiding: not checked with OBS.
- Hold-to-hide and the F1 cheat sheet poll the key state (GetAsyncKeyState, 25x per second) instead of
  RegisterHotKey, so the game still receives the key (RegisterHotKey would swallow Mouse2 / F1).
- Text crosshair "bundled default font": no font file was provided, so the default is the Windows UI font.
- UI scale (100/125/150%) scales the settings text only: Qt high-DPI scaling stays off to keep the overlay pixel exact.
- es / pt_BR / fr / tr are machine-translated; ar was written by hand earlier. Native speakers should review.
- Gallery thumbnails need the `gallery/` folder on the `main` branch (pushed with v2.1.0).
- Process names for the built-in games come from memory; Call of Duty titles may need extra exes.
