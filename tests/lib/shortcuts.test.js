const test = require("node:test")
const assert = require("node:assert/strict")
const S = require("../../lib/shortcuts.js")
const P = require("../../lib/precheck.js")

const ENGINES = S.engines([], [])

test("keyword and domain chips", () => {
  assert.equal(S.chipFor("yt", ENGINES).name, "YouTube")
  assert.equal(S.chipFor("YouTube.com", ENGINES).name, "YouTube")
  assert.equal(S.chipFor("https://www.youtube.com/", ENGINES).name, "YouTube")
  assert.equal(S.chipFor("gg", ENGINES).name, "Google AI Mode")
  assert.equal(S.chipFor("youtube", ENGINES), null)
  assert.equal(S.chipFor("", ENGINES), null)
})

test("inline search needs an exact keyword", () => {
  assert.deepEqual(S.inlineSearch("yt lofi beats", ENGINES).query, "lofi beats")
  assert.equal(S.inlineSearch("gg  what is omarchy ", ENGINES).engine.keyword, "gg")
  assert.equal(S.inlineSearch("ytt lofi", ENGINES), null)
  assert.equal(S.inlineSearch("yt", ENGINES), null)
  assert.equal(S.inlineSearch("firefox dev", ENGINES), null)
})

test("search urls are encoded", () => {
  const yt = S.findEngine(ENGINES, "yt")
  assert.equal(S.searchUrl(yt, "lofi & chill"), "https://www.youtube.com/results?search_query=lofi%20%26%20chill")
  assert.equal(S.searchUrl(S.findEngine(ENGINES, "gg"), "what is ai?"),
    "https://www.google.com/search?udm=50&q=what%20is%20ai%3F")
})

test("custom engines override, disabled builtins vanish, invalid ones are ignored", () => {
  const list = S.engines([
    { keyword: "amz", name: "Amazon", url: "https://www.amazon.in/s?k=%s" },
    { keyword: "g", name: "Kagi", url: "https://kagi.com/search?q=%s" },
    { keyword: "bad one", url: "https://x/%s" },
    { keyword: "nourl", url: "ftp://x/%s" },
    { keyword: "nos", url: "https://x/" }
  ], ["x", "R"])
  assert.equal(S.findEngine(list, "amz").name, "Amazon")
  assert.equal(S.findEngine(list, "g").name, "Kagi")
  assert.equal(S.findEngine(list, "x"), null)
  assert.equal(S.findEngine(list, "r"), null)
  assert.equal(S.findEngine(list, "nourl"), null)
  assert.equal(S.findEngine(list, "nos"), null)
})

test("url detection", () => {
  assert.equal(S.detectUrl("github.com/omacom/omarchy"), "https://github.com/omacom/omarchy")
  assert.equal(S.detectUrl("https://example.org/a?b=c"), "https://example.org/a?b=c")
  assert.equal(S.detectUrl("localhost:3000"), "http://localhost:3000")
  assert.equal(S.detectUrl("127.0.0.1:8080/api"), "http://127.0.0.1:8080/api")
  for (const t of ["chrome", "1.5", "5.5 gb", "omarchy.menu", "a b.com", "", "http://", "file.txt"])
    assert.equal(S.detectUrl(t), "", t)
})

test("precheck gate", () => {
  for (const t of ["357/2", "$100", "₹2400", "#ff8800", "pi", "time in tokyo", "days until dec 25",
                   "now in unix", "what day is 15 aug", "sqrt(2)", "noon in london", "rgb(1,2,3)"])
    assert.equal(P.mayBeAnswer(t), true, t)
  for (const t of ["chrome", "firefox dev", "screen warmer", "yt lofi", "", "install docker", "x".repeat(300)])
    assert.equal(P.mayBeAnswer(t), false, t)
})
