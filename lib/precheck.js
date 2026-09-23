// Could this text be a calculator/converter query? A false answer lets Beam
// redraw immediately instead of waiting for the engine (spec §2.5 rule 3).

var ANSWER_WORDS = /\b(pi|now|today|tomorrow|yesterday|time|days?|until|since|unix|epoch|timestamp|noon|midnight|what|sqrt|sin|cos|tan|log|ln|exp|abs|round|floor|ceil|min|max|rgba?|hsl)\b/i

function mayBeAnswer(text) {
  var t = String(text || "")
  if (!t.trim() || t.length > 200) return false
  return /[0-9$€£₹¥₩₽₺₫฿₱₪₦#]/.test(t) || ANSWER_WORDS.test(t)
}

if (typeof module !== "undefined") module.exports = { mayBeAnswer: mayBeAnswer }
