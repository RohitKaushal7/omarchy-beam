import QtQuick
import QtTest
import "../../ui"
import "../../lib/keys.js" as SearchKeys
import "../../lib/edit.js" as Edit

// The search line wired as Beam.qml wires it: keys go through lib/keys.js,
// edits through lib/edit.js and back into filterText, typed text stays with
// the input. Real key events, offscreen.
Item {
  id: root
  width: 480
  height: 60

  property string filterText: ""
  property var ops: []
  property int searches: 0

  function setText(text) {
    root.filterText = text
    root.searches += 1
  }
  onFilterTextChanged: if (input.text !== root.filterText) input.text = root.filterText

  function applyEdit(next) {
    if (next.text !== root.filterText) root.setText(next.text)
    if (input.text !== next.text) input.text = next.text
    input.place(next.cursor, next.anchor)
  }

  Item {
    id: keyCatcher
    Keys.priority: Keys.BeforeItem
    Keys.onPressed: function(event) {
      var action = SearchKeys.route(event, { text: root.filterText, chip: false, confirming: false,
                                             selection: input.hasSelection })
      if (!action) return
      event.accepted = true
      if (action.op === "edit") root.applyEdit(Edit.apply(input.editState(), action))
      else if (action.op === "copyText") root.ops = root.ops.concat(["copyText:" + Edit.selected(input.editState())])
      else if (action.op !== "none") root.ops = root.ops.concat([action.op])
    }
  }

  SearchInput {
    id: input
    anchors.fill: parent
    keyHandler: keyCatcher
    font.pixelSize: 20
    onTextChanged: {
      var flat = Edit.flatten(input.editState())
      if (flat.text !== input.text) root.applyEdit(flat)
      else if (input.text !== root.filterText) root.setText(input.text)
    }
  }

  TestCase {
    name: "SearchInput"
    when: windowShown

    function caret() { return findChild(input, "caret") }
    function type(text) { for (var i = 0; i < text.length; i++) keyClick(text.charAt(i)) }

    function init() {
      root.setText("")
      root.ops = []
      root.searches = 0
      input.forceActiveFocus()
      verify(input.activeFocus)
    }

    function test_typing_at_the_end_shows_no_caret() {
      type("hello")
      compare(root.filterText, "hello")
      compare(input.cursorPosition, 5)
      verify(!input.caretShown)
      verify(caret() === null || !caret().visible)
    }

    function test_arrows_move_a_visible_caret_and_typing_goes_there() {
      type("hello")
      keyClick(Qt.Key_Left)
      keyClick(Qt.Key_Left)
      compare(input.cursorPosition, 3)
      verify(input.caretShown)
      verify(caret() !== null && caret().visible)
      type("X")
      compare(root.filterText, "helXlo")
      compare(input.cursorPosition, 4, "the caret survives the round trip through filterText")
      keyClick(Qt.Key_End)
      compare(input.cursorPosition, 6)
      verify(!input.caretShown)
      keyClick(Qt.Key_Home)
      compare(input.cursorPosition, 0)
      verify(input.caretShown)
    }

    function test_backspace_and_delete_act_at_the_caret() {
      type("12345")
      keyClick(Qt.Key_Left)
      keyClick(Qt.Key_Left)
      keyClick(Qt.Key_Backspace)
      compare(root.filterText, "1245")
      compare(input.cursorPosition, 2)
      keyClick(Qt.Key_Delete)
      compare(root.filterText, "125")
      compare(input.cursorPosition, 2)
    }

    function test_word_moves_and_word_delete() {
      type("100 usd in inr")
      keyClick(Qt.Key_Left, Qt.ControlModifier)
      compare(input.cursorPosition, 11)
      keyClick(Qt.Key_Left, Qt.ControlModifier)
      keyClick(Qt.Key_Left, Qt.ControlModifier)
      compare(input.cursorPosition, 4)
      keyClick(Qt.Key_Right, Qt.ControlModifier)
      compare(input.cursorPosition, 7)
      keyClick(Qt.Key_Backspace, Qt.ControlModifier)
      compare(root.filterText, "100  in inr")
      compare(input.cursorPosition, 4)
    }

    function test_ctrl_a_selects_all_and_typing_replaces_it() {
      type("firefox")
      keyClick(Qt.Key_A, Qt.ControlModifier)
      verify(input.hasSelection)
      compare(input.selectedText, "firefox")
      verify(input.caretShown)
      type("z")
      compare(root.filterText, "z")
      verify(!input.hasSelection)
    }

    function test_ctrl_a_then_backspace_clears() {
      type("357/2")
      keyClick(Qt.Key_A, Qt.ControlModifier)
      keyClick(Qt.Key_Backspace)
      compare(root.filterText, "")
    }

    function test_shift_arrows_select_and_ctrl_c_copies_the_selection() {
      type("hello world")
      keyClick(Qt.Key_Left, Qt.ControlModifier | Qt.ShiftModifier)
      compare(input.selectedText, "world")
      keyClick(Qt.Key_C, Qt.ControlModifier)
      compare(root.ops, ["copyText:world"])
      keyClick(Qt.Key_Right)
      verify(!input.hasSelection)
      compare(input.cursorPosition, 11)
      keyClick(Qt.Key_C, Qt.ControlModifier)
      compare(root.ops, ["copyText:world", "copy"], "no selection: the selected row is copied")
    }

    function test_shift_home_selects_to_the_start_and_typing_replaces_it() {
      type("abc def")
      keyClick(Qt.Key_Left)
      keyClick(Qt.Key_Home, Qt.ShiftModifier)
      compare(input.selectedText, "abc de")
      compare(input.cursorPosition, 0)
      type("x")
      compare(root.filterText, "xf")
      compare(input.cursorPosition, 1)
    }

    function test_the_inputs_own_clipboard_shortcuts_never_run() {
      type("abc")
      keyClick(Qt.Key_A, Qt.ControlModifier)
      keyClick(Qt.Key_X, Qt.ControlModifier)
      compare(root.filterText, "abc", "Ctrl+X does not cut")
      keyClick(Qt.Key_Delete, Qt.ShiftModifier)
      compare(root.filterText, "", "Shift+Delete deletes the selection, it does not cut")
      keyClick(Qt.Key_Z, Qt.ControlModifier)
      compare(root.filterText, "", "no undo behind Beam's back")
      keyClick(Qt.Key_F14)
      compare(root.filterText, "", "nor through F14, Undo on X11 keyboards")
      keyClick(Qt.Key_V, Qt.ControlModifier)
      keyClick(Qt.Key_Insert, Qt.ShiftModifier)
      keyClick(Qt.Key_Insert, Qt.ControlModifier | Qt.ShiftModifier)
      compare(root.ops, ["paste", "paste", "paste"], "paste goes to Beam's bounded paste")
      compare(root.filterText, "")
    }

    function test_text_set_from_outside_puts_the_caret_at_the_end() {
      type("abc")
      keyClick(Qt.Key_Home)
      root.setText("g lofi")
      compare(input.text, "g lofi")
      compare(input.cursorPosition, 6)
      verify(!input.caretShown)
    }

    function test_place_puts_the_caret_at_the_cursor_end() {
      root.setText("abcdef")
      input.place(2, 5)
      compare(input.cursorPosition, 2)
      compare(input.selectedText, "cde")
      compare(input.editState(), { text: "abcdef", cursor: 2, anchor: 5 })
      input.place(5, 2)
      compare(input.cursorPosition, 5)
      compare(input.editState(), { text: "abcdef", cursor: 5, anchor: 2 })
      input.place(3, 3)
      verify(!input.hasSelection)
      compare(input.cursorPosition, 3)
    }

    function test_newlines_are_flattened_and_the_caret_kept() {
      type("ab")
      keyClick(Qt.Key_Left)
      input.insert(input.cursorPosition, "x\ny")
      compare(root.filterText, "ax yb")
      compare(input.text, "ax yb")
      compare(input.cursorPosition, 4)
    }

    function test_arrows_on_an_empty_line_do_nothing() {
      keyClick(Qt.Key_Left)
      keyClick(Qt.Key_Home)
      keyClick(Qt.Key_A, Qt.ControlModifier)
      compare(root.filterText, "")
      compare(root.searches, 0)
    }

    function test_up_down_and_enter_still_reach_beam() {
      type("x")
      keyClick(Qt.Key_Down)
      keyClick(Qt.Key_Up)
      keyClick(Qt.Key_Return)
      keyClick(Qt.Key_Tab)
      compare(root.ops, ["move", "move", "enter", "tab"])
    }
  }
}
