// Result rows: one flat shape for the ListModel, list assembly, identity-based
// selection and late insertion (spec §2.5).

var ROW_DEFAULTS = {
  key: "", kind: "", icon: "", iconFont: "", appIcon: "", appId: "", label: "", detail: "",
  hint: "", value: "", copy: "", jev: false, risky: false, action: "", target: "", url: "", pending: false
}

function row(fields) {
  var out = {}
  for (var k in ROW_DEFAULTS) out[k] = fields && fields[k] !== undefined ? fields[k] : ROW_DEFAULTS[k]
  return out
}

// Same glyphs as the matching settings rows.
var ANSWER_ICONS = { calculator: "󰃬", units: "󰑭", currency: "󰇁", time: "󰅐", developer: "󰅩" }

function answerRows(answers) {
  var out = []
  var list = Array.isArray(answers) ? answers : []
  for (var i = 0; i < list.length; i++) {
    var a = list[i] || {}
    out.push(row({ key: "answer:" + i, kind: "answer", icon: ANSWER_ICONS[a.kind] || ANSWER_ICONS.calculator,
      label: String(a.value || ""),
      value: String(a.value || ""), copy: String(a.copy || ""), detail: String(a.detail || ""),
      pending: !!a.pending }))
  }
  return out
}

// entry: a menu item (action/menu/link) or an app item from menu.appItem().
function entryRow(entry, detail, hint, risky) {
  if (entry.kind === "app") {
    return row({ key: "app:" + entry.appId, kind: "app", appIcon: entry.appIcon, appId: entry.appId,
      label: entry.label, detail: entry.description || "" })
  }
  var isMenu = entry.kind === "menu" || entry.kind === "link"
  return row({ key: (isMenu ? "menu:" : "action:") + entry.id, kind: isMenu ? "menu" : "action",
    icon: entry.icon, iconFont: entry.iconFont || "", label: entry.label, detail: detail || "",
    hint: hint || "", risky: !!risky, action: entry.action || "",
    target: entry.kind === "link" ? entry.target : entry.id })
}

function shortcutRow(engine, query) {
  if (!query) {
    return row({ key: "shortcut:" + engine.keyword, kind: "shortcut", icon: "󰍉", url: "",
      label: engine.name, detail: "Press Tab to search " + engine.name, target: engine.keyword })
  }
  return row({ key: "search:" + engine.keyword, kind: "web", icon: "󰍉", label: query,
    detail: "Search " + engine.name, target: engine.keyword, url: "" })
}

function urlRow(url) {
  var shown = url.replace(/^https?:\/\//, "")
  return row({ key: "url:" + url, kind: "url", icon: "󰖟", label: "Open " + shown, detail: url, url: url })
}

function webRow(engine, text) {
  return row({ key: "web", kind: "web", icon: "󰖟", label: "Search " + engine.name + " for “" + text + "”",
    target: engine.keyword })
}

function agentRow(text) {
  return row({ key: "agent", kind: "agent", icon: "󰚩", label: "Ask agent: “" + text + "”" })
}

// Shown above the fallback rows when nothing else matched; never selectable.
function emptyRow(text) {
  return row({ key: "empty", kind: "empty", icon: "󰈉", label: "No matches for “" + text + "”" })
}

function selectable(r) {
  return !!r && r.kind !== "empty"
}

// Spec §2.2 order: answers, shortcut/url, apps+actions, then fallbacks — led by
// a "No matches" row when only the fallbacks are left.
function compose(parts) {
  var p = parts || {}
  var answers = p.answers || [], lead = p.lead || [], results = p.results || [], fallbacks = p.fallbacks || []
  var rows = [].concat(answers, lead, results)
  if (!rows.length && fallbacks.length && p.text) rows.push(emptyRow(p.text))
  return rows.concat(fallbacks)
}

function firstSelectableKey(rows) {
  for (var i = 0; i < rows.length; i++) if (selectable(rows[i])) return rows[i].key
  return ""
}

// Index of the selectable row `delta` rows from `from`: ±1 wraps, bigger
// moves (page) clamp; -1 for none.
function nextSelectable(rows, from, delta) {
  var idx = []
  for (var i = 0; i < rows.length; i++) if (selectable(rows[i])) idx.push(i)
  if (!idx.length) return -1
  var at = idx.indexOf(from)
  if (at < 0) return delta < 0 ? idx[idx.length - 1] : idx[0]
  if (Math.abs(delta) === 1) return idx[(at + delta + idx.length) % idx.length]
  return idx[Math.max(0, Math.min(idx.length - 1, at + delta))]
}

function indexOfKey(rows, key) {
  if (!key) return -1
  for (var i = 0; i < rows.length; i++) if (rows[i].key === key) return i
  return -1
}

// Where a late row goes: answers at the very top, the ✦ row after the leading
// answer/shortcut/url rows.
function insertionIndex(rows, newRow) {
  if (newRow.kind === "answer") {
    var a = 0
    while (a < rows.length && rows[a].kind === "answer") a++
    return a
  }
  var i = 0
  while (i < rows.length && (rows[i].kind === "answer" || rows[i].kind === "shortcut" || rows[i].kind === "url"
         || rows[i].key.indexOf("search:") === 0)) i++
  return i
}

// Late data may only insert (spec rule 2). Returns the new rows and where the
// row went; if the row already exists it is marked instead ({index: -1}).
function lateInsert(rows, newRow) {
  // A real result replaces the "No matches" message.
  var removed = indexOfKey(rows, "empty")
  if (removed >= 0) rows = rows.slice(0, removed).concat(rows.slice(removed + 1))
  var existing = indexOfKey(rows, newRow.key)
  if (existing >= 0) {
    var marked = rows.slice()
    marked[existing] = row(Object.assign({}, rows[existing], { jev: rows[existing].jev || newRow.jev }))
    return { rows: marked, index: -1, marked: existing, removed: removed }
  }
  var at = insertionIndex(rows, newRow)
  return { rows: rows.slice(0, at).concat([newRow], rows.slice(at)), index: at, marked: -1, removed: removed }
}

// The recent-picks list after activating `r`: newest first, no duplicates,
// at most `max`. Mirrors what the helper writes to recent.json.
function rememberRecent(list, r, max) {
  var out = [r]
  var old = Array.isArray(list) ? list : []
  for (var i = 0; i < old.length && out.length < (max || 20); i++) {
    if (old[i] && old[i].key !== r.key) out.push(old[i])
  }
  return out
}

function jevWanted(o) {
  var text = String(o.text || "").trim()
  return !!o.enabled && !!o.keyAvailable && text.length >= (o.minChars || 3) && /[a-z]/i.test(text)
    && !o.hasAnswers && !o.chip && !o.url && !o.inlineSearch && !o.strongLocal && text.length <= 200
}

if (typeof module !== "undefined") {
  module.exports = { row: row, answerRows: answerRows, entryRow: entryRow, shortcutRow: shortcutRow,
    urlRow: urlRow, webRow: webRow, agentRow: agentRow, emptyRow: emptyRow, compose: compose,
    selectable: selectable, firstSelectableKey: firstSelectableKey, nextSelectable: nextSelectable, indexOfKey: indexOfKey,
    insertionIndex: insertionIndex, lateInsert: lateInsert, rememberRecent: rememberRecent,
    jevWanted: jevWanted }
}
