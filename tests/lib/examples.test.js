const test = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const Examples = require("../../lib/examples.js")
const Settings = require("../../lib/settings.js")
const S = require("../../lib/shortcuts.js")
const Compose = require("../../lib/compose.js")
const Menu = require("../../lib/menu.js")
const P = require("../../lib/precheck.js")

const OMARCHY = process.env.OMARCHY_PATH || "/usr/share/omarchy"
const DEFAULT_MENU = path.join(OMARCHY, "default/omarchy/omarchy-menu.jsonc")
const hasOmarchy = fs.existsSync(DEFAULT_MENU)

// Feature settings get examples; tuning knobs (timings, sizes, paths) do not.
const FEATURES = ["sources.apps", "sources.actions", "sources.recent", "sources.calculator", "sources.units",
  "sources.currency", "sources.time", "sources.developer", "sources.shortcuts", "sources.urls",
  "sources.webSearchRow", "sources.agentRow", "jev.enabled", "calc.homeCurrency", "calc.grouping",
  "calc.significantDigits", "search.fallbackEngine", "behavior.confirmRisky", "behavior.keybindingHints",
  "behavior.agentCommand"]
const CHECKS = ["ui", "url", "menu", "risky", "app", "hint", "chip", "inline", "disabled", "web", "agent", "agentRun"]

const DEFAULT_SETTINGS = Settings.merge({})
const CUSTOM_SETTINGS = Settings.merge({
  search: { fallbackEngine: "ddg", disabledBuiltins: ["x", "r"],
            engines: [{ keyword: "amz", name: "Amazon", url: "https://www.amazon.in/s?k=%s" },
                      { keyword: "g", name: "Kagi", url: "https://kagi.com/search?q=%s" }] },
  behavior: { agentCommand: "claude -p" }
})

function enginesFor(settings) {
  return S.engines(settings.search.engines, settings.search.disabledBuiltins)
}

function linesFor(p, settings) {
  return Examples.forPath(p, settings, enginesFor(settings), S.BUILTINS)
}

function eachLine(settings, fn) {
  for (const p of FEATURES) for (const line of linesFor(p, settings)) fn(p, line)
}

test("EXAMPLES is strict JSON, so the Python test reads the same data", () => {
  const text = fs.readFileSync(path.join(__dirname, "../../lib/examples.js"), "utf8")
  const m = /^var EXAMPLES = (\{[\s\S]*?^\})$/m.exec(text)
  assert.ok(m)
  assert.deepEqual(JSON.parse(m[1]), Examples.EXAMPLES)
})

test("every feature setting, and only those, has examples", () => {
  assert.deepEqual(Object.keys(Examples.EXAMPLES).sort(), FEATURES.slice().sort())
  for (const p of FEATURES) {
    const [group, key] = p.split(".")
    assert.ok(key in Settings.DEFAULTS[group], p)
    const n = linesFor(p, DEFAULT_SETTINGS).length
    assert.ok(n >= 3 && n <= 20, `${p} has ${n} lines`)
  }
  for (const p of ["look.width", "look.maxRows", "jev.debounceMs", "jev.minChars", "jev.cacheSize", "jev.keyFile",
                   "calc.ratesRefreshHours", "engine.idleExitMinutes"]) {
    assert.deepEqual(Examples.forPath(p, DEFAULT_SETTINGS, enginesFor(DEFAULT_SETTINGS), S.BUILTINS), [], p)
  }
})

test("every line says how it is checked", () => {
  for (const [p, section] of Object.entries(Examples.EXAMPLES)) {
    for (const line of section.lines) {
      if (section.engine) assert.ok(!line.check || line.check === "ui", `${p}: ${line.q}`)
      else assert.ok(CHECKS.includes(line.check), `${p}: ${line.q} has check ${line.check}`)
    }
  }
  for (const settings of [DEFAULT_SETTINGS, CUSTOM_SETTINGS]) {
    eachLine(settings, (p, line) => {
      assert.equal(typeof line.q, "string", p)
      assert.ok(String(line.a).length > 0, `${p}: ${line.q}`)
      if (!Examples.EXAMPLES[p].engine) assert.ok(CHECKS.includes(line.check), `${p}: ${line.q}`)
    })
  }
})

