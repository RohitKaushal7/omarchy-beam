const test = require("node:test")
const assert = require("node:assert/strict")
const { spawnSync } = require("node:child_process")
const Proc = require("../../lib/proc.js")

function run(argv) {
  const started = Date.now()
  const r = spawnSync(argv[0], argv.slice(1), { encoding: "utf8", maxBuffer: 1 << 24 })
  return { out: r.stdout, code: r.status, ms: Date.now() - started }
}

test("output is cut at the byte limit", () => {
  const r = run(Proc.bounded(["/usr/bin/yes", "abc"], 5, 100))
  assert.equal(r.out.length, 100)
})

test("strict mode fails an oversized result instead of truncating it", () => {
  assert.notEqual(run(Proc.bounded(["/usr/bin/yes", "abc"], 5, 100, true)).code, 0)
  assert.equal(run(Proc.bounded(["/usr/bin/printf", "ok"], 5, 100, true)).out, "ok")
})

test("a hung command and its children end at the deadline", () => {
  const r = run(Proc.bounded(["/bin/bash", "-c", "sleep 30 & sleep 30; wait"], 1, 100))
  assert.ok(r.ms < 4000, `took ${r.ms} ms`)
})

test("arguments are passed as data, never as shell text", () => {
  const r = run(Proc.bounded(["/usr/bin/printf", "%s", "$(echo pwned); `id`"], 5, 100))
  assert.equal(r.out, "$(echo pwned); `id`")
})
