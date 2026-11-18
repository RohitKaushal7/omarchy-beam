pragma Singleton
import QtQuick

QtObject {
  readonly property QtObject menu: QtObject {
    readonly property color text: "#dddddd"
    readonly property color selectedBackground: "#333333"
    readonly property color selectedText: "#ffffff"
  }
}
