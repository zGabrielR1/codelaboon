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
            package_metadata = root / 'codelaboon.egg-info'
            package_metadata.mkdir()
            root_environments = [
                root / 'build', root / 'tools.egg-info', root / '.pytest_cache', root / 'examples',
            ]
            for root_environment in root_environments:
                root_environment.mkdir()
                (root_environment / 'pyvenv.cfg').touch()
                (root_environment / 'cached.pyc').touch()

            command = [sys.executable, str(cleanup)]
            result = subprocess.run(
                [*command, '--dry-run'], check=True, capture_output=True, text=True,
            )
            self.assertCountEqual(
                map(Path, result.stdout.splitlines()),
                [Path('dist'), Path('codelaboon.egg-info'), Path('providers') / '__pycache__'],
            )
            self.assertTrue(source_cache.is_dir())
            self.assertTrue(build_output.is_dir())
            self.assertTrue(package_metadata.is_dir())

            subprocess.run(command, check=True, capture_output=True)
            self.assertFalse(source_cache.exists())
            self.assertFalse(build_output.exists())
            self.assertFalse(package_metadata.exists())
            self.assertTrue(cached_dependency.is_file())
            for root_environment in root_environments:
                self.assertTrue((root_environment / 'pyvenv.cfg').is_file())
                self.assertTrue((root_environment / 'cached.pyc').is_file())
