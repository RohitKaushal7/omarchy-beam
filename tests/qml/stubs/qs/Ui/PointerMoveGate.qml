import QtQuick

QtObject {
  property Item referenceItem: null
  function reset() {}
  function moved(item, mouse) { return false }
}
