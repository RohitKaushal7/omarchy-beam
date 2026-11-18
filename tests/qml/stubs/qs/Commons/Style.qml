pragma Singleton
import QtQuick

// Stand-in for Omarchy's qs.Commons Style, for qmltestrunner: the shell's own
// module needs Quickshell's built-in plugins, which only load inside quickshell.
QtObject {
  function space(n) { return Math.round(n) }
  function duration(ms) { return ms }
  readonly property int cornerRadius: 6
  readonly property QtObject spacing: QtObject {
    readonly property int xs: 4
    readonly property int md: 12
    readonly property int controlHeight: 32
  }
  readonly property QtObject font: QtObject {
    readonly property string family: "monospace"
    readonly property string menuFamily: "monospace"
    readonly property int bodySmall: 11
    readonly property int body: 12
    readonly property int title: 14
    readonly property int iconLarge: 18
  }
}
