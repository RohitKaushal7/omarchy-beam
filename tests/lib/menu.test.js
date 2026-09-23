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
  const guards = Menu.parseGuardOutput("setup.hidden:w:0\nsystem.lock:w:1\n")
  assert.deepEqual(guards, { "setup.hidden": false, "system.lock": true })
  const entries = Menu.searchable(t.items, t.itemOrder, guards)
  assert.ok(!entries.some(e => e.id === "setup.hidden"))
  assert.ok(Menu.guardScript(t.items).includes("setup.hidden:w:1"))
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
  assert.equal(Menu.search(t.items, entries, "nightlight")[0].entry.id, "trigger.toggle.nightlight")
  assert.ok(Menu.guardScript(t.items).length > 0)
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
