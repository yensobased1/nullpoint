/* Shared by run_tests.js (Node) and test.html (browser): compare the builder with the app's test vectors.
 * Pixels must match exactly in position; alpha within 2 and color within 3 (the app stores premultiplied
 * pixels, so reading them back rounds a little). */
(function (root) {
  "use strict";
  function check(N, vectors) {
    return vectors.map((v) => {
      const code = N.exportCode(v.cross);
      if (code !== v.code) return { name: v.name, ok: false, why: "code differs:\n  app " + v.code + "\n  web " + code };
      const got = N.render(v.cross);
      if (got.size !== v.pixels.length) return { name: v.name, ok: false, why: `pixel count ${got.size} vs ${v.pixels.length}` };
      for (const [x, y, r, g, b, a] of v.pixels) {
        const p = got.get(x + "," + y);
        if (!p) return { name: v.name, ok: false, why: `missing pixel ${x},${y}` };
        if (Math.abs(p[3] - a) > 2) return { name: v.name, ok: false, why: `alpha at ${x},${y}: ${p[3]} vs ${a}` };
        if (a >= 64 && [r, g, b].some((c, i) => Math.abs(p[i] - c) > 3))
          return { name: v.name, ok: false, why: `color at ${x},${y}: ${p.slice(0, 3)} vs ${[r, g, b]}` };
      }
      return { name: v.name, ok: true };
    });
  }
  if (typeof module !== "undefined" && module.exports) module.exports = { check };
  else root.NullpointCompare = { check };
})(typeof globalThis !== "undefined" ? globalThis : this);
