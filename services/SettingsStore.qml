import Quickshell
import Quickshell.Io
import QtQuick
import "../lib/settings.js" as Settings

// Beam's settings live inline on its entry in ~/.config/omarchy/shell.json
// (Omarchy storage rule 3): read through a watched FileView, written through
// the shell's updateEntryInline so the shell stays the file's only writer.
Item {
  id: store
  visible: false

  property string pluginId: "dev.reuk.beam"
  property var shell: null
  property var settings: Settings.merge({})

  signal changed()

  function load(text) {
    var config = ({})
    try { config = JSON.parse(text) } catch (e) { config = ({}) }
    store.settings = Settings.merge(Settings.findEntry(config, store.pluginId))
    store.changed()
  }

  function set(path, value) {
    var next = Settings.withValue(store.settings, path, value)
    if (JSON.stringify(next) === JSON.stringify(store.settings)) return
    store.settings = next
    store.changed()
    if (store.shell && typeof store.shell.updateEntryInline === "function")
      store.shell.updateEntryInline(store.pluginId, next)
  }

  FileView {
    path: Quickshell.env("HOME") + "/.config/omarchy/shell.json"
    watchChanges: true
    printErrors: false
    onLoaded: store.load(text())
    onLoadFailed: store.load("{}")
    onFileChanged: reload()
  }
}
