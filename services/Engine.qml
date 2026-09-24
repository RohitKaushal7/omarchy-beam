import Quickshell
import Quickshell.Io
import QtQuick
import "../lib/proc.js" as Proc

// Owns the Python helper (bin/beam.py serve): lazy start, JSON lines in and
// out, one restart after a crash, then local-only for the rest of the session.
Item {
  id: engine
  visible: false

  readonly property string script: decodeURIComponent(String(Qt.resolvedUrl("../bin/beam.py")).replace(/^file:\/\//, ""))
  property bool ready: false
  property bool disabled: false
  property var queue: []
  property int crashes: 0
  property real firstCrashAt: 0
  property bool stopping: false
  // TYPESAFE_API_KEY as the user's login shell sees it. omarchy-shell is
  // started by the session, not a login shell, so a key exported from shell
  // rc files is missing from Quickshell.env; ask the login shell once, and
  // only while Jev is enabled.
  property bool wantKey: false
  property string loginKey: ""
  property bool keyProbed: Quickshell.env("TYPESAFE_API_KEY") ? true : false
  property bool startWhenProbed: false

  signal message(var msg)

  function start() {
    if (engine.disabled || proc.running) return
    if (engine.wantKey && !engine.keyProbed) {
      engine.startWhenProbed = true
      if (!keyProbe.running) keyProbe.running = true
      return
    }
    engine.ready = false
    proc.running = true
  }

  // Messages sent before the helper says "ready" wait in a short queue.
  function send(obj) {
    if (engine.disabled) return false
    var line = JSON.stringify(obj) + "\n"
    if (!proc.running || !engine.ready) {
      engine.queue = engine.queue.concat([line]).slice(-50)
      engine.start()
      return true
    }
    proc.write(line)
    return true
  }

  function stop() {
    if (!proc.running) return
    engine.stopping = true
    proc.signal(15)
  }

  function environment() {
    var env = { PATH: "/usr/bin:/bin" }
    var names = ["HOME", "LANG", "LC_ALL", "LC_MONETARY", "LC_NUMERIC", "TZ", "XDG_CACHE_HOME",
                 "XDG_STATE_HOME", "TYPESAFE_API_KEY"]
    for (var i = 0; i < names.length; i++) {
      var value = Quickshell.env(names[i])
      if (value) env[names[i]] = String(value)
    }
    if (!env.TYPESAFE_API_KEY && engine.loginKey) env.TYPESAFE_API_KEY = engine.loginKey
    return env
  }

  // The probe's command line is constant; the key only ever travels on its
  // stdout. The login shell gets no stdin, 3 s and 4 KiB of output, and only
  // the text between the \x1e markers counts, so anything a profile prints
  // (a motd, fastfetch) never becomes part of the key.

  function keyFromProbe(text) {
    var found = String(text || "").match(/\x1e([A-Za-z0-9._~+\/=:-]{8,512})\x1e/g)
    return found ? found[found.length - 1].slice(1, -1) : ""
  }

  Process {
    id: keyProbe
    command: Proc.bounded([Quickshell.env("SHELL") || "/bin/bash", "-lc", 'printf "\\036%s\\036" "${TYPESAFE_API_KEY-}"'], 3, 4096)
    stdout: StdioCollector { id: keyOut; waitForEnd: true }
    onExited: {
      engine.loginKey = engine.keyFromProbe(keyOut.text)
      engine.keyProbed = true
      if (engine.startWhenProbed) {
        engine.startWhenProbed = false
        engine.start()
      } else if (engine.loginKey && proc.running) {
        engine.stop()  // Jev was just enabled: the next query restarts the helper with the key
      }
    }
  }

  onWantKeyChanged: if (engine.wantKey && !engine.keyProbed && !keyProbe.running) keyProbe.running = true
  Component.onCompleted: if (engine.wantKey && !engine.keyProbed) keyProbe.running = true

  Process {
    id: proc
    command: ["/usr/bin/python3", "-I", engine.script, "serve"]
    clearEnvironment: true
    environment: engine.environment()
    stdinEnabled: true
    stdout: SplitParser {
      onRead: function(line) {
        if (line.length > 1048576) {
          proc.signal(9)
          return
        }
        var msg
        try { msg = JSON.parse(line) } catch (e) { return }
        if (msg.op === "ready") {
          engine.ready = true
          engine.message(msg)  // Beam sends config + catalog first…
          var pending = engine.queue
          engine.queue = []
          for (var i = 0; i < pending.length; i++) proc.write(pending[i])  // …then the queue
          return
        }
        engine.message(msg)
      }
    }
    onExited: function(exitCode, exitStatus) {
      engine.ready = false
      if (engine.stopping || (exitCode === 0 && exitStatus === 0)) {
        engine.stopping = false  // idle exit or shutdown; the next send restarts it
        return
      }
      var now = Date.now()
      if (now - engine.firstCrashAt > 60000) {
        engine.firstCrashAt = now
        engine.crashes = 0
      }
      engine.crashes += 1
      if (engine.crashes >= 2) {
        engine.disabled = true
        engine.queue = []
        return
      }
      if (engine.queue.length > 0) engine.start()
    }
  }

  Component.onDestruction: engine.stop()
}
