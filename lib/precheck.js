// Could this text be a calculator/converter query? A false answer lets Beam
// redraw immediately instead of waiting for the engine (spec §2.5 rule 3).

var ANSWER_WORDS = /\b(pi|now|today|tomorrow|yesterday|time|days?|until|since|unix|epoch|timestamp|noon|midnight|what|sqrt|sin|cos|tan|log|ln|exp|abs|round|floor|ceil|min|max|rgba?|hsl)\b/i

function mayBeAnswer(text) {
  var t = String(text || "")
  if (!t.trim() || t.length > 200) return false
  return /[0-9$€£₹¥₩₽₺₫฿₱₪₦#]/.test(t) || ANSWER_WORDS.test(t)
}

// Narrower: text that reads as a sum, conversion or date from its first
// characters (357/2, $50, #ff8800, sqrt 2, days until dec 25). Enter on such
// text waits for the helper's answer instead of running the row below it.
var ANSWER_LEAD = /^\s*(?:[-+(.]\s*)?[0-9$€£₹¥₩₽₺₫฿₱₪₦#]/
var ANSWER_LEAD_WORDS = /^\s*(?:(?:sqrt|sin|cos|tan|log|ln|exp|abs|round|floor|ceil|min|max|pi|ans|what\s+(?:day|time)|days?\s+(?:until|till|til|to|since|from)|(?:now|time)\s+in|today|tomorrow|yesterday|in\s+\d)\b|what\s*%)/i

function likelyAnswer(text) {
  var t = String(text || "")
  if (!mayBeAnswer(t)) return false
  return ANSWER_LEAD.test(t) || ANSWER_LEAD_WORDS.test(t)
}

if (typeof module !== "undefined") module.exports = { mayBeAnswer: mayBeAnswer, likelyAnswer: likelyAnswer }
