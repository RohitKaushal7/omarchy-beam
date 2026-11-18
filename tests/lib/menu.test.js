const test = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const Menu = require("../../lib/menu.js")

const OMARCHY = process.env.OMARCHY_PATH || "/usr/share/omarchy"
const DEFAULT_MENU = path.join(OMARCHY, "default/omarchy/omarchy-menu.jsonc")
const hasOmarchy = fs.existsSync(DEFAULT_MENU)

function tree(entries, user) {
  return Menu.mergeMenuSources(Menu.parseMenuJsonc(entries), Menu.parseMenuJsonc(user || ""))
}

const SAMPLE = `{
  // comment
  "trigger": {"icon":"x","label":"Trigger"},
  "trigger.toggle": {"label":"Toggle"},
  "trigger.toggle.nightlight": {"label":"Nightlight","action":"omarchy-toggle-nightlight"},
  "system": {"label":"System"},
  "system.lock": {"label":"Lock","action":"omarchy-system-lock"},
  "system.reboot": {"label":"Reboot","action":"omarchy-system-reboot"},
  "remove": {"label":"Remove"},
  "remove.theme": {"label":"Theme","action":"echo remove"},
  "setup": {"label":"Setup","aliases":["settings"]},
  "setup.hidden": {"label":"Hidden thing","action":"echo hi","when":"false"},
}`

test("parses JSONC with comments and trailing commas", () => {
  const t = tree(SAMPLE)
  assert.equal(t.items["trigger.toggle.nightlight"].kind, "action")
  assert.equal(t.items["trigger.toggle"].parent, "trigger")
  assert.equal(Menu.pathFor(t.items, "trigger.toggle.nightlight"), "Trigger › Toggle › Nightlight")
  assert.equal(Menu.parentPathFor(t.items, "trigger.toggle.nightlight"), "Trigger › Toggle")
})

test("malformed user file keeps the defaults", () => {
  const t = tree(SAMPLE, "{ this is not json")
  assert.ok(t.items["trigger.toggle.nightlight"])
})

test("user entries replace default entries like the Omarchy menu does", () => {
  // Omarchy normalises each user entry before merging, so an override that
  // omits `action` clears it. Beam mirrors that so both show the same rows.
  const t = tree(SAMPLE, `{"trigger.toggle.nightlight": {"label": "Night light", "action": "x"}}`)
  assert.equal(t.items["trigger.toggle.nightlight"].label, "Night light")
  assert.equal(t.items["trigger.toggle.nightlight"].action, "x")
})

test("search ranks exact over prefix over contains", () => {
  const t = tree(SAMPLE)
  const entries = Menu.searchable(t.items, t.itemOrder, {})
  const rows = Menu.search(t.items, entries, "night")
  assert.equal(rows[0].entry.id, "trigger.toggle.nightlight")
  assert.ok(rows[0].score < Menu.STRONG_SCORE)
  const settings = Menu.search(t.items, entries, "settings")
  assert.equal(settings[0].entry.id, "setup")
})

test("when:false hides entries, and guard output parses", () => {
  const t = tree(SAMPLE)
  const guard = Menu.guardScript(t.items)
  const index = guard.ids.indexOf("setup.hidden")
  assert.ok(index >= 0)
  assert.ok(guard.script.includes(`echo ${index}:w:1`))
  const lines = guard.ids.map((id, i) => `${i}:w:${id === "setup.hidden" ? 0 : 1}`).join("\n")
  const guards = Menu.parseGuardOutput(lines + "\n", guard.ids)
  assert.equal(guards["setup.hidden"], false)
  const entries = Menu.searchable(t.items, t.itemOrder, guards)
  assert.ok(!entries.some(e => e.id === "setup.hidden"))
})

test("menu ids never reach the guard script as shell text", () => {
  const t = tree(`{"x": {"label": "X", "action": "true", "when": "true"}}`,
                 `{"a;$(touch /tmp/pwn)": {"label": "Bad", "action": "true", "when": "true"}}`)
  const guard = Menu.guardScript(t.items)
  assert.ok(!guard.script.includes("touch"))
  assert.ok(guard.ids.includes("a;$(touch /tmp/pwn)"))
  const results = Menu.parseGuardOutput(guard.ids.map((_, i) => `${i}:w:1`).join("\n"), guard.ids)
  assert.equal(results["a;$(touch /tmp/pwn)"], true)
  assert.deepEqual(Menu.parseGuardOutput("7:w:1\nnope:w:0\n", guard.ids), {})
})

