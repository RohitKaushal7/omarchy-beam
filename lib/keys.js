// What a key does on Beam's search line. The search line's text input hands
// every key here first (Keys.forwardTo); a null result lets it type the key,
// which is how input-method and dead-key text arrive.

// Qt::Key and Qt::KeyboardModifier values, so the routing runs under node too.
var KEY = {
  Escape: 0x01000000, Tab: 0x01000001, Backtab: 0x01000002, Backspace: 0x01000003,
  Return: 0x01000004, Enter: 0x01000005, Insert: 0x01000006, Delete: 0x01000007,
  Home: 0x01000010, End: 0x01000011, Left: 0x01000012, Up: 0x01000013,
  Right: 0x01000014, Down: 0x01000015, PageUp: 0x01000016, PageDown: 0x01000017,
  F14: 0x0100003d, F16: 0x0100003f, F18: 0x01000041, F20: 0x01000043, Menu: 0x01000055,
  Copy: 0x010000cf, Cut: 0x010000d0, Paste: 0x010000e2, Undo: 0x01000123, Redo: 0x01000124,
  Unknown: 0x01ffffff,
  Comma: 0x2c, A: 0x41, C: 0x43, U: 0x55, V: 0x56
}
var MOD = { Shift: 0x02000000, Control: 0x04000000, Alt: 0x08000000, Meta: 0x10000000 }

// event: { key, modifiers, isAutoRepeat }
// state: { text, chip (bool), confirming (bool), selection (bool: text is selected),
//          releases (see noteRelease), now (ms) }
// Returns { op, ... } or null:
//   unconfirm, clear, dismiss      Esc, in that order of preference
//   settings, tab                  Ctrl+, · Tab
//   copyText                       Ctrl+C with text selected on the line
//   copy                           Ctrl+C otherwise: the selected row's value
//   paste                          Ctrl+V or Shift+Insert, at the caret
//   unchip                         Backspace on an empty line drops the chip
//   edit { edit, extend, word }    caret, selection and deletion; see lib/edit.js
//   move { delta }                 ↑ ↓ PageUp PageDown
//   enter { paste }                Enter, Shift+Enter
//   none                           swallowed: held Enter, Shift+Tab, every other
//                                  Ctrl, Alt or Super chord, and every other
//                                  non-text key (F14, Undo, Redo, Cut, Insert…),
//                                  so the text input's own undo, redo, cut, copy
//                                  and paste never run
function route(event, state) {
  var key = event.key
  var mods = event.modifiers || 0
  var ctrl = (mods & MOD.Control) !== 0
  var shift = (mods & MOD.Shift) !== 0
  var altMeta = (mods & (MOD.Alt | MOD.Meta)) !== 0
  var text = String(state.text || "")

  if (key === KEY.Escape) return { op: state.confirming ? "unconfirm" : (text || state.chip ? "clear" : "dismiss") }
  if (ctrl && key === KEY.Comma) return { op: "settings" }
  // Flattened and capped, rather than the text field's own paste. Before
  // copy, so Ctrl+Shift+Insert (a paste in Qt) never overwrites the clipboard.
  if (isPaste(key, ctrl, shift)) return { op: "paste" }
  if (isCopy(key, ctrl, shift)) return { op: state.selection ? "copyText" : "copy" }
  if (key === KEY.Tab) return { op: "tab" }
  // Nothing to go back to; never let it move focus off the search line.
  if (key === KEY.Backtab) return { op: "none" }
  if (key === KEY.Backspace && !text && state.chip) return { op: "unchip" }
  if (!altMeta) {
    var edit = editFor(key, ctrl, shift, mods)
    if (edit) return text ? edit : { op: "none" }
  }
  if (key === KEY.Up) return { op: "move", delta: -1 }
  if (key === KEY.Down) return { op: "move", delta: 1 }
  if (key === KEY.PageUp) return { op: "move", delta: -6 }
  if (key === KEY.PageDown) return { op: "move", delta: 6 }
  if (key === KEY.Return || key === KEY.Enter) {
    // A held key repeats; every run, and every confirmation of a risky
    // action, needs its own press.
    if (!freshPress(state.releases, event, state.now)) return { op: "none" }
    return { op: "enter", paste: shift }
  }
  // Shortcuts Beam does not use, and keys that carry no text: cut, undo,
  // redo, overwrite mode. Key_unknown can carry a character, so it types.
  if (ctrl || altMeta || (key >= 0x01000000 && key !== KEY.Unknown)) return { op: "none" }
  return null
}

