import Quickshell
import Quickshell.Io
import QtQuick

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

  signal message(var msg)

  function start() {
    if (engine.disabled || proc.running) return
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
                 "XDG_STATE_HOME", "TYPESAFE_API_KEY", "TYPESAFE_BASE_URL"]
    for (var i = 0; i < names.length; i++) {
      var value = Quickshell.env(names[i])
      if (value) env[names[i]] = String(value)
    }
    return env
  }

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
