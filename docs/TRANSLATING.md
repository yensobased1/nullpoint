# Translating Nullpoint

Every piece of UI text lives in `crosshair/lang/<code>.json`. The **key** is the English text, the **value** is the
translation:

```json
"Reduce motion": "Bewegung reduzieren",
```

Missing keys simply show in English, so a partial translation never breaks anything.

## Fix or improve a language

Everything except English and Arabic was machine-translated. Native speakers' fixes are very welcome:

1. Open `crosshair/lang/<code>.json` (e.g. `de.json`, `ja.json`).
2. Change only the **values** (right side). Never change a key: it must match the English text in the code exactly.
3. Keep these unchanged inside the text: file types like `(*.svg)`, `.nullpoint`, `nullpoint://`, `!crosshair`,
   `chat:read`, `#RRGGBB`, `127.0.0.1`, sizes like `1920x1080`, `CSGO-`, `0;P`, key names (`F1`, `Shift`, `Esc`).
4. Plain text only: no HTML tags like `<b>` (the tests reject them).
5. Keep it short. Labels sit next to sliders; long text gets cut off.
6. Check it: run `python crosshair/lang_report.py` and the tests (`python -m unittest` inside `crosshair/`).
7. Open a pull request (or an issue with your changes).

## Add a new language

1. Copy `crosshair/lang/en.json` to `crosshair/lang/<code>.json` (codes: `de`, `pt_BR`, `zh_CN`, ...).
2. Translate the values.
3. Add the language to `LANGUAGES` in `crosshair/ui/i18n.py` (`"<code>": "Name in that language"`).
   Right-to-left languages also go in `RTL`. Chinese / Japanese / Korean style scripts can get a Windows UI font in
   `FONTS`, so characters use the right regional shapes.
4. Run `python crosshair/lang_report.py --strict`: it must report 0 missing keys.

## When the English text changes

`lang_report.py` lists `tr("...")` texts in the code that `en.json` doesn't have yet, and for every language the keys
that are missing or extra compared with `en.json`. Add new English keys to `en.json` (key and value the same), then
translate them in the other files.