// A held key repeats in two ways. Qt marks its own repeats isAutoRepeat.
// Through a Wayland input method (QT_IM_MODULE=wayland, fcitx5) each repeat
// arrives as a release and a press sent back to back, neither marked. A
// person cannot let go of a key and press it again within REPEAT_GAP_MS, so
// a press that close behind a release of the same key is a repeat too.
var REPEAT_GAP_MS = 30

// Enter and keypad Enter are one key here; Space is the other one counted.
function pressKind(key) {
  if (key === KEY.Return || key === KEY.Enter) return "enter"
  if (key === 0x20) return "space"
  return ""
}

// Record a real release. releases: a plain object the key handler keeps.
function noteRelease(releases, event, now) {
  var kind = pressKind(event.key)
  if (releases && kind && !event.isAutoRepeat) releases[kind] = now
}

// Is this press a new one, rather than a held key repeating?
function freshPress(releases, event, now) {
  if (event.isAutoRepeat) return false
  var last = releases ? releases[pressKind(event.key)] : undefined
  return last === undefined || !(now - last <= REPEAT_GAP_MS)
}

// A click on a row armed for "press again" confirms only once the
// double-click interval since arming has passed, so a double-click (Qt
// reports its second click as a click too) cannot arm the row and run it.
function deliberateClick(confirming, now, armedAt, doubleClickInterval) {
  return !confirming || now - armedAt >= doubleClickInterval
}

// The desktop's double-click interval from Qt.styleHints, or Qt's default.
function doubleClickMs(styleHints) {
  var ms = styleHints ? Number(styleHints.mouseDoubleClickInterval) : 0
  return ms > 0 ? ms : 400
}

// Qt's paste and copy key sequences on Linux.
function isPaste(key, ctrl, shift) {
  return (ctrl && key === KEY.V) || (shift && key === KEY.Insert) || key === KEY.Paste || key === KEY.F18
}

function isCopy(key, ctrl, shift) {
  return (ctrl && !shift && (key === KEY.C || key === KEY.Insert)) || key === KEY.Copy || key === KEY.F16
}

// The editing keys: Left/Right (Ctrl: by word), Home/End, Shift to select;
// Backspace and Delete (Ctrl: a word); Ctrl+U deletes to the start; Ctrl+A
// selects all.
function editFor(key, ctrl, shift, mods) {
  if (key === KEY.Left) return { op: "edit", edit: ctrl ? "wordLeft" : "left", extend: shift }
  if (key === KEY.Right) return { op: "edit", edit: ctrl ? "wordRight" : "right", extend: shift }
  if (key === KEY.Home) return { op: "edit", edit: "home", extend: shift }
  if (key === KEY.End) return { op: "edit", edit: "end", extend: shift }
  if (key === KEY.Backspace) return { op: "edit", edit: "backspace", word: ctrl }
  if (key === KEY.Delete) return { op: "edit", edit: "delete", word: ctrl }
  // Ctrl+U and Ctrl+A only, not Ctrl+Shift+U (Unicode input).
  if (key === KEY.U && mods === MOD.Control) return { op: "edit", edit: "deleteToStart" }
  if (key === KEY.A && mods === MOD.Control) return { op: "edit", edit: "selectAll" }
  return null
}

if (typeof module !== "undefined") {
  module.exports = { KEY: KEY, MOD: MOD, REPEAT_GAP_MS: REPEAT_GAP_MS, route: route,
                     noteRelease: noteRelease, freshPress: freshPress,
                     deliberateClick: deliberateClick, doubleClickMs: doubleClickMs }
}
