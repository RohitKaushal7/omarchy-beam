import QtQuick

Item {
  property bool showLabel: true
  property string value: ""
  property var options: []
  property bool hasCursor: false
  property string fontFamily: ""
  signal changed(string value)
}
