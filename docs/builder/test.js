// Browser version of run_tests.js (needs http(s): vectors.json is fetched from the same folder).
fetch("vectors.json")
  .then((r) => r.json())
  .then((vectors) => {
    const results = window.NullpointCompare.check(window.Nullpoint, vectors);
    const out = document.getElementById("out");
    out.textContent = results.map((r) => (r.ok ? "ok   " : "FAIL ") + r.name + (r.ok ? "" : "  " + r.why)).join("\n")
      + "\n\n" + (results.every((r) => r.ok) ? "All passed." : "Some checks failed.");
  })
  .catch((e) => { document.getElementById("out").textContent = "Could not load vectors.json: " + e; });
