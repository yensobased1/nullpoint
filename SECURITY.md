# Security policy

## Reporting a vulnerability

Please **don't** open a public issue for security problems.

Report privately through GitHub: **Security** tab of this repository -> **Report a vulnerability**
(https://github.com/yensobased1/nullpoint/security/advisories/new). Include what you found, how to reproduce it,
and which version you tested (Settings > App Settings shows it).

You'll get a reply within a week. Fixes ship in the next release, and you're credited in the release notes unless
you'd rather not be.

## Supported versions

Only the latest release gets security fixes. Nullpoint checks for updates once a day (when enabled) and tells you
when a new version is out.

## Scope

In scope: anything that lets outside input (share codes, `nullpoint://` links, QR images, dropped or imported files,
the gallery, the stream page, Twitch chat, update data) do more than show or import a crosshair after you confirm it,
read or write files outside Nullpoint's folders, run code, or leak data.

Nullpoint is a plain click-through window. It never injects into games, hooks DirectX or reads game memory or game
pixels. Reports about anti-cheat behaviour are welcome too.

What was checked so far is in [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md).