test("risky actions", () => {
  const t = tree(SAMPLE)
  assert.equal(Menu.isRisky(t.items["system.reboot"]), true)
  assert.equal(Menu.isRisky(t.items["remove.theme"]), true)
  assert.equal(Menu.isRisky(t.items["system.lock"]), false)
  assert.equal(Menu.isRisky(t.items["system"]), false)
  assert.equal(Menu.isRisky(t.items["trigger.toggle.nightlight"]), false)
})

test("apps are ranked with the same scorer", () => {
  const t = tree(SAMPLE)
  const app = Menu.appItem({ id: "chromium.desktop", name: "Chromium", subtext: "Web Browser",
    keywords: ["browser"], icon: "chromium" }, 99)
  const rows = Menu.search(t.items, [app].concat(Menu.searchable(t.items, t.itemOrder, {})), "chrom")
  assert.equal(rows[0].entry.id, "apps.chromium.desktop")
  assert.ok(rows[0].score < Menu.STRONG_SCORE)
  assert.equal(Menu.search(t.items, [app], "browser")[0].entry.appId, "chromium.desktop")
})

test("keybinding hints", () => {
  const binds = Menu.parseKeybindings(
    "SUPER CTRL + N                      → Toggle nightlight\n" +
    "PRINT                               → Screenshot\n" +
    "SUPER + PRINT                       → Color picker\n" +
    "SUPER CTRL + PRINT                  → Extract text (OCR) from screenshot\n")
  assert.equal(binds.length, 4)
  assert.equal(Menu.hintFor("Nightlight", binds), "Super+Ctrl+N")
  assert.equal(Menu.hintFor("Screenshot", binds), "")  // two bindings mention it
  assert.equal(Menu.hintFor("Lock", binds), "")        // too short
  assert.equal(Menu.prettyKeys("SUPER SHIFT CTRL + SPACE"), "Super+Shift+Ctrl+Space")
})

test("real Omarchy menu loads", { skip: !hasOmarchy }, () => {
  const t = tree(fs.readFileSync(DEFAULT_MENU, "utf8"))
  assert.ok(Object.keys(t.items).length > 100)
  const entries = Menu.searchable(t.items, t.itemOrder, {})
  // 4.5 splits the toggle into Nightlight On / Off rows, one per `when:` state.
  assert.match(Menu.search(t.items, entries, "nightlight")[0].entry.id, /^trigger\.toggle\.nightlight(-on|-off)?$/)
  assert.ok(Menu.guardScript(t.items).script.length > 0)
})

test("an app named exactly like the query outranks a same-named menu action", () => {
  const t = tree(SAMPLE + "", `{"setup.defaults.browser.chromium": {"label": "Chromium", "action": "x"}}`)
  const apps = Menu.appItems([{ id: "chromium", name: "Chromium", subtext: "Web Browser", keywords: [], icon: "chromium" }],
                             t.itemOrder.length)
  assert.equal(apps[0].order, t.itemOrder.length)
  const rows = Menu.search(t.items, Menu.searchable(t.items, t.itemOrder, {}).concat(apps), "chromium")
  assert.equal(rows[0].entry.id, "apps.chromium")
})

test("allowedBySources honours the apps and actions toggles", () => {
  const app = Menu.appItem({ id: "slack", name: "Slack" }, 0)
  const action = { id: "trigger.toggle.nightlight", kind: "action" }
  const submenu = { id: "setup", kind: "menu" }
  const both = { apps: true, actions: true }
  assert.equal(Menu.allowedBySources(app, both), true)
  assert.equal(Menu.allowedBySources(app, { apps: false, actions: true }), false)
  assert.equal(Menu.allowedBySources(action, { apps: true, actions: false }), false)
  assert.equal(Menu.allowedBySources(submenu, { apps: true, actions: false }), false)
  assert.equal(Menu.allowedBySources(submenu, { apps: false, actions: true }), true)
})

test("search ignores text beyond 200 characters and stays fast on pasted walls of text", () => {
  const t = tree(SAMPLE)
  const entries = Menu.searchable(t.items, t.itemOrder, {})
  const wall = ("night ").repeat(2000)
  const start = Date.now()
  assert.deepEqual(Menu.search(t.items, entries, wall), [])
  assert.ok(Date.now() - start < 20)
})

test("keybinding hints are never shown for install, remove or update entries", () => {
  assert.equal(Menu.hintAllowed({ id: "style.theme", kind: "action" }), true)
  assert.equal(Menu.hintAllowed({ id: "install.style.theme", kind: "action" }), false)
  assert.equal(Menu.hintAllowed({ id: "remove.theme", kind: "action" }), false)
  assert.equal(Menu.hintAllowed({ id: "update.system", kind: "action" }), false)
  assert.equal(Menu.hintAllowed({ id: "apps.x", kind: "app" }), false)
})