test("Beam asks the helper for every engine example (the precheck lets it through)", () => {
  for (const [p, section] of Object.entries(Examples.EXAMPLES)) {
    if (!section.engine) continue
    for (const line of section.lines) {
      if (line.none) continue
      assert.ok(P.mayBeAnswer(line.q), `${p}: ${line.q}`)
      assert.equal(S.inlineSearch(line.q, enginesFor(DEFAULT_SETTINGS)), null, `${p}: ${line.q} reads as a shortcut`)
    }
  }
})

test("URL examples match Beam's URL row", () => {
  for (const line of Examples.EXAMPLES["sources.urls"].lines) {
    if (line.check !== "url") continue
    const url = S.detectUrl(line.q)
    if (line.none) assert.equal(url, "", line.q)
    else assert.equal(Compose.urlRow(url).label, line.a, line.q)
  }
})

test("app examples match the way Beam ranks apps", () => {
  for (const line of Examples.EXAMPLES["sources.apps"].lines) {
    if (line.check !== "app") continue
    const entry = Menu.appItem(Object.assign({ id: "fixture" }, line.app), 0)
    const found = Menu.search({}, [entry], line.q)
    assert.equal(found.length, 1, line.q)
    assert.equal(found[0].entry.label, line.a, line.q)
  }
})

test("action examples match the real Omarchy menu", { skip: !hasOmarchy }, () => {
  const t = Menu.mergeMenuSources(Menu.parseMenuJsonc(fs.readFileSync(DEFAULT_MENU, "utf8")), Menu.parseMenuJsonc(""))
  const entries = Menu.searchable(t.items, t.itemOrder, {})
  const lines = Examples.EXAMPLES["sources.actions"].lines.concat(Examples.EXAMPLES["behavior.confirmRisky"].lines)
  for (const line of lines) {
    if (line.check !== "menu" && line.check !== "risky") continue
    const top = Menu.search(t.items, entries, line.q)[0]
    assert.ok(top, line.q)
    assert.equal(Menu.isRisky(top.entry), !!line.risky, `${line.q} risky`)
    if (line.check === "risky") {
      if (line.risky) assert.equal(line.a, "Press Enter again to " + top.entry.label)  // ResultRow's text
      continue
    }
    const shown = top.entry.label + " · " + Menu.parentPathFor(t.items, top.entry.id)
    if (line.pattern) assert.match(shown, new RegExp(line.pattern), line.q)
    else assert.equal(shown, line.a, line.q)
  }
})

test("keybinding hint examples match Beam's hint rules", () => {
  for (const line of Examples.EXAMPLES["behavior.keybindingHints"].lines) {
    const entry = Object.assign({ kind: "action" }, line.entry)
    const hint = Menu.hintAllowed(entry) ? Menu.hintFor(entry.label, Menu.parseKeybindings(line.bindings.join("\n"))) : ""
    assert.equal(hint, line.hint, line.q)
    if (hint) assert.ok(line.a.endsWith(hint), line.q)
  }
})

