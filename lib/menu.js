// Omarchy menu data for Beam: JSONC parsing, the menu tree, search scoring and
// guard scripts. The parsing, tree, scoring and guard functions are ported from
// Omarchy's shell/plugins/menu/MenuModel.js (MIT, © Omarchy contributors) so
// Beam finds exactly what the Omarchy menu finds; the rest is Beam's own.

function stripJsonc(raw) {
  return String(raw || "")
    .replace(/^\s*\/\/[^\n]*(\n|$)/gm, "")
    .replace(/,(\s*[}\]])/g, "$1")
}

function normalizeAliases(value) {
  if (Array.isArray(value)) return value.filter(function(v) { return v })
  if (typeof value === "string" && value) return [value]
  return []
}

function normalizeItem(id, raw) {
  var value = raw || {}
  var parent = value.parent
  if (parent === undefined)
    parent = id.indexOf(".") >= 0 ? id.split(".").slice(0, -1).join(".") : "root"
  if (id === "root") parent = ""
  return {
    id: id,
    parent: parent,
    kind: value.action ? "action" : (value.target ? "link" : "menu"),
    icon: value.icon || "",
    iconFont: value.iconFont || "",
    label: value.label || id,
    title: value.title || "",
    target: value.target || "",
    description: value.description || "",
    action: value.action || "",
    provider: value.provider || "",
    aliases: normalizeAliases(value.aliases),
    when: value.when || "",
    checked: value.checked || ""
  }
}

function parseMenuJsonc(raw) {
  var stripped = stripJsonc(raw)
  if (!stripped.trim()) return []
  var parsed
  try {
    parsed = JSON.parse(stripped)
  } catch (e) {
    return []
  }
  if (typeof parsed !== "object" || parsed === null) return []
  var source = (parsed.items && typeof parsed.items === "object" && !Array.isArray(parsed.items))
    ? parsed.items : parsed
  var out = []
  for (var id in source) {
    var entry = source[id]
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) continue
    out.push(normalizeItem(id, entry))
  }
  return out
}

function mergeMenuSources(defaultItems, userItems) {
  var items = ({})
  var order = []
  var sources = [defaultItems || [], userItems || []]
  for (var s = 0; s < sources.length; s++) {
    for (var i = 0; i < sources[s].length; i++) {
      var entry = sources[s][i]
      if (!entry || !entry.id) continue
      if (!items[entry.id]) order.push(entry.id)
      var merged = {}
      var prior = items[entry.id] || {}
      for (var k in prior) merged[k] = prior[k]
      for (var k2 in entry) merged[k2] = entry[k2]
      items[entry.id] = merged
    }
  }
  if (!items.root) {
    items.root = normalizeItem("root", { label: "Go" })
    order.unshift("root")
  }
  for (var j = 0; j < order.length; j++) items[order[j]].order = j
  return { items: items, itemOrder: order }
}

function item(items, id) {
  return items && items[id] ? items[id] : null
}

function depthFor(items, id) {
  var depth = 0
  var current = item(items, id)
  for (var guard = 0; current && current.parent && current.parent !== "root" && guard < 32; guard++) {
    depth += 1
    current = item(items, current.parent)
  }
  return depth
}

function pathFor(items, id) {
  var labels = []
  var current = item(items, id)
  for (var guard = 0; current && current.id !== "root" && guard < 32; guard++) {
    labels.unshift(current.label)
    current = item(items, current.parent)
  }
  return labels.join(" › ")
}

function parentPathFor(items, id) {
  var entry = item(items, id)
  if (!entry || !entry.parent || entry.parent === "root") return ""
  return pathFor(items, entry.parent)
}

function isVisible(items, itemOrder, whenResults, entry, depth) {
  if (!entry) return false
  if (entry.when && whenResults && whenResults[entry.id] === false) return false
  if (entry.kind !== "menu" && entry.kind !== "link") return true
  if (entry.provider) return true
  var guard = depth || 0
  if (guard >= 32) return false
  var target = entry.kind === "link" ? entry.target : entry.id
  for (var i = 0; i < itemOrder.length; i++) {
    var child = item(items, itemOrder[i])
    if (child && child.parent === target && isVisible(items, itemOrder, whenResults, child, guard + 1)) return true
  }
  return false
}

function searchableToken(value) {
  return String(value || "").replace(/[._-]+/g, " ")
}

function leafIdFor(id) {
  var parts = String(id || "").split(".")
  return parts[parts.length - 1]
}

function nameSearchText(entry) {
  var aliases = []
  var values = Array.isArray(entry.aliases) ? entry.aliases : []
  for (var i = 0; i < values.length; i++) aliases.push(searchableToken(values[i]))
  return [entry.label, searchableToken(leafIdFor(entry.id)), aliases.join(" ")].join(" ").toLowerCase()
}

function termInSearchWords(term, text) {
  var words = String(text || "").toLowerCase().split(/\s+/)
  return words.indexOf(term) >= 0
}