test("Jev only sees apps and everyday actions, not install/remove/update entries", () => {
  assert.equal(Menu.jevEligible({ id: "trigger.toggle.nightlight", kind: "action" }), true)
  assert.equal(Menu.jevEligible({ id: "setup", kind: "menu" }), true)
  assert.equal(Menu.jevEligible(Menu.appItem({ id: "foot", name: "Foot" }, 0)), true)
  assert.equal(Menu.jevEligible({ id: "update.hardware.bluetooth", kind: "action" }), false)
  assert.equal(Menu.jevEligible({ id: "install.style.theme", kind: "action" }), false)
  assert.equal(Menu.jevEligible({ id: "remove.theme", kind: "action" }), false)
  assert.equal(Menu.jevEligible({ id: "update", kind: "menu" }), false)
})

test("recent picks break ties within a score tier, never across tiers", () => {
  const t = tree(`{
    "a": {"label":"A"},
    "a.theme-one": {"label":"Theme one","action":"x"},
    "a.theme-two": {"label":"Theme two","action":"x"},
    "a.my-theme": {"label":"My theme","action":"x"},
  }`)
  const entries = Menu.searchable(t.items, t.itemOrder, {})
  const ids = rows => rows.map(r => r.entry.id)
  // Without recents: prefix matches in menu order, then the contains match.
  assert.deepEqual(ids(Menu.search(t.items, entries, "theme")), ["a.theme-one", "a.theme-two", "a.my-theme"])
  const recent = ["a.my-theme", "a.theme-two"]
  const rankOf = entry => recent.indexOf(entry.id)
  // Theme two was picked recently, so it leads its tier; My theme was picked
  // more recently still, but a contains match never climbs over a prefix one.
  assert.deepEqual(ids(Menu.search(t.items, entries, "theme", 0, rankOf)), ["a.theme-two", "a.theme-one", "a.my-theme"])
  // The more recent of two recents wins inside a tier.
  const both = entry => ["a.theme-one", "a.theme-two"].indexOf(entry.id)
  assert.deepEqual(ids(Menu.search(t.items, entries, "theme", 0, both)).slice(0, 2), ["a.theme-one", "a.theme-two"])
  const flipped = entry => ["a.theme-two", "a.theme-one"].indexOf(entry.id)
  assert.deepEqual(ids(Menu.search(t.items, entries, "theme", 0, flipped)).slice(0, 2), ["a.theme-two", "a.theme-one"])
})

test("disabled: rows that evaluate true leave search, as in the Omarchy menu's search", () => {
  const t = tree(`{
    "install": {"label":"Install"},
    "install.browser": {"label":"Browser"},
    "install.browser.firefox": {"label":"Firefox","disabled":"omarchy-pkg-present firefox","action":"x"},
    "install.browser.zen": {"label":"Zen","when":"omarchy-hw-x86","disabled":"omarchy-pkg-present zen-browser-bin","action":"x"},
  }`)
  assert.equal(t.items["install.browser.firefox"].disabled, "omarchy-pkg-present firefox")
  const guard = Menu.guardScript(t.items)
  const fx = guard.ids.indexOf("install.browser.firefox")
  const zen = guard.ids.indexOf("install.browser.zen")
  assert.ok(fx >= 0 && zen >= 0)
  assert.ok(guard.script.includes(`echo ${fx}:d:1`))
  assert.ok(guard.script.includes(`echo ${zen}:w:1`) && guard.script.includes(`echo ${zen}:d:1`))
  const out = `${fx}:d:1\n${zen}:w:1\n${zen}:d:0\n`
  assert.deepEqual(Menu.parseGuardOutput(out, guard.ids), { "install.browser.zen": true })
  const disabled = Menu.parseGuardOutput(out, guard.ids, "d")
  assert.deepEqual(disabled, { "install.browser.firefox": true, "install.browser.zen": false })
  const entries = Menu.searchable(t.items, t.itemOrder, {}, disabled)
  assert.deepEqual(Menu.search(t.items, entries, "firefox"), [])
  assert.equal(Menu.search(t.items, entries, "zen")[0].entry.id, "install.browser.zen")
  // Before the guards answer, nothing is disabled, as in the menu.
  assert.equal(Menu.search(t.items, Menu.searchable(t.items, t.itemOrder, {}), "firefox").length, 1)
  // The submenu stays, as it does in the menu.
  assert.ok(entries.some(e => e.id === "install.browser"))
})
