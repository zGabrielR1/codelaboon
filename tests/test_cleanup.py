from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class CleanupTests(unittest.TestCase):
    def test_cleanup_preserves_a_virtual_environment_with_a_custom_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / 'scripts'
            scripts.mkdir()
            cleanup = scripts / 'cleanup.py'
            shutil.copyfile(Path(__file__).resolve().parents[1] / 'scripts' / cleanup.name, cleanup)

            environment = root / 'providers' / 'python-tools'
            environment_cache = environment / 'lib' / '__pycache__'
            environment_cache.mkdir(parents=True)
            (environment / 'pyvenv.cfg').touch()
            cached_dependency = environment_cache / 'dependency.pyc'
            cached_dependency.touch()

            source_cache = root / 'providers' / '__pycache__'
            source_cache.mkdir()
            build_output = root / 'dist'
            build_output.mkdir()

            command = [sys.executable, str(cleanup)]
            result = subprocess.run(
                [*command, '--dry-run'], check=True, capture_output=True, text=True,
            )
            self.assertCountEqual(
                map(Path, result.stdout.splitlines()),
                [Path('dist'), Path('providers') / '__pycache__'],
            )
            self.assertTrue(source_cache.is_dir())
            self.assertTrue(build_output.is_dir())

            subprocess.run(command, check=True, capture_output=True)
            self.assertFalse(source_cache.exists())
            self.assertFalse(build_output.exists())
            self.assertTrue(cached_dependency.is_file())
