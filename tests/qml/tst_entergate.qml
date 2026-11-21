import QtQuick
import QtTest
import "../../services"

// A held Enter runs only on rows the user would have seen: never because a
// wait for a slow answer ran out.
TestCase {
  id: test
  name: "EnterGate"

  property var runs: []

  EnterGate {
    id: gate
    wait: 60
    onActivate: function(paste) { test.runs = test.runs.concat([paste]) }
  }

  function init() {
    gate.cancel()
    test.runs = []
  }

  function test_enter_with_nothing_pending_runs_at_once() {
    gate.press(true, false, false)
    compare(test.runs, [true])
    verify(!gate.queued)
  }

  function test_a_wait_that_runs_out_drops_the_enter() {
    gate.press(false, false, true)
    verify(gate.queued)
    wait(150)
    compare(test.runs, [], "the selected fallback must not run unconfirmed")
    verify(!gate.queued)
    verify(gate.missed)
  }

  function test_after_the_first_redraw_a_slow_answer_still_drops_the_enter() {
    gate.press(false, true, true)
    wait(150)
    compare(test.runs, [], "the redraw is pending, so nothing times out yet")
    gate.redrawn(true)
    wait(150)
    compare(test.runs, [])
    verify(gate.missed)
  }

  function test_the_answer_arriving_in_time_runs_the_held_enter() {
    gate.press(true, false, true)
    gate.answered()
    compare(test.runs, [true])
    wait(150)
    compare(test.runs, [true], "runs once")
  }

  function test_the_first_redraw_runs_a_held_enter_when_no_answer_is_due() {
    gate.press(false, true, false)
    compare(test.runs, [])
    gate.redrawn(false)
    compare(test.runs, [false])
  }

  function test_the_next_enter_after_a_drop_runs_the_row_the_user_sees() {
    gate.press(false, false, true)
    wait(150)
    gate.press(false, false, true)
    compare(test.runs, [false])
  }

  function test_new_text_cancels_a_held_enter() {
    gate.press(false, false, true)
    gate.cancel()
    gate.answered()
    wait(150)
    compare(test.runs, [])
    verify(!gate.missed)
  }

  function test_a_late_answer_after_a_drop_does_not_run_anything() {
    gate.press(false, false, true)
    wait(150)
    gate.answered()
    compare(test.runs, [])
    verify(!gate.missed)
  }
}
