import Quickshell
import QtQuick
import qs.Commons
import qs.Ui

// One result row, styled like an Omarchy menu row: icon · label · detail ·
// trailing hint. Answer rows show the result large; the ✦ marks a Jev pick.
BorderSurface {
  id: row

  required property int index
  required property string key
  required property string kind
  required property string icon
  required property string iconFont
  required property string appIcon
  required property string appId
  required property string label
  required property string detail
  required property string hint
  required property bool jev
  required property bool risky
  required property bool pending

  property bool hasCursor: false
  property bool confirming: false
  property bool copied: false
  property var appLibrary: null
  property color foreground: Color.menu.text
  property color selectedText: Color.menu.selectedText
  property color selectedBackground: Color.menu.selectedBackground
  property var selectedBorderSpec: Border.none()
  property string fontFamily: Style.font.menuFamily
  property int baseHeight: Style.space(50)
  property int detailHeight: Style.space(58)

  readonly property bool isApp: row.kind === "app"
  readonly property bool isAnswer: row.kind === "answer"
  readonly property real reservedLeft: Border.left(row.selectedBorderSpec)
  readonly property real reservedRight: Border.right(row.selectedBorderSpec)
  readonly property string trailing: row.copied ? "Copied"
    : (row.jev ? "✦" : (row.kind === "menu" ? "›" : (row.kind === "shortcut" ? "Tab" : row.hint)))

  height: row.detail.length > 0 || row.confirming ? row.detailHeight : row.baseHeight
  radius: Style.cornerRadius
  color: row.hasCursor ? row.selectedBackground : "transparent"
  borderSpec: row.hasCursor ? row.selectedBorderSpec : Border.none()

  Text {
    id: iconText
    textFormat: Text.PlainText
    visible: !row.isApp
    text: row.icon
    color: row.hasCursor ? row.selectedText : row.foreground
    opacity: row.isAnswer ? 0.7 : 1
    font.family: row.iconFont.length > 0 ? row.iconFont : row.fontFamily
    font.pixelSize: Style.font.iconLarge
    width: Style.space(36)
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    anchors.left: parent.left
    anchors.leftMargin: row.reservedLeft + Style.space(8)
    y: content.y + labelText.y + (labelText.height - height) / 2
  }

  Image {
    visible: row.isApp
    width: Style.font.iconLarge
    height: Style.font.iconLarge
    fillMode: Image.PreserveAspectFit
    sourceSize.width: width * Screen.devicePixelRatio
    sourceSize.height: height * Screen.devicePixelRatio
    source: row.isApp && row.appLibrary ? row.appLibrary.iconSource(row.appIcon) : ""
    asynchronous: true
    anchors.left: parent.left
    anchors.leftMargin: row.reservedLeft + Style.space(8) + (Style.space(36) - width) / 2
    y: content.y + labelText.y + (labelText.height - height) / 2
  }

  Column {
    id: content
    anchors.left: iconText.right
    anchors.leftMargin: Style.space(6)
    anchors.right: trail.left
    anchors.rightMargin: Style.space(8)
    anchors.verticalCenter: parent.verticalCenter
    spacing: Style.space(3)

    Text {
      id: labelText
      textFormat: Text.PlainText
      width: parent.width
      text: row.confirming ? "Press Enter again to " + row.label : row.label
      color: row.confirming ? Color.urgent : (row.hasCursor ? row.selectedText : row.foreground)
      opacity: row.pending ? 0.6 : 1
      font.family: row.fontFamily
      font.pixelSize: Style.font.heading
      font.weight: row.isAnswer ? Font.DemiBold : Font.Medium
      elide: Text.ElideRight
    }

    Text {
      textFormat: Text.PlainText
      width: parent.width
      visible: row.detail.length > 0 && !row.confirming
      text: row.detail
      color: row.foreground
      opacity: 0.52
      font.family: row.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
    }
  }

  Text {
    id: trail
    textFormat: Text.PlainText
    anchors.right: parent.right
    anchors.rightMargin: row.reservedRight + Style.space(10)
    y: content.y + labelText.y + (labelText.height - height) / 2
    text: row.trailing
    color: row.jev || row.copied ? row.selectedText : row.foreground
    opacity: row.jev || row.copied ? 0.9 : (row.kind === "menu" ? 0.36 : 0.45)
    font.family: row.fontFamily
    font.pixelSize: row.kind === "menu" || row.jev ? Style.font.heading : Style.font.bodySmall
  }
}
