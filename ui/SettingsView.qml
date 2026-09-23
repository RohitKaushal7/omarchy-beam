import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui

// Beam settings, built from Omarchy's own controls. Every change goes through
// SettingsStore.set (validated, then written to shell.json by the shell).
FocusScope {
  id: view

  property var store: null
  property string jevStatus: "unknown"
  property color foreground: Color.menu.text
  property string fontFamily: Style.font.menuFamily

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
    { title: "Sources", items: [
      { path: "sources.apps", type: "bool", label: "Apps" },
      { path: "sources.actions", type: "bool", label: "Omarchy actions" },
      { path: "sources.recent", type: "bool", label: "Recent picks", description: "Shown before you type" },
      { path: "sources.calculator", type: "bool", label: "Calculator" },
      { path: "sources.units", type: "bool", label: "Unit conversion" },
      { path: "sources.currency", type: "bool", label: "Currency", description: "Daily rates from ExchangeRate-API" },
      { path: "sources.time", type: "bool", label: "Time zones and dates" },
      { path: "sources.developer", type: "bool", label: "Developer values", description: "Bases, colours, unix time, byte sizes" },
      { path: "sources.shortcuts", type: "bool", label: "Search shortcuts", description: "yt, g, gg… then Tab" },
      { path: "sources.urls", type: "bool", label: "Open URLs" },
      { path: "sources.webSearchRow", type: "bool", label: "Web search row" },
      { path: "sources.agentRow", type: "bool", label: "Ask agent row" }
    ] },
    { title: "Jev (match by meaning)", items: [
      { path: "jev.enabled", type: "bool", label: "Use Jev", description: view.jevText },
      { path: "jev.debounceMs", type: "int", label: "Pause before asking (ms)", from: 100, to: 2000, step: 50 },
      { path: "jev.minChars", type: "int", label: "Minimum characters", from: 1, to: 20, step: 1 },
      { path: "jev.cacheSize", type: "int", label: "Cached answers", from: 0, to: 10000, step: 100 },
      { path: "jev.keyFile", type: "text", label: "Key file" }
    ] },
    { title: "Calculator", items: [
      { path: "calc.homeCurrency", type: "text", label: "Home currency", description: "auto, or a code like INR" },
      { path: "calc.grouping", type: "choice", label: "Number grouping", options: ["auto", "indian", "international"] },
      { path: "calc.significantDigits", type: "int", label: "Significant digits", from: 3, to: 20, step: 1 },
      { path: "calc.ratesRefreshHours", type: "int", label: "Refresh rates every (hours)", from: 1, to: 720, step: 1 }
    ] },
    { title: "Search", items: [
      { path: "search.fallbackEngine", type: "text", label: "Web search row engine", description: "A shortcut keyword, e.g. g or ddg" }
    ] },
    { title: "Behaviour", items: [
      { path: "behavior.confirmRisky", type: "bool", label: "Confirm reboot, remove, update and install" },
      { path: "behavior.keybindingHints", type: "bool", label: "Show keybinding hints" },
      { path: "behavior.agentCommand", type: "text", label: "Agent command" },
      { path: "engine.idleExitMinutes", type: "int", label: "Stop the helper after idle (minutes)", from: 1, to: 1440, step: 1 }
    ] },
    { title: "Look", items: [
      { path: "look.width", type: "int", label: "Width", from: 400, to: 1000, step: 20 },
      { path: "look.maxRows", type: "int", label: "Visible rows", from: 3, to: 20, step: 1 }
    ] }
  ]

  function get(path) {
    var parts = path.split(".")
    var group = view.settings[parts[0]] || {}
    return group[parts[1]]
  }

  function set(path, value) {
    if (view.store) view.store.set(path, value)
  }

  Keys.onEscapePressed: view.closeRequested()

  Flickable {
    id: flick
    anchors.fill: parent
    contentHeight: column.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    Column {
      id: column
      width: flick.width
      spacing: Style.spacing.md

      Text {
        textFormat: Text.PlainText
        text: "Beam settings  ·  Esc to go back  ·  custom search shortcuts: search.engines in shell.json"
        color: view.foreground
        opacity: 0.52
        font.family: view.fontFamily
        font.pixelSize: Style.font.bodySmall
        width: parent.width
        wrapMode: Text.WordWrap
      }

      Repeater {
        model: view.sections

        delegate: Column {
          id: section
          required property var modelData
          width: column.width
          spacing: Style.spacing.xs

          PanelSectionHeader {
            text: section.modelData.title
            foreground: view.foreground
            fontFamily: view.fontFamily
          }

          Repeater {
            model: section.modelData.items

            delegate: Loader {
              id: field
              required property var modelData
              readonly property var spec: modelData
              width: section.width
              sourceComponent: modelData.type === "bool" ? boolField
                : (modelData.type === "int" ? intField : (modelData.type === "choice" ? choiceField : textField))
            }
          }
        }
      }
    }
  }

  Component {
    id: boolField
    Toggle {
      readonly property var spec: parent ? parent.spec : ({})
      label: spec.label || ""
      description: spec.description || ""
      checked: view.get(spec.path) === true
      fontFamily: view.fontFamily
      onClicked: view.set(spec.path, !checked)
    }
  }

  Component {
    id: intField
    NumberField {
      readonly property var spec: parent ? parent.spec : ({})
      label: spec.label || ""
      value: Number(view.get(spec.path)) || 0
      from: spec.from
      to: spec.to
      stepSize: spec.step || 1
      fontFamily: view.fontFamily
      onModified: function(value) { view.set(spec.path, value) }
    }
  }

  Component {
    id: choiceField
    Dropdown {
      readonly property var spec: parent ? parent.spec : ({})
      label: spec.label || ""
      value: String(view.get(spec.path))
      options: spec.options || []
      fontFamily: view.fontFamily
      onChanged: function(value) { view.set(spec.path, value) }
    }
  }

  Component {
    id: textField
    Column {
      readonly property var spec: parent ? parent.spec : ({})
      spacing: Style.spacing.xs

      Text {
        textFormat: Text.PlainText
        text: spec.label + (spec.description ? "  ·  " + spec.description : "")
        color: view.foreground
        font.family: view.fontFamily
        font.pixelSize: Style.font.body
      }

      TextField {
        width: parent.width
        text: String(view.get(spec.path) || "")
        onEditingFinished: view.set(spec.path, text)
      }
    }
  }
}
