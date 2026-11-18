// What each feature setting accepts and gives, shown under the focused row in
// Beam's settings view.
//
// EXAMPLES is strict JSON (double quotes, no comments or trailing commas):
// tests/test_examples.py reads it as JSON and runs every engine line through
// the real helper, and tests/lib/examples.test.js checks the rest against
// Beam's own code. A line is:
//
//   q        what you type ("" for an empty box)
//   keys     a key pressed after it: ⇥ Tab, ↵ Enter, ⇧↵ Shift+Enter
//   a        what Beam gives
//   note     a dim aside: a condition or the syntax it shows off
//   varies   the result changes with live state ("live rate", "now"); `a` is
//            then representative, and `pattern` is the shape the tests check
//   check    how the tests verify it when the section has no `engine`:
//            "url", "menu", "app", "hint", or "ui" for key behaviour
//
// Engine lines may also carry `copy` (what Enter copies; `a` shows it),
// `rows` (which answer rows `a` joins with " · ", default all), `none` (no
// answer row at all), and `settings`, `locale` or `ans` (the context the line
// assumes, stated in its note).

var EXAMPLES = {
  "sources.calculator": { "engine": "calculator", "lines": [
    { "q": "357/2", "a": "178.5" },
    { "q": "2(3+4)", "a": "14", "note": "implied ×; x, ×, ÷, − work too" },
    { "q": "2^10", "a": "1,024", "note": "or 2**10" },
    { "q": "5!", "a": "120" },
    { "q": "10 mod 3", "a": "1" },
    { "q": "sqrt 2", "a": "1.414213562", "note": "sin cos tan log ln exp abs floor ceil min max" },
    { "q": "round(3.14159, 2)", "a": "3.14" },
    { "q": "2pi", "a": "6.283185307", "note": "pi and e" },
    { "q": "18% of 2400", "a": "432" },
    { "q": "2400 + 18%", "a": "2,832", "note": "or - 18%" },
    { "q": "what % of 2400 is 432", "a": "18%" },
    { "q": "ans * 2", "a": "357", "ans": "178.5", "note": "ans is the last answer you copied" },
    { "q": "555 - 1234", "a": "-679", "note": "spaces mean minus" },
    { "q": "555-1234", "a": "no answer", "none": true, "note": "reads as a phone number" },
    { "q": "357/2", "keys": "↵ / ⇧↵", "a": "copies / pastes 178.5", "copy": "178.5",
      "note": "paste goes to the app you were in" }
  ] },

  "sources.units": { "engine": "units", "lines": [
    { "q": "5 ft in cm", "a": "152.4 cm", "note": "in, to, as, into, →, =" },
    { "q": "5'11\" in cm", "a": "180.34 cm" },
    { "q": "72f to c", "a": "22.22222222°C" },
    { "q": "100 km/h in mph", "a": "62.13711922 mph" },
    { "q": "3.2 GB in MiB", "a": "3,051.757813 MiB" },
    { "q": "2 weeks in days", "a": "14 days" },
    { "q": "6 ft", "a": "1.8288 m · 182.88 cm", "note": "no target: the usual ones" },
    { "q": "1 cup in ml", "a": "236.5882365 ml" },
    { "q": "1 acre in m2", "a": "4,046.856422 m²" },
    { "q": "30 psi in bar", "a": "2.068427188 bar" },
    { "q": "500 kcal in kJ", "a": "2,092 kJ" },
    { "q": "90 deg in rad", "a": "1.570796327 rad" },
    { "q": "5 ft in cm", "keys": "↵", "a": "copies 152.4", "copy": "152.4", "note": "the number, no unit" }
  ] },

  "sources.currency": { "engine": "currency", "lines": [
    { "q": "100 usd in inr", "a": "₹9,351.35", "varies": "live rate", "pattern": "^₹[0-9,]+\\.[0-9]{2}$" },
    { "q": "₹2400 to eur", "a": "€23.33", "varies": "live rate", "pattern": "^€[0-9,]+\\.[0-9]{2}$" },
    { "q": "$50", "a": "₹4,675.67", "varies": "live rate", "pattern": "^₹[0-9,]+\\.[0-9]{2}$",
      "settings": { "calc": { "homeCurrency": "INR" } }, "note": "no target: your home currency, here INR" },
    { "q": "10k inr in usd", "a": "$106.94", "varies": "live rate", "pattern": "^\\$[0-9,]+\\.[0-9]{2}$",
      "note": "k, m, lakh, crore" },
    { "q": "1 lakh inr in usd", "a": "$1,069.36", "varies": "live rate", "pattern": "^\\$[0-9,]+\\.[0-9]{2}$" },
    { "q": "50 bucks in rupees", "a": "₹4,675.67", "varies": "live rate", "pattern": "^₹[0-9,]+\\.[0-9]{2}$",
      "note": "dollars, euros, quid, yen…" },
    { "q": "100 eur in jpy", "a": "¥17,531", "varies": "live rate", "pattern": "^¥[0-9,]+$" },
    { "q": "100 usd in chf", "a": "CHF 84.07", "varies": "live rate", "pattern": "^CHF [0-9,]+\\.[0-9]{2}$" },
    { "q": "100 usd in inr", "keys": "↵", "a": "copies 9351.35", "copy": "9351.35",
      "varies": "live rate", "pattern": "^[0-9]+\\.[0-9]{2}$", "note": "plain digits" }
  ] },

  "sources.time": { "engine": "time", "lines": [
    { "q": "3pm ist in jst", "a": "18:30", "note": "IST, UTC, PST, CET… or a city" },
    { "q": "11pm ist in jst", "a": "02:30 (next day)" },
    { "q": "10:30 utc in ist", "a": "16:00" },
    { "q": "3pm ist in pst", "a": "01:30", "varies": "today's offset", "pattern": "^[0-9]{2}:[0-9]{2}$" },
    { "q": "noon in london", "a": "06:30", "varies": "from your zone", "pattern": "^[0-9]{2}:[0-9]{2}( \\((next|previous) day\\))?$" },
    { "q": "now in tokyo", "a": "04:15 · Thu 19 Nov", "varies": "now",
      "pattern": "^[0-9]{2}:[0-9]{2} · [A-Z][a-z]{2} [0-9]{1,2} [A-Z][a-z]{2}$", "note": "or tokyo time" },
    { "q": "days until dec 25", "a": "36 days", "varies": "from today", "pattern": "^[0-9,]+ days$" },
    { "q": "days since 2026-01-01", "a": "322 days", "varies": "from today", "pattern": "^[0-9,]+ days$" },
    { "q": "today + 90 days", "a": "Wed, 17 Feb 2027", "varies": "from today",
      "pattern": "^[A-Z][a-z]{2}, [0-9]{1,2} [A-Z][a-z]{2} [0-9]{4}$", "note": "± days, weeks, months, years" },
    { "q": "in 3 weeks", "a": "Thu, 10 Dec 2026", "varies": "from today",
      "pattern": "^[A-Z][a-z]{2}, [0-9]{1,2} [A-Z][a-z]{2} [0-9]{4}$" },
    { "q": "what day is 15 aug 2027", "a": "Sunday" },
    { "q": "2026-12-25", "a": "Friday", "note": "a date, not a sum" },
    { "q": "2027-01-01 - 2026-12-25", "a": "7 days" }
  ] },

  "sources.developer": { "engine": "developer", "lines": [
    { "q": "0xff", "a": "255 · 0b11111111 · 0o377", "note": "0x, 0b, 0o" },
    { "q": "255 in bin", "a": "0b11111111 · 0xff · 0o377", "note": "in hex, bin, oct, dec" },
    { "q": "#ff8800", "a": "rgb(255, 136, 0) · hsl(32, 100%, 50%)", "note": "#rgb and #rrggbbaa too" },
    { "q": "rgb(255, 136, 0)", "a": "#ff8800 · hsl(32, 100%, 50%)", "note": "or rgba(…)" },
    { "q": "hsl(32, 100%, 50%)", "a": "#ff8800 · rgb(255, 136, 0)" },
    { "q": "1700000000", "a": "Wed, 15 Nov 2023 · 03:43:20 IST", "rows": [0], "varies": "your zone",
      "pattern": "^[A-Z][a-z]{2}, 1[45] Nov 2023 · [0-9]{2}:[0-9]{2}:20 \\S+$" },
    { "q": "1700000000000", "a": "2023-11-14T22:13:20Z", "rows": [1], "note": "ms too; the UTC row" },
    { "q": "now in unix", "a": "1795029326", "varies": "now", "pattern": "^[0-9]{10}$", "note": "or unix, epoch" },
    { "q": "1536000 bytes", "a": "1.46 MiB · 1.54 MB" }
  ] },

  "sources.apps": { "lines": [
    { "q": "firefox", "a": "Firefox", "check": "app", "app": { "name": "Firefox", "subtext": "Web Browser" },
      "note": "with its icon, if installed" },
    { "q": "fire", "a": "Firefox", "check": "app", "app": { "name": "Firefox", "subtext": "Web Browser" },
      "note": "the start of a name" },
    { "q": "code", "a": "Visual Studio Code", "check": "app", "app": { "name": "Visual Studio Code" },
      "note": "any word of it" },
    { "q": "browser", "a": "Firefox", "check": "app", "app": { "name": "Firefox", "subtext": "Web Browser" },
      "note": "a word of its description" },
    { "q": "firefox", "keys": "↵", "a": "launches it as the Apps menu does", "check": "ui" }
  ] },

  "sources.actions": { "lines": [
    { "q": "lock", "a": "Lock · System", "check": "menu" },
    { "q": "nightlight", "a": "Nightlight On · Trigger › Toggle", "check": "menu",
      "pattern": "^Nightlight (On|Off) · Trigger › Toggle$", "note": "On or Off, whichever applies" },
    { "q": "wallpaper", "a": "Background · Appearance", "check": "menu", "note": "menu aliases work" },
    { "q": "theme", "a": "Theme · Appearance", "check": "menu", "note": "then Install and Remove ones" },
    { "q": "font", "a": "Font · Appearance", "check": "menu", "note": "a submenu: opens it" },
    { "q": "keybindings", "a": "Keybindings · Learn", "check": "menu" },
    { "q": "reboot", "a": "Reboot · System", "check": "menu", "risky": true, "note": "asks for a second ↵" }
  ] },

  "sources.recent": { "lines": [
    { "q": "", "a": "your last 6 picks, newest first", "check": "ui" },
    { "q": "theme", "a": "a recent Theme pick leads the other Theme rows", "check": "ui" },
    { "q": "theme", "a": "a recent Theme Corners pick stays below them", "check": "ui",
      "note": "exact, then prefix, then contains" },
    { "q": "", "a": "apps and actions only; answers are not kept", "check": "ui" }
  ] },

  "sources.shortcuts": { "lines": [] },

  "sources.urls": { "lines": [
    { "q": "github.com/omacom/omarchy", "a": "Open github.com/omacom/omarchy", "check": "url" },
    { "q": "https://omarchy.org/docs", "a": "Open omarchy.org/docs", "check": "url" },
    { "q": "localhost:3000", "a": "Open localhost:3000", "check": "url", "note": "over http" },
    { "q": "192.168.1.1:8080/admin", "a": "Open 192.168.1.1:8080/admin", "check": "url" },
    { "q": "notes.txt", "a": "no URL row", "check": "url", "none": true, "note": "not a known domain ending" },
    { "q": "omarchy.org", "keys": "↵", "a": "opens it in your browser", "check": "ui" }
  ] },

  "sources.webSearchRow": { "lines": [] },
  "sources.agentRow": { "lines": [] },

  "jev.enabled": { "lines": [
    { "q": "screen warmer", "a": "✦ Nightlight", "varies": "Jev's pick", "check": "ui" },
    { "q": "change wallpaper", "a": "✦ Background", "varies": "Jev's pick", "check": "ui" },
    { "q": "nightlight", "a": "no ✦ row: the name already matches", "check": "ui" },
    { "q": "357/2", "a": "no ✦ row for answers, URLs or shortcuts", "check": "ui" },
    { "q": "screen warmer", "keys": "↵", "a": "runs the ✦ row; Jev never runs anything itself", "check": "ui" }
  ] },

  "calc.homeCurrency": { "engine": "currency", "lines": [
    { "q": "$50", "a": "₹4,675.67", "varies": "live rate", "pattern": "^₹[0-9,]+\\.[0-9]{2}$",
      "settings": { "calc": { "homeCurrency": "INR" } }, "note": "INR" },
    { "q": "$50", "a": "€45.46", "varies": "live rate", "pattern": "^€[0-9,]+\\.[0-9]{2}$",
      "settings": { "calc": { "homeCurrency": "EUR" } }, "note": "EUR" },
    { "q": "$50", "a": "€45.46", "varies": "live rate", "pattern": "^€[0-9,]+\\.[0-9]{2}$",
      "locale": "de_DE.UTF-8", "note": "auto, with a German locale" },
    { "q": "₹500", "a": "$5.35", "varies": "live rate", "pattern": "^\\$[0-9,]+\\.[0-9]{2}$",
      "settings": { "calc": { "homeCurrency": "INR" } }, "note": "INR: home money goes to USD" },
    { "q": "$50 in gbp", "a": "£37.88", "varies": "live rate", "pattern": "^£[0-9,]+\\.[0-9]{2}$",
      "settings": { "calc": { "homeCurrency": "INR" } }, "note": "a target you type always wins" }
  ] },

  "calc.grouping": { "engine": "calculator", "lines": [
    { "q": "2500000 / 2", "a": "12,50,000", "settings": { "calc": { "grouping": "indian" } }, "note": "indian" },
    { "q": "2500000 / 2", "a": "1,250,000", "settings": { "calc": { "grouping": "international" } },
      "note": "international" },
    { "q": "2500000 / 2", "a": "12,50,000", "locale": "en_IN.UTF-8", "note": "auto, en_IN locale" },
    { "q": "2500000 / 2", "a": "1,250,000", "note": "auto, other locales" },
    { "q": "1000000 usd in inr", "a": "₹9,35,13,494.00", "kind": "currency", "varies": "live rate",
      "pattern": "^₹[0-9]{1,2}(,[0-9]{2})*,[0-9]{3}\\.[0-9]{2}$", "note": "auto: rupees always Indian" }
  ] },

  "calc.significantDigits": { "engine": "calculator", "lines": [
    { "q": "1/3", "a": "0.333", "settings": { "calc": { "significantDigits": 3 } }, "note": "3" },
    { "q": "1/3", "a": "0.3333333333", "settings": { "calc": { "significantDigits": 10 } }, "note": "10" },
    { "q": "1/3", "a": "0.33333333333333333333", "settings": { "calc": { "significantDigits": 20 } }, "note": "20" },
    { "q": "2^64", "a": "1.844674407e+19", "settings": { "calc": { "significantDigits": 10 } },
      "note": "10: big numbers go scientific" },
    { "q": "72f to c", "a": "22.2°C", "kind": "units", "settings": { "calc": { "significantDigits": 3 } },
      "note": "3: units too" }
  ] },

  "search.fallbackEngine": { "lines": [] },

  "behavior.confirmRisky": { "lines": [
    { "q": "reboot", "keys": "↵", "a": "Press Enter again to Reboot", "check": "risky", "risky": true,
      "note": "system, remove, update, install" },
    { "q": "lock", "keys": "↵", "a": "locks at once", "check": "risky", "risky": false,
      "note": "Lock and Screensaver are safe" },
    { "q": "reboot", "keys": "↵ ↑", "a": "moving away cancels it", "check": "ui" }
  ] },

  "behavior.keybindingHints": { "lines": [
    { "q": "lock", "a": "Lock · System  Super+Ctrl+L", "check": "hint", "varies": "your bindings",
      "entry": { "id": "system.lock", "label": "Lock" }, "hint": "Super+Ctrl+L",
      "bindings": ["SUPER CTRL + L → Lock system"] },
    { "q": "emoji", "a": "Emoji · Trigger  Super+Period", "check": "hint", "varies": "your bindings",
      "entry": { "id": "trigger.emoji", "label": "Emoji" }, "hint": "Super+Period",
      "bindings": ["SUPER + PERIOD → Emoji picker"] },
    { "q": "theme", "a": "no hint", "check": "hint", "note": "two bindings mention Theme",
      "entry": { "id": "appearance.theme", "label": "Theme" }, "hint": "",
      "bindings": ["SUPER CTRL + T → Theme menu", "SUPER SHIFT CTRL + SPACE → Theme menu"] },
    { "q": "theme", "a": "Theme · Install › Style: no hint", "check": "hint", "note": "never on install, remove, update rows",
      "entry": { "id": "install.style.theme", "label": "Theme" }, "hint": "",
      "bindings": ["SUPER CTRL + T → Theme"] }
  ] },

  "behavior.agentCommand": { "lines": [] }
}

