import Quickshell
import Quickshell.Io
import QtQuick
import "../lib/menu.js" as Menu

// Omarchy menu entries (default + user JSONC, `when:` guards), apps from the
// shell's app library and keybinding hints, ready for search and for Jev.
Item {
  id: source
  visible: false

  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var appLibrary: null
  property var defaultItems: []
  property var userItems: []
  property var items: ({})
  property var itemOrder: []
  property var whenResults: ({})
  property var entries: []
  property var bindings: []
  property bool guardsPending: false

  signal changed()

  function rebuildTree() {
    var tree = Menu.mergeMenuSources(source.defaultItems, source.userItems)
    source.items = tree.items
    source.itemOrder = tree.itemOrder
    source.rebuildEntries()
    source.evaluateGuards()
  }

  function appEntries() {
    if (!source.appLibrary) return []
    var rows = source.appLibrary.sortedEntries("")
    var apps = []
    for (var i = 0; i < rows.length; i++) {
      var entry = rows[i].entry
      if (!entry || !entry.id) continue
      var keywords = []
      try {
        for (var k = 0; entry.keywords && k < entry.keywords.length; k++) keywords.push(String(entry.keywords[k]))
      } catch (e) { }
      apps.push({
        id: String(entry.id),
        name: source.appLibrary.entryName(entry),
        subtext: source.appLibrary.entrySubtext(entry),
        keywords: keywords,
        icon: String(entry.icon || "")
      })
    }
    return Menu.appItems(apps, source.itemOrder.length)
  }

  function rebuildEntries() {
    source.entries = Menu.searchable(source.items, source.itemOrder, source.whenResults).concat(source.appEntries())
    source.changed()
  }

  function keyFor(entry) {
    if (entry.kind === "app") return "app:" + entry.appId
    return (entry.kind === "menu" || entry.kind === "link" ? "menu:" : "action:") + entry.id
  }

  function entryForKey(key) {
    for (var i = 0; i < source.entries.length; i++) {
      if (source.keyFor(source.entries[i]) === key) return source.entries[i]
    }
    return null
  }

  function detailFor(entry) {
    return entry.kind === "app" ? (entry.description || "") : Menu.parentPathFor(source.items, entry.id)
  }

  // Jev's option list: one line per app/action/submenu.
  function catalog() {
    var out = []
    for (var i = 0; i < source.entries.length; i++) {
      var entry = source.entries[i]
      if (!Menu.jevEligible(entry)) continue
      out.push({ key: source.keyFor(entry), label: entry.label,
                 path: entry.kind === "app" ? (entry.description || "App") : Menu.parentPathFor(source.items, entry.id) })
    }
    return out
  }

  function hintFor(label) {
    return Menu.hintFor(label, source.bindings)
  }

  // Re-check `when:` guards and keybindings; called on every open, as the
  // Omarchy menu does. Results replace the entries for the next keystroke.
  function refresh() {
    source.evaluateGuards()
    if (!bindProc.running) bindProc.running = true
  }

  function evaluateGuards() {
    if (guardProc.running) {
      source.guardsPending = true
      return
    }
    source.guardsPending = false
    var script = Menu.guardScript(source.items)
    if (!script) return
    guardProc.collected = ""
    guardProc.command = ["bash", "-lc", script]
    guardProc.running = true
  }

  FileView {
    path: source.omarchyPath + "/default/omarchy/omarchy-menu.jsonc"
    watchChanges: true
    printErrors: false
    onLoaded: { source.defaultItems = Menu.parseMenuJsonc(text()); source.rebuildTree() }
    onFileChanged: reload()
  }

  FileView {
    path: Quickshell.env("HOME") + "/.config/omarchy/extensions/omarchy-menu.jsonc"
    watchChanges: true
    printErrors: false
    onLoaded: { source.userItems = Menu.parseMenuJsonc(text()); source.rebuildTree() }
    onLoadFailed: { source.userItems = []; source.rebuildTree() }
    onFileChanged: reload()
  }

  Process {
    id: guardProc
    property string collected: ""
    stdout: SplitParser { onRead: function(data) { guardProc.collected += data + "\n" } }
    onExited: function(exitCode, exitStatus) {
      if (exitCode === 0 && exitStatus === 0) {
        source.whenResults = Menu.parseGuardOutput(guardProc.collected)
        source.rebuildEntries()
      }
      if (source.guardsPending) Qt.callLater(source.evaluateGuards)
    }
  }

  Process {
    id: bindProc
    property string collected: ""
    command: ["bash", "-lc", "omarchy menu keybindings --print"]
    onStarted: bindProc.collected = ""
    stdout: SplitParser { onRead: function(data) { bindProc.collected += data + "\n" } }
    onExited: function(exitCode) {
      if (exitCode === 0) source.bindings = Menu.parseKeybindings(bindProc.collected)
    }
  }

  Connections {
    target: source.appLibrary
    function onAppsChanged() { source.rebuildEntries() }
  }

  onAppLibraryChanged: source.rebuildEntries()
}
