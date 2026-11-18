import QtQuick

Item {
  property string label: ""
  property int value: 0
  property int from: 0
  property int to: 100
  property int stepSize: 1
  property real fieldWidth: 120
  property bool hasCursor: false
  property string fontFamily: ""
  property FieldStub field: FieldStub {}
  signal modified(int value)
  width: fieldWidth
  height: 32
}