// ── lines built from live settings ──────────────────────────────────────────

function _engineFor(engines, keyword) {
  var kw = String(keyword || "").toLowerCase()
  for (var i = 0; i < engines.length; i++) if (engines[i].keyword === kw) return engines[i]
  return null
}

// The row Beam's web search fallback uses: the configured engine, else the first.
function _fallback(settings, engines) {
  var search = settings && settings.search ? settings.search : {}
  return _engineFor(engines, search.fallbackEngine) || engines[0] || null
}

function _agentArgv(settings) {
  var behavior = settings && settings.behavior ? settings.behavior : {}
  return String(behavior.agentCommand || "").trim().split(/\s+/).filter(function(w) { return w })
}

function _shortcutLines(settings, engines, builtins) {
  var lines = []
  var sample = _engineFor(engines, "yt") || engines[0]
  if (sample) {
    lines.push({ q: sample.keyword, keys: "⇥", a: sample.name + " chip; then type your search", check: "chip" })
    if (sample.domain) lines.push({ q: sample.domain, keys: "⇥", a: "the same chip, by its domain", check: "chip" })
    lines.push({ q: sample.keyword + " lofi beats", a: "lofi beats · Search " + sample.name, check: "inline",
      note: "keyword, space, search" })
  }
  var builtinKeywords = {}
  var list = Array.isArray(builtins) ? builtins : []
  for (var b = 0; b < list.length; b++) builtinKeywords[list[b].keyword] = list[b]
  for (var i = 0; i < engines.length; i++) {
    var e = engines[i]
    var builtin = builtinKeywords[e.keyword]
    var custom = !builtin || builtin.name !== e.name || builtin.url !== e.url
    lines.push({ q: e.keyword + " …", a: e.name, check: "inline", keyword: e.keyword,
      note: custom ? "yours" : "" })
  }
  var search = settings && settings.search ? settings.search : {}
  var off = Array.isArray(search.disabledBuiltins) ? search.disabledBuiltins : []
  for (var j = 0; j < off.length; j++) {
    var gone = builtinKeywords[String(off[j]).toLowerCase()]
    if (gone && !_engineFor(engines, gone.keyword)) {
      lines.push({ q: gone.keyword + " …", a: gone.name, check: "disabled", keyword: gone.keyword,
        note: "turned off in disabledBuiltins", off: true })
    }
  }
  return lines
}

