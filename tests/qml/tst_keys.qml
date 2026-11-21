import QtQuick
import QtTest
import "../../lib/keys.js" as SearchKeys

// lib/keys.js spells out Qt's key and modifier values so node can test it;
// they must be the ones Qt hands the key handler.
TestCase {
  name: "SearchKeys"

  function test_key_values_are_qts() {
    var K = SearchKeys.KEY
    var pairs = [[K.Escape, Qt.Key_Escape], [K.Tab, Qt.Key_Tab], [K.Backtab, Qt.Key_Backtab],
                 [K.Backspace, Qt.Key_Backspace], [K.Return, Qt.Key_Return], [K.Enter, Qt.Key_Enter],
                 [K.Insert, Qt.Key_Insert], [K.Delete, Qt.Key_Delete], [K.Home, Qt.Key_Home], [K.End, Qt.Key_End],
                 [K.Left, Qt.Key_Left], [K.Up, Qt.Key_Up], [K.Right, Qt.Key_Right], [K.Down, Qt.Key_Down],
                 [K.PageUp, Qt.Key_PageUp], [K.PageDown, Qt.Key_PageDown], [K.Comma, Qt.Key_Comma],
                 [K.F14, Qt.Key_F14], [K.F16, Qt.Key_F16], [K.F18, Qt.Key_F18], [K.F20, Qt.Key_F20],
                 [K.Menu, Qt.Key_Menu], [K.Copy, Qt.Key_Copy], [K.Cut, Qt.Key_Cut], [K.Paste, Qt.Key_Paste],
                 [K.Undo, Qt.Key_Undo], [K.Redo, Qt.Key_Redo], [K.Unknown, Qt.Key_unknown],
                 [K.A, Qt.Key_A], [K.C, Qt.Key_C], [K.U, Qt.Key_U], [K.V, Qt.Key_V]]
    for (var i = 0; i < pairs.length; i++) compare(pairs[i][0], pairs[i][1], "key " + i)
    var M = SearchKeys.MOD
    compare(M.Shift, Qt.ShiftModifier)
    compare(M.Control, Qt.ControlModifier)
    compare(M.Alt, Qt.AltModifier)
    compare(M.Meta, Qt.MetaModifier)
  }

  function test_held_enter_is_swallowed() {
    var held = { key: Qt.Key_Return, modifiers: Qt.NoModifier, isAutoRepeat: true }
    compare(SearchKeys.route(held, { text: "reboot", chip: false, confirming: true }).op, "none")
  }
}
