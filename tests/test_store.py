import io
import json
import os
import stat
import tempfile
import unittest

from helpers import read
from beam import store


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class WriteJson(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_owner_only_file_and_new_directory(self):
        path = os.path.join(self.dir, "beam", "x.json")
        store.write_json(path, {"a": 1})
        self.assertEqual(mode(path), 0o600)
        self.assertEqual(mode(os.path.dirname(path)), 0o700)
        self.assertEqual(json.loads(read(path)), {"a": 1})

    def test_existing_file_becomes_owner_only(self):
        path = os.path.join(self.dir, "x.json")
        with open(path, "w") as f:
            f.write("{}")
        os.chmod(path, 0o644)
        store.write_json(path, {"a": 2})
        self.assertEqual(mode(path), 0o600)

    def test_planted_tmp_symlink_is_not_followed(self):
        victim = os.path.join(self.dir, "victim")
        with open(victim, "w") as f:
            f.write("keep")
        path = os.path.join(self.dir, "x.json")
        os.symlink(victim, path + ".tmp")
        store.write_json(path, {"a": 3})
        self.assertEqual(read(victim), "keep")
        self.assertEqual(json.loads(read(path)), {"a": 3})

    def test_no_temp_files_left(self):
        path = os.path.join(self.dir, "x.json")
        store.write_json(path, [1, 2])
        self.assertEqual(os.listdir(self.dir), ["x.json"])


class ReadBounded(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_reads_small_json(self):
        path = os.path.join(self.dir, "x.json")
        store.write_json(path, {"a": 1})
        self.assertEqual(store.read_json(path), {"a": 1})

    def test_rejects_oversized_file(self):
        path = os.path.join(self.dir, "big.json")
        with open(path, "w") as f:
            f.write("[" + "1," * 1000 + "1]")
        with self.assertRaises(ValueError):
            store.read_json(path, limit=100)

    def test_rejects_devices_quickly(self):
        with self.assertRaises(ValueError):
            store.read_text("/dev/zero", limit=4096)

    def test_rejects_non_finite_numbers(self):
        path = os.path.join(self.dir, "nan.json")
        with open(path, "w") as f:
            f.write('{"a": NaN, "b": Infinity}')
        with self.assertRaises(ValueError):
            store.read_json(path)


class AppendLine(unittest.TestCase):
    def test_existing_log_becomes_owner_only(self):
        path = os.path.join(tempfile.mkdtemp(), "log.jsonl")
        with open(path, "w") as f:
            f.write("{}\n")
        os.chmod(path, 0o644)
        store.append_line(path, "{}", max_bytes=2000)
        self.assertEqual(mode(path), 0o600)

    def test_owner_only_and_trimmed_to_newest_lines(self):
        path = os.path.join(tempfile.mkdtemp(), "state", "log.jsonl")
        for i in range(400):
            store.append_line(path, json.dumps({"i": i}), max_bytes=2000)
        self.assertEqual(mode(path), 0o600)
        self.assertLessEqual(os.path.getsize(path), 2000)
        rows = [json.loads(line) for line in read(path).splitlines()]
        self.assertEqual(rows[-1], {"i": 399})
        self.assertEqual([r["i"] for r in rows], list(range(rows[0]["i"], 400)))


class BoundedLines(unittest.TestCase):
    def test_overlong_line_is_skipped_and_stream_resyncs(self):
        stream = io.StringIO("a" * 5000 + "\n" + '{"op":"ping"}\n' + "tail")
        self.assertEqual(list(store.bounded_lines(stream, limit=100)),
                         [None, '{"op":"ping"}\n', "tail"])


if __name__ == "__main__":
    unittest.main()
