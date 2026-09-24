import Quickshell
import Quickshell.Io
import QtQuick
import qs.Commons
import "../lib/apps.js" as Apps
import "../lib/proc.js" as Proc

// The same interface as Omarchy's app-library facade (entryName, entrySubtext,
// sortedEntries, iconSource, refreshIcons, launch, appsChanged), built from
// Quickshell's DesktopEntries. Beam uses it while omarchy-shell hands
// third-party `menu` plugins a null appLibrary: the shell checks
// Array.isArray(manifest.kinds), and the manifest it passes through its
// Instantiator model carries `kinds` as a Qt list, not a JS array. Once the
// shell provides the facade, Beam uses that instead.
Item {
  id: source
  visible: false

  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var configuredHidden: ({})
  property var desktopHidden: ({})

  signal appsChanged()

  function entryName(entry) {
    return String((entry && entry.name) || (entry && entry.id) || "")
  }

  function entrySubtext(entry) {
    return String((entry && entry.genericName) || "")
  }

  function sortedEntries(query) {
    var hidden = ({})
    for (var a in source.configuredHidden) hidden[a] = true
    for (var b in source.desktopHidden) hidden[b] = true
    return Apps.visibleEntries(DesktopEntries.applications.values || [], hidden)
  }

  function iconSource(icon) {
    var value = String(icon || "")
    if (!value) return Quickshell.iconPath("application-x-executable", true)
    if (value.indexOf("file://") === 0 || value.indexOf("image://") === 0) return value
    if (value.charAt(0) === "/") return Util.fileUrl(value)
    var themed = Quickshell.iconPath(value, true)
    return themed.length > 0 ? themed : Quickshell.iconPath("application-x-executable", true)
  }

  function refreshIcons() {
  }

  // Omarchy's launch path: gtk-launch in a uwsm scope, keeping the .desktop
  // suffix so ids like org.telegram.desktop resolve.
  function launch(desktopId, name) {
    var id = String(desktopId || "")
    if (id) Util.execDetached("uwsm-app -- gtk-launch " + Util.shellQuote(id + ".desktop"))
  }

  function hiddenScanCommand() {
    var desktop = [Quickshell.env("XDG_CURRENT_DESKTOP"), Quickshell.env("XDG_SESSION_DESKTOP"), Quickshell.env("DESKTOP_SESSION")]
      .filter(function(v) { return String(v || "").length > 0 }).join(":")
    return Proc.bounded([source.omarchyPath + "/shell/services/hidden-entries.sh", desktop], 10, 262144, true)
  }

  FileView {
    path: source.omarchyPath + "/default/omarchy/launcher.hides"
    watchChanges: true
    printErrors: false
    onLoaded: { source.configuredHidden = Apps.parseIdList(text()); source.appsChanged() }
    onFileChanged: reload()
    onLoadFailed: { source.configuredHidden = ({}); source.appsChanged() }
  }

  // No login shell on purpose (as Omarchy's own scan): a login shell's
  // profile can touch ~/.local/share and retrigger the desktop-entry watcher.
  Process {
    id: hiddenScan
    property string collected: ""
    command: source.hiddenScanCommand()
    onStarted: hiddenScan.collected = ""
    stdout: SplitParser { onRead: function(line) { hiddenScan.collected += line + "\n" } }
    onExited: function(exitCode) {
      if (exitCode !== 0) return  // timed out or oversized: keep the last good list
      source.desktopHidden = Apps.parseIdList(hiddenScan.collected)
      source.appsChanged()
    }
  }

  Connections {
    target: DesktopEntries.applications
    function onValuesChanged() {
      if (!hiddenScan.running) hiddenScan.running = true
      source.appsChanged()
    }
  }

  Component.onCompleted: hiddenScan.running = true
}
