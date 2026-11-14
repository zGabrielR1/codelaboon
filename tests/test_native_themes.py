"""Packaged native themes must preserve user themes and their upstream notice."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from codelaboon import native_themes


class NativeThemeTests(unittest.TestCase):
    def test_installs_both_native_formats_without_replacing_user_themes(self):
        with tempfile.TemporaryDirectory() as directory:
            for engine in ("opencode", "omp"):
                root = Path(directory) / engine
                (root / "themes").mkdir(parents=True)
                custom = root / "themes/mine.json"
                custom.write_text('{"user":"preserved"}', encoding="utf-8")
                native_themes.install(engine, root)
                native_themes.install(engine, root)
                self.assertEqual(custom.read_text(), '{"user":"preserved"}')
                theme = json.loads((root / "themes/codelaboon-kilo.json").read_text())
                self.assertIn("theme" if engine == "opencode" else "colors", theme)
                self.assertEqual(list((root / "themes").glob(".theme-*")), [])

    def test_kilo_theme_retains_source_hash_and_mit_notice(self):
        assets = native_themes.ASSETS
        provenance = json.loads((assets / "PROVENANCE.json").read_text())
        content = (assets / "opencode/codelaboon-kilo.json").read_bytes()
        self.assertEqual(hashlib.sha256(content).hexdigest(), provenance["source_sha256"])
        notice = (assets / provenance["license"]).read_text()
        self.assertIn("Copyright (c) 2026 Kilo Code", notice)
        self.assertIn("Permission is hereby granted", notice)


if __name__ == "__main__":
    unittest.main()
