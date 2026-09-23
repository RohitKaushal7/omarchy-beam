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

function answerRows(answers) {
  var out = []
  var list = Array.isArray(answers) ? answers : []
  for (var i = 0; i < list.length; i++) {
    var a = list[i] || {}
    out.push(row({ key: "answer:" + i, kind: "answer", icon: "󰃬", label: String(a.value || ""),
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

// Spec §2.2 order: answers, shortcut/url, apps+actions, then fallbacks.
function compose(parts) {
  var p = parts || {}
  return [].concat(p.answers || [], p.lead || [], p.results || [], p.fallbacks || [])
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
  var existing = indexOfKey(rows, newRow.key)
  if (existing >= 0) {
    var marked = rows.slice()
    marked[existing] = row(Object.assign({}, rows[existing], { jev: rows[existing].jev || newRow.jev }))
    return { rows: marked, index: -1, marked: existing }
  }
  var at = insertionIndex(rows, newRow)
  return { rows: rows.slice(0, at).concat([newRow], rows.slice(at)), index: at, marked: -1 }
}

function jevWanted(o) {
  var text = String(o.text || "").trim()
  return !!o.enabled && !!o.keyAvailable && text.length >= (o.minChars || 3) && /[a-z]/i.test(text)
    && !o.hasAnswers && !o.chip && !o.url && !o.inlineSearch && !o.strongLocal && text.length <= 200
}

if (typeof module !== "undefined") {
  module.exports = { row: row, answerRows: answerRows, entryRow: entryRow, shortcutRow: shortcutRow,
    urlRow: urlRow, webRow: webRow, agentRow: agentRow, compose: compose, indexOfKey: indexOfKey,
    insertionIndex: insertionIndex, lateInsert: lateInsert, jevWanted: jevWanted }
}
