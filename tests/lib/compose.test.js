const test = require("node:test")
const assert = require("node:assert/strict")
const C = require("../../lib/compose.js")
const Settings = require("../../lib/settings.js")

const action = (id, label) => C.entryRow({ id, kind: "action", label, icon: "", action: "run-" + id }, "", "", false)

test("rows always carry every role", () => {
  const r = C.row({ key: "k", label: "L" })
  assert.equal(Object.keys(r).length, 17)
  assert.equal(r.jev, false)
  assert.equal(r.icon, "")
})

test("compose order: answers, lead, results, fallbacks", () => {
  const rows = C.compose({
    answers: C.answerRows([{ value: "178.5", copy: "178.5", detail: "357 ÷ 2" }]),
    lead: [C.urlRow("https://x.com")],
    results: [action("a", "A")],
    fallbacks: [C.agentRow("q")]
  })
  assert.deepEqual(rows.map(r => r.kind), ["answer", "url", "action", "agent"])
  assert.equal(rows[0].copy, "178.5")
})

test("late ✦ row goes after answers/leads and keeps the selected item", () => {
  const rows = [C.row({ key: "search:yt", kind: "web" }), action("a", "A"), action("b", "B"), C.agentRow("q")]
  const selected = "action:b"
  const star = Object.assign(action("c", "C"), { jev: true })
  const out = C.lateInsert(rows, star)
  assert.equal(out.index, 1)
  assert.deepEqual(out.rows.map(r => r.key), ["search:yt", "action:c", "action:a", "action:b", "agent"])
  assert.equal(C.indexOfKey(out.rows, selected), 3)
  assert.equal(C.indexOfKey(rows, selected), 2)
})

test("late ✦ for an existing row marks it without moving anything", () => {
  const rows = [action("a", "A"), action("b", "B")]
  const out = C.lateInsert(rows, Object.assign(action("b", "B"), { jev: true }))
  assert.equal(out.index, -1)
  assert.equal(out.marked, 1)
  assert.deepEqual(out.rows.map(r => r.key), ["action:a", "action:b"])
  assert.equal(out.rows[1].jev, true)
  assert.equal(rows[1].jev, false)
})

test("late answers go on top", () => {
  const rows = [action("a", "A"), C.agentRow("q")]
  const out = C.lateInsert(rows, C.answerRows([{ value: "4", copy: "4" }])[0])
  assert.equal(out.index, 0)
})

test("jev gate", () => {
  const base = { enabled: true, keyAvailable: true, text: "screen warmer", minChars: 3 }
  assert.equal(C.jevWanted(base), true)
  for (const k of ["hasAnswers", "chip", "url", "inlineSearch", "strongLocal"])
    assert.equal(C.jevWanted(Object.assign({}, base, { [k]: true })), false, k)
  assert.equal(C.jevWanted(Object.assign({}, base, { text: "ab" })), false)
  assert.equal(C.jevWanted(Object.assign({}, base, { text: "123" })), false)
  assert.equal(C.jevWanted(Object.assign({}, base, { keyAvailable: false })), false)
  assert.equal(C.jevWanted(Object.assign({}, base, { text: "a".repeat(300) })), false)
})

test("settings merge validates types and bounds", () => {
  const s = Settings.merge({ sources: { units: false, apps: "yes" }, jev: { debounceMs: 5, minChars: "4" },
    calc: { grouping: "weird" }, look: { width: 99999 }, search: { engines: "nope" }, junk: 1 })
  assert.equal(s.sources.units, false)
  assert.equal(s.sources.apps, true)
  assert.equal(s.jev.debounceMs, 100)
  assert.equal(s.jev.minChars, 4)
  assert.equal(s.calc.grouping, "auto")
  assert.equal(s.look.width, 1000)
  assert.deepEqual(s.search.engines, [])
  assert.equal(s.junk, undefined)
  assert.deepEqual(Settings.merge(null), Settings.merge({}))
})

test("settings withValue and findEntry", () => {
  const s = Settings.withValue(Settings.merge({}), "jev.enabled", false)
  assert.equal(s.jev.enabled, false)
  assert.deepEqual(Settings.withValue(s, "nope.path", 1), s)
  assert.deepEqual(Settings.findEntry({ plugins: [{ id: "a" }, { id: "dev.reuk.beam", x: 1 }] }, "dev.reuk.beam"),
    { id: "dev.reuk.beam", x: 1 })
  assert.equal(Settings.findEntry({}, "dev.reuk.beam"), null)
})

test("applyEntry replaces Beam's entry and keeps everything else", () => {
  const before = JSON.stringify({ version: 1, bar: { id: "omarchy.bar" },
    plugins: [{ id: "other", x: 1 }, { id: "dev.reuk.beam", sources: { apps: true } }] }, null, 2) + "\n"
  const next = Settings.merge({ sources: { apps: false } })
  const text = Settings.applyEntry(before, "dev.reuk.beam", next)
  const parsed = JSON.parse(text)
  assert.deepEqual(parsed.bar, { id: "omarchy.bar" })
  assert.deepEqual(parsed.plugins[0], { id: "other", x: 1 })
  assert.equal(parsed.plugins[1].id, "dev.reuk.beam")
  assert.equal(parsed.plugins[1].sources.apps, false)
  assert.ok(text.endsWith("}\n"))
  assert.ok(text.includes('\n  "plugins"'))  // two-space indent, like the shell writes it
})

test("applyEntry refuses to touch an unreadable config or one without Beam's entry", () => {
  const next = Settings.merge({})
  assert.equal(Settings.applyEntry("{ not json", "dev.reuk.beam", next), null)
  assert.equal(Settings.applyEntry(JSON.stringify({ plugins: [] }), "dev.reuk.beam", next), null)
  assert.equal(Settings.applyEntry("", "dev.reuk.beam", next), null)
})

test("rememberRecent puts the pick first, drops its older copy and caps the list", () => {
  const list = [{ key: "app:a" }, { key: "menu:b" }]
  const next = C.rememberRecent(list, C.row({ key: "menu:b", kind: "menu", label: "B" }), 20)
  assert.deepEqual(next.map(r => r.key), ["menu:b", "app:a"])
  assert.equal(next[0].label, "B")
  assert.deepEqual(list.map(r => r.key), ["app:a", "menu:b"])  // input untouched
  let many = []
  for (let i = 0; i < 25; i++) many = C.rememberRecent(many, C.row({ key: "k" + i }), 20)
  assert.equal(many.length, 20)
  assert.equal(many[0].key, "k24")
  assert.deepEqual(C.rememberRecent(null, C.row({ key: "x" }), 20).map(r => r.key), ["x"])
})
