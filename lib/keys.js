// What a key does on Beam's search line. The search line's text input hands
// every key here first (Keys.forwardTo); a null result lets it type the key,
// which is how input-method and dead-key text arrive.

// Qt::Key and Qt::KeyboardModifier values, so the routing runs under node too.
var KEY = {
  Escape: 0x01000000, Tab: 0x01000001, Backtab: 0x01000002, Backspace: 0x01000003,
  Return: 0x01000004, Enter: 0x01000005, Insert: 0x01000006, Delete: 0x01000007,
  Home: 0x01000010, End: 0x01000011, Left: 0x01000012, Up: 0x01000013,
  Right: 0x01000014, Down: 0x01000015, PageUp: 0x01000016, PageDown: 0x01000017,
  Comma: 0x2c, A: 0x41, C: 0x43, U: 0x55, V: 0x56
}
var MOD = { Shift: 0x02000000, Control: 0x04000000, Alt: 0x08000000, Meta: 0x10000000 }

// event: { key, modifiers, isAutoRepeat }
// state: { text, chip (bool), confirming (bool) }
// Returns { op, ... } or null:
//   unconfirm, clear, dismiss      Esc, in that order of preference
//   settings, copy, paste, tab     Ctrl+, · Ctrl+C · Ctrl+V or Shift+Insert · Tab
//   unchip                         Backspace on an empty line drops the chip
//   edit                           Backspace, Ctrl+Backspace, Ctrl+U
//   move { delta }                 ↑ ↓ PageUp PageDown
//   enter { paste }                Enter, Shift+Enter
//   none                           swallowed: held Enter, Shift+Tab
function route(event, state) {
  var key = event.key
  var mods = event.modifiers || 0
  var ctrl = (mods & MOD.Control) !== 0
  var shift = (mods & MOD.Shift) !== 0
  var text = String(state.text || "")

  if (key === KEY.Escape) return { op: state.confirming ? "unconfirm" : (text || state.chip ? "clear" : "dismiss") }
  if (ctrl && key === KEY.Comma) return { op: "settings" }
  if (ctrl && key === KEY.C) return { op: "copy" }
  // Flattened and capped, rather than the text field's own paste.
  if ((ctrl && key === KEY.V) || (shift && key === KEY.Insert)) return { op: "paste" }
  if (key === KEY.Tab) return { op: "tab" }
  // Nothing to go back to; never let it move focus off the search line.
  if (key === KEY.Backtab) return { op: "none" }
  if (key === KEY.Backspace && !text && state.chip) return { op: "unchip" }
  if (editsText(event, text)) return { op: "edit" }
  if (key === KEY.Up) return { op: "move", delta: -1 }
  if (key === KEY.Down) return { op: "move", delta: 1 }
  if (key === KEY.PageUp) return { op: "move", delta: -6 }
  if (key === KEY.PageDown) return { op: "move", delta: 6 }
  if (key === KEY.Return || key === KEY.Enter) {
    // A held key repeats; every run, and every confirmation of a risky
    // action, needs its own press.
    if (event.isAutoRepeat) return { op: "none" }
    return { op: "enter", paste: shift }
  }
  return null
}

// The shell's Util.editsFilter: Backspace (plain, Shift or Ctrl) and Ctrl+U,
// never with Alt or Super, and only when there is text to edit.
function editsText(event, text) {
  var mods = event.modifiers || 0
  if (!text || (mods & (MOD.Alt | MOD.Meta))) return false
  if (event.key === KEY.U) return mods === MOD.Control
  return event.key === KEY.Backspace
}

if (typeof module !== "undefined") module.exports = { KEY: KEY, MOD: MOD, route: route }
