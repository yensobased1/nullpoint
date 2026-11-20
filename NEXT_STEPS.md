# Next steps

## v2.2 progress (stopped at the usage budget, 2026-11-19)
Done and committed: phase 1 (visuals), phase 2 (editor), phase 3 (games, display, tools), phase 4 (library and sharing),
plus: built-in game profiles removed (games keep centering; optional profile + offset per game). 98 tests pass.
Nothing is pushed or released yet: v2.2 work lives in local commits on `main`.

Left to do, in order (spec: "Feature Pack v2.2"):
- Phase 5: gallery grid / search / tags (#68, #69), gallery submit issue template (#70), OBS page themes (#74),
  Twitch !crosshair with keyring token (#75), web builder in docs/builder with shared test vectors (#77).
- Phase 6: tooltip previews (#81), safe mode (#90), config/library auto-repair + rotating backups (#91).
- Phase 7: de / ru / pl / it / ja / ko / zh_CN + CJK fonts (#93, #94), missing-key report + docs/TRANSLATING.md (#95).
- Phase 8: security audit (pip-audit, bandit, secret scan, hashes, fuzz tests, SECURITY.md, dependabot, CodeQL,
  docs/SECURITY_AUDIT.md).
- Phase 9: in-app updater with SHA-256 check (#96), beta channel (#97), signing step + docs/SIGNING.md (#98),
  Scoop + Chocolatey (#99), MSIX + docs/STORE.md (#100), release v2.2.0.

Notes from phases 1-4:
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
