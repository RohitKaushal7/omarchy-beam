// Desktop applications for Beam's own app source, used while Omarchy does not
// hand third-party menu plugins its app library (see services/AppSource.qml).
// Mirrors Omarchy's rules: skip NoDisplay entries and the ids hidden by
// launcher.hides or hidden-entries.sh.

function normalizeDesktopId(id) {
  var value = String(id || "").trim()
  if (value.slice(-8) === ".desktop") value = value.slice(0, -8)
  return value
}

function parseIdList(text) {
  var out = ({})
  var lines = String(text || "").split("\n")
  for (var i = 0; i < lines.length; i++) {
    var id = normalizeDesktopId(lines[i])
    if (id) out[id] = true
  }
  return out
}

// [{ entry }] sorted by name, the shape Omarchy's sortedEntries("") returns.
function visibleEntries(values, hidden) {
  var rows = []
  var list = values || []
  for (var i = 0; i < list.length; i++) {
    var entry = list[i]
    if (!entry || entry.noDisplay) continue
    if (hidden && hidden[String(entry.id || "")]) continue
    var name = String(entry.name || "")
    if (!name) continue
    rows.push({ entry: entry, key: name.toLowerCase() })
  }
  rows.sort(function(a, b) { return a.key < b.key ? -1 : (a.key > b.key ? 1 : 0) })
  return rows
}

if (typeof module !== "undefined") {
  module.exports = { normalizeDesktopId: normalizeDesktopId, parseIdList: parseIdList, visibleEntries: visibleEntries }
}
