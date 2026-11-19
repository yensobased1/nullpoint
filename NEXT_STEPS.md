# Next steps

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
