import QtQuick
import QtQuick.Controls as QQC
import qs.Commons
import qs.Ui
import "../lib/settings.js" as Settings
import "../lib/examples.js" as Examples
import "../lib/shortcuts.js" as Shortcuts
import "../lib/keys.js" as SearchKeys

// Beam settings: one compact row per setting (icon · label · control), keyboard
// first. ↑/↓ move, ←/→ change numbers and choices, Space/Enter flips a switch
// or edits text, Esc goes back. Every change goes through SettingsStore.set.
// The focused row of a feature grows to list what it accepts and gives
// (lib/examples.js); the others stay one line.
FocusScope {
  id: view

  property var store: null
  // When Enter and Space were last really let go; Beam shares its own.
  property var keyReleases: ({})
  property string jevStatus: "unknown"
  property color foreground: Color.menu.text
  property color selectedBackground: Color.menu.selectedBackground
  property color selectedText: Color.menu.selectedText
  property var selectedBorderSpec: Border.none()
  property string fontFamily: Style.font.menuFamily
  property int rowHeight: Style.space(50)
  property int detailRowHeight: Style.space(58)

  // Example lines under the focused feature: one fixed height each, so a row
  // knows its full height the moment the cursor lands on it.
  readonly property int exampleLineHeight: Math.ceil(exampleMetrics.height)
  readonly property int exampleSpacing: Style.space(3)

  FontMetrics {
    id: exampleMetrics
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
  }

  property int cursor: -1
  property bool editing: false
  property var activeEditor: null

  signal closeRequested()
  // A settings text field asks Beam for its bounded paste (see insertText)
  // and hands it selected text to copy through wl-copy.
  signal pasteRequested()
  signal copyRequested(string text)

  readonly property var settings: view.store ? view.store.settings : ({})
  readonly property var engines: view.settings.search
    ? Shortcuts.engines(view.settings.search.engines, view.settings.search.disabledBuiltins) : []
  readonly property string jevText: ({
    "env": "Key found in TYPESAFE_API_KEY ✓",
    "file": "Key found in the key file ✓",
    "no-key": "No key found: Jev is off",
    "auth-failed": "TypeSafe rejected the key: Jev is off",
    "off": "Turned off"
  })[view.jevStatus] || "Checking…"

  readonly property var sections: [
    { title: "Sources", icon: "󰀻", items: [
      { path: "sources.apps", type: "bool", icon: "󰀻", label: "Apps" },
      { path: "sources.actions", type: "bool", icon: "󱓞", label: "Omarchy actions" },
      { path: "sources.recent", type: "bool", icon: "󰋚", label: "Recent picks", description: "Shown before you type; lead equal matches" },
      { path: "sources.calculator", type: "bool", icon: "󰃬", label: "Calculator" },
      { path: "sources.units", type: "bool", icon: "󰑭", label: "Unit conversion" },
      { path: "sources.currency", type: "bool", icon: "󰇁", label: "Currency", description: "Daily rates from ExchangeRate-API" },
      { path: "sources.time", type: "bool", icon: "󰅐", label: "Time zones and dates" },
      { path: "sources.developer", type: "bool", icon: "󰅩", label: "Developer values", description: "Bases, colours, unix time, byte sizes" },
      { path: "sources.shortcuts", type: "bool", icon: "󰍉", label: "Search shortcuts", description: "yt, g, gg… then Tab" },
      { path: "sources.urls", type: "bool", icon: "󰌷", label: "Open URLs" },
      { path: "sources.webSearchRow", type: "bool", icon: "󰖟", label: "Web search row" },
      { path: "sources.agentRow", type: "bool", icon: "󰚩", label: "Ask agent row" }
    ] },
    { title: "Jev · match by meaning", icon: "✦", items: [
      { path: "jev.enabled", type: "bool", icon: "✦", label: "Use Jev", description: view.jevText },
      { path: "jev.debounceMs", type: "int", icon: "󰔟", label: "Pause before asking (ms)", from: 100, to: 2000, step: 50 },
      { path: "jev.minChars", type: "int", icon: "󰎠", label: "Minimum characters", from: 1, to: 20, step: 1 },
      { path: "jev.cacheSize", type: "int", icon: "󰆼", label: "Cached answers", from: 0, to: 10000, step: 100 },
      { path: "jev.keyFile", type: "text", icon: "󰌆", label: "Key file", description: "Used when TYPESAFE_API_KEY is not set" }
    ] },
    { title: "Calculator", icon: "󰃬", items: [
      { path: "calc.homeCurrency", type: "text", icon: "󰢯", label: "Home currency", description: "auto, or a code like INR" },
      { path: "calc.grouping", type: "choice", icon: "󰉻", label: "Number grouping", options: ["auto", "indian", "international"] },
      { path: "calc.significantDigits", type: "int", icon: "󰎠", label: "Significant digits", from: 3, to: 20, step: 1 },
      { path: "calc.ratesRefreshHours", type: "int", icon: "󰑐", label: "Refresh rates every (hours)", from: 1, to: 720, step: 1 }
    ] },
    { title: "Search", icon: "󰍉", items: [
      { path: "search.fallbackEngine", type: "text", icon: "󰖟", label: "Web search row engine", description: "A shortcut keyword, e.g. g or ddg" }
    ] },
    { title: "Behaviour", icon: "󰒓", items: [
      { path: "behavior.confirmRisky", type: "bool", icon: "󰀦", label: "Confirm risky actions", description: "Reboot, remove, update and install" },
      { path: "behavior.keybindingHints", type: "bool", icon: "󰌌", label: "Show keybinding hints" },
      { path: "behavior.agentCommand", type: "text", icon: "󰚩", label: "Agent command" },
      { path: "engine.idleExitMinutes", type: "int", icon: "󰒲", label: "Stop the helper after idle (min)", from: 1, to: 1440, step: 1 }
    ] },
    { title: "Look", icon: "󰏘", items: [
      { path: "look.width", type: "int", icon: "󰡎", label: "Width", from: 400, to: 1000, step: 20 },
      { path: "look.maxRows", type: "int", icon: "󰉹", label: "Visible rows", from: 3, to: 20, step: 1 }
    ] }
  ]
  readonly property var rows: Settings.flattenSections(view.sections)

  function get(path) {
    var parts = String(path).split(".")
    var group = view.settings[parts[0]] || {}
    return group[parts[1]]
  }

  function set(path, value) {
    if (view.store) view.store.set(path, value)
  }

  function move(delta) {
    pointerGate.reset()
    view.cursor = Settings.nextField(view.rows, view.cursor, delta)
    view.reveal()
  }

  // Keep the focused row, examples and all, inside the list. The row grows or
  // shrinks as the cursor lands on it, so lay the list out before measuring.
  function reveal() {
    if (view.cursor < 0 || !view.visible) return
    list.forceLayout()
    list.positionViewAtIndex(view.cursor, ListView.Contain)
  }

  // Hover and clicks move the cursor too, and a settings change can add or
  // drop example lines (a new search engine); reveal after those as well.
  onCursorChanged: Qt.callLater(view.reveal)
  onSettingsChanged: Qt.callLater(view.reveal)

  function change(delta) {
    var spec = view.rows[view.cursor]
    if (!spec || spec.type === "header" || spec.type === "text") return
    view.set(spec.path, Settings.stepValue(spec, view.get(spec.path), delta))
  }

  function activate() {
    var spec = view.rows[view.cursor]
    if (!spec || spec.type === "header") return
    if (spec.type === "text") {
      var slot = list.itemAtIndex(view.cursor)
      if (slot && slot.item && typeof slot.item.edit === "function") slot.item.edit()
    } else if (spec.type !== "int") {
      view.change(1)
    }
  }

  // Give the keyboard back to the view. A FocusScope's forceActiveFocus()
  // hands focus to whichever child last had it, so the text field that was
  // being edited must drop its own focus first, or it takes the keys back.
  function refocus() {
    if (view.activeEditor) view.activeEditor.focus = false
    view.activeEditor = null
    view.editing = false
    view.forceActiveFocus()
  }

  // Hover moves the highlight only after the pointer really moves, so a
  // pointer resting over the card does not steal the keyboard's place.
  PointerMoveGate {
    id: pointerGate
    referenceItem: view
  }

  // Text from Beam's bounded paste goes into the field being edited, over its
  // selection. Dropped if editing has ended since the paste was asked for.
  function insertText(text) {
    var editor = view.activeEditor
    if (!editor || !view.editing) return
    if (editor.selectionStart !== editor.selectionEnd) editor.remove(editor.selectionStart, editor.selectionEnd)
    editor.insert(editor.cursorPosition, text)
  }

  // Called each time settings opens: start at the first setting, at the top.
  function reset() {
    pointerGate.reset()
    view.refocus()
    view.cursor = Settings.nextField(view.rows, -1, 1)
    list.positionViewAtBeginning()
  }

  Keys.onPressed: function(event) {
    if (view.editing) return
    var shift = (event.modifiers & Qt.ShiftModifier) !== 0
    if (event.key === Qt.Key_Escape) view.closeRequested()
    else if (event.key === Qt.Key_Up || event.key === Qt.Key_Backtab) view.move(-1)
    else if (event.key === Qt.Key_Down || event.key === Qt.Key_Tab) view.move(1)
    else if (event.key === Qt.Key_PageUp) view.move(-6)
    else if (event.key === Qt.Key_PageDown) view.move(6)
    else if (event.key === Qt.Key_Left) view.change(shift ? -10 : -1)
    else if (event.key === Qt.Key_Right) view.change(shift ? 10 : 1)
    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) {
      // A held key flips a switch once, whichever way it repeats.
      if (SearchKeys.freshPress(view.keyReleases, event, Date.now())) view.activate()
    }
    else return
    event.accepted = true
  }
  Keys.onReleased: function(event) { SearchKeys.noteRelease(view.keyReleases, event, Date.now()) }

  Column {
    anchors.fill: parent
    spacing: Style.spacing.md

    Text {
      id: hint
      textFormat: Text.PlainText
      width: parent.width
      text: "↑↓ move  ·  ←→ change  ·  Enter toggle or edit  ·  Esc back"
      color: view.foreground
      opacity: 0.45
      font.family: view.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
    }

    ListView {
      id: list
      objectName: "settingsList"
      width: parent.width
      focus: false
      keyNavigationEnabled: false  // the view owns the arrow keys
      height: parent.height - hint.height - parent.spacing
      model: view.rows
      clip: true
      spacing: Style.spacing.xs
      boundsBehavior: Flickable.StopAtBounds

      delegate: Loader {
        required property var modelData
        required property int index
        readonly property var spec: modelData
        readonly property int rowIndex: index
        width: ListView.view.width
        sourceComponent: modelData.type === "header" ? headerRow : fieldRow
      }
    }
  }

  Component {
    id: headerRow

    Item {
      readonly property var spec: parent ? parent.spec : ({})
      height: Style.space(34)

      Row {
        anchors.left: parent.left
        anchors.leftMargin: Style.space(8)
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Style.space(4)
        spacing: Style.space(8)

        Text {
          textFormat: Text.PlainText
          text: spec.icon || ""
          color: view.selectedText
          font.family: view.fontFamily
          font.pixelSize: Style.font.body
        }

        Text {
          textFormat: Text.PlainText
          text: spec.title || ""
          color: view.foreground
          opacity: 0.7
          font.family: view.fontFamily
          font.pixelSize: Style.font.bodySmall
          font.weight: Font.DemiBold
        }
      }
    }
  }

  Component {
    id: fieldRow

    BorderSurface {
      id: rowItem
      readonly property var spec: parent ? parent.spec : ({})
      readonly property int rowIndex: parent ? parent.rowIndex : -1
      readonly property bool hasCursor: view.cursor === rowItem.rowIndex
      readonly property string description: spec.description || ""
      readonly property var examples: Examples.forPath(spec.path || "", view.settings, view.engines, Shortcuts.BUILTINS)
      readonly property bool expanded: rowItem.hasCursor && rowItem.examples.length > 0
      readonly property bool featureOff: spec.type === "bool" && view.get(spec.path) !== true
      readonly property int headHeight: description ? view.detailRowHeight : view.rowHeight
      readonly property int exampleCount: rowItem.examples.length + (rowItem.featureOff ? 1 : 0)
      readonly property int examplesHeight: rowItem.expanded
        ? rowItem.exampleCount * view.exampleLineHeight + (rowItem.exampleCount - 1) * view.exampleSpacing
          + Style.space(10)
        : 0

      function edit() {
        if (textControl.item) textControl.item.startEdit()
      }

      // No animation: the cursor moves through many rows a keystroke at a time.
      height: rowItem.headHeight + rowItem.examplesHeight
      radius: Style.cornerRadius
      color: rowItem.hasCursor ? view.selectedBackground : "transparent"
      borderSpec: rowItem.hasCursor ? view.selectedBorderSpec : Border.none()

      MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onPositionChanged: function(mouse) {
          if (pointerGate.moved(rowItem, mouse)) view.cursor = rowItem.rowIndex
        }
        onClicked: function(mouse) {
          view.cursor = rowItem.rowIndex
          view.refocus()
          if (mouse.y < rowItem.headHeight) view.activate()  // the example lines only display
        }
      }

      Item {
        id: head
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: rowItem.headHeight
      }

      Text {
        id: icon
        textFormat: Text.PlainText
        text: spec.icon || ""
        color: rowItem.hasCursor ? view.selectedText : view.foreground
        font.family: view.fontFamily
        font.pixelSize: Style.font.iconLarge
        width: Style.space(36)
        horizontalAlignment: Text.AlignHCenter
        anchors.left: parent.left
        anchors.leftMargin: Style.space(8)
        anchors.verticalCenter: head.verticalCenter
      }

      Column {
        anchors.left: icon.right
        anchors.leftMargin: Style.space(6)
        anchors.right: control.left
        anchors.rightMargin: Style.space(12)
        anchors.verticalCenter: head.verticalCenter
        spacing: Style.space(2)

        Text {
          textFormat: Text.PlainText
          width: parent.width
          text: spec.label || ""
          color: rowItem.hasCursor ? view.selectedText : view.foreground
          font.family: view.fontFamily
          font.pixelSize: Style.font.title
          font.weight: Font.Medium
          elide: Text.ElideRight
        }

        Text {
          textFormat: Text.PlainText
          width: parent.width
          visible: rowItem.description.length > 0
          text: rowItem.description
          color: view.foreground
          opacity: 0.52
          font.family: view.fontFamily
          font.pixelSize: Style.font.bodySmall
          elide: Text.ElideRight
        }
      }

      Item {
        id: control
        anchors.right: parent.right
        anchors.rightMargin: Style.space(10)
        anchors.verticalCenter: head.verticalCenter
        width: spec.type === "text" ? Math.round(rowItem.width * 0.42)
          : (spec.type === "choice" ? Style.space(180) : (spec.type === "int" ? Style.space(120) : switchControl.width))
        height: Math.max(switchControl.height, Style.spacing.controlHeight)

        ToggleSwitch {
          id: switchControl
          visible: spec.type === "bool"
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          interactive: false
          checked: view.get(spec.path) === true
        }

        NumberField {
          visible: spec.type === "int"
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          label: ""
          fieldWidth: Style.space(120)
          from: spec.from || 0
          to: spec.to || 100
          stepSize: spec.step || 1
          value: Number(view.get(spec.path)) || 0
          hasCursor: rowItem.hasCursor
          fontFamily: view.fontFamily
          field.focusPolicy: Qt.NoFocus
          field.editable: false
          onModified: function(value) { view.set(spec.path, value) }
          // Read-only, but a drag would still select its digits onto the
          // primary selection.
          Component.onCompleted: if (field.contentItem) field.contentItem.selectByMouse = false
        }

        Dropdown {
          visible: spec.type === "choice"
          anchors.fill: parent
          showLabel: false
          value: String(view.get(spec.path))
          options: spec.options || []
          hasCursor: rowItem.hasCursor
          fontFamily: view.fontFamily
          onChanged: function(value) {
            view.set(spec.path, value)
            view.refocus()
          }
        }

        Loader {
          id: textControl
          anchors.fill: parent
          active: spec.type === "text"
          // Enter, Esc, Tab or clicking away all save the text and hand the
          // keyboard back to the view.
          // The field edits as usual, but never pastes, copies or sets the
          // primary selection by itself: no mouse selection, middle-click
          // paste or context menu, and its paste and copy keys go through
          // Beam's bounded wl-paste and wl-copy (lib/keys.js fieldKey).
          sourceComponent: TextField {
            id: editor
            function startEdit() {
              forceActiveFocus()
              selectAll()
            }
            selectByMouse: false
            QQC.ContextMenu.menu: null
            text: String(view.get(spec.path) || "")
            hasCursor: rowItem.hasCursor
            font.family: view.fontFamily
            onActiveFocusChanged: if (activeFocus) {
              view.cursor = rowItem.rowIndex
              view.activeEditor = editor
              view.editing = true
            }
            onEditingFinished: view.set(spec.path, text)
            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Escape || event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                  || event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
                view.set(spec.path, text)
                view.refocus()
                event.accepted = true
                return
              }
              var clip = SearchKeys.fieldKey(event)
              if (clip === "paste") view.pasteRequested()
              else if (clip === "copy" && editor.selectedText) view.copyRequested(editor.selectedText)
              if (clip) event.accepted = true
            }

            // Left button: start editing, or put the caret where you click.
            // Middle and right do nothing.
            MouseArea {
              anchors.fill: parent
              acceptedButtons: Qt.AllButtons
              cursorShape: Qt.IBeamCursor
              onPressed: function(mouse) {
                if (mouse.button !== Qt.LeftButton) return
                if (!editor.activeFocus) {
                  editor.startEdit()
                } else {
                  editor.deselect()
                  editor.cursorPosition = editor.positionAt(mouse.x, mouse.y)
                }
              }
            }
          }
        }
      }

      // What the feature accepts and gives: query → result (aside). Shown,
      // dimmed, while the feature is off, so you can see what turning it on
      // brings. Display only; nothing here runs.
      Loader {
        id: examplesBlock
        objectName: "examples"
        anchors.top: head.bottom
        anchors.left: parent.left
        anchors.leftMargin: Style.space(50)
        anchors.right: parent.right
        anchors.rightMargin: Style.space(14)
        active: rowItem.expanded

        sourceComponent: Column {
          id: block
          spacing: view.exampleSpacing

          // One width for every query, so the arrows line up.
          readonly property real queryColumn: {
            var widest = 0
            for (var i = 0; i < rowItem.examples.length; i++) {
              widest = Math.max(widest, exampleMetrics.advanceWidth(Examples.queryText(rowItem.examples[i])))
            }
            return Math.ceil(Math.min(widest, block.width * 0.45))
          }

          Text {
            objectName: "offCaption"
            textFormat: Text.PlainText
            width: block.width
            height: view.exampleLineHeight
            verticalAlignment: Text.AlignVCenter
            visible: rowItem.featureOff
            text: "Off · Enter turns it on and gives you these"
            color: view.foreground
            opacity: 0.6
            font.family: view.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.italic: true
            elide: Text.ElideRight
          }

          Repeater {
            model: rowItem.examples

            Item {
              id: line
              required property var modelData
              readonly property string note: Examples.noteText(modelData)
              width: block.width
              height: view.exampleLineHeight
              opacity: rowItem.featureOff || modelData.off ? 0.45 : 1

              Text {
                id: query
                textFormat: Text.PlainText
                width: Math.min(implicitWidth, block.queryColumn)
                text: Examples.queryText(line.modelData)
                color: view.selectedText
                font.family: Style.font.family
                font.pixelSize: Style.font.bodySmall
                elide: Text.ElideRight
              }

              Text {
                id: arrow
                textFormat: Text.PlainText
                x: block.queryColumn + Style.space(8)
                text: "→"
                color: view.foreground
                opacity: 0.4
                font.family: view.fontFamily
                font.pixelSize: Style.font.bodySmall
              }

              Text {
                id: result
                textFormat: Text.PlainText
                x: arrow.x + arrow.width + Style.space(8)
                width: Math.min(implicitWidth, Math.max(0, line.width - x))
                text: String(line.modelData.a || "")
                color: view.foreground
                opacity: 0.78
                font.family: view.fontFamily
                font.pixelSize: Style.font.bodySmall
                elide: Text.ElideRight
              }

              Text {
                textFormat: Text.PlainText
                x: result.x + result.width + Style.space(6)
                width: Math.max(0, line.width - x)
                visible: line.note.length > 0 && width > Style.space(24)
                text: line.note
                color: view.foreground
                opacity: 0.42
                font.family: view.fontFamily
                font.pixelSize: Style.font.bodySmall
                elide: Text.ElideRight
              }
            }
          }
        }
      }
    }
  }
}