function descriptionTextMatches(query, text) {
  var terms = String(query || "").toLowerCase().trim().split(/\s+/)
  for (var i = 0; i < terms.length; i++) {
    if (terms[i] && !termInSearchWords(terms[i], text)) return false
  }
  return true
}

function matchesQuery(entry, query) {
  if (!entry || entry.id === "root") return false
  var nameText = nameSearchText(entry)
  var descriptionText = String(entry.description || "").toLowerCase()
  var terms = String(query || "").toLowerCase().trim().split(/\s+/)
  for (var i = 0; i < terms.length; i++) {
    if (!terms[i]) continue
    if (nameText.indexOf(terms[i]) >= 0) continue
    if (termInSearchWords(terms[i], descriptionText)) continue
    return false
  }
  return true
}

function searchScore(items, entry, query) {
  var needle = String(query || "").toLowerCase().trim()
  var label = String(entry.label || "").toLowerCase()
  var nameText = nameSearchText(entry)
  var descriptionText = String(entry.description || "").toLowerCase()
  var score = 80
  if (label === needle) score = entry.parent === "root" ? 2 : 0
  else if (entry.kind === "app" && label.split(/\s+/).indexOf(needle) >= 0) score = 0
  else if (label.indexOf(needle) === 0) score = 10
  else if (label.indexOf(needle) >= 0) score = 30
  else if (nameText.indexOf(needle) >= 0) score = 40
  else if (descriptionTextMatches(needle, descriptionText)) score = 60
  if (entry.kind === "menu" || entry.kind === "link") score -= 2
  if (entry.kind === "app") score -= 5
  return score * 1000 + depthFor(items, entry.id) * 25 + (entry.order || 0)
}

// Exact or prefix label matches (and whole-word app names) score below this;
// such a match suppresses Jev for the query.
var STRONG_SCORE = 20000

var GUARD_READERS = [
  "omarchy-channel-current", "omarchy-default-agent", "omarchy-default-browser",
  "omarchy-default-editor", "omarchy-default-terminal", "omarchy-dns"
]

function guardHelpers() {
  return 'declare -A __omarchy_pkgs=()\n'
    + 'mapfile -t __omarchy_pkg_names < <({ pacman -Qq; LC_ALL=C pacman -Qi'
    + " | awk '/^[A-Za-z]/ { provides = ($0 ~ /^Provides/); sub(/^[^:]*: /, \"\") }"
    + ' provides && $0 != "None" { n = split($0, p, " ");'
    + ' for (i = 1; i <= n; i++) { sub(/[<>=].*/, "", p[i]); print p[i] } }\'; } 2>/dev/null)\n'
    + 'for __omarchy_pkg in "${__omarchy_pkg_names[@]}"; do __omarchy_pkgs[$__omarchy_pkg]=1; done\n'
    + '__omarchy_pkg_has() { [[ -n ${__omarchy_pkgs[$1]-} ]] && return 0; '
    + '[[ $1 == *[\\<\\>=]* ]] && { pacman -Q "$1" &>/dev/null; return; }; return 1; }\n'
    + 'omarchy-pkg-present() { local p; for p in "$@"; do __omarchy_pkg_has "$p" || return 1; done; return 0; }\n'
    + 'omarchy-pkg-missing() { local p; for p in "$@"; do __omarchy_pkg_has "$p" || return 0; done; return 1; }\n'
    + 'omarchy-cmd-present() { local c; for c in "$@"; do command -v "$c" &>/dev/null || return 1; done; return 0; }\n'
    + 'omarchy-cmd-missing() { local c; for c in "$@"; do command -v "$c" &>/dev/null || return 0; done; return 1; }\n'
}

function guardReaderSlot(index) {
  return "${__omarchy_read_" + index + "}"
}

function substituteGuardReaders(expression) {
  for (var i = 0; i < GUARD_READERS.length; i++)
    expression = expression.split("$(" + GUARD_READERS[i] + ")").join(guardReaderSlot(i))
  return expression
}

function guardLine(id, expression) {
  return "if { " + substituteGuardReaders(expression) + "; } >/dev/null 2>&1; then echo "
    + id + ":w:1; else echo " + id + ":w:0; fi\n"
}

// One bash script answering every `when:` guard as `<id>:w:<0|1>` lines.
// Beam never shows ✓ markers, so `checked:` guards are not evaluated.
function guardScript(items) {
  var guards = ""
  var ids = Object.keys(items || {})
  for (var i = 0; i < ids.length; i++) {
    var entry = items[ids[i]]
    if (entry && entry.when) guards += guardLine(ids[i], entry.when)
  }
  if (!guards) return ""
  var prelude = guardHelpers()
  for (var r = 0; r < GUARD_READERS.length; r++) {
    if (guards.indexOf(guardReaderSlot(r)) < 0) continue
    prelude += "__omarchy_read_" + r + "=$(" + GUARD_READERS[r] + " 2>/dev/null) || :\n"
  }
  return prelude + guards
}

