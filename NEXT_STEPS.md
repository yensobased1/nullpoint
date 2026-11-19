# Next steps

Feature Pack v2 is implemented (phases 1-4). Not verified / known gaps:

- Not tested inside real games (Fortnite, VALORANT, CS2, ...) or with exclusive fullscreen; process names for
  the new built-in games come from memory. Call of Duty titles may need extra exes (add via Games & Display).
- Stream-safe mode: the Win32 call succeeds here, but hiding from OBS was not checked with a real capture.
- Update checker: only the version compare is unit-tested; no live GitHub release was queried.
- Animated GIF: tested with a 1-frame GIF only (Pillow isn't installed to make multi-frame test files).
- Arabic: translations written by hand; a native speaker should proofread `crosshair/lang/ar.json`.
  The preview's "(Nx doesn't fit)" note is not translated.
- Light theme: combo-box arrows use the native style.
- Rebuild `lang/en.json` after adding UI strings: call `tr()` on every new string; `ui.i18n.seen` collects
  the keys at runtime (see `test_lang.py`, which fails when `ar.json` misses a key).
