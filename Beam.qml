import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import QtQuick
import qs.Commons
import qs.Ui
import "services"
import "ui"
import "lib/menu.js" as Menu
import "lib/shortcuts.js" as Shortcuts
import "lib/precheck.js" as Precheck
import "lib/compose.js" as Compose
import "lib/proc.js" as Proc

// Beam: one box for apps, Omarchy actions, inline answers, search shortcuts
// and URLs. Stability rules (spec §2.5): only keystrokes rebuild the list;
// late data may only insert rows; the highlight follows the item's key.
Item {
  id: root

  // Injected by omarchy-shell.
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null

  readonly property string pluginId: (root.manifest && root.manifest.id) || "dev.reuk.beam"
  // Omarchy's app library, which the shell hands every `menu` plugin: the same
  // apps, hidden entries, launcher, terminal-app handling and launch feedback
  // as the Omarchy menu.
  readonly property var appLibrary: root.shell && root.shell.appLibrary ? root.shell.appLibrary : null
  readonly property var settings: settingsStore.settings
  readonly property var engines: Shortcuts.engines(root.settings.search.engines, root.settings.search.disabledBuiltins)
  readonly property string stateDir: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/beam"

  property bool opened: false
  property bool settingsOpen: false
  property string filterText: ""
  property var chip: null
  property var rows: []
  property string selectedKey: ""
  readonly property int selectedIndex: Compose.indexOfKey(root.rows, root.selectedKey)
  property int serial: 0
  property var pendingLocal: null
  property var lastLocal: null
  property bool enterQueued: false
  property bool pasteQueued: false
  // The serial of the last keystroke sent to the helper, and of the last reply.
  property int answerAsked: -1
  property int answerHeard: -1
  property string confirmKey: ""
  property string copiedKey: ""
  property var recent: []
  property string jevStatus: "unknown"
  property bool animateInsert: false
  property int layoutSerial: 0
  // "Press Enter again" is for the row it was armed on; moving away cancels it.
  onSelectedKeyChanged: if (root.confirmKey && root.selectedKey !== root.confirmKey) root.confirmKey = ""
  // The search line shows filterText; edits made here (Backspace, paste, chips) flow back to it.
  onFilterTextChanged: if (filterInput.text !== root.filterText) filterInput.text = root.filterText

  // Omarchy menu surface tokens, so themes that style the menu style Beam.
  property color background: Color.menu.background
  property color foreground: Color.menu.text
  property color border: Color.menu.border
  property var borderSpec: Border.surfaceSpec("menu", "border", border, Math.max(1, Style.space(2)))
  property color scrim: Color.menu.scrim
  property color selectedBackground: Color.menu.selectedBackground
  property color selectedText: Color.menu.selectedText
  property color selectedBorder: Color.menu.selectedBorder
  property var selectedBorderSpec: Border.surfaceSpec("menu", "selected-border", selectedBorder, 0)
  readonly property int cornerRadius: Style.cornerRadius
  property string fontFamily: Style.font.menuFamily
  property int contentMargin: Style.spacing.panelPadding
  property int headerHeight: Math.max(Style.space(34), Style.font.title + Style.spacing.controlPaddingY * 2)
  property int contentSpacing: Style.spacing.md
  property int baseRowHeight: Math.max(Style.space(50), Style.font.body + Style.spacing.rowPaddingX * 2)
  property int detailRowHeight: Math.max(Style.space(58), Style.font.body + Style.font.caption + Style.spacing.rowPaddingX * 2)
  property int rowPeek: Math.round(baseRowHeight * 0.55)
  property int rowSpacing: Style.spacing.xs
  property int cardWidth: Math.min(Style.space(root.settings.look.width), panel.width - Style.gapsOut * 2)
  property int visibleRowsHeight: root.settingsOpen ? Math.round(panel.height * 0.6) : rowListHeight(root.layoutSerial)
  property bool showList: root.settingsOpen || displayModel.count > 0 || root.filterText.length > 0
  property int cardHeight: Math.min(contentMargin * 2 + headerHeight + (showList ? contentSpacing + visibleRowsHeight : 0),
                                    panel.height - Style.gapsOut * 2)

  // ── lifecycle ───────────────────────────────────────────────────────────

  function open(payloadJson) {
    root.opened = true
    root.settingsOpen = false
    root.chip = null
    root.confirmKey = ""
    root.copiedKey = ""
    root.enterQueued = false
    root.pasteQueued = false
    root.setText("")
    engine.start()
    menuSource.refresh()
    if (root.appLibrary) root.appLibrary.refreshIcons()
    Qt.callLater(function() { filterInput.forceActiveFocus() })
  }

  function close() {
    root.opened = false
    answerTimer.stop()
    enterWait.stop()
    jevTimer.stop()
    closeTimer.stop()
  }

  function dismiss() {
    root.close()
    // The shell API can go stale while Beam stays loaded (see SettingsStore);
    // the IPC command reaches the host either way.
    if (root.shell && typeof root.shell.hide === "function") root.shell.hide(root.pluginId)
    else Quickshell.execDetached(["omarchy-shell", "shell", "hide", root.pluginId])
  }

  function toggle() {
    if (root.opened) root.dismiss()
    else root.open("{}")
  }

  // `omarchy-shell shell call dev.reuk.beam status x` — a snapshot for troubleshooting.
  function status(arg) {
    return JSON.stringify({ hasShell: !!root.shell, opened: root.opened, engineReady: engine.ready, engineDisabled: engine.disabled,
                            jev: root.jevStatus, entries: menuSource.entries.length,
                            appLibrary: root.appLibrary ? "shell" : "none",
                            card: { x: card.x, y: card.y, width: card.width, height: card.height },
                            settingsCursor: settingsView.cursor,
                            settingsEditing: settingsView.editing,
                            filterText: root.filterText,
                            rows: root.rows.map(function(r) { return r.kind + " " + r.key }),
                            settings: root.settings })
  }

  // ── typing → rows ───────────────────────────────────────────────────────

  function answersEnabled() {
    var s = root.settings.sources
    return s.calculator || s.units || s.currency || s.time || s.developer
  }

  function setText(text) {
    root.filterText = text
    root.serial += 1
    root.confirmKey = ""
    root.enterQueued = false  // an Enter waiting on the previous text must not act on this one
    enterWait.stop()
    jevTimer.stop()
    var local = root.localParts(text)
    if (!root.chip && text.trim() && root.answersEnabled() && !engine.disabled && Precheck.mayBeAnswer(text)) {
      root.pendingLocal = local
      root.answerAsked = root.serial
      engine.send({ op: "answer", id: root.serial, q: text })
      answerTimer.restart()
    } else {
      root.commit([], local)
    }
  }

  function entryRow(entry) {
    var hint = root.settings.behavior.keybindingHints && Menu.hintAllowed(entry) ? menuSource.hintFor(entry.label) : ""
    var risky = root.settings.behavior.confirmRisky && Menu.isRisky(entry)
    return Compose.entryRow(entry, menuSource.detailFor(entry), hint, risky)
  }

  function searchEntries() {
    var s = root.settings.sources
    if (s.apps && s.actions) return menuSource.entries
    return menuSource.entries.filter(function(e) { return Menu.allowedBySources(e, s) })
  }

  function recentRows() {
    var out = []
    for (var i = 0; i < root.recent.length && out.length < 6; i++) {
      var entry = menuSource.entryForKey(root.recent[i].key)
      if (entry && Menu.allowedBySources(entry, root.settings.sources)) out.push(root.entryRow(entry))
    }
    return out
  }

  // Recent picks break ties between equally good matches (see Menu.search).
  function recentRanker() {
    var rank = ({})
    for (var i = 0; i < root.recent.length; i++) {
      var key = root.recent[i] && root.recent[i].key
      if (key && rank[key] === undefined) rank[key] = i
    }
    return function(entry) {
      var at = rank[menuSource.keyFor(entry)]
      return at === undefined ? -1 : at
    }
  }

  function localParts(text) {
    var t = text.trim()
    var s = root.settings.sources
    var parts = { lead: [], results: [], fallbacks: [], strongLocal: false, url: "", inline: null }
    if (root.chip) {
      if (t) parts.lead.push(Compose.shortcutRow(root.chip, t))
      parts.strongLocal = true
      return parts
    }
    if (!t) {
      parts.results = s.recent ? root.recentRows() : []
      parts.strongLocal = true
      return parts
    }
    if (/^beam( settings?)?$/i.test(t)) {
      parts.lead.push(Compose.row({ key: "settings", kind: "settings", icon: "", label: "Beam settings",
                                    detail: "Sources, Jev, calculator, search shortcuts" }))
    }
    if (s.shortcuts) {
      parts.inline = Shortcuts.inlineSearch(t, root.engines)
      var candidate = Shortcuts.chipFor(t, root.engines)
      if (parts.inline) parts.lead.push(Compose.shortcutRow(parts.inline.engine, parts.inline.query))
      else if (candidate) parts.lead.push(Compose.shortcutRow(candidate, ""))
    }
    if (s.urls) {
      parts.url = Shortcuts.detectUrl(t)
      if (parts.url) parts.lead.push(Compose.urlRow(parts.url))
    }
    var found = Menu.search(menuSource.items, root.searchEntries(), t, 30, s.recent ? root.recentRanker() : null)
    for (var i = 0; i < found.length; i++) {
      if (found[i].score < Menu.STRONG_SCORE) parts.strongLocal = true
      parts.results.push(root.entryRow(found[i].entry))
    }
    if (s.webSearchRow) {
      var engineForRow = Shortcuts.findEngine(root.engines, root.settings.search.fallbackEngine) || root.engines[0]
      if (engineForRow) parts.fallbacks.push(Compose.webRow(engineForRow, t))
    }
    if (s.agentRow) parts.fallbacks.push(Compose.agentRow(t))
    return parts
  }

  // One redraw per keystroke (spec §2.5 rule 3).
  function commit(answers, local) {
    answerTimer.stop()
    root.pendingLocal = null
    root.lastLocal = local
    var next = Compose.compose({ answers: Compose.answerRows(answers), lead: local.lead,
                                 results: local.results, fallbacks: local.fallbacks, text: root.filterText.trim() })
    root.replaceRows(next)
    root.selectedKey = Compose.firstSelectableKey(next)
    root.scheduleJev(answers.length > 0, local)
    if (root.enterQueued) {
      if (root.awaitingAnswer()) enterWait.start()  // the helper is slow to start; hold Enter for it
      else root.flushEnter()
    }
  }

  function replaceRows(next) {
    root.animateInsert = false
    displayModel.clear()
    for (var i = 0; i < next.length; i++) displayModel.append(next[i])
    root.rows = next
    root.layoutSerial += 1
    pointerGate.reset()
    Qt.callLater(root.revealCursor)
  }

  // Late data may only insert (rule 2); the highlight keeps its key (rule 1).
  function lateInsert(newRow) {
    var out = Compose.lateInsert(root.rows, newRow)
    if (out.removed >= 0) displayModel.remove(out.removed)  // the "No matches" message
    if (out.index < 0) {
      if (out.marked >= 0) displayModel.setProperty(out.marked, "jev", true)
      root.rows = out.rows
      return
    }
    root.animateInsert = true
    displayModel.insert(out.index, newRow)
    root.rows = out.rows
    if (!root.selectedKey || root.selectedKey === "empty") root.selectedKey = newRow.key
    root.layoutSerial += 1
    Qt.callLater(root.revealCursor)
  }

  function updateAnswers(answers) {
    var fresh = Compose.answerRows(answers)
    for (var i = 0; i < fresh.length; i++) {
      var at = Compose.indexOfKey(root.rows, fresh[i].key)
      if (at >= 0) {
        displayModel.set(at, fresh[i])
        var copy = root.rows.slice()
        copy[at] = fresh[i]
        root.rows = copy
      } else {
        root.lateInsert(fresh[i])
      }
    }
  }

  function scheduleJev(hasAnswers, local) {
    var want = Compose.jevWanted({
      enabled: root.settings.jev.enabled,
      keyAvailable: root.jevStatus === "env" || root.jevStatus === "file",
      text: root.filterText, minChars: root.settings.jev.minChars, hasAnswers: hasAnswers,
      chip: !!root.chip, url: !!local.url, inlineSearch: !!local.inline, strongLocal: local.strongLocal
    })
    if (!want) return
    jevTimer.interval = root.settings.jev.debounceMs
    jevTimer.forSerial = root.serial
    jevTimer.restart()
  }

  // ── engine ──────────────────────────────────────────────────────────────

  function sendConfig() {
    engine.send({ op: "config", settings: root.settings })
  }

  function sendCatalog() {
    var s = root.settings.sources
    var items = menuSource.catalog().filter(function(item) {
      return item.key.indexOf("app:") === 0 ? s.apps : s.actions
    })
    engine.send({ op: "catalog", items: items })
  }

  function onEngineMessage(msg) {
    if (msg.op === "ready") {
      root.sendConfig()
      root.sendCatalog()
    } else if (msg.op === "config") {
      root.jevStatus = String(msg.jev || "unknown")
    } else if (msg.op === "answer") {
      if (msg.id !== root.serial || !root.opened) return
      root.answerHeard = msg.id
      if (root.pendingLocal) root.commit(msg.answers || [], root.pendingLocal)
      else if (msg.update) root.updateAnswers(msg.answers || [])
      else {
        var late = Compose.answerRows(msg.answers || [])
        for (var i = 0; i < late.length; i++) root.lateInsert(late[i])
        if (root.enterQueued) {
          // Enter was held for this answer, so it gets the cursor, as it would have on time.
          if (late.length > 0) root.selectedKey = late[0].key
          root.flushEnter()
        }
      }
    } else if (msg.op === "jev") {
      if (msg.status) root.jevStatus = String(msg.status)
      if (msg.id !== root.serial || !msg.pick || !root.opened) return
      var entry = menuSource.entryForKey(msg.pick.key)
      if (!entry || !Menu.allowedBySources(entry, root.settings.sources)) return
      var starred = root.entryRow(entry)
      starred.jev = true
      root.lateInsert(starred)
    }
  }

  // ── keys and actions ────────────────────────────────────────────────────

  function move(delta) {
    var next = Compose.nextSelectable(root.rows, root.selectedIndex, delta)
    if (next < 0) return
    root.selectedKey = root.rows[next].key
    root.confirmKey = ""
    pointerGate.reset()
    root.revealCursor()
  }

  function tab() {
    root.confirmKey = ""
    var t = root.filterText.trim()
    if (!root.settings.sources.shortcuts || root.chip) return
    var engineChip = Shortcuts.chipFor(t, root.engines)
    if (engineChip) {
      root.chip = engineChip
      root.setText("")
      return
    }
    var inline = Shortcuts.inlineSearch(t, root.engines)
    if (inline) {
      root.chip = inline.engine
      root.setText(inline.query)
    }
  }

  // An answer was asked for this text and has not come back, and the text
  // reads like one (357/2, not firefox 2). Only a starting or restarting
  // helper is ever this slow.
  function awaitingAnswer() {
    return root.answerAsked === root.serial && root.answerHeard !== root.serial && !engine.disabled
      && Precheck.likelyAnswer(root.filterText)
  }

  // paste: Shift+Enter, which also types an answer into the focused app.
  // Enter waits for the first redraw (at most 40 ms) and, for text that reads
  // like a sum, for its answer (at most enterWait), so 357/2⏎ never falls
  // through to web search.
  function enter(paste) {
    if (answerTimer.running || root.awaitingAnswer()) {
      root.enterQueued = true
      root.pasteQueued = !!paste
      if (!answerTimer.running) enterWait.start()
      return
    }
    root.activateSelected(paste)
  }

  function flushEnter() {
    enterWait.stop()
    if (!root.enterQueued) return
    root.enterQueued = false
    root.activateSelected(root.pasteQueued)
  }

  function activateSelected(paste) {
    if (root.selectedIndex >= 0) root.activate(root.rows[root.selectedIndex], paste)
  }

  function paste() {
    root.confirmKey = ""
    if (!pasteProc.running) pasteProc.running = true
  }

  // The text goes to wl-copy on stdin, never on a command line. With paste,
  // Shift+Insert follows once wl-copy holds it, as the clipboard picker does.
  function copyText(text, paste) {
    copyProc.pending.push({ text: String(text), paste: !!paste })
    if (!copyProc.running) copyProc.next()
  }

  function copySelected() {
    root.confirmKey = ""
    if (root.selectedIndex < 0) return
    var r = root.rows[root.selectedIndex]
    var value = r.kind === "answer" ? r.copy : (r.kind === "url" ? r.url : (r.kind === "action" ? r.action : ""))
    if (value) root.copyText(value)
  }

  // The helper persists recent.json; the in-memory list updates at once, since
  // a FileView watching a file that did not exist yet never sees it appear.
  function remember(r) {
    if (!root.settings.sources.recent) return
    root.recent = Compose.rememberRecent(root.recent, r, 20)
    engine.send({ op: "recent", entry: r })
  }

  function launch(argv) {
    root.dismiss()
    Util.execArgv(argv)
  }

  function activate(r, paste) {
    if (!r) return
    if (r.kind === "answer") {
      if (!r.copy) return
      root.copyText(r.copy, paste)
      engine.send({ op: "used", copy: r.copy })
      if (paste) {
        root.dismiss()  // the paste goes to whatever had focus before Beam
        return
      }
      root.copiedKey = r.key
      closeTimer.restart()
    } else if (r.kind === "shortcut") {
      root.chip = Shortcuts.findEngine(root.engines, r.target)
      root.setText("")
    } else if (r.kind === "web") {
      var searchEngine = Shortcuts.findEngine(root.engines, r.target)
      var query = r.key === "web" ? root.filterText.trim() : r.label
      if (searchEngine) root.launch(["omarchy-launch-browser", Shortcuts.searchUrl(searchEngine, query)])
    } else if (r.kind === "url") {
      root.launch(["omarchy-launch-browser", r.url])
    } else if (r.kind === "agent") {
      var argv = String(root.settings.behavior.agentCommand).trim().split(/\s+/)
      root.launch(argv.concat([root.filterText.trim()]))
    } else if (r.kind === "settings") {
      root.openSettings()
    } else if (r.kind === "app") {
      root.remember(r)
      root.dismiss()
      if (root.appLibrary) root.appLibrary.launch(r.appId, r.label)
    } else if (r.kind === "menu") {
      root.remember(r)
      root.launch(["omarchy-menu", "summon", r.target])
    } else if (r.kind === "action") {
      if (r.risky && root.confirmKey !== r.key) {
        root.confirmKey = r.key
        return
      }
      root.remember(r)
      root.dismiss()
      Util.execDetached(r.action)
    }
  }

  function openSettings() {
    root.settingsOpen = true
    Qt.callLater(function() { settingsView.reset() })
  }

  function closeSettings() {
    root.settingsOpen = false
    Qt.callLater(function() { filterInput.forceActiveFocus() })
  }

  // ── layout helpers (the menu's fold: end mid-row when rows overflow) ────

  function rowHeightFor(r) {
    return r.detail || root.confirmKey === r.key ? root.detailRowHeight : root.baseRowHeight
  }

  function rowListHeight(_serial) {
    if (root.rows.length === 0) return root.baseRowHeight * 2
    var top = panel.cardTop
    var available = Math.min(panel.height - top - Style.gapsOut - root.contentMargin * 2 - root.headerHeight - root.contentSpacing,
                             Math.round(panel.height * 0.7),
                             root.settings.look.maxRows * (root.detailRowHeight + root.rowSpacing))
    var totals = []
    var total = 0
    for (var i = 0; i < root.rows.length; i++) {
      if (i > 0) total += root.rowSpacing
      total += root.rowHeightFor(root.rows[i])
      totals.push(total)
    }
    if (total <= available) return total
    var full = 0
    while (full < totals.length && totals[full] <= available) full++
    while (full > 1 && totals[full - 1] + root.rowSpacing + root.rowPeek > available) full--
    return full < 1 ? Math.max(available, root.baseRowHeight) : totals[full - 1] + root.rowSpacing + root.rowPeek
  }

  function revealCursor() {
    if (root.selectedIndex >= 0) resultList.positionViewAtIndex(root.selectedIndex, ListView.Contain)
  }

  // ── wiring ──────────────────────────────────────────────────────────────

  ListModel { id: displayModel }

  Engine {
    id: engine
    wantKey: root.settings.jev.enabled
    onMessage: function(line) { root.onEngineMessage(JSON.parse(line)) }
  }

  MenuSource {
    id: menuSource
    appLibrary: root.appLibrary
    onChanged: if (engine.ready) root.sendCatalog()
  }

  SettingsStore {
    id: settingsStore
    pluginId: root.pluginId
    shell: root.shell
    onChanged: if (engine.ready) {
      root.sendConfig()
      root.sendCatalog()
    }
  }

  FileView {
    path: root.stateDir + "/recent.json"
    watchChanges: true
    printErrors: false
    onLoaded: {
      try { root.recent = JSON.parse(text()) } catch (e) { root.recent = [] }
      if (!Array.isArray(root.recent)) root.recent = []
    }
    onLoadFailed: root.recent = []
    onFileChanged: reload()
  }

  // Ctrl+V: clipboard text, newlines flattened, capped (pastes are rarely
  // searches; long ones still work for web search and Ask agent). wl-paste
  // gets 2 s and 4 KiB, so a huge or stalled clipboard can't grow or wedge
  // the shell; 1000 characters always fit in 4 KiB of UTF-8.
  Process {
    id: pasteProc
    command: Proc.bounded(["/usr/bin/wl-paste", "--no-newline", "--type", "text"], 2, 4096)
    stdout: StdioCollector { id: pasteOut; waitForEnd: true }
    onExited: function(exitCode) {
      if (exitCode !== 0 || !root.opened) return
      var text = String(pasteOut.text || "").replace(/\s*[\r\n]+\s*/g, " ").slice(0, 1000)
      if (text) root.setText(root.filterText + text)
    }
  }

  Process {
    id: copyProc
    property var pending: []
    property string current: ""
    property bool pasteAfter: false
    function next() {
      if (copyProc.pending.length === 0) return
      var job = copyProc.pending.shift()
      copyProc.current = job.text
      copyProc.pasteAfter = job.paste
      copyProc.stdinEnabled = true
      copyProc.running = true
    }
    command: ["/usr/bin/wl-copy"]
    onStarted: {
      copyProc.write(copyProc.current)
      copyProc.current = ""
      copyProc.stdinEnabled = false  // closes stdin; wl-copy then serves the clipboard
    }
    onExited: function(exitCode) {
      if (copyProc.pasteAfter && exitCode === 0 && !pasteKeyProc.running) pasteDelay.restart()
      copyProc.pasteAfter = false
      copyProc.next()
    }
  }

  // omarchy-clipboard-paste-text's paste: a moment for Beam's layer to unmap
  // and focus to return to the app, then Shift+Insert. Only keys are typed;
  // the value itself stays on the clipboard.
  Timer {
    id: pasteDelay
    interval: 150
    onTriggered: if (!pasteKeyProc.running) pasteKeyProc.running = true
  }

  Process {
    id: pasteKeyProc
    command: Proc.bounded(["/usr/bin/wtype", "-M", "shift", "-k", "Insert", "-m", "shift"], 3, 1024)
  }

  Timer {
    id: answerTimer
    interval: 40
    onTriggered: if (root.pendingLocal) root.commit([], root.pendingLocal)
  }

  // The longest Enter waits on a missing answer before running the selected row.
  Timer {
    id: enterWait
    interval: 1500
    onTriggered: root.flushEnter()
  }

  Timer {
    id: jevTimer
    property int forSerial: -1
    onTriggered: if (root.opened && jevTimer.forSerial === root.serial)
      engine.send({ op: "jev", id: root.serial, q: root.filterText.trim() })
  }

  Timer {
    id: closeTimer
    interval: 350
    onTriggered: root.dismiss()
  }

  PointerMoveGate {
    id: pointerGate
    referenceItem: card
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omarchy-beam"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    // The top edge stays put from the moment Beam opens, so the card only
    // grows downward as rows arrive; it never re-centres or jumps.
    readonly property int cardTop: Math.max(Style.gapsOut, Math.round(height * 0.22))

    Rectangle {
      anchors.fill: parent
      color: root.scrim
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.dismiss()
    }

    BorderSurface {
      id: card
      width: root.cardWidth
      height: Math.min(root.cardHeight, panel.height - Style.gapsOut - panel.cardTop)
      radius: root.cornerRadius
      anchors.horizontalCenter: parent.horizontalCenter
      y: panel.cardTop
      color: root.background
      borderSpec: root.borderSpec
      padding: root.contentMargin

      MouseArea { anchors.fill: parent; onClicked: {} }

      // Focus is on filterInput, which forwards every key here first and types
      // whatever this leaves unaccepted, input-method text included.
      Item {
        id: keyCatcher
        anchors.fill: parent

        Keys.priority: Keys.BeforeItem
        Keys.onPressed: function(event) {
          var ctrl = (event.modifiers & Qt.ControlModifier) !== 0
          var shift = (event.modifiers & Qt.ShiftModifier) !== 0
          if (event.key === Qt.Key_Escape) {
            if (root.confirmKey) root.confirmKey = ""
            else if (root.filterText || root.chip) {
              root.chip = null
              root.setText("")
            } else root.dismiss()
          } else if (ctrl && event.key === Qt.Key_Comma) {
            root.openSettings()
          } else if (ctrl && event.key === Qt.Key_C) {
            root.copySelected()
          } else if ((ctrl && event.key === Qt.Key_V) || (shift && event.key === Qt.Key_Insert)) {
            root.paste()  // flattened and capped, rather than the text field's own paste
          } else if (event.key === Qt.Key_Tab) {
            root.tab()
          } else if (event.key === Qt.Key_Backtab) {
            // nothing to go back to; never let it move focus off the search line
          } else if (event.key === Qt.Key_Backspace && !root.filterText && root.chip) {
            root.chip = null
            root.setText("")
          } else if (Util.editsFilter(event, root.filterText)) {
            root.setText(Util.editedFilter(event, root.filterText))
          } else if (event.key === Qt.Key_Up) {
            root.move(-1)
          } else if (event.key === Qt.Key_Down) {
            root.move(1)
          } else if (event.key === Qt.Key_PageUp) {
            root.move(-6)
          } else if (event.key === Qt.Key_PageDown) {
            root.move(6)
          } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.enter(shift)
          } else {
            return
          }
          event.accepted = true
        }
      }

      Column {
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset
        spacing: root.contentSpacing

        Item {
          width: parent.width
          height: root.headerHeight

          Row {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.spacing.md

            Chip {
              visible: !!root.chip && !root.settingsOpen
              text: root.chip ? root.chip.name : ""
              fontFamily: root.fontFamily
              anchors.verticalCenter: parent.verticalCenter
            }

            Item {
              width: parent.width - (root.chip ? Style.space(140) : 0)
              height: root.headerHeight
              anchors.verticalCenter: parent.verticalCenter

              // A TextInput, not a Text fed by key events, so fcitx5 and other
              // input methods (and dead keys) can type here.
              FilterInput {
                id: filterInput
                anchors.fill: parent
                visible: !root.settingsOpen
                keyHandler: keyCatcher
                verticalAlignment: TextInput.AlignVCenter
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.heading
                // Input-method commits can carry newlines; the box is one line.
                onTextChanged: {
                  var clean = text.replace(/\s*[\r\n]+\s*/g, " ")
                  if (clean !== root.filterText) root.setText(clean)
                  else if (clean !== text) text = clean
                }
              }

              Text {
                textFormat: Text.PlainText
                anchors.fill: parent
                verticalAlignment: Text.AlignVCenter
                visible: root.settingsOpen || (!root.filterText && !filterInput.preeditText)
                text: root.settingsOpen ? "Beam settings" : (root.chip ? "Search " + root.chip.name + "…" : "Beam…")
                color: root.foreground
                opacity: root.settingsOpen ? 1 : 0.58
                font.family: root.fontFamily
                font.pixelSize: Style.font.heading
                elide: Text.ElideRight
              }

              // The pointer never edits the line: no selecting, no middle-click
              // paste around Ctrl+V's cap.
              MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
              }
            }
          }
        }

        Item {
          width: parent.width
          height: root.visibleRowsHeight
          visible: root.showList

          ListView {
            id: resultList
            anchors.fill: parent
            visible: !root.settingsOpen
            model: displayModel
            clip: true
            spacing: root.rowSpacing
            boundsBehavior: Flickable.StopAtBounds

            add: Transition {
              enabled: root.animateInsert
              NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Style.duration(140); easing.type: Easing.OutCubic }
            }
            addDisplaced: Transition {
              enabled: root.animateInsert
              NumberAnimation { property: "y"; duration: Style.duration(140); easing.type: Easing.OutCubic }
            }

            delegate: ResultRow {
              id: resultRow
              width: ListView.view.width
              hasCursor: resultRow.key === root.selectedKey
              confirming: resultRow.key === root.confirmKey
              copied: resultRow.key === root.copiedKey
              appLibrary: root.appLibrary
              foreground: root.foreground
              selectedText: root.selectedText
              selectedBackground: root.selectedBackground
              selectedBorderSpec: root.selectedBorderSpec
              fontFamily: root.fontFamily
              baseHeight: root.baseRowHeight
              detailHeight: root.detailRowHeight

              MouseArea {
                id: rowMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onPositionChanged: function(mouse) {
                  if (resultRow.kind !== "empty" && pointerGate.moved(resultRow, mouse)) root.selectedKey = resultRow.key
                }
                onClicked: {
                  root.selectedKey = resultRow.key
                  root.activateSelected()
                }
              }
            }
          }

          Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: Math.min(Style.space(28), parent.height / 2)
            visible: !root.settingsOpen && opacity > 0
            opacity: resultList.contentHeight > resultList.height
              ? Math.max(0, Math.min(1, (resultList.contentY - resultList.originY) / height)) : 0
            gradient: Gradient {
              GradientStop { position: 0; color: root.background }
              GradientStop { position: 1; color: Util.alpha(root.background, 0) }
            }
          }

          Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: Math.min(Style.space(28), parent.height / 2)
            visible: !root.settingsOpen && opacity > 0
            opacity: resultList.contentHeight > resultList.height
              ? Math.max(0, Math.min(1, (resultList.originY + resultList.contentHeight - resultList.height - resultList.contentY) / height)) : 0
            gradient: Gradient {
              GradientStop { position: 0; color: Util.alpha(root.background, 0) }
              GradientStop { position: 1; color: root.background }
            }
          }

          Column {
            anchors.centerIn: parent
            spacing: Style.space(8)
            visible: !root.settingsOpen && displayModel.count === 0 && root.filterText.length > 0

            Text {
              text: "󰈉"
              textFormat: Text.PlainText
              color: root.selectedText
              opacity: 0.8
              font.family: root.fontFamily
              font.pixelSize: Style.font.displayLarge
              horizontalAlignment: Text.AlignHCenter
              width: Style.space(320)
            }

            Text {
              textFormat: Text.PlainText
              text: "No matches for “" + root.filterText + "”"
              color: root.foreground
              opacity: 0.7
              font.family: root.fontFamily
              font.pixelSize: Style.font.title
              horizontalAlignment: Text.AlignHCenter
              width: Style.space(320)
            }
          }

          SettingsView {
            id: settingsView
            anchors.fill: parent
            visible: root.settingsOpen
            store: settingsStore
            jevStatus: root.jevStatus
            foreground: root.foreground
            selectedBackground: root.selectedBackground
            selectedText: root.selectedText
            selectedBorderSpec: root.selectedBorderSpec
            fontFamily: root.fontFamily
            rowHeight: root.baseRowHeight
            detailRowHeight: root.detailRowHeight
            onCloseRequested: root.closeSettings()
          }
        }
      }
    }
  }
}
