import QtQuick
import qs.Commons
import qs.Ui

// The active search-engine chip before the query text: [ YouTube ].
BorderSurface {
  id: chip

  property string text: ""
  property color foreground: Color.menu.text
  property color accent: Color.menu.selectedText
  property string fontFamily: Style.font.menuFamily

  implicitWidth: label.implicitWidth + Style.spacing.controlPaddingX * 2
  implicitHeight: label.implicitHeight + Style.spacing.xs * 2
  radius: Style.cornerRadius
  color: Util.alpha(chip.accent, 0.14)
  borderSpec: Border.none()

  Text {
    id: label
    anchors.centerIn: parent
    textFormat: Text.PlainText
    text: chip.text
    color: chip.accent
    font.family: chip.fontFamily
    font.pixelSize: Style.font.title
    font.weight: Font.Medium
  }
}
