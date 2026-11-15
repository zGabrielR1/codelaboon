import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock,patch
import zipfile
import xml.etree.ElementTree as ET
from codelaboon import ide


class EditorIntegrationTests(unittest.TestCase):
    def test_public_vsix_has_no_local_bootstrap_or_bundled_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            path=ide.build_vsix(Path(directory)/'connector.vsix')
            with zipfile.ZipFile(path) as archive:
                self.assertNotIn('extension/backend.json',archive.namelist())
                self.assertFalse(any('node_modules' in name for name in archive.namelist()))
                package=json.loads(archive.read('extension/package.json'))
                self.assertIn('anthropic.claude-code',package['extensionDependencies'])
                ET.fromstring(archive.read('extension.vsixmanifest'))
            self.assertLess(path.stat().st_size,30000)

    def test_local_vsix_only_carries_wrapper_paths_not_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path=ide.build_vsix(Path(directory)/'connector.vsix',{'wrapper':'/local/wrapper','configDir':'/local/config'})
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(json.loads(archive.read('extension/backend.json'))['wrapper'],'/local/wrapper')

    def test_wrapper_preserves_sdk_flags_and_maps_only_claude_aliases(self):
        cli=MagicMock(providers={'kilo':object()})
        gateway=MagicMock(token='private-local-token')
        gateway.models.return_value=[{'id':'free','name':'free','api':'chat'}]
        context=MagicMock()
        context.__enter__.return_value=(gateway,'http://127.0.0.1:1234/v1')
        import signal
        old=signal.getsignal(signal.SIGTERM)
        try:
            with patch('codelaboon.cli.CodelaboonCLI',return_value=cli),patch('codelaboon.native_gateway.serve',return_value=context),patch('codelaboon.claude_engine.launch',return_value=0) as launch:
                with self.assertRaises(SystemExit) as result:
                    ide.claude_wrapper([sys.executable,'--model','sonnet','--input-format','stream-json','--permission-prompt-tool','stdio'])
                self.assertEqual(result.exception.code,0)
                args=launch.call_args.args[1]
                self.assertEqual(args,['--model','free','--input-format','stream-json','--permission-prompt-tool','stdio'])
        finally:signal.signal(signal.SIGTERM,old)

    def test_wrapper_script_uses_existing_python_without_downloading_runtime(self):
        with tempfile.TemporaryDirectory() as directory,patch('codelaboon.ide.config_dir',return_value=Path(directory)):
            path=ide.wrapper_path()
            text=path.read_text()
            self.assertIn(sys.executable,text)
            self.assertNotIn('pip install',text)


if __name__=='__main__':unittest.main()
