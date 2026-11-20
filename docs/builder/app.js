/* Builder page: controls -> crosshair dict -> preview + XH4 code. DOM is built with createElement / textContent
 * only (no innerHTML), so nothing typed or pasted can become markup. */
(function () {
  "use strict";
  const N = window.Nullpoint;
  const c = N.clone(N.DEFAULT);
  const $ = (id) => document.getElementById(id);

  // [legend, [[label, section or "", key, kind, min, max, step | options]]]
  const SPEC = [
    ["Shape", [["Shape", "", "shape", "select", N.SUPPORTED], ["Color", "", "color", "color"],
      ["Line style", "style", "kind", "select", ["solid", "dashed", "dotted"]],
      ["Dash length", "style", "dash", "range", 1, 10, 1], ["Dash gap", "style", "gap", "range", 1, 10, 1]]],
    ["Inner lines", [["Show", "inner", "on", "check"], ["Length", "inner", "len", "range", 0, 30, 1],
      ["Thickness", "inner", "thick", "range", 1, 10, 1], ["Gap", "inner", "gap", "range", 0, 40, 1],
      ["Opacity", "inner", "alpha", "range", 0, 1, 0.01]]],
    ["Outer lines", [["Show", "outer", "on", "check"], ["Length", "outer", "len", "range", 0, 30, 1],
      ["Thickness", "outer", "thick", "range", 1, 10, 1], ["Gap", "outer", "gap", "range", 0, 40, 1],
      ["Opacity", "outer", "alpha", "range", 0, 1, 0.01]]],
    ["Center dot", [["Show", "dot", "on", "check"], ["Shape", "dot", "shape", "select", ["square", "circle", "diamond"]],
      ["Size", "dot", "size", "range", 1, 10, 1], ["Opacity", "dot", "alpha", "range", 0, 1, 0.01]]],
    ["Outline", [["Show", "outline", "on", "check"], ["Thickness", "outline", "thick", "range", 1, 6, 1],
      ["Opacity", "outline", "alpha", "range", 0, 1, 0.01]]],
    ["Shadow / glow", [["Show", "shadow", "on", "check"], ["Type", "shadow", "mode", "select", ["shadow", "glow"]],
      ["Glow color", "shadow", "color", "color"], ["Size", "shadow", "size", "range", 0, 8, 1],
      ["Opacity", "shadow", "alpha", "range", 0, 1, 0.01]]],
    ["Per-arm (inner lines)", [["Link all arms", "arms", "link", "check"], ["Top", "arms", "t", "range", 0, 30, 1],
      ["Right", "arms", "r", "range", 0, 30, 1], ["Bottom", "arms", "b", "range", 0, 30, 1],
      ["Left", "arms", "l", "range", 0, 30, 1]]],
  ];

  const target = (sec) => (sec ? c[sec] : c);

  function control(label, sec, key, kind, a, b, step) {
    const wrap = document.createElement("label");
    wrap.className = "field";
    const name = document.createElement("span");
    name.textContent = label;
    wrap.append(name);
    let input;
    const obj = target(sec);
    if (kind === "select") {
      input = document.createElement("select");
      for (const v of a) {
        const o = document.createElement("option");
        o.value = v;
        o.textContent = v;
        input.append(o);
      }
      input.value = obj[key];
      input.addEventListener("change", () => { obj[key] = input.value; update(); });
    } else if (kind === "check") {
      input = document.createElement("input");
      input.type = "checkbox";
      input.checked = obj[key];
      input.addEventListener("change", () => { obj[key] = input.checked; update(); });
    } else if (kind === "color") {
      input = document.createElement("input");
      input.type = "color";
      input.value = "#" + obj[key];
      input.addEventListener("input", () => { obj[key] = input.value.slice(1).toUpperCase(); update(); });
    } else {
      const out = document.createElement("output");
      out.textContent = obj[key];
      wrap.append(out);
      input = document.createElement("input");
      input.type = "range";
      Object.assign(input, { min: a, max: b, step });
      input.value = obj[key];
      input.addEventListener("input", () => {
        obj[key] = step < 1 ? Math.round(parseFloat(input.value) * 100) / 100 : parseInt(input.value, 10);
        out.textContent = obj[key];
        update();
      });
    }
    input.setAttribute("aria-label", label);
    wrap.append(input);
    return wrap;
  }

  for (const [legend, rows] of SPEC) {
    const fs = document.createElement("fieldset");
    const lg = document.createElement("legend");
    lg.textContent = legend;
    fs.append(lg);
    for (const row of rows) fs.append(control(...row));
    $("controls").append(fs);
  }

  function draw(canvas, px, zoom) {
    const ctx = canvas.getContext("2d");
    const n = Math.floor(canvas.width / zoom), mid = Math.floor(n / 2);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let y = 0; y < n; y++)
      for (let x = 0; x < n; x++) {
        ctx.fillStyle = (x + y) % 2 ? "#232323" : "#1b1b1b";
        if (zoom > 2) ctx.fillRect(x * zoom, y * zoom, zoom, zoom);
      }
    for (const [k, [r, g, b, a]] of px) {
      const [dx, dy] = k.split(",").map(Number);
      ctx.fillStyle = `rgba(${r},${g},${b},${a / 255})`;
      ctx.fillRect((mid + dx) * zoom, (mid + dy) * zoom, zoom, zoom);
    }
  }

  function update() {
    const px = N.render(c);
    draw($("view"), px, 10);
    draw($("real"), px, 1);
    const code = N.exportCode(c);
    $("code").value = code;
    $("link").href = "nullpoint://import/" + N.quote(code);
  }

  $("copy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("code").value);
      $("status").textContent = "Copied.";
    } catch (e) {
      $("code").select();
      $("status").textContent = "Press Ctrl+C to copy.";
    }
  });
  update();
})();
