# Microsoft Store (MSIX) and other package managers

Nothing in this repo submits or publishes anything. These are the steps for you.

## Microsoft Store (MSIX)

Nullpoint is a normal desktop app, so it ships as a **full trust** MSIX (`runFullTrust`). Files:
`packaging/msix/AppxManifest.xml` and `packaging/msix/build_msix.ps1`.

### What changes inside the Store package

- "Start with Windows" and `nullpoint://` links use the manifest (`windows.startupTask`, `windows.protocol`)
  instead of the registry. The Run-key / HKCU entries the normal build writes don't apply to packaged apps, so
  the settings checkboxes for these don't take effect in the Store build yet (follow-up: detect the package and
  use the StartupTask API).
- The in-app updater should stay off in the Store build (the Store updates the app). Leave
  "Update check" empty there.

### Account and costs (check before you start)

- A Microsoft Partner Center developer account is needed (https://partner.microsoft.com/dashboard).
  Check the current registration fee for individual and company accounts: Microsoft has changed it over time.
- The Store signs the package for you; you don't need your own certificate for Store distribution.
- Apps that ask for `runFullTrust` go through extra review. Explain in the submission notes that Nullpoint is an
  overlay that only draws a click-through window (no injection, no game memory access).

### Steps

1. Create the developer account, then **Apps and games > New product > MSIX or PWA app**, reserve the name
   "Nullpoint" (or another free name).
2. In **Product management > Product identity**, copy `Package/Identity/Name` and `Package/Identity/Publisher`.
   Put them into `packaging/msix/AppxManifest.xml` (Identity `Name`, and pass the publisher to the build script).
3. Install the Windows SDK: `winget install Microsoft.WindowsSDK.10.0.22621`.
4. Build: `build.bat`, then
   `powershell -File packaging\msix\build_msix.ps1 -Version 2.2.0 -Publisher "CN=<from Partner Center>"`.
5. Optional local test: sideloading an unsigned MSIX needs Developer Mode, or sign it with a test certificate.
6. In Partner Center, create a submission: upload `dist\Nullpoint-2.2.0.msix`, fill in the listing (description,
   screenshots, a privacy policy URL: a short page saying Nullpoint collects and sends nothing is enough), age
   rating, and submit for review.

## Scoop

Manifest: `packaging/scoop/nullpoint.json` (portable `Nullpoint.exe`, hash filled by
`python packaging\update_manifests.py <version>`).

1. Create a public GitHub repo for your bucket, e.g. `yensobased1/scoop-bucket`, with a `bucket/` folder.
2. Copy `nullpoint.json` into `bucket/` and push.
3. Users install with `scoop bucket add yensobased1 https://github.com/yensobased1/scoop-bucket` then
   `scoop install nullpoint`.
4. Test locally first: `scoop install .\packaging\scoop\nullpoint.json`.

## Chocolatey

Package: `packaging/chocolatey/` (portable exe, checked against its SHA-256; URL and hash filled by
`update_manifests.py`).

1. Create an account at https://community.chocolatey.org and copy your API key from your account page.
2. Build: `choco pack packaging\chocolatey\nullpoint.nuspec` (makes `nullpoint.2.2.0.nupkg`).
3. Test: `choco install nullpoint -s . -y` (in an admin terminal), check it starts, then `choco uninstall nullpoint`.
4. Publish: `choco apikey -k <your key> -s https://push.chocolatey.org/`, then
   `choco push nullpoint.2.2.0.nupkg -s https://push.chocolatey.org/`. Community packages go through moderation.

## winget

Manifests for each version are in `packaging/winget/manifests/y/yensobased1/Nullpoint/<version>/` (see
NEXT_STEPS.md for the pull request steps).