function _webLines(settings, engines) {
  var engine = _fallback(settings, engines)
  if (!engine) return [{ q: "best ramen", a: "no row: no search engine is set up", check: "ui" }]
  return [
    { q: "best ramen", a: "Search " + engine.name + " for “best ramen”", check: "web", note: "after the results" },
    { q: "best ramen", keys: "↵", a: "opens that search in your browser", check: "ui" },
    { q: "qwzx", a: "No matches for “qwzx”, then this row", check: "ui" },
    { q: "357/2", a: "still offered, below the answer", check: "ui" }
  ]
}

function _agentLines(settings) {
  var argv = _agentArgv(settings)
  var lines = [{ q: "fix my wifi", a: "Ask agent: “fix my wifi”", check: "agent", note: "the last row" },
    { q: "357/2", a: "still offered, after everything else", check: "ui" }]
  if (argv.length) {
    lines.push({ q: "fix my wifi", keys: "↵", a: "runs " + argv.join(" ") + " \"fix my wifi\"", check: "agentRun",
      note: "your text is one argument" })
  }
  return lines
}

function _fallbackLines(settings, engines) {
  var lines = _webLines(settings, engines).slice(0, 2)
  var search = settings && settings.search ? settings.search : {}
  var wanted = String(search.fallbackEngine || "")
  if (!_engineFor(engines, wanted) && engines.length) {
    lines.push({ q: wanted || "(empty)", a: "not a shortcut keyword, so " + engines[0].name + " is used",
      check: "ui" })
  }
  var keywords = engines.map(function(e) { return e.keyword })
  if (keywords.length) lines.push({ q: "any of", a: keywords.join(" "), check: "ui", note: "shortcut keywords" })
  return lines
}

