import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tag_real


class MissingFileHandlingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.data_dir = self.base / "data"
        self.batches_dir = self.data_dir / "batches"
        self.config_dir = self.base / "config"
        self.library_dir = self.base / "library"
        self.data_dir.mkdir()
        self.batches_dir.mkdir()
        self.config_dir.mkdir()
        (self.library_dir / "images").mkdir(parents=True)

        self.paths_patch = mock.patch.multiple(
            tag_real,
            DATA_DIR=self.data_dir,
            BATCHES_DIR=self.batches_dir,
            PROGRESS_FILE=self.data_dir / "progress.json",
            PENDING_FILE=self.data_dir / "pending.json",
            SUGGESTED_FILE=self.data_dir / "suggested_tags.json",
            EXCEPTIONS_FILE=self.data_dir / "exceptions.json",
            TAGS_FILE=self.config_dir / "tags.json",
            LIB_PATH=self.library_dir,
        )
        self.paths_patch.start()

        self.write_json(tag_real.PROGRESS_FILE, tag_real.default_prog())
        self.write_json(tag_real.SUGGESTED_FILE, {"version": "1.1", "suggested": {}})
        self.write_json(tag_real.EXCEPTIONS_FILE, [])
        self.write_json(
            tag_real.TAGS_FILE,
            {
                "version": "test",
                "tags": {
                    "?": [{"name": "?-???"}],
                    "?": [{"name": "?-???"}],
                },
            },
        )

    def tearDown(self):
        self.paths_patch.stop()
        self.tmp.cleanup()

    def write_json(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_json(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def missing_item(self):
        return {
            "id": "missing-1",
            "name": "Crystal",
            "ext": "jpg",
            "btime": 0,
            "modificationTime": 1778257460000,
            "tags": [],
        }

    def test_prepare_marks_missing_source_file_as_processed_exception(self):
        with mock.patch.object(tag_real, "iter_items", return_value=iter([self.missing_item()])), \
             mock.patch.object(tag_real, "eagle_get", return_value={"data": {"tags": []}}) as eagle_get:
            tag_real.cmd_prepare(limit=20)

        eagle_get.assert_not_called()

        pending = self.read_json(tag_real.PENDING_FILE)
        self.assertEqual([], pending)

        prog = self.read_json(tag_real.PROGRESS_FILE)
        self.assertIn("missing-1", prog["processed_ids"])
        self.assertEqual(1, prog["total_processed"])
        self.assertEqual("file_missing", prog["records"][-1]["exception_reason"])

        exceptions = self.read_json(tag_real.EXCEPTIONS_FILE)
        self.assertEqual(1, len(exceptions))
        self.assertEqual("file_missing", exceptions[0]["reason"])
        self.assertIn("Crystal.jpg", exceptions[0]["extra"]["path"])

    def test_apply_batch_skips_missing_source_file_without_starting_pool(self):
        missing_path = self.base / "does-not-exist" / "Crystal.jpg"
        self.write_json(
            tag_real.PENDING_FILE,
            [
                {
                    "index": 1,
                    "item_id": "missing-1",
                    "name": "Crystal",
                    "ext": "jpg",
                    "file_path": str(missing_path),
                    "existing_tags": [],
                    "modificationTime": 1778257460000,
                }
            ],
        )

        class PoolShouldNotStart:
            def __init__(self, *args, **kwargs):
                raise AssertionError("Pool should not start for missing source files")

        with mock.patch.object(tag_real.multiprocessing, "Pool", PoolShouldNotStart):
            tag_real.cmd_apply_batch(batch_id="1", batch_size=20, workers=1)

        prog = self.read_json(tag_real.PROGRESS_FILE)
        self.assertIn("missing-1", prog["processed_ids"])
        self.assertEqual(1, prog["total_processed"])

        batch = self.read_json(self.batches_dir / "batch_results_001.json")
        self.assertEqual("skipped_missing_file", batch[0]["status"])
        self.assertEqual("file_missing", batch[0]["failure_reason"])

        exceptions = self.read_json(tag_real.EXCEPTIONS_FILE)
        self.assertEqual(1, len(exceptions))
        self.assertEqual("file_missing", exceptions[0]["reason"])


if __name__ == "__main__":
    unittest.main()
