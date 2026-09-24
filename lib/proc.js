// Bounded helper processes. Everything Beam reads from another program runs
// through this wrapper: `timeout` ends the command and its whole process
// group at the deadline, and `head -c` caps the output at the producer, so
// the long-lived shell never buffers more than `bytes` or waits forever.
// The wrapper script is constant; the command travels as separate
// arguments, never as shell text.

var SCRIPT = '/usr/bin/timeout -k 1 "$1" "${@:3}" </dev/null 2>/dev/null | /usr/bin/head -c "$2"'

// strict: an overflowing or timed-out command fails (non-zero exit) instead
// of yielding its first `bytes` of output.
function bounded(argv, seconds, bytes, strict) {
  var script = (strict ? "set -o pipefail; " : "") + SCRIPT
  return ["/bin/bash", "-c", script, "beam-bounded", String(seconds), String(bytes)].concat(argv)
}

if (typeof module !== "undefined") {
  module.exports = { bounded: bounded }
}
