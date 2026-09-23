import QtQuick
import qs.Commons
import qs.Ui
import "../lib/settings.js" as Settings

// Beam settings: one compact row per setting (icon · label · control), keyboard
// first. ↑/↓ move, ←/→ change numbers and choices, Space/Enter flips a switch
// or edits text, Esc goes back. Every change goes through SettingsStore.set.
FocusScope {
  id: view

  property var store: null
  property string jevStatus: "unknown"
  property color foreground: Color.menu.text
  property color selectedBackground: Color.menu.selectedBackground
  property color selectedText: Color.menu.selectedText
  property var selectedBorderSpec: Border.none()
  property string fontFamily: Style.font.menuFamily
  property int rowHeight: Style.space(50)
  property int detailRowHeight: Style.space(58)

  property int cursor: -1
  property bool editing: false

  signal closeRequested()

  readonly property var settings: view.store ? view.store.settings : ({})
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
      { path: "sources.recent", type: "bool", icon: "󰋚", label: "Recent picks", description: "Shown before you type" },
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
    if (view.cursor >= 0) list.positionViewAtIndex(view.cursor, ListView.Contain)
  }

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

  function endEdit() {
    view.editing = false
    view.forceActiveFocus()
  }

  // Hover moves the highlight only after the pointer really moves, so a
  // pointer resting over the card does not steal the keyboard's place.
  PointerMoveGate {
    id: pointerGate
    referenceItem: view
  }

  onVisibleChanged: if (visible) {
    pointerGate.reset()
    view.editing = false
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
    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) view.activate()
    else return
    event.accepted = true
  }

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
      width: parent.width
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

      function edit() {
        if (textControl.item) textControl.item.startEdit()
      }

      height: description ? view.detailRowHeight : view.rowHeight
      radius: Style.cornerRadius
      color: rowItem.hasCursor ? view.selectedBackground : "transparent"
      borderSpec: rowItem.hasCursor ? view.selectedBorderSpec : Border.none()

      MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onPositionChanged: function(mouse) {
          if (pointerGate.moved(rowItem, mouse)) view.cursor = rowItem.rowIndex
        }
        onClicked: {
          view.cursor = rowItem.rowIndex
          view.forceActiveFocus()
          view.activate()
        }
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
        anchors.verticalCenter: parent.verticalCenter
      }

      Column {
        anchors.left: icon.right
        anchors.leftMargin: Style.space(6)
        anchors.right: control.left
        anchors.rightMargin: Style.space(12)
        anchors.verticalCenter: parent.verticalCenter
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
        anchors.verticalCenter: parent.verticalCenter
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
        }

        Dropdown {
          visible: spec.type === "choice"
          anchors.fill: parent
          showLabel: false
          value: String(view.get(spec.path))
          options: spec.options || []
          hasCursor: rowItem.hasCursor
          fontFamily: view.fontFamily
          onChanged: function(value) { view.set(spec.path, value) }
        }

        Loader {
          id: textControl
          anchors.fill: parent
          active: spec.type === "text"
          sourceComponent: TextField {
            property bool reverting: false
            function startEdit() {
              view.editing = true
              forceActiveFocus()
              selectAll()
            }
            text: String(view.get(spec.path) || "")
            hasCursor: rowItem.hasCursor
            font.family: view.fontFamily
            onActiveFocusChanged: if (activeFocus) view.editing = true
            onEditingFinished: {
              if (!reverting) view.set(spec.path, text)
              reverting = false
              view.endEdit()
            }
            Keys.onEscapePressed: function(event) {
              reverting = true
              text = String(view.get(spec.path) || "")
              view.endEdit()
              event.accepted = true
            }
          }
        }
      }
    }
  }
}