function parseGuardOutput(text) {
  var results = ({})
  var lines = String(text || "").split("\n")
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim()
    var m = /^(.*):w:([01])$/.exec(line)
    if (m) results[m[1]] = m[2] === "1"
  }
  return results
}

// ── Beam additions ──────────────────────────────────────────────────────────

var RISKY_PREFIXES = ["remove.", "system.", "update.", "install."]
var SAFE_IDS = { "system.lock": true, "system.screensaver": true }

function isRisky(entry) {
  if (!entry || entry.kind !== "action" || SAFE_IDS[entry.id]) return false
  for (var i = 0; i < RISKY_PREFIXES.length; i++) {
    if (String(entry.id).indexOf(RISKY_PREFIXES[i]) === 0) return true
  }
  return false
}

// App entries shaped like menu items so one scorer ranks both, as the menu does.
function appItem(app, order) {
  var aliases = app.subtext ? [app.subtext] : []
  if (Array.isArray(app.keywords)) aliases = aliases.concat(app.keywords)
  return {
    id: "apps." + app.id, parent: "apps", kind: "app", icon: "", iconFont: "",
    appIcon: String(app.icon || ""), appId: String(app.id), label: String(app.name || app.id),
    title: "", target: "", description: String(app.subtext || ""), action: "", provider: "",
    aliases: aliases, when: "", checked: "", order: order
  }
}

// App items ordered after the menu's own items, as Omarchy's mergeAppRows does.
// Scores step by 1000 per match tier, so `order` must stay small: baseOrder is
// the menu's item count.
function appItems(apps, baseOrder) {
  var out = []
  var list = Array.isArray(apps) ? apps : []
  for (var i = 0; i < list.length; i++) out.push(appItem(list[i], (baseOrder || 0) + i))
  return out
}

// Visible, searchable entries: actions, submenus and apps (never root, never
// provider submenus' children, which load on demand in the Omarchy menu).
function searchable(items, itemOrder, whenResults) {
  var out = []
  for (var i = 0; i < itemOrder.length; i++) {
    var entry = item(items, itemOrder[i])
    if (!entry || entry.id === "root" || entry.id === "apps") continue
    if (!isVisible(items, itemOrder, whenResults, entry)) continue
    out.push(entry)
  }
  return out
}

function search(items, entries, query, limit) {
  var q = String(query || "").trim()
  if (!q) return []
  var rows = []
  for (var i = 0; i < entries.length; i++) {
    if (!matchesQuery(entries[i], q)) continue
    rows.push({ entry: entries[i], score: searchScore(items, entries[i], q) })
  }
  rows.sort(function(a, b) {
    if (a.score !== b.score) return a.score - b.score
    return String(a.entry.label).localeCompare(String(b.entry.label))
  })
  return limit ? rows.slice(0, limit) : rows
}

// `omarchy menu keybindings --print` lines: "SUPER CTRL + N      → Toggle nightlight"
function parseKeybindings(text) {
  var out = []
  var lines = String(text || "").split("\n")
  for (var i = 0; i < lines.length; i++) {
    var parts = lines[i].split("→")
    if (parts.length < 2) continue
    var keys = parts[0].trim()
    var description = parts.slice(1).join("→").trim()
    if (keys && description) out.push({ keys: keys, description: description })
  }
  return out
}

function prettyKeys(keys) {
  var names = { SUPER: "Super", SHIFT: "Shift", CTRL: "Ctrl", ALT: "Alt" }
  var tokens = String(keys).replace(/\+/g, " ").split(/\s+/).filter(function(t) { return t })
  return tokens.map(function(t) {
    if (names[t]) return names[t]
    return t.length === 1 ? t.toUpperCase() : t.charAt(0) + t.slice(1).toLowerCase()
  }).join("+")
}

function words(text) {
  return String(text || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()
}

// A binding hints a label when its description contains the label as whole
// words and no other binding does. Labels under 4 characters never match.
function hintFor(label, bindings) {
  var needle = words(label)
  if (needle.length < 4) return ""
  var found = ""
  for (var i = 0; i < bindings.length; i++) {
    var hay = " " + words(bindings[i].description) + " "
    if (hay.indexOf(" " + needle + " ") < 0) continue
    if (found) return ""
    found = prettyKeys(bindings[i].keys)
  }
  return found
}

if (typeof module !== "undefined") {
  module.exports = {
    stripJsonc: stripJsonc, parseMenuJsonc: parseMenuJsonc, mergeMenuSources: mergeMenuSources,
    item: item, depthFor: depthFor, pathFor: pathFor, parentPathFor: parentPathFor, isVisible: isVisible,
    matchesQuery: matchesQuery, searchScore: searchScore, STRONG_SCORE: STRONG_SCORE,
    guardScript: guardScript, parseGuardOutput: parseGuardOutput, isRisky: isRisky, appItem: appItem,
    searchable: searchable, search: search, appItems: appItems, parseKeybindings: parseKeybindings, prettyKeys: prettyKeys,
    hintFor: hintFor
  }
}
