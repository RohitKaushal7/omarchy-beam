import Quickshell
import Quickshell.Io
import QtQuick
import "../lib/settings.js" as Settings

// Beam's settings live inline on its entry in ~/.config/omarchy/shell.json
// (Omarchy storage rule 3): read through a watched FileView, written through
// the shell's updateEntryInline while Beam holds a live shell API.
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
    if (store.shell && typeof store.shell.updateEntryInline === "function") {
      store.shell.updateEntryInline(store.pluginId, next)
      return
    }
    // omarchy-shell rebuilds plugin APIs whenever shell.json changes and does
    // not hand a kept-loaded plugin the new one, so after the first write
    // `shell` is null. Write Beam's entry the way the shell would; the shell
    // watches the file and reloads it.
    var text = Settings.applyEntry(configFile.text(), store.pluginId, next)
    if (text !== null) configFile.setText(text)
  }

  FileView {
    id: configFile
    path: Quickshell.env("HOME") + "/.config/omarchy/shell.json"
    watchChanges: true
    blockLoading: true
    atomicWrites: true
    printErrors: false
    onLoaded: store.load(text())
    onLoadFailed: store.load("{}")
    onFileChanged: reload()
  }
}
