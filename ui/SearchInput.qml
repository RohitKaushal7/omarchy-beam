pragma ComponentBehavior: Bound

import QtQuick

// Beam's search line. A TextInput, because Qt hands input-method text
// (fcitx5 composing Japanese, Chinese or Korean) and dead keys only to text
// inputs. Every key goes to keyHandler first; it moves the caret and edits
// through lib/edit.js and place(), and leaves only typed text to the input,
// which puts it at the caret. The input's own shortcuts (undo, cut, copy,
// paste) never see a key, and the pointer never reaches it, so it never
// pastes or copies by itself, and never sets the primary selection. Like
// any editable Qt input it still follows the clipboard while it exists (Qt
// checks each new offer for text, to know whether paste is possible); Beam
// makes it only while open.
//
// No caret while you type at the end, as before; it shows once it is
// somewhere else, or while text is selected.
TextInput {
  id: input

  property Item keyHandler: null
  readonly property bool hasSelection: input.selectionStart !== input.selectionEnd
  readonly property bool caretShown: input.activeFocus && (input.hasSelection || input.cursorPosition < input.length)

  focus: true
  clip: true
  selectByMouse: false
  Keys.priority: Keys.BeforeItem
  Keys.forwardTo: input.keyHandler ? [input.keyHandler] : []
  // Ctrl, Alt and Super chords are shortcuts, never text; keyHandler takes
  // the ones Beam uses, and the rest stop here.
  Keys.onPressed: function(event) {
    if (event.modifiers & (Qt.AltModifier | Qt.MetaModifier | Qt.ControlModifier)) event.accepted = true
  }

  cursorDelegate: Rectangle {
    objectName: "caret"
    width: Math.max(1, Math.round(input.font.pixelSize / 14))
    color: input.color
    visible: input.caretShown
  }

  // The text, caret and selection, for lib/edit.js.
  function editState() {
    var anchor = input.cursorPosition === input.selectionStart ? input.selectionEnd : input.selectionStart
    return { text: input.text, cursor: input.cursorPosition, anchor: anchor }
  }

  // Put the caret at cursor, selecting back to anchor when they differ.
  function place(cursor, anchor) {
    if (anchor === undefined || anchor === cursor) {
      input.deselect()
      input.cursorPosition = cursor
    } else {
      input.select(anchor, cursor)
    }
  }
}
