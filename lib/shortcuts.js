// Search shortcuts (keyword or domain + Tab) and URL detection.

var BUILTINS = [
  { keyword: "g", name: "Google", domain: "google.com", url: "https://www.google.com/search?q=%s" },
  { keyword: "gg", name: "Google AI Mode", domain: "", url: "https://www.google.com/search?udm=50&q=%s" },
  { keyword: "yt", name: "YouTube", domain: "youtube.com", url: "https://www.youtube.com/results?search_query=%s" },
  { keyword: "ddg", name: "DuckDuckGo", domain: "duckduckgo.com", url: "https://duckduckgo.com/?q=%s" },
  { keyword: "gh", name: "GitHub", domain: "github.com", url: "https://github.com/search?q=%s&type=repositories" },
  { keyword: "r", name: "Reddit", domain: "reddit.com", url: "https://www.reddit.com/search/?q=%s" },
  { keyword: "maps", name: "Google Maps", domain: "", url: "https://www.google.com/maps/search/%s" },
  { keyword: "aw", name: "Arch Wiki", domain: "wiki.archlinux.org", url: "https://wiki.archlinux.org/index.php?search=%s" },
  { keyword: "aur", name: "AUR", domain: "aur.archlinux.org", url: "https://aur.archlinux.org/packages?K=%s" },
  { keyword: "npm", name: "npm", domain: "npmjs.com", url: "https://www.npmjs.com/search?q=%s" },
  { keyword: "p", name: "Perplexity", domain: "perplexity.ai", url: "https://www.perplexity.ai/search?q=%s" },
  { keyword: "cl", name: "Claude", domain: "claude.ai", url: "https://claude.ai/new?q=%s" },
  { keyword: "x", name: "X", domain: "x.com", url: "https://x.com/search?q=%s" }
]

var TLDS = ("com org net io dev app ai co in uk de fr jp gov edu me tv xyz info biz us ca au so gg sh "
  + "ly to cc page site tech cloud eu nl se no es it ch ru cn br mx kr sg nz ie be at pl pt fi dk cz gr "
  + "ro hu il ae sa tr id my ph vn th pk bd lk np live blog news store shop wiki fyi gl ms tk run").split(" ")

function validEngine(e) {
  return !!e && typeof e.keyword === "string" && /^\S+$/.test(e.keyword)
    && typeof e.url === "string" && /^https?:\/\//.test(e.url) && e.url.indexOf("%s") >= 0
}

// Built-ins minus disabled keywords, then valid custom engines (a custom
// engine with a built-in's keyword replaces it).
function engines(custom, disabled) {
  var off = {}
  var list = Array.isArray(disabled) ? disabled : []
  for (var i = 0; i < list.length; i++) off[String(list[i]).toLowerCase()] = true
  var byKeyword = {}
  var order = []
  var all = BUILTINS.concat(Array.isArray(custom) ? custom : [])
  for (var j = 0; j < all.length; j++) {
    var e = all[j]
    if (!validEngine(e)) continue
    var kw = e.keyword.toLowerCase()
    if (off[kw]) continue
    if (!byKeyword[kw]) order.push(kw)
    byKeyword[kw] = { keyword: kw, name: String(e.name || e.keyword), url: e.url,
      domain: String(e.domain || "").toLowerCase().replace(/^www\./, "") }
  }
  return order.map(function(k) { return byKeyword[k] })
}

function findEngine(list, keyword) {
  var kw = String(keyword || "").toLowerCase()
  for (var i = 0; i < list.length; i++) if (list[i].keyword === kw) return list[i]
  return null
}

// "yt" or "youtube.com" (the whole text) → the engine Tab would turn into a chip.
function chipFor(text, list) {
  var t = String(text || "").trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/$/, "")
  if (!t) return null
  for (var i = 0; i < list.length; i++) {
    if (list[i].keyword === t || (list[i].domain && list[i].domain === t)) return list[i]
  }
  return null
}

// "yt lofi beats" → { engine: YouTube, query: "lofi beats" }; keywords only.
function inlineSearch(text, list) {
  var m = /^(\S+)\s+(\S.*)$/.exec(String(text || "").trim())
  if (!m) return null
  var engine = findEngine(list, m[1])
  return engine ? { engine: engine, query: m[2].trim() } : null
}

function searchUrl(engine, query) {
  return engine.url.split("%s").join(encodeURIComponent(String(query || "").trim()))
}

function detectUrl(text) {
  var t = String(text || "").trim()
  if (!t || /\s/.test(t)) return ""
  if (/^https?:\/\/[^\s/$.?#].\S*$/i.test(t)) return t
  if (/^(localhost|127(?:\.\d{1,3}){3}|\d{1,3}(?:\.\d{1,3}){3})(:\d{1,5})?(\/\S*)?$/i.test(t)) return "http://" + t
  var m = /^([a-z0-9-]+(?:\.[a-z0-9-]+)+)(:\d{1,5})?(\/\S*)?$/i.exec(t)
  if (!m) return ""
  var labels = m[1].toLowerCase().split(".")
  return TLDS.indexOf(labels[labels.length - 1]) >= 0 ? "https://" + t : ""
}

if (typeof module !== "undefined") {
  module.exports = { BUILTINS: BUILTINS, engines: engines, findEngine: findEngine, chipFor: chipFor,
    inlineSearch: inlineSearch, searchUrl: searchUrl, detectUrl: detectUrl }
}