for (const [name, settings] of [["default", DEFAULT_SETTINGS], ["custom", CUSTOM_SETTINGS]]) {
  test(`shortcut, web and agent examples follow the ${name} settings`, () => {
    const engines = enginesFor(settings)
    const fallback = S.findEngine(engines, settings.search.fallbackEngine) || engines[0]  // as Beam.qml picks it
    eachLine(settings, (p, line) => {
      const where = `${p}: ${line.q}`
      if (line.check === "chip") {
        const chip = S.chipFor(line.q, engines)
        assert.ok(chip, where)
        assert.ok(line.a.indexOf(chip.name) >= 0 || line.a.indexOf("same chip") >= 0, where)
      } else if (line.check === "inline" && line.keyword) {
        assert.equal(S.inlineSearch(line.keyword + " cats", engines).engine.name, line.a, where)
      } else if (line.check === "inline") {
        const hit = S.inlineSearch(line.q, engines)
        const r = Compose.shortcutRow(hit.engine, hit.query)
        assert.equal(r.label + " · " + r.detail, line.a, where)
      } else if (line.check === "disabled") {
        assert.equal(S.inlineSearch(line.keyword + " cats", engines), null, where)
        assert.equal(S.chipFor(line.keyword, engines), null, where)
      } else if (line.check === "web") {
        assert.equal(Compose.webRow(fallback, line.q).label, line.a, where)
      } else if (line.check === "agent") {
        assert.equal(Compose.agentRow(line.q).label, line.a, where)
      } else if (line.check === "agentRun") {
        const argv = String(settings.behavior.agentCommand).trim().split(/\s+/).concat([line.q])  // as Beam.qml runs it
        assert.equal(line.a, "runs " + argv.slice(0, -1).join(" ") + " \"" + argv[argv.length - 1] + "\"", where)
      }
    })
  })
}

test("search shortcut examples list every live engine and the turned-off built-ins", () => {
  const lines = linesFor("sources.shortcuts", CUSTOM_SETTINGS)
  const listed = lines.filter(l => l.keyword && !l.off).map(l => l.keyword)
  assert.deepEqual(listed, enginesFor(CUSTOM_SETTINGS).map(e => e.keyword))
  assert.deepEqual(lines.filter(l => l.off).map(l => l.keyword), ["x", "r"])
  assert.equal(lines.find(l => l.keyword === "g").a, "Kagi")
  assert.equal(lines.find(l => l.keyword === "g").note, "yours")
  assert.equal(lines.find(l => l.keyword === "amz").note, "yours")
  assert.equal(lines.find(l => l.keyword === "yt").note, "")
  const def = linesFor("sources.shortcuts", DEFAULT_SETTINGS)
  assert.equal(def.filter(l => l.keyword).length, S.BUILTINS.length)
  assert.equal(def.filter(l => l.off).length, 0)
})

test("the web search row example names the configured engine", () => {
  assert.equal(linesFor("sources.webSearchRow", DEFAULT_SETTINGS)[0].a, "Search Google for “best ramen”")
  assert.equal(linesFor("sources.webSearchRow", CUSTOM_SETTINGS)[0].a, "Search DuckDuckGo for “best ramen”")
  const unknown = Settings.withValue(DEFAULT_SETTINGS, "search.fallbackEngine", "nope")
  const lines = linesFor("search.fallbackEngine", unknown)
  assert.equal(lines[0].a, "Search Google for “best ramen”")
  assert.ok(lines.some(l => /not a shortcut keyword, so Google is used/.test(l.a)))
})

test("Jev examples quote the live pause and minimum length", () => {
  const s = Settings.withValue(Settings.withValue(DEFAULT_SETTINGS, "jev.debounceMs", 500), "jev.minChars", 4)
  const lines = linesFor("jev.enabled", s)
  assert.ok(lines.some(l => /500 ms pause/.test(l.a) && /^4\+ characters/.test(l.note)))
  assert.equal(Examples.EXAMPLES["jev.enabled"].lines.length + 1, lines.length)  // the data is not mutated
})

test("display helpers", () => {
  assert.equal(Examples.queryText({ q: "yt", keys: "⇥" }), "yt ⇥")
  assert.equal(Examples.queryText({ q: "" }), "(nothing typed)")
  assert.equal(Examples.noteText({ varies: "live rate", note: "k, m" }), "(live rate · k, m)")
  assert.equal(Examples.noteText({}), "")
})
