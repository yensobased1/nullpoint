// Node check: the builder's share codes and pixels must match the app (vectors.json is written by the app's
// tests: crosshair/test_builder.py --write). Run: node docs/builder/run_tests.js
"use strict";
const fs = require("fs");
const path = require("path");
const N = require("./nullpoint.js");
const vectors = JSON.parse(fs.readFileSync(path.join(__dirname, "vectors.json"), "utf8"));
const results = require("./compare.js").check(N, vectors);
for (const r of results) console.log((r.ok ? "ok   " : "FAIL ") + r.name + (r.ok ? "" : "  " + r.why));
process.exit(results.every((r) => r.ok) ? 0 : 1);