function _jevLines(settings) {
  var jev = settings && settings.jev ? settings.jev : {}
  var lines = EXAMPLES["jev.enabled"].lines.slice()
  lines.splice(2, 0, { q: "screen warmer", a: "asks after a " + (jev.debounceMs || 350) + " ms pause",
    check: "ui", note: (jev.minChars || 3) + "+ characters, only when nothing matches well" })
  return lines
}

// The lines to show under `path`, or [] for settings that are not features.
// `engines` is Shortcuts.engines(...) for the live settings; `builtins` is
// Shortcuts.BUILTINS, so turned-off built-ins can still be listed.
function forPath(path, settings, engines, builtins) {
  var list = Array.isArray(engines) ? engines : []
  if (path === "sources.shortcuts") return _shortcutLines(settings, list, builtins)
  if (path === "sources.webSearchRow") return _webLines(settings, list)
  if (path === "sources.agentRow" || path === "behavior.agentCommand") return _agentLines(settings)
  if (path === "search.fallbackEngine") return _fallbackLines(settings, list)
  if (path === "jev.enabled") return _jevLines(settings)
  var section = EXAMPLES[path]
  return section ? section.lines : []
}

// Display text for a line's query column and its dim aside.
function queryText(line) {
  var q = line.q === "" ? "(nothing typed)" : String(line.q || "")
  return line.keys ? q + " " + line.keys : q
}

function noteText(line) {
  var parts = []
  if (line.varies) parts.push(line.varies)
  if (line.note) parts.push(line.note)
  return parts.length ? "(" + parts.join(" · ") + ")" : ""
}

if (typeof module !== "undefined") {
  module.exports = { EXAMPLES: EXAMPLES, forPath: forPath, queryText: queryText, noteText: noteText }
}
