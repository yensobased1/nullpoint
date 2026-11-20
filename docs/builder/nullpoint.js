/* Nullpoint crosshair core for the web builder: share codes (XH4) and the pixel-exact renderer.
 * A port of crosshair/share_code.py export_code() and the rectangle parts of crosshair/overlay.py render().
 * Checked against the app with shared test vectors (vectors.json): see run_tests.js and test.html.
 * Supported here: shapes cross / t / dot / plus / square, solid / dashed / dotted lines, dot shapes, outline,
 * shadow / glow, per-arm lengths and colors. Rings, rotation, polygons, text and gradients need the app. */
(function (root) {
  "use strict";

  const DEFAULT = {
    mode: "lines", color: "00FFFF",
    outline: { on: true, thick: 1, alpha: 0.5 },
    dot: { on: true, size: 2, alpha: 1.0, shape: "square" },
    inner: { on: true, len: 6, thick: 2, gap: 3, alpha: 0.8, vsep: false, vlen: 6 },
    outer: { on: false, len: 2, thick: 2, gap: 10, alpha: 0.35, vsep: false, vlen: 2 },
    png: { scale: 100, alpha: 1.0, rot: 0 },
    shape: "cross", rot: 0,
    ring: { on: false, radius: 10, thick: 1, alpha: 1.0, gaps: 0, gapsize: 20, gaprot: 0 },
    colors: { same: true, lines: "00FFFF", dot: "00FFFF", ring: "00FFFF", outline: "000000" },
    rainbow: { on: false, speed: 5, sat: 1.0 },
    shadow: { on: false, size: 2, alpha: 0.5, mode: "shadow", color: "FFFFFF" },
    gradient: { on: false, c2: "FFFFFF" },
    style: { kind: "solid", dash: 4, gap: 2 },
    text: { chars: "+", font: "", size: 24, bold: true, alpha: 1.0 },
    arms: { link: true, t: 6, r: 6, b: 6, l: 6, ct: "", cr: "", cb: "", cl: "" },
    expand: { on: false, px: 4, ms: 120 },
  };

  // [code key, section, [[field, type]]] in the same order as share_code.FIELDS (types: i int, f float, b bool)
  const LINE = [["on", "b"], ["len", "i"], ["thick", "i"], ["gap", "i"], ["alpha", "f"], ["vsep", "b"], ["vlen", "i"]];
  const FIELDS = [
    ["o", "outline", [["on", "b"], ["thick", "i"], ["alpha", "f"]]],
    ["d", "dot", [["on", "b"], ["size", "i"], ["alpha", "f"]]],
    ["i", "inner", LINE], ["e", "outer", LINE],
    ["p", "png", [["scale", "i"], ["alpha", "f"], ["rot", "i"]]],
    ["g", "ring", [["on", "b"], ["radius", "i"], ["thick", "i"], ["alpha", "f"], ["gaps", "i"], ["gapsize", "i"], ["gaprot", "i"]]],
    ["w", "rainbow", [["on", "b"], ["speed", "i"], ["sat", "f"]]],
    ["h", "shadow", [["on", "b"], ["size", "i"], ["alpha", "f"]]],
    ["a", "arms", [["link", "b"], ["t", "i"], ["r", "i"], ["b", "i"], ["l", "i"]]],
    ["f", "expand", [["on", "b"], ["px", "i"], ["ms", "i"]]],
  ];
  const MODE_KEYS = { lines: "l", png: "p", text: "t" };
  const SHAPE_KEYS = { cross: "c", t: "t", dot: "d", circle: "o", square: "q", chevron: "v", x: "x",
    hexagon: "6", triangle: "3", diamond: "4", plus: "p" };
  const STYLE_KEYS = { solid: "s", dashed: "d", dotted: "o" };
  const DOT_KEYS = { square: "s", circle: "c", diamond: "d" };
  const HALO_KEYS = { shadow: "s", glow: "g" };
  const HEX = /^[0-9A-Fa-f]{6}$/;

  const clone = (o) => JSON.parse(JSON.stringify(o));

  function merge(base, data) {
    const out = clone(base);
    for (const k of Object.keys(data || {})) {
      if (out[k] && typeof out[k] === "object" && typeof data[k] === "object") Object.assign(out[k], data[k]);
      else out[k] = data[k];
    }
    return out;
  }

  // Python f"{round(v, 2):g}" for the values sliders make
  const fmtFloat = (v) => String(Math.round(v * 100) / 100);
  const num = (v, t) => (t === "b" ? (v ? "1" : "0") : t === "f" ? fmtFloat(v) : String(Math.round(v)));
  // Python urllib.parse.quote(s, safe="")
  const quote = (s) => encodeURIComponent(s).replace(/[!'()*]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase());
  const hexOr = (v, d) => (typeof v === "string" && HEX.test(v) ? v.toUpperCase() : d);

  function exportCode(c) {
    const parts = ["XH4", "m:" + (MODE_KEYS[c.mode] || "l"), "c:" + c.color.toUpperCase()];
    for (const [key, sec, fields] of FIELDS) parts.push(key + ":" + fields.map(([f, t]) => num(c[sec][f], t)).join(","));
    parts.push("s:" + (SHAPE_KEYS[c.shape] || "c"), "r:" + String(c.rot),
      "k:" + [num(c.colors.same, "b"), ...["lines", "dot", "ring", "outline"].map((k) => c.colors[k].toUpperCase())].join(","),
      "y:" + num(c.gradient.on, "b") + "," + c.gradient.c2.toUpperCase(),
      "l:" + [STYLE_KEYS[c.style.kind] || "s", String(c.style.dash), String(c.style.gap)].join(","),
      "z:" + (DOT_KEYS[c.dot.shape] || "s"),
      "q:" + (HALO_KEYS[c.shadow.mode] || "s") + "," + hexOr(c.shadow.color, "FFFFFF"),
      "u:" + ["ct", "cr", "cb", "cl"].map((k) => hexOr(c.arms[k], "")).join(","));
    const t = c.text;
    parts.push("x:" + [quote(t.chars), String(t.size), num(t.bold, "b"), num(t.alpha, "f"), quote(t.font)].join(","));
    return parts.join(";");
  }

  // ---------- geometry (overlay.py) ----------
  const band = (c, size) => c - Math.floor(size / 2);

  function dashSegments(length, style, thick) {
    if (style.kind === "solid") return [[0, length]];
    const dash = style.kind === "dotted" ? thick : Math.max(style.dash, thick + 1);
    const out = [];
    for (let pos = 0; pos < length; pos += dash + style.gap) out.push([pos, Math.min(dash, length - pos)]);
    return out;
  }

  function armRects(sec, c, top, style, lens) {
    if (!sec.on) return {};
    const t = sec.thick, g = sec.gap, hl = sec.len, vl = sec.vsep ? sec.vlen : hl;
    lens = lens || { r: hl, l: hl, b: vl, t: vl };
    const b = band(c, t), near = c + g + (t % 2), far = c - g;
    const seg = (n) => (n > 0 ? dashSegments(n, style, t) : []);
    const out = {
      r: seg(lens.r).map(([o, n]) => [near + o, b, n, t]),
      l: seg(lens.l).map(([o, n]) => [far - o - n, b, n, t]),
      b: seg(lens.b).map(([o, n]) => [b, near + o, t, n]),
    };
    if (top) out.t = seg(lens.t).map(([o, n]) => [b, far - o - n, t, n]);
    return out;
  }

  function plusRects(sec, c) {
    if (!sec.on) return [];
    const t = sec.thick, r = sec.gap + sec.len, b = band(c, t), w = 2 * r + (t % 2);
    return [[c - r, b, w, t], [b, c - r, t, w]];
  }

  function squareRects(sec, c) {
    if (!sec.on || sec.len + sec.gap <= 0) return [];
    const t = sec.thick, r = sec.gap + sec.len, x0 = c - r, w = 2 * r + (t % 2);
    if (w <= 2 * t) return [[x0, x0, w, w]];
    return [[x0, x0, w, t], [x0, x0 + w - t, w, t], [x0, x0 + t, t, w - 2 * t], [x0 + w - t, x0 + t, t, w - 2 * t]];
  }

  function dotRects(size, c, shape) {
    const a = band(c, size);
    if (shape === "square" || size <= 2) return [[a, a, size, size]];
    const h = size / 2, out = [];
    for (let j = 0; j < size; j++) {
      const dy = Math.abs(j + 0.5 - h);
      const w = shape === "circle" ? Math.sqrt(Math.max(0, (h - 0.25) ** 2 - dy * dy)) : h - dy;
      let n = 0;
      for (let i = 0; i < size; i++) if (Math.abs(i + 0.5 - h) <= w + 1e-9) n++;
      if (n) out.push([a + Math.floor((size - n) / 2), a + j, n, 1]);
    }
    return out;
  }

  const SUPPORTED = ["cross", "t", "dot", "plus", "square"];

  function parts(c, center) {
    const same = c.colors.same;
    const lines = same ? c.color : c.colors.lines, dotCol = same ? c.color : c.colors.dot;
    const out = [];
    const shape = c.shape, arms = c.arms;
    const perArm = !arms.link && (shape === "cross" || shape === "t");
    if (shape !== "dot") {
      for (const k of ["inner", "outer"]) {
        const sec = c[k];
        if (!sec.on) continue;
        if (shape === "square") { out.push({ rects: squareRects(sec, center), color: lines, alpha: sec.alpha }); continue; }
        if (shape === "plus") { out.push({ rects: plusRects(sec, center), color: lines, alpha: sec.alpha }); continue; }
        const lens = perArm && k === "inner" ? { t: arms.t, r: arms.r, b: arms.b, l: arms.l } : null;
        const groups = armRects(sec, center, shape !== "t", c.style, lens);
        if (perArm) {
          for (const a of Object.keys(groups)) {
            if (groups[a].length) out.push({ rects: groups[a], color: hexOr(arms["c" + a], lines), alpha: sec.alpha });
          }
        } else {
          const all = [].concat(...Object.values(groups));
          if (all.length) out.push({ rects: all, color: lines, alpha: sec.alpha });
        }
      }
    }
    if (c.dot.on) out.push({ rects: dotRects(c.dot.size, center, c.dot.shape), color: dotCol, alpha: c.dot.alpha });
    return out;
  }

  // Python round() (half to even) so alpha bytes match the app
  function pyRound(x) {
    const f = Math.floor(x), d = x - f;
    if (Math.abs(d - 0.5) < 1e-9) return f % 2 === 0 ? f : f + 1;
    return Math.round(x);
  }

  /** -> Map "dx,dy" -> [r, g, b, a] relative to the center pixel. Same layer order as overlay.render(). */
  function render(c) {
    const C = 128, px = new Map();
    const ps = parts(c, C);
    const rgb = (hex) => [0, 2, 4].map((i) => parseInt(hex.substr(i, 2), 16));
    const fill = (rects, grow, col) => {
      for (const [x, y, w, h] of rects)
        for (let yy = y - grow; yy < y + h + grow; yy++)
          for (let xx = x - grow; xx < x + w + grow; xx++) px.set(xx - C + "," + (yy - C), col);
    };
    const allRects = [].concat(...ps.map((p) => p.rects));
    const o = c.outline.on && c.outline.thick > 0 ? c.outline.thick : 0;
    const sh = c.shadow;
    if (sh.on && sh.size > 0 && sh.alpha > 0) {
      const glow = sh.mode === "glow";
      const base = glow && HEX.test(sh.color) ? rgb(sh.color) : [0, 0, 0];
      for (let k = sh.size; k > 0; k--) {
        const f = (sh.size - k + 1) / sh.size;
        fill(allRects, o + k, [...base, pyRound(255 * sh.alpha * (glow ? f * f : f))]);
      }
    }
    if (o) fill(allRects, o, [...rgb(same(c) ? "000000" : c.colors.outline), pyRound(255 * c.outline.alpha)]);
    for (const p of ps) fill(p.rects, 0, [...rgb(p.color), pyRound(255 * p.alpha)]);
    for (const [k, v] of px) if (!v[3]) px.delete(k);
    return px;
  }
  const same = (c) => c.colors.same;

  const api = { DEFAULT, SUPPORTED, merge, clone, exportCode, render, quote, dotRects, armRects };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Nullpoint = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
