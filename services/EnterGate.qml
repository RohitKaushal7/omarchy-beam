import QtQuick

// Holds an Enter pressed before Beam has drawn the rows for the text, so it
// acts on what the user would have seen. It waits for the first redraw (at
// most the 40 ms answer timer) and, for text that reads like a sum, for the
// helper's answer. If that answer does not come within `wait` ms, the Enter
// is dropped rather than run on whatever row happens to be selected (often
// web search): Beam stays open and the next Enter is a fresh decision.
QtObject {
  id: gate

  property int wait: 1500
  // An Enter is held.
  readonly property bool queued: gate._queued
  // An Enter was held for an answer that did not come in time.
  readonly property bool missed: gate._missed

  property bool _queued: false
  property bool _missed: false
  property bool _paste: false

  // Run the selected row, with paste (Shift+Enter) or not.
  signal activate(bool paste)

  // redrawPending: the rows for this text are not drawn yet.
  // answerPending: an answer for this text was asked for and has not come.
  // After a dropped Enter the user has seen the selected row, so the next
  // Enter runs it without waiting again.
  function press(paste, redrawPending, answerPending) {
    var seen = gate._missed
    gate._missed = false
    if (!redrawPending && (!answerPending || seen)) {
      gate.activate(!!paste)
      return
    }
    gate._queued = true
    gate._paste = !!paste
    if (redrawPending) timer.stop()
    else if (!timer.running) timer.start()
  }

  // The rows were drawn. A held Enter runs now, unless it is waiting on an answer.
  function redrawn(answerPending) {
    if (!gate._queued) return
    if (answerPending) {
      if (!timer.running) timer.start()
    } else {
      gate.flush()
    }
  }

  // The answer the Enter was held for arrived.
  function answered() {
    gate._missed = false
    gate.flush()
  }

  // The user moved the selection: a late answer no longer takes it.
  function moved() {
    gate._missed = false
  }

  // The text changed, or Beam closed: a held Enter must not act on new rows.
  function cancel() {
    timer.stop()
    gate._queued = false
    gate._missed = false
    gate._paste = false
  }

  function flush() {
    timer.stop()
    if (!gate._queued) return
    gate._queued = false
    var paste = gate._paste
    gate._paste = false
    gate.activate(paste)
  }

  property Timer _timer: Timer {
    id: timer
    interval: gate.wait
    onTriggered: {
      gate._queued = false
      gate._paste = false
      gate._missed = true
    }
  }
}
