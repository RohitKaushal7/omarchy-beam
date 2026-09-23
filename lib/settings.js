// Beam settings: defaults, validation and the shell.json entry shape.

var DEFAULTS = {
  sources: { apps: true, actions: true, recent: true, calculator: true, units: true, currency: true,
    time: true, developer: true, shortcuts: true, urls: true, webSearchRow: true, agentRow: true },
  jev: { enabled: true, debounceMs: 350, minChars: 3, keyFile: "~/.config/typesafe/api_key", cacheSize: 500 },
  calc: { homeCurrency: "auto", grouping: "auto", significantDigits: 10, ratesRefreshHours: 24 },
  search: { fallbackEngine: "g", engines: [], disabledBuiltins: [] },
  behavior: { confirmRisky: true, keybindingHints: true, agentCommand: "omarchy agent prompt" },
  engine: { idleExitMinutes: 10 },
  look: { width: 560, maxRows: 8 }
}

var BOUNDS = {
  "jev.debounceMs": [100, 2000], "jev.minChars": [1, 20], "jev.cacheSize": [0, 10000],
  "calc.significantDigits": [3, 20], "calc.ratesRefreshHours": [1, 720],
  "engine.idleExitMinutes": [1, 1440], "look.width": [400, 1000], "look.maxRows": [3, 20]
}

var CHOICES = { "calc.grouping": ["auto", "indian", "international"] }

function clone(v) {
  return JSON.parse(JSON.stringify(v))
}

function coerce(path, fallback, value) {
  if (value === undefined || value === null) return fallback
  if (typeof fallback === "boolean") return typeof value === "boolean" ? value : fallback
  if (typeof fallback === "number") {
    // Only real numbers or numeric strings; "", " ", [] and booleans would
    // otherwise coerce to 0/1 and clamp to a bound instead of the default.
    var numeric = typeof value === "number" || (typeof value === "string" && /^\s*-?\d+(\.\d+)?\s*$/.test(value))
    var n = Number(value)
    if (!numeric || !isFinite(n)) return fallback
    var b = BOUNDS[path]
    n = Math.round(n)
    return b ? Math.max(b[0], Math.min(b[1], n)) : n
  }
  if (Array.isArray(fallback)) return Array.isArray(value) ? clone(value) : clone(fallback)
  if (typeof fallback === "string") {
    if (typeof value !== "string" || !value.trim()) return fallback
    if (CHOICES[path] && CHOICES[path].indexOf(value) < 0) return fallback
    return value
  }
  return fallback
}

// Settings from Beam's shell.json entry; anything missing or invalid → default.
function merge(entry) {
  var src = entry && typeof entry === "object" ? entry : {}
  var out = {}
  for (var group in DEFAULTS) {
    var g = src[group] && typeof src[group] === "object" && !Array.isArray(src[group]) ? src[group] : {}
    out[group] = {}
    for (var key in DEFAULTS[group]) out[group][key] = coerce(group + "." + key, clone(DEFAULTS[group][key]), g[key])
  }
  return out
}

// A copy of `settings` with one dotted path changed, re-validated.
function withValue(settings, path, value) {
  var next = clone(settings)
  var parts = String(path).split(".")
  if (parts.length !== 2 || !(parts[0] in DEFAULTS) || !(parts[1] in DEFAULTS[parts[0]])) return merge(next)
  next[parts[0]][parts[1]] = value
  return merge(next)
}

function findEntry(shellConfig, id) {
  var plugins = shellConfig && Array.isArray(shellConfig.plugins) ? shellConfig.plugins : []
  for (var i = 0; i < plugins.length; i++) if (plugins[i] && plugins[i].id === id) return plugins[i]
  return null
}

// shell.json text with Beam's entry replaced by {id, ...settings}, formatted
// the way omarchy-shell writes it; null when the file cannot be read or has no
// entry for `id` (a third-party plugin is enabled only while its entry exists,
// so Beam never adds one).
function applyEntry(configText, id, settings) {
  var config
  try { config = JSON.parse(String(configText || "")) } catch (e) { return null }
  if (!config || typeof config !== "object" || !Array.isArray(config.plugins)) return null
  var found = false
  for (var i = 0; i < config.plugins.length; i++) {
    if (!config.plugins[i] || config.plugins[i].id !== id) continue
    var entry = { id: id }
    for (var k in settings) if (k !== "id") entry[k] = clone(settings[k])
    config.plugins[i] = entry
    found = true
  }
  return found ? JSON.stringify(config, null, 2) + "\n" : null
}

// ── settings view ─────────────────────────────────────────────────────────

// Sections → one flat row list: a header row, then that section's fields.
function flattenSections(sections) {
  var rows = []
  for (var i = 0; i < sections.length; i++) {
    rows.push({ type: "header", title: sections[i].title, icon: sections[i].icon || "" })
    for (var j = 0; j < sections[i].items.length; j++) rows.push(sections[i].items[j])
  }
  return rows
}

// Index of the field `delta` fields away from `from` (headers skipped).
// ±1 wraps; bigger moves (page) clamp to the first or last field.
function nextField(rows, from, delta) {
  var fields = []
  for (var i = 0; i < rows.length; i++) if (rows[i].type !== "header") fields.push(i)
  if (!fields.length) return -1
  var at = fields.indexOf(from)
  if (at < 0) return delta < 0 ? fields[fields.length - 1] : fields[0]
  if (Math.abs(delta) === 1) return fields[(at + delta + fields.length) % fields.length]
  return fields[Math.max(0, Math.min(fields.length - 1, at + delta))]
}

// The value after pressing ←/→ `delta` times on a field.
function stepValue(spec, current, delta) {
  if (spec.type === "bool") return !current
  if (spec.type === "choice") {
    var options = spec.options || []
    var at = options.indexOf(current)
    if (at < 0) return options[0]
    return options[((at + delta) % options.length + options.length) % options.length]
  }
  if (spec.type === "int") {
    var n = Number(current) + delta * (spec.step || 1)
    return Math.max(spec.from, Math.min(spec.to, n))
  }
  return current
}

if (typeof module !== "undefined") {
  module.exports = { DEFAULTS: DEFAULTS, merge: merge, withValue: withValue, findEntry: findEntry,
    applyEntry: applyEntry, flattenSections: flattenSections, nextField: nextField, stepValue: stepValue }
}
