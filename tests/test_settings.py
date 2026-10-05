"""Unit tests for the Settings configuration wrapper."""
import json
import tempfile
import unittest
from pathlib import Path

from settings import Settings


class SettingsTests(unittest.TestCase):
    """Verify loading and lookup of YAML and JSON settings files."""

    def setUp(self):
        """Create a temporary directory to hold settings files."""
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def _write(self, name: str, text: str) -> Path:
        """Write a settings file into the temporary directory."""
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_yaml_file_is_loaded(self):
        """Values from a YAML file are available by key."""
        path = self._write("a.yaml", "pollSeconds: 30\nrss:\n  title: News\n")

        settings = Settings(path)

        self.assertEqual(settings["pollSeconds"], 30)
        self.assertEqual(settings["rss"], {"title": "News"})

    def test_json_file_is_loaded(self):
        """Values from a JSON file are available by key."""
        path = self._write("a.json", json.dumps({"pollSeconds": 5}))

        self.assertEqual(Settings(path)["pollSeconds"], 5)

    def test_string_filename_is_accepted(self):
        """A plain string path works the same as a Path."""
        path = self._write("a.yml", "key: value\n")

        self.assertEqual(Settings(str(path))["key"], "value")

    def test_get_returns_default_for_missing_key(self):
        """get() falls back to the default when the key is absent."""
        settings = Settings(self._write("a.yaml", "key: value\n"))

        self.assertEqual(settings.get("key"), "value")
        self.assertIsNone(settings.get("missing"))
        self.assertEqual(settings.get("missing", 7), 7)

    def test_missing_key_raises_key_error(self):
        """Item access to an absent key raises KeyError."""
        settings = Settings(self._write("a.yaml", "key: value\n"))

        with self.assertRaises(KeyError):
            settings["missing"]  # pylint: disable=pointless-statement

    def test_load_accepts_alternate_filename(self):
        """load() can read a different file than the constructor path."""
        first = self._write("a.yaml", "key: one\n")
        second = self._write("b.json", json.dumps({"key": "two"}))
        settings = Settings(first)

        settings.load(second)

        self.assertEqual(settings["key"], "two")

    def test_unsupported_extension_raises_value_error(self):
        """Files that are neither YAML nor JSON are rejected."""
        settings = Settings(self._write("a.txt", "key: value\n"))

        with self.assertRaises(ValueError):
            settings.load()


if __name__ == "__main__":
    unittest.main()
