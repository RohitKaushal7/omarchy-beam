import QtQuick
import QtTest
import "../../ui"
import "../../lib/settings.js" as Settings

// Offscreen: QT_QPA_PLATFORM=offscreen /usr/lib/qt6/bin/qmltestrunner -import tests/qml/stubs -input tests/qml
Item {
  id: root
  width: 560
  height: 420

  QtObject {
    id: store
    property var settings: Settings.merge({})
    function set(path, value) { store.settings = Settings.withValue(store.settings, path, value) }
  }

  // Colours are passed in, as Beam does: once an earlier test file has loaded,
  // qmltestrunner resolves `Color` to QtQuick's own type, not the qs.Commons
  // stub, so the view's Color.menu defaults would read undefined.
  SignalSpy { id: pasteSpy; target: view; signalName: "pasteRequested" }
  SignalSpy { id: copySpy; target: view; signalName: "copyRequested" }

  SettingsView {
    id: view
    anchors.fill: parent
    store: store
    foreground: "#dddddd"
    selectedBackground: "#333333"
    selectedText: "#ffffff"
  }

  TestCase {
    name: "SettingsExamples"
    when: windowShown

    function list() { return findChild(view, "settingsList") }
    function row(i) { return list().itemAtIndex(i).item }
    function examples(i) { return findChild(row(i), "examples") }
    function indexOf(path) {
      for (var i = 0; i < view.rows.length; i++) if (view.rows[i].path === path) return i
      return -1
    }
    function goTo(path) {
      var target = indexOf(path)
      verify(target > 0, path)
      view.reset()
      while (view.cursor !== target) view.move(1)
      wait(0)
    }
    function fullyVisible(i) {
      var l = list()
      var r = row(i)
      var top = r.mapToItem(l, 0, 0).y
      return top >= -0.5 && top + r.height <= l.height + 0.5
    }

    function init() {
      store.settings = Settings.merge({})
      view.reset()
      wait(0)
    }

    function test_only_the_focused_feature_expands() {
      var first = view.cursor
      compare(view.rows[first].path, "sources.apps")
      verify(examples(first).item !== null)
      verify(row(first).height > view.rowHeight)
      wait(0)  // the Column lays its lines out at polish time; the row must already fit them
      compare(row(first).height, view.rowHeight + Math.round(examples(first).item.implicitHeight) + 10)
      var base = view.rowHeight
      view.move(1)
      wait(0)
      compare(examples(first).item, null)
      compare(row(first).height, base)
      verify(examples(view.cursor).item !== null)
    }

    function test_settings_that_are_not_features_stay_one_line() {
      var paths = ["look.width", "look.maxRows", "jev.debounceMs", "engine.idleExitMinutes", "jev.keyFile"]
      for (var i = 0; i < paths.length; i++) {
        goTo(paths[i])
        compare(examples(view.cursor).item, null, paths[i])
        verify(row(view.cursor).height <= view.detailRowHeight, paths[i])
      }
    }

    function test_the_focused_row_stays_fully_in_view() {
      var fields = 0
      for (var i = 0; i < view.rows.length; i++) if (view.rows[i].type !== "header") fields++
      // Checked straight after the key, before any later pass could fix it up.
      for (var step = 0; step < fields; step++) {
        view.move(1)
        verify(fullyVisible(view.cursor) || row(view.cursor).height > list().height, view.rows[view.cursor].path)
      }
      view.move(-6)
      verify(fullyVisible(view.cursor))
    }

    function test_a_feature_that_is_off_still_shows_its_examples() {
      store.set("sources.apps", false)
      view.reset()
      wait(0)
      var block = examples(view.cursor).item
      verify(block !== null)
      verify(findChild(block, "offCaption").visible)
      store.set("sources.apps", true)
      wait(0)
      verify(!findChild(examples(view.cursor).item, "offCaption").visible)
    }

    function test_a_held_key_flips_a_switch_once() {
      goTo("behavior.confirmRisky")
      verify(view.activeFocus)
      var before = store.settings.behavior.confirmRisky
      wait(80)
      keyClick(Qt.Key_Space)
      compare(store.settings.behavior.confirmRisky, !before)
      // An input method's repeat: a release and a press back to back.
      keyClick(Qt.Key_Space)
      compare(store.settings.behavior.confirmRisky, !before, "a repeat")
      keyClick(Qt.Key_Space)
      compare(store.settings.behavior.confirmRisky, !before, "repeats right behind a release do nothing")
      wait(80)
      keyClick(Qt.Key_Space)
      compare(store.settings.behavior.confirmRisky, before, "a fresh press flips it back")
    }

    function test_text_fields_use_beams_clipboard_path() {
      store.set("jev.keyFile", "/tmp/key")
      goTo("jev.keyFile")
      wait(80)
      keyClick(Qt.Key_Return)
      verify(view.editing)
      var editor = view.activeEditor
      compare(editor.selectedText, "/tmp/key")
      verify(!editor.selectByMouse)
      pasteSpy.clear()
      copySpy.clear()
      keyClick(Qt.Key_V, Qt.ControlModifier)
      keyClick(Qt.Key_Insert, Qt.ShiftModifier)
      compare(pasteSpy.count, 2)
      keyClick(Qt.Key_C, Qt.ControlModifier)
      compare(copySpy.count, 1)
      compare(copySpy.signalArguments[0][0], "/tmp/key")
      keyClick(Qt.Key_X, Qt.ControlModifier)
      keyClick(Qt.Key_Delete, Qt.ShiftModifier)
      compare(editor.text, "/tmp/key", "no cut")
      view.insertText("/home/me/key")
      compare(editor.text, "/home/me/key", "the bounded paste replaces the selection")
      mouseClick(editor, 5, editor.height / 2, Qt.MiddleButton)
      compare(editor.text, "/home/me/key", "no middle-click paste")
      keyClick(Qt.Key_Escape)
      verify(!view.editing)
      compare(store.settings.jev.keyFile, "/home/me/key")
      view.insertText("late")
      compare(store.settings.jev.keyFile, "/home/me/key", "a paste that lands after editing is dropped")
    }

    function test_shortcut_examples_follow_the_engines() {
      goTo("sources.shortcuts")
      var before = row(view.cursor).height
      store.set("search.engines", [{ keyword: "amz", name: "Amazon", url: "https://www.amazon.in/s?k=%s" }])
      compare(row(view.cursor).height, before + view.exampleLineHeight + view.exampleSpacing)
      wait(0)
      verify(fullyVisible(view.cursor))
    }
  }
}
